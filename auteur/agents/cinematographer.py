"""Cinematographer — renders shots with Wan (text-to-video / image-to-video).

Wan runs as an async DashScope job: POST creates a task, then we poll until the video URL is
ready. The Budget Governor caps the number of clips we're allowed to render. Image-to-video is
used to carry a key frame forward for continuity when a previous shot's last frame is a good
anchor.

NOTE: this is the integration surface that must be validated against live DashScope during the
build — the request/response shapes below follow the Wan2.7 async API and will be hardened once
keys are wired in.
"""

from __future__ import annotations

import time

import requests

from ..budget import BudgetGovernor
from ..config import (
    DASHSCOPE_NATIVE_BASE,
    WAN_I2V_MODEL,
    WAN_T2V_MODEL,
    require_api_key,
)

STAGE = "cinematographer"
_POLL_INTERVAL_S = 5
_POLL_TIMEOUT_S = 600


class Cinematographer:
    def __init__(self, governor: BudgetGovernor, resolution: str = "720P"):
        self.governor = governor
        self.resolution = resolution

    def render(self, prompt: str, *, image_url: str | None = None) -> str:
        """Render one clip; return a URL to the generated video. Honours the clip budget."""
        if not self.governor.can_render_clip():
            raise RuntimeError("clip budget exhausted")

        model = WAN_I2V_MODEL if image_url else WAN_T2V_MODEL
        task_id = self._create_task(model, prompt, image_url)
        url = self._poll(task_id)
        self.governor.record_video(STAGE, model, clips=1, note=prompt[:80])
        return url

    # --- DashScope async video API ---------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {require_api_key()}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

    def _create_task(self, model: str, prompt: str, image_url: str | None) -> str:
        payload: dict = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {"resolution": self.resolution},
        }
        if image_url:
            payload["input"]["img_url"] = image_url
        r = requests.post(
            f"{DASHSCOPE_NATIVE_BASE}/services/aigc/video-generation/video-synthesis",
            json=payload,
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["output"]["task_id"]

    def _poll(self, task_id: str) -> str:
        deadline = time.time() + _POLL_TIMEOUT_S
        while time.time() < deadline:
            r = requests.get(
                f"{DASHSCOPE_NATIVE_BASE}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {require_api_key()}"},
                timeout=30,
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
