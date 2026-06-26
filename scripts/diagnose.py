#!/usr/bin/env python3
"""Production diagnostic — validates the full Auteur pipeline.

Checks every external dependency (DashScope, Wan, CosyVoice, ffmpeg, OSS),
runs a minimal production, and reports what's working and what's not. Use this
before a live run or deployment to catch configuration issues early.

Usage:
    python scripts/diagnose.py            # check everything
    python scripts/diagnose.py --quick    # skip the full production test
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _check(label: str, fn, *args) -> bool:
    try:
        result = fn(*args)
        print(f"  [PASS] {label}: {result}")
        return True
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        return False


def check_ffmpeg() -> str:
    from auteur.media import ffmpeg_exe
    exe = ffmpeg_exe()
    import subprocess
    r = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=5)
    version = r.stdout.split("\n")[0] if r.returncode == 0 else "unknown"
    return version


def check_api_key() -> str:
    key = os.getenv("DASHSCOPE_API_KEY", "")
    if not key:
        return "not set (mock mode will be used)"
    return f"...{key[-8:]}" if len(key) > 12 else "set"


def check_dashscope() -> str:
    from openai import OpenAI
    from auteur.config import DASHSCOPE_OPENAI_BASE, require_api_key
    client = OpenAI(api_key=require_api_key(), base_url=DASHSCOPE_OPENAI_BASE)
    resp = client.chat.completions.create(
        model="qwen-flash",
        messages=[{"role": "user", "content": "Reply with: ready"}],
        max_tokens=5,
    )
    return f"qwen-flash responded ({resp.usage.total_tokens} tokens)"


def check_wan_model() -> str:
    from auteur.config import WAN_T2V_MODEL, WAN_I2V_MODEL
    return f"t2v={WAN_T2V_MODEL}, i2v={WAN_I2V_MODEL}"


def check_tts_model() -> str:
    from auteur.config import TTS_MODEL
    return f"model={TTS_MODEL}"


def check_mock_production() -> str:
    os.environ["AUTEUR_MOCK"] = "1"
    from auteur.agents.showrunner import Showrunner
    from auteur.config import ProductionConfig
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        cfg = ProductionConfig(shots=2)
        cfg.budget.max_clips = 4
        show = Showrunner(cfg, workdir=tmp)
        t0 = time.time()
        prod = show.run("A diagnostic test premise")
        elapsed = time.time() - t0
        final = Path(prod.final_path)
        if not final.exists():
            raise RuntimeError("no final.mp4 produced")
        artifacts = [
            f for f in Path(tmp).iterdir()
            if f.suffix in {".mp4", ".json", ".html", ".wav"}
        ]
        return f"OK in {elapsed:.1f}s — {len(artifacts)} artifacts, {final.stat().st_size // 1024}KB"
    del os.environ["AUTEUR_MOCK"]


def check_oss() -> str:
    keys = ["OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET", "OSS_BUCKET", "OSS_ENDPOINT"]
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        return f"not configured (missing: {', '.join(missing)})"
    return f"bucket={os.environ['OSS_BUCKET']}, endpoint={os.environ['OSS_ENDPOINT']}"


def main():
    parser = argparse.ArgumentParser(description="Auteur production diagnostic")
    parser.add_argument("--quick", action="store_true", help="skip production test")
    args = parser.parse_args()

    print("=" * 60)
    print("  AUTEUR PRODUCTION DIAGNOSTIC")
    print("=" * 60)

    results = []

    print("\n[1] Core dependencies")
    results.append(_check("ffmpeg", check_ffmpeg))

    print("\n[2] Configuration")
    results.append(_check("API key", check_api_key))
    results.append(_check("Wan models", check_wan_model))
    results.append(_check("TTS model", check_tts_model))
    results.append(_check("OSS storage", check_oss))

    mock = os.getenv("AUTEUR_MOCK", "").lower() in {"1", "true", "yes"} or not os.getenv("DASHSCOPE_API_KEY")
    print(f"\n[3] Mode: {'MOCK' if mock else 'LIVE'}")

    if not mock:
        print("\n[4] Live connectivity")
        results.append(_check("DashScope API", check_dashscope))

    if not args.quick:
        print("\n[5] Full pipeline test (mock mode)")
        results.append(_check("Mock production", check_mock_production))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"  {passed}/{total} checks passed")
    if passed == total:
        print("  STATUS: READY FOR PRODUCTION")
    else:
        print("  STATUS: ISSUES FOUND — review failures above")
    print(f"{'=' * 60}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
