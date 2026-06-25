"""Proof of Alibaba Cloud deployment.

This file is the single point that demonstrates Auteur's backend runs on Alibaba Cloud, as
required by the hackathon submission rules. It does two cloud-native things:

  1. Calls Alibaba Cloud Model Studio (DashScope) for Qwen + Wan inference.
  2. Persists generated assets (clips, key frames, the final cut) to Alibaba Cloud OSS
     (Object Storage Service), returning public URLs the agents and Qwen-VL critic consume.

The FastAPI app in `serve()` is what runs on the ECS instance (or Function Compute). The demo
recording for the submission shows this process serving traffic from an Alibaba Cloud host.

Env (set on the ECS instance / in .env):
  DASHSCOPE_API_KEY        - Model Studio key
  OSS_ACCESS_KEY_ID        - RAM user access key
  OSS_ACCESS_KEY_SECRET    - RAM user secret
  OSS_BUCKET               - target bucket
  OSS_ENDPOINT             - e.g. oss-ap-southeast-1.aliyuncs.com
"""

from __future__ import annotations

import os
import uuid

# --- Alibaba Cloud OSS asset storage ---------------------------------------------------

def upload_to_oss(data: bytes, key: str | None = None, content_type: str = "video/mp4") -> str:
    """Upload bytes to Alibaba Cloud OSS and return the object URL.

    Uses the official `oss2` SDK. This is the concrete Alibaba Cloud service call that proves
    the backend stores its artifacts on Alibaba Cloud infrastructure.
    """
    import oss2  # Alibaba Cloud OSS SDK

    auth = oss2.Auth(os.environ["OSS_ACCESS_KEY_ID"], os.environ["OSS_ACCESS_KEY_SECRET"])
    endpoint = os.environ["OSS_ENDPOINT"]
    bucket_name = os.environ["OSS_BUCKET"]
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    key = key or f"auteur/{uuid.uuid4().hex}.mp4"
    bucket.put_object(key, data, headers={"Content-Type": content_type})
    # Virtual-hosted style URL.
    host = endpoint.replace("https://", "").replace("http://", "")
    return f"https://{bucket_name}.{host}/{key}"


# --- DashScope (Alibaba Cloud Model Studio) health check -------------------------------

def dashscope_smoke_test() -> str:
    """Confirm the ECS host can reach Alibaba Cloud Model Studio and run Qwen inference."""
    from openai import OpenAI

    from auteur.config import DASHSCOPE_OPENAI_BASE

    client = OpenAI(api_key=os.environ["DASHSCOPE_API_KEY"], base_url=DASHSCOPE_OPENAI_BASE)
    resp = client.chat.completions.create(
        model="qwen-flash",
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
    )
    return resp.choices[0].message.content or ""


# --- The service that runs on Alibaba Cloud ECS ----------------------------------------

def build_app():
    """FastAPI app served from the Alibaba Cloud ECS instance."""
    from fastapi import FastAPI
    from pydantic import BaseModel

    from auteur.agents.showrunner import Showrunner
    from auteur.config import ProductionConfig

    app = FastAPI(title="Auteur — running on Alibaba Cloud")

    class ProduceRequest(BaseModel):
        premise: str
        shots: int = 6

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "cloud": "alibaba", "dashscope": dashscope_smoke_test()}

    @app.post("/produce")
    def produce(req: ProduceRequest) -> dict:
        show = Showrunner(ProductionConfig(shots=req.shots))
        prod = show.run(req.premise)
        return {"final": prod.final_path, "ledger": show.governor.summary()}

    return app


def serve() -> None:
    import uvicorn

    uvicorn.run(build_app(), host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    serve()
