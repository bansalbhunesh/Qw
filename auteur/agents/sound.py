"""Sound — dialogue voicing via DashScope TTS (CosyVoice) + music cues.

Each shot's dialogue is voiced with a per-character voice from the Style Bible. CosyVoice runs
as a DashScope async job (same pattern as Wan). TTS calls are metered in the ledger. In mock
mode we emit a placeholder tone so the path is exercised without spend.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from .. import log, media
from ..budget import BudgetGovernor
from ..config import DASHSCOPE_NATIVE_BASE, TTS_MODEL, is_mock, require_api_key
from ..models import Character
from ..retry import with_retry

STAGE = "sound"
_log = log.get("sound")

_POLL_INTERVAL_S = 3
_POLL_TIMEOUT_S = 120

# CosyVoice voice map — character voice descriptors to DashScope voice IDs.
# Uses English-compatible voices for the international endpoint.
_VOICE_MAP: dict[str, str] = {
    "warm": "longshu",
    "gravelly": "longjielidou",
    "youthful": "longxiaoxia",
    "neutral": "longshu",
    "deep": "longjielidou",
    "soft": "longxiaoxia",
}

# Mood -> a root/third/fifth triad (Hz) for the procedural score bed. Lower octaves read as
# warmer and sit comfortably under dialogue. Minor triads for darker moods, major for hope.
_SCORE_KEYS: dict[str, tuple[float, float, float]] = {
    "tense": (146.83, 174.61, 220.00),      # D minor
    "urgent": (146.83, 174.61, 220.00),
    "melancholy": (220.00, 261.63, 329.63),  # A minor
    "sad": (220.00, 261.63, 329.63),
    "bittersweet": (220.00, 261.63, 329.63),
    "tender": (130.81, 164.81, 196.00),      # C major
    "hopeful": (130.81, 164.81, 196.00),
    "warm": (130.81, 164.81, 196.00),
    "cathartic": (196.00, 246.94, 293.66),   # G major
    "triumphant": (196.00, 246.94, 293.66),
    "neutral": (164.81, 196.00, 246.94),     # E minor
}


class Sound:
    def __init__(self, governor: BudgetGovernor):
        self.governor = governor

    def voice_line(self, text: str, character: Character | None, out_path: str) -> str | None:
        """Synthesize one dialogue line to an audio file. Returns path or None if empty line."""
        if not text.strip():
            return None

        if is_mock():
            self._mock_tone(out_path, text)
            self.governor.record_tts(STAGE, "mock-tts", note=text[:60])
            return out_path

        voice_id = _VOICE_MAP.get(character.voice, "longxiaochun") if character else "longxiaochun"
        _log.info("voicing: '%s' (voice=%s)", text[:50], voice_id)

        def _do_tts():
            return self._cosyvoice_sync(text, voice_id, out_path)

        path = with_retry(_do_tts, label=f"tts/{text[:20]}", max_retries=3, base_delay=2.0)
        self.governor.record_tts(STAGE, TTS_MODEL, note=text[:60])
        return path

    # --- score bed ----------------------------------------------------------------

    def score(self, mood: str, duration: float, out_path: str, intensity: float = 0.5) -> str:
        """Synthesize a warm ambient music bed for the whole piece, keyed to the emotional mood.

        Procedural (ffmpeg-only) so it always works offline and costs zero tokens: a triad pad
        tuned to a mood-appropriate key, softened with tremolo, a low-pass for warmth, and a
        touch of echo for space. Volume scales with intensity but stays low — it sits *under*
        dialogue, never over it.
        """
        if duration <= 0:
            duration = 8.0
        root, third, fifth = _SCORE_KEYS.get(mood.lower(), _SCORE_KEYS["neutral"])
        vol = max(0.08, min(0.28, 0.12 + 0.18 * float(intensity)))
        fade = min(2.0, duration / 4)
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        fcomplex = (
            "[0:a][1:a][2:a]amix=inputs=3:duration=longest:normalize=0[mix];"
            "[mix]tremolo=f=0.15:d=0.4,lowpass=f=900,aecho=0.8:0.7:55:0.3,"
            f"afade=t=in:d={fade:.2f},afade=t=out:st={max(0.0, duration - fade):.2f}:d={fade:.2f},"
            f"volume={vol:.2f}[a]"
        )
        media._run([
            "-f", "lavfi", "-i", f"sine=frequency={root}:duration={duration:.2f}",
            "-f", "lavfi", "-i", f"sine=frequency={third}:duration={duration:.2f}",
            "-f", "lavfi", "-i", f"sine=frequency={fifth}:duration={duration:.2f}",
            "-filter_complex", fcomplex, "-map", "[a]",
            "-c:a", "pcm_s16le", str(out),
        ])
        _log.info("score: mood=%s intensity=%.1f duration=%.1fs -> %s",
                  mood, intensity, duration, out.name)
        return str(out)

    # --- DashScope CosyVoice TTS ---------------------------------------------------

    def _cosyvoice_sync(self, text: str, voice: str, out_path: str) -> str:
        """CosyVoice via the DashScope speech synthesis endpoint."""
        headers = {
            "Authorization": f"Bearer {require_api_key()}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": TTS_MODEL,
            "input": {"text": text},
            "parameters": {"voice": voice, "format": "wav", "sample_rate": 22050},
        }

        url = f"{DASHSCOPE_NATIVE_BASE}/services/aigc/text2audio/audio-synthesis"
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        if r.status_code >= 400:
            _log.error("TTS API %d: %s", r.status_code, r.text[:300])
        r.raise_for_status()
        body = r.json()

        # Some TTS endpoints return audio inline; others return a task to poll.
        if "output" in body and "audio_url" in body.get("output", {}):
            return self._download_audio(body["output"]["audio_url"], out_path)

        task_id = body.get("output", {}).get("task_id")
        if task_id:
            return self._poll_tts(task_id, out_path)

        raise RuntimeError(f"unexpected TTS response: {body}")

    def _poll_tts(self, task_id: str, out_path: str) -> str:
        deadline = time.time() + _POLL_TIMEOUT_S
        while time.time() < deadline:
            r = requests.get(
                f"{DASHSCOPE_NATIVE_BASE}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {require_api_key()}"}, timeout=30,
            )
            r.raise_for_status()
            out = r.json().get("output", {})
            status = out.get("task_status", "UNKNOWN")

            if status == "SUCCEEDED":
                audio_url = out.get("audio_url") or out.get("results", [{}])[0].get("url", "")
                if not audio_url:
                    raise RuntimeError(f"TTS SUCCEEDED but no audio_url: {out}")
                return self._download_audio(audio_url, out_path)

            if status in {"FAILED", "CANCELED"}:
                raise RuntimeError(f"TTS task {task_id} {status}: {out}")

            time.sleep(_POLL_INTERVAL_S)
        raise TimeoutError(f"TTS task {task_id} did not finish in {_POLL_TIMEOUT_S}s")

    @staticmethod
    def _download_audio(url: str, out_path: str) -> str:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 14):
                    f.write(chunk)
        _log.info("downloaded TTS -> %s (%d KB)", Path(out_path).name,
                  Path(out_path).stat().st_size // 1024)
        return out_path

    @staticmethod
    def _mock_tone(out_path: str, text: str) -> None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        duration = max(1.0, min(5.0, len(text) * 0.06))  # rough speech duration
        media._run([
            "-f", "lavfi", "-i", f"sine=frequency=330:duration={duration:.1f}",
            "-c:a", "pcm_s16le", str(out),
        ])
