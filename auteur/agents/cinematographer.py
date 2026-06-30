"""Cinematographer — renders shots with Wan (text-to-video / image-to-video).

Always returns a LOCAL clip path. In live mode, creates a Wan async DashScope job, polls
until complete, downloads and verifies the result. Retries on transient failures. The Budget
Governor caps how many clips may be rendered.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from .. import log, media
from ..budget import BudgetGovernor
from ..config import (
    DASHSCOPE_NATIVE_BASE,
    WAN_I2V_MODEL,
    WAN_T2V_MODEL,
    is_mock,
    require_api_key,
)
from ..retry import with_retry

STAGE = "cinematographer"
_log = log.get("dp")

_POLL_INTERVAL_S = 8
_POLL_TIMEOUT_S = 600
_MIN_CLIP_BYTES = 4096


class RenderFailed(RuntimeError):
    """A Wan render task failed after retries."""


class QuotaExhausted(RuntimeError):
    """The account's free-tier Wan quota is exhausted; paid billing must be enabled."""


class Cinematographer:
    """Renders shots via Wan (text-to-video / image-to-video) with budget enforcement.

    Supports both t2v and i2v modes. When a reference image is provided (for visual
    continuity), attempts i2v first and falls back to t2v on failure. All renders are
    metered through the Budget Governor.
    """

    def __init__(self, governor: BudgetGovernor, resolution: str = "720P",
                 aspect_ratio: str = "9:16"):
        self.governor = governor
        self.resolution = resolution
        self.aspect_ratio = aspect_ratio

    def render(
        self,
        prompt: str,
        out_path: str | Path,
        *,
        index: int = 0,
        reference_image: str | None = None,
        image_url: str | None = None,
        duration: float = 5.0,
    ) -> str:
        """Render one shot to a local clip.

        If `reference_image` (a local image path) or `image_url` (a public URL) is given,
        renders image-to-video (visual continuity from the previous shot). If that i2v render
        fails for any reason, it falls back to plain text-to-video so a production never stalls.

        `duration` controls target clip length (3-8s). Used for shot pacing — hooks and
        climaxes get longer screen time than transitional beats.
        """
        if not self.governor.can_render_clip():
            raise RuntimeError("clip budget exhausted")

        self._duration = max(3.0, min(8.0, duration))

        if is_mock():
            path = media.make_placeholder_clip(out_path, index=index, seconds=self._duration)
            self.governor.record_video(STAGE, "mock-wan", clips=1, note=prompt[:80])
            return path

        seed = image_url
        if seed is None and reference_image and Path(reference_image).exists():
            seed = self._upload_image(reference_image)

        fallback_reason = ""
        if seed:
            try:
                path = self._render_with(WAN_I2V_MODEL, prompt, out_path, index, seed)
                self.governor.record_video(
                    STAGE, WAN_I2V_MODEL, clips=1, note=f"i2v continuity | {prompt[:60]}",
                )
                _log.info("shot %d rendered (i2v, continuity) -> %s", index, path)
                return path
            except Exception as exc:  # i2v unsupported / failed — degrade gracefully
                fallback_reason = f"{type(exc).__name__}: {exc}"[:90]
                _log.warning("shot %d i2v failed (%s) — falling back to t2v", index, fallback_reason)

        path = self._render_with(WAN_T2V_MODEL, prompt, out_path, index, None)
        # Record WHY we used t2v so the ledger reveals i2v failures without needing console logs.
        note = f"t2v (i2v fallback: {fallback_reason})" if fallback_reason else prompt[:80]
        self.governor.record_video(STAGE, WAN_T2V_MODEL, clips=1, note=note)
        _log.info("shot %d rendered (t2v) -> %s", index, path)
        return path

    def _render_with(
        self, model: str, prompt: str, out_path: str | Path, index: int, image_url: str | None,
    ) -> str:
        duration = getattr(self, "_duration", 5.0)
        _log.info("rendering shot %d with %s (%d chars, %.1fs)", index, model, len(prompt), duration)

        def _do_render():
            task_id = self._create_task(model, prompt, image_url, duration=duration)
            url = self._poll(task_id)
            return self._download(url, out_path)

        return with_retry(_do_render, label=f"wan/shot_{index}", max_retries=2, base_delay=5.0)

    # --- image upload for i2v continuity -----------------------------------------------

    def _upload_image(self, local_path: str) -> str | None:
        """Upload a local image to DashScope's temporary OSS bucket, returning an oss:// URL.

        This is required because the Wan i2v API only accepts HTTP or oss:// URLs for img_url,
        not base64 data URIs. Returns None on failure (caller falls back to t2v).
        """
        try:
            import oss2
        except ImportError:
            _log.warning("oss2 not installed — cannot upload anchor for i2v")
            return None

        try:
            headers = {**self._auth_headers(), "Content-Type": "application/json"}
            fname = Path(local_path).name
            r = requests.post(
                f"{DASHSCOPE_NATIVE_BASE}/uploads",
                json={"model": WAN_I2V_MODEL, "file_name": fname},
                headers=headers, timeout=30,
            )
            if r.status_code >= 400:
                _log.warning("upload cert API %d: %s", r.status_code, r.text[:200])
            r.raise_for_status()
            data = r.json().get("data", {})
            _log.info("upload cert keys: %s", list(data.keys()))

            auth = oss2.StsAuth(
                data["oss_access_key_id"],
                data["oss_access_key_secret"],
                data.get("security_token") or data["oss_security_token"],
            )
            endpoint = data.get("upload_host") or data["oss_endpoint"]
            bucket = oss2.Bucket(auth, endpoint, data["oss_bucket_name"])
            obj_key = data["x_oss_object_name"]
            bucket.put_object_from_file(obj_key, local_path)
            oss_url = f"oss://{data['oss_bucket_name']}/{obj_key}"
            _log.info("uploaded anchor -> %s", oss_url)
            return oss_url
        except Exception as exc:
            _log.warning("anchor upload failed (%s) — i2v will be skipped", exc)
            return None

    # --- DashScope async video API ---------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {require_api_key()}"}

    def _create_task(self, model: str, prompt: str, image_url: str | None,
                     duration: float = 5.0) -> str:
        from ..config import wan_size
        # Send an explicit vertical `size` (fixes resolution AND 9:16 aspect). wan2.2-t2v-plus
        # does NOT support `duration` customization, so we only include it when explicitly
        # enabled (AUTEUR_WAN_DURATION=1) for models/tiers that do.
        params: dict = {"size": wan_size(self.resolution, self.aspect_ratio)}
        import os
        if os.getenv("AUTEUR_WAN_DURATION", "").lower() in {"1", "true", "yes"}:
            params["duration"] = int(round(duration))
        payload: dict = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": params,
        }
        if image_url:
            payload["input"]["img_url"] = image_url

        headers = {**self._auth_headers(), "Content-Type": "application/json",
                    "X-DashScope-Async": "enable"}
        if image_url and image_url.startswith("oss://"):
            headers["X-DashScope-OssResourceResolve"] = "enable"

        r = requests.post(
            f"{DASHSCOPE_NATIVE_BASE}/services/aigc/video-generation/video-synthesis",
            json=payload, headers=headers, timeout=30,
        )
        if r.status_code >= 400:
            # The response body carries the real reason (quota, model access, region, etc.).
            # Surface it loudly — a bare 403 is undebuggable without it.
            _log.error("Wan create-task %d for model=%s: %s",
                       r.status_code, model, r.text[:500])
            # Free-tier quota exhaustion is an account-billing issue, not a transient error —
            # raise a distinct exception so the showrunner stops retrying and gives clear guidance.
            if r.status_code == 403 and "FreeTierOnly" in r.text:
                raise QuotaExhausted(
                    "Wan free-tier quota exhausted. Enable paid billing in the Alibaba Cloud "
                    "Model Studio console (and turn off 'use free tier only' mode) to continue."
                )
        r.raise_for_status()
        body = r.json()
        task_id = body.get("output", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"no task_id in Wan response: {body}")
        _log.info("wan task created: %s", task_id)
        return task_id

    def _poll(self, task_id: str) -> str:
        deadline = time.time() + _POLL_TIMEOUT_S
        while time.time() < deadline:
            r = requests.get(
                f"{DASHSCOPE_NATIVE_BASE}/tasks/{task_id}",
                headers=self._auth_headers(), timeout=30,
            )
            r.raise_for_status()
            out = r.json().get("output", {})
            status = out.get("task_status", "UNKNOWN")

            if status == "SUCCEEDED":
                video_url = out.get("video_url") or out.get("results", [{}])[0].get("url")
                if not video_url:
                    raise RuntimeError(f"SUCCEEDED but no video_url in: {out}")
                return video_url

            if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                msg = out.get("message", str(out))
                raise RenderFailed(f"Wan task {task_id} {status}: {msg}")

            _log.info("wan task %s: %s", task_id, status)
            time.sleep(_POLL_INTERVAL_S)

        raise TimeoutError(f"Wan task {task_id} did not finish in {_POLL_TIMEOUT_S}s")

    def _download(self, url: str, out_path: str | Path) -> str:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)

        size = out_path.stat().st_size
        if size < _MIN_CLIP_BYTES:
            out_path.unlink(missing_ok=True)
            raise RuntimeError(f"downloaded clip too small ({size}B), likely corrupt")

        _log.info("downloaded %s (%d KB)", out_path.name, size // 1024)
        return str(out_path)
