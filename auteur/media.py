"""Media utilities — ffmpeg-backed clip generation, frame sampling, and assembly.

Works without a system ffmpeg by falling back to the static binary bundled with
`imageio-ffmpeg`, so the pipeline runs anywhere. In mock mode we synthesize placeholder clips
here; in live mode the same frame-sampling and assembly code operates on real Wan output.
"""

from __future__ import annotations

import base64
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    """Resolve an ffmpeg binary: system first, then the imageio-ffmpeg static build."""
    from shutil import which

    sys_ff = which("ffmpeg")
    if sys_ff:
        return sys_ff
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(args: list[str]) -> None:
    subprocess.run([ffmpeg_exe(), "-y", *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --- mock clip synthesis ---------------------------------------------------------------

def make_placeholder_clip(out_path: str | Path, index: int, seconds: int = 4,
                          size: str = "720x1280") -> str:
    """Generate a deterministic vertical test clip with a tone, distinct per shot index.

    Used in mock mode so assembly produces a genuine .mp4 the demo/tests can inspect.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    hue = (index * 47) % 360  # vary color per shot so the cut is visibly multi-shot
    _run([
        "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=24:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency={220 + index * 40}:duration={seconds}",
        "-vf", f"hue=h={hue}", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(out_path),
    ])
    return str(out_path)


# --- frame sampling (feeds the Qwen-VL critic) -----------------------------------------

def extract_frames(clip_path: str | Path, n: int = 3) -> list[str]:
    """Extract ~n evenly spaced frames as PNGs; return their paths."""
    clip_path = Path(clip_path)
    out_dir = clip_path.parent / f"{clip_path.stem}_frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "f_%02d.png")
    # fps=1 then cap at n keeps it simple and deterministic for short clips.
    _run(["-i", str(clip_path), "-vf", f"fps=1,scale=512:-1", "-frames:v", str(n), pattern])
    return sorted(str(p) for p in out_dir.glob("f_*.png"))


def frame_to_data_uri(png_path: str | Path) -> str:
    """Encode a frame as a data URI Qwen-VL can consume directly (no OSS round-trip needed)."""
    raw = Path(png_path).read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


# --- assembly --------------------------------------------------------------------------

def concat_clips(clip_paths: list[str], out_path: str | Path) -> str:
    """Concatenate clips into one short. Re-encodes for robustness across heterogeneous inputs."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not clip_paths:
        raise ValueError("no clips to assemble")

    listing = out_path.with_suffix(".concat.txt")
    listing.write_text("".join(f"file '{Path(p).resolve()}'\n" for p in clip_paths))
    _run([
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(out_path),
    ])
    return str(out_path)
