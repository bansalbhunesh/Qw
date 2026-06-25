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


class Cinematographer:
    def __init__(self, governor: BudgetGovernor, resolution: str = "720P"):
        self.governor = governor
        self.resolution = resolution

    def render(
        self,
        prompt: str,
        out_path: str | Path,
        *,
        index: int = 0,
        image_url: str | None = None,
    ) -> str:
        if not self.governor.can_render_clip():
            raise RuntimeError("clip budget exhausted")

        if is_mock():
            path = media.make_placeholder_clip(out_path, index=index)
            self.governor.record_video(STAGE, "mock-wan", clips=1, note=prompt[:80])
            return path

        model = WAN_I2V_MODEL if image_url else WAN_T2V_MODEL
        _log.info("rendering shot %d with %s (%d chars prompt)", index, model, len(prompt))

        def _do_render():
            task_id = self._create_task(model, prompt, image_url)
            url = self._poll(task_id)
            return self._download(url, out_path)

        path = with_retry(_do_render, label=f"wan/shot_{index}", max_retries=2, base_delay=5.0)
        self.governor.record_video(STAGE, model, clips=1, note=prompt[:80])
        _log.info("shot %d rendered -> %s", index, path)
        return path

    # --- DashScope async video API ---------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {require_api_key()}"}

    def _create_task(self, model: str, prompt: str, image_url: str | None) -> str:
        payload: dict = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {"resolution": self.resolution},
        }
        if image_url:
            payload["input"]["img_url"] = image_url

        headers = {**self._auth_headers(), "Content-Type": "application/json",
                    "X-DashScope-Async": "enable"}

        r = requests.post(
            f"{DASHSCOPE_NATIVE_BASE}/services/aigc/video-generation/video-synthesis",
            json=payload, headers=headers, timeout=30,
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
