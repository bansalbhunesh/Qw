"""Alibaba Cloud deployment — the proof-of-cloud file for the hackathon submission.

This file demonstrates Auteur's backend running on Alibaba Cloud:
  1. DashScope (Model Studio) for Qwen + Wan inference.
  2. OSS (Object Storage Service) for clip/frame/final-cut persistence.
  3. FastAPI service on ECS (or Function Compute) with health checks.

The demo recording shows this process serving traffic from an Alibaba Cloud host.

Required env on the ECS instance / in .env:
  DASHSCOPE_API_KEY        - Model Studio key
  OSS_ACCESS_KEY_ID        - RAM user access key
  OSS_ACCESS_KEY_SECRET    - RAM user secret
  OSS_BUCKET               - target bucket
  OSS_ENDPOINT             - e.g. oss-ap-southeast-1.aliyuncs.com
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from auteur import log as _logmod
from auteur.retry import with_retry

_log = _logmod.get("deploy")


# --- Alibaba Cloud OSS asset storage ---------------------------------------------------

class OSSClient:
    """Thin wrapper over the oss2 SDK with retry and structured logging."""

    def __init__(self):
        import oss2

        self.auth = oss2.Auth(os.environ["OSS_ACCESS_KEY_ID"], os.environ["OSS_ACCESS_KEY_SECRET"])
        self.endpoint = os.environ["OSS_ENDPOINT"]
        self.bucket_name = os.environ["OSS_BUCKET"]
        self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)

    def upload(self, data: bytes, key: str | None = None, content_type: str = "video/mp4") -> str:
        key = key or f"auteur/{uuid.uuid4().hex}"
        def _put():
            self.bucket.put_object(key, data, headers={"Content-Type": content_type})
        with_retry(_put, label=f"oss/put/{key}")
        host = self.endpoint.replace("https://", "").replace("http://", "")
        url = f"https://{self.bucket_name}.{host}/{key}"
        _log.info("uploaded %d KB -> %s", len(data) // 1024, url)
        return url

    def upload_file(self, path: str | Path, key: str | None = None) -> str:
        path = Path(path)
        content_type = "video/mp4" if path.suffix == ".mp4" else "application/octet-stream"
        return self.upload(path.read_bytes(), key=key, content_type=content_type)


def _oss_available() -> bool:
    return all(os.environ.get(k) for k in ("OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET",
                                            "OSS_BUCKET", "OSS_ENDPOINT"))


# --- DashScope health check -----------------------------------------------------------

def dashscope_smoke_test() -> dict:
    from openai import OpenAI
    from auteur.config import DASHSCOPE_OPENAI_BASE

    client = OpenAI(api_key=os.environ["DASHSCOPE_API_KEY"], base_url=DASHSCOPE_OPENAI_BASE)
    resp = client.chat.completions.create(
        model="qwen-flash",
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
    )
    return {
        "model": "qwen-flash",
        "reply": resp.choices[0].message.content or "",
        "tokens": getattr(resp.usage, "total_tokens", 0),
    }


# --- FastAPI service (runs on Alibaba Cloud ECS) ----------------------------------------

def build_app():
    from fastapi import FastAPI, BackgroundTasks
    from fastapi.responses import FileResponse
    from pydantic import BaseModel

    from auteur.agents.showrunner import Showrunner
    from auteur.config import ProductionConfig

    app = FastAPI(title="Auteur — running on Alibaba Cloud", version="0.1.0")

    class ProduceRequest(BaseModel):
        premise: str
        shots: int = 6
        max_tokens: int = 120_000
        max_spend_usd: float = 2.00
        quality_gate: float = 0.0
        dynamic_resolution: bool = False

    class ProduceResponse(BaseModel):
        final: str | None
        storyboard: str | None = None
        ledger: dict
        manifest: dict | None = None

    @app.get("/healthz")
    def healthz() -> dict:
        result = {"status": "ok", "cloud": "alibaba"}
        if os.environ.get("DASHSCOPE_API_KEY"):
            try:
                result["dashscope"] = dashscope_smoke_test()
            except Exception as e:
                result["dashscope"] = {"error": str(e)}
        if _oss_available():
            result["oss"] = {"configured": True, "bucket": os.environ["OSS_BUCKET"]}
        return result

    @app.post("/produce", response_model=ProduceResponse)
    def produce(req: ProduceRequest) -> ProduceResponse:
        cfg = ProductionConfig(shots=req.shots, quality_gate=req.quality_gate,
                               dynamic_resolution=req.dynamic_resolution)
        cfg.budget.max_tokens = req.max_tokens
        cfg.budget.max_spend_usd = req.max_spend_usd
        workdir = Path("productions") / uuid.uuid4().hex[:12]
        show = Showrunner(cfg, workdir=workdir)
        prod = show.run(req.premise)

        storyboard_path = workdir / "storyboard.html"
        response = ProduceResponse(
            final=prod.final_path, ledger=show.governor.summary(),
            storyboard=str(storyboard_path) if storyboard_path.exists() else None,
        )

        manifest_path = workdir / "manifest.json"
        if manifest_path.exists():
            response.manifest = json.loads(manifest_path.read_text())

        if prod.final_path and _oss_available():
            try:
                oss = OSSClient()
                url = oss.upload_file(prod.final_path)
                response.final = url
            except Exception as e:
                _log.error("OSS upload failed: %s", e)

        return response

    @app.get("/productions/{prod_id}/final.mp4")
    def get_final(prod_id: str) -> FileResponse:
        path = Path("productions") / prod_id / "final.mp4"
        if not path.exists():
            from fastapi import HTTPException
            raise HTTPException(404, "production not found")
        return FileResponse(path, media_type="video/mp4")

    return app


def serve() -> None:
    import uvicorn

    _logmod.setup()
    port = int(os.getenv("PORT", "8000"))
    _log.info("starting Auteur on Alibaba Cloud ECS, port %d", port)
    uvicorn.run(build_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    serve()
