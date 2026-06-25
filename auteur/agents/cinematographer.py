"""Cinematographer — renders shots with Wan (text-to-video / image-to-video).

Always returns a LOCAL clip path so everything downstream (frame sampling, critic, assembly)
operates uniformly:
  * mock mode  -> synthesize a deterministic placeholder clip with ffmpeg (no spend).
  * live mode  -> create a Wan async DashScope job, poll, download the result locally.

The Budget Governor caps how many clips may be rendered.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..budget import BudgetGovernor
from ..config import (
    DASHSCOPE_NATIVE_BASE,
    WAN_I2V_MODEL,
    WAN_T2V_MODEL,
    is_mock,
    require_api_key,
)
from .. import media

STAGE = "cinematographer"
_POLL_INTERVAL_S = 5
_POLL_TIMEOUT_S = 600


class Cinematographer:
    def __init__(self, governor: BudgetGovernor, resolution: str = "720P"):
        self.governor = governor
        self.resolution = resolution

    def render(self, prompt: str, out_path: str | Path, *, index: int = 0,
               image_url: str | None = None) -> str:
        """Render one clip to `out_path`; return its local path. Honours the clip budget."""
        if not self.governor.can_render_clip():
            raise RuntimeError("clip budget exhausted")

        if is_mock():
            path = media.make_placeholder_clip(out_path, index=index)
            self.governor.record_video(STAGE, "mock-wan", clips=1, note=prompt[:80])
            return path

        model = WAN_I2V_MODEL if image_url else WAN_T2V_MODEL
        task_id = self._create_task(model, prompt, image_url)
        url = self._poll(task_id)
        path = self._download(url, out_path)
        self.governor.record_video(STAGE, model, clips=1, note=prompt[:80])
        return path

    # --- DashScope async video API ---------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {require_api_key()}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

    def _create_task(self, model: str, prompt: str, image_url: str | None) -> str:
        import requests

        payload: dict = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {"resolution": self.resolution},
        }
        if image_url:
            payload["input"]["img_url"] = image_url
        r = requests.post(
            f"{DASHSCOPE_NATIVE_BASE}/services/aigc/video-generation/video-synthesis",
            json=payload, headers=self._headers(), timeout=30,
        )
        r.raise_for_status()
        return r.json()["output"]["task_id"]

    def _poll(self, task_id: str) -> str:
        import requests

        deadline = time.time() + _POLL_TIMEOUT_S
        while time.time() < deadline:
            r = requests.get(
                f"{DASHSCOPE_NATIVE_BASE}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {require_api_key()}"}, timeout=30,
            )
            r.raise_for_status()
            out = r.json()["output"]
            status = out.get("task_status")
            if status == "SUCCEEDED":
                return out["video_url"]
            if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                raise RuntimeError(f"Wan task {task_id} failed: {out}")
            time.sleep(_POLL_INTERVAL_S)
        raise TimeoutError(f"Wan task {task_id} did not finish in {_POLL_TIMEOUT_S}s")

    def _download(self, url: str, out_path: str | Path) -> str:
        import requests

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
        return str(out_path)
