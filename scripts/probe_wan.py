"""Direct probe of the DashScope Wan video endpoint — prints the full response body.

Use this to diagnose a 403/4xx on video-synthesis without running the whole pipeline.
It also lists which Wan model names your account is allowed to call, by trying a few.

    python scripts/probe_wan.py

Reads DASHSCOPE_API_KEY from the environment (or .env if python-dotenv is installed).
"""

from __future__ import annotations

import os
import sys

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE = os.getenv("DASHSCOPE_NATIVE_BASE", "https://dashscope-intl.aliyuncs.com/api/v1")
KEY = os.getenv("DASHSCOPE_API_KEY", "")

# Candidate t2v model names to probe — the first that returns a task_id (or a
# non-"model access" error) is the one your account can use.
CANDIDATES = [
    "wan2.7-t2v",
    "wan2.2-t2v-plus",
    "wanx2.1-t2v-turbo",
    "wanx2.1-t2v-plus",
    "wanx-v1",
    "wan2.5-t2v-preview",
]

# Candidate image-to-video model names (used for visual continuity / frame-chaining).
I2V_CANDIDATES = [
    "wan2.7-i2v",
    "wan2.2-i2v-plus",
    "wan2.2-i2v-flash",
    "wan2.5-i2v-preview",
    "wanx2.1-i2v-turbo",
]

PROMPT = "A serene mountain lake at sunrise, cinematic, gentle mist over the water."
# A small public image so the i2v create-task is well-formed; we only check model acceptance.
SAMPLE_IMG = "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg"


def probe(model: str, *, img_url: str | None = None) -> None:
    url = f"{BASE}/services/aigc/video-generation/video-synthesis"
    headers = {
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    payload = {
        "model": model,
        "input": {"prompt": PROMPT},
        "parameters": {"resolution": "720P"},
    }
    if img_url:
        payload["input"]["img_url"] = img_url
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
    except Exception as exc:
        print(f"  {model:24s} -> EXCEPTION: {exc}")
        return

    status = r.status_code
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:300]}

    if status < 300 and body.get("output", {}).get("task_id"):
        print(f"  {model:24s} -> OK (task_id={body['output']['task_id']})  <-- THIS MODEL WORKS")
        return

    code = body.get("code", "")
    msg = body.get("message", "")
    print(f"  {model:24s} -> {status}  code={code!r}  message={msg!r}")


def main() -> int:
    if not KEY:
        print("DASHSCOPE_API_KEY not set. Set it in your environment or .env first.")
        return 1
    print(f"Endpoint: {BASE}")
    print(f"Key: ...{KEY[-6:]}  (len={len(KEY)})\n")
    print("Probing candidate Wan t2v (text-to-video) model names:\n")
    for m in CANDIDATES:
        probe(m)

    print("\nProbing candidate Wan i2v (image-to-video, for continuity) model names:\n")
    for m in I2V_CANDIDATES:
        probe(m, img_url=SAMPLE_IMG)

    print(
        "\nReading the result:\n"
        "  * 'OK (task_id=...)'        -> use that model name "
        "(AUTEUR_MODEL_WAN_T2V / AUTEUR_MODEL_WAN_I2V).\n"
        "  * code='InvalidApiKey'      -> key problem.\n"
        "  * code='FreeTierOnly'/quota -> free Wan quota exhausted; enable billing/top-up.\n"
        "  * 'Model not exist'         -> that model name isn't valid; use one that returned OK.\n"
        "  * code='AccessDenied'       -> model needs activation in the Model Studio console.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
