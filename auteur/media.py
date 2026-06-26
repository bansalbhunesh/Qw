"""Media utilities — ffmpeg-backed clip generation, frame sampling, and assembly.

Works without a system ffmpeg by falling back to the static binary bundled with
`imageio-ffmpeg`. All media operations go through here so we control codec uniformity,
error handling, and the frame format the Qwen-VL critic receives.
"""

from __future__ import annotations

import base64
import json
import subprocess
from functools import lru_cache
from pathlib import Path

from . import log

_log = log.get("media")


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    from shutil import which

    sys_ff = which("ffmpeg")
    if sys_ff:
        return sys_ff
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


@lru_cache(maxsize=1)
def ffprobe_exe() -> str:
    from shutil import which

    sys_fp = which("ffprobe")
    if sys_fp:
        return sys_fp
    ff = ffmpeg_exe()
    candidate = ff.replace("ffmpeg", "ffprobe")
    if Path(candidate).exists():
        return candidate
    return ff  # fallback — probe via ffmpeg -i


def _run(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [ffmpeg_exe(), "-y", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(f"ffmpeg failed (rc={result.returncode}): {stderr}")
    return result


# --- probing -----------------------------------------------------------------------

def has_audio_stream(path: str | Path) -> bool:
    """True if the file has at least one audio stream. Wan clips render silent, so we
    must detect this before trying to mix or crossfade audio.

    Uses ffprobe when a real one is available; falls back to parsing `ffmpeg -i` stderr
    (imageio-ffmpeg ships ffmpeg but not ffprobe, so `ffprobe_exe()` may return ffmpeg,
    which doesn't understand -select_streams)."""
    probe = ffprobe_exe()
    if "ffprobe" in Path(probe).name.lower():
        try:
            r = subprocess.run(
                [probe, "-v", "error", "-select_streams", "a",
                 "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                return bool(r.stdout.strip())
        except Exception:
            pass
    # Fallback: parse ffmpeg -i stderr for an Audio stream line.
    try:
        r = subprocess.run([ffmpeg_exe(), "-i", str(path)],
                           capture_output=True, text=True, timeout=15)
        return "Audio:" in r.stderr
    except Exception:
        return False


def probe_duration(path: str | Path) -> float:
    """Return clip duration in seconds."""
    try:
        r = subprocess.run(
            [ffprobe_exe(), "-v", "quiet", "-print_format", "json",
             "-show_format", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        pass
    # Fallback — ffmpeg -i prints duration in stderr
    r = subprocess.run(
        [ffmpeg_exe(), "-i", str(path)],
        capture_output=True, text=True, timeout=15,
    )
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 4.0  # safe fallback for test clips


# --- mock clip synthesis ---------------------------------------------------------------

def shot_duration(importance: float, beat_label: str = "") -> float:
    """Compute shot duration based on importance and beat type.

    Hooks and climaxes get longer screen time; transitional beats are tighter.
    Returns seconds (3.0 to 8.0 range).
    """
    base = 3.0 + importance * 4.0
    label = beat_label.lower()
    if label in {"hook", "climax", "button"}:
        base += 1.0
    elif label in {"setup", "escalation"}:
        base -= 0.5
    return round(max(3.0, min(8.0, base)), 1)


def make_placeholder_clip(
    out_path: str | Path, index: int, seconds: float = 4, size: str = "720x1280",
) -> str:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    hue = (index * 47) % 360
    _run([
        "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=24:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency={220 + index * 40}:duration={seconds}",
        "-vf", f"hue=h={hue}", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-shortest", str(out_path),
    ])
    _log.info("mock clip %d -> %s (%.1fs)", index, out_path, seconds)
    return str(out_path)


# --- frame sampling (feeds the Qwen-VL critic) -----------------------------------------

def extract_frames(clip_path: str | Path, n: int = 3) -> list[str]:
    """Extract ~n evenly spaced frames as PNGs; return their paths.

    Uses select filter for precise frame picking instead of fps filter, ensuring we hit
    the beginning, middle, and end of the clip regardless of duration.
    """
    clip_path = Path(clip_path)
    out_dir = clip_path.parent / f"{clip_path.stem}_frames"
    out_dir.mkdir(parents=True, exist_ok=True)

    duration = probe_duration(clip_path)
    # Don't try to extract more frames than the clip has seconds
    n = min(n, max(1, int(duration)))
    if n == 1:
        timestamps = [min(duration / 2, max(0, duration - 0.5))]
    else:
        step = max(0.01, (duration - 0.5) / (n - 1))
        timestamps = [min(i * step, duration - 0.3) for i in range(n)]

    paths: list[str] = []
    for i, ts in enumerate(timestamps):
        out_png = out_dir / f"f_{i:02d}.png"
        try:
            _run([
                "-ss", f"{ts:.2f}", "-i", str(clip_path),
                "-vf", "scale=512:-1", "-frames:v", "1", str(out_png),
            ])
            if out_png.exists() and out_png.stat().st_size > 0:
                paths.append(str(out_png))
        except RuntimeError:
            pass  # seek past end — skip this frame

    if not paths:
        # Last resort: just grab the first frame
        fallback = out_dir / "f_fallback.png"
        _run(["-i", str(clip_path), "-vf", "scale=512:-1", "-frames:v", "1", str(fallback)])
        if fallback.exists():
            paths.append(str(fallback))

    _log.info("extracted %d frames from %s", len(paths), clip_path.name)
    return paths


def frame_to_data_uri(png_path: str | Path) -> str:
    raw = Path(png_path).read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    suffix = Path(png_path).suffix.lstrip(".").lower() or "png"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    return f"data:image/{mime};base64,{b64}"


def extract_last_frame(clip_path: str | Path, out_path: str | Path | None = None) -> str:
    """Grab the final frame of a clip as a full-resolution PNG.

    Used to seed the next shot (image-to-video) so the character and world carry forward
    visually, not just textually. Tries an end-relative seek first, then a duration-based one.
    """
    clip_path = Path(clip_path)
    out = Path(out_path) if out_path else clip_path.with_name(f"{clip_path.stem}_last.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    # -sseof seeks relative to end-of-file; grab the last available frame.
    try:
        _run(["-sseof", "-0.5", "-i", str(clip_path), "-update", "1", "-frames:v", "1", str(out)])
        if out.exists() and out.stat().st_size > 0:
            return str(out)
    except RuntimeError:
        pass

    # Fallback: seek to just before the probed duration.
    dur = probe_duration(clip_path)
    ts = max(0.0, dur - 0.3)
    _run(["-ss", f"{ts:.2f}", "-i", str(clip_path), "-update", "1", "-frames:v", "1", str(out)])
    return str(out)


# --- audio overlay ------------------------------------------------------------------

def overlay_audio(video_path: str, audio_path: str | None, out_path: str | Path) -> str:
    """Merge a dialogue audio track onto a video clip. If no audio, copy the clip."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not audio_path or not Path(audio_path).exists():
        import shutil
        shutil.copy2(video_path, out_path)
        return str(out_path)

    _run([
        "-i", video_path, "-i", audio_path,
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path),
    ])
    return str(out_path)


def mix_music(
    video_path: str | Path, music_path: str | Path, out_path: str | Path,
    music_volume: float = 0.6,
) -> str:
    """Mix a music bed UNDER a video's existing audio (dialogue + clip sound).

    The bed is attenuated and mixed at low weight so dialogue stays intelligible. Falls back to
    copying the original video if the mix fails (e.g. video has no audio track)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # If the video has no audio track (Wan clips render silent and TTS may have failed),
    # attach the music as the sole audio track instead of mixing — otherwise ffmpeg's
    # amix references a non-existent [0:a] and the whole score is dropped.
    if not has_audio_stream(video_path):
        try:
            _run([
                "-i", str(video_path), "-i", str(music_path),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path),
            ])
            _log.info("video had no audio — music added as primary track")
            return str(out_path)
        except RuntimeError as exc:
            _log.warning("music attach failed (%s) — shipping silent", exc)
            import shutil
            shutil.copy2(video_path, out_path)
            return str(out_path)

    try:
        _run([
            "-i", str(video_path), "-i", str(music_path),
            "-filter_complex",
            f"[1:a]volume={music_volume}[m];"
            "[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path),
        ])
        return str(out_path)
    except RuntimeError as exc:
        _log.warning("music mix failed (%s) — shipping without score", exc)
        import shutil
        shutil.copy2(video_path, out_path)
        return str(out_path)


# --- assembly --------------------------------------------------------------------------

def concat_clips(clip_paths: list[str], out_path: str | Path) -> str:
    """Concatenate clips into one short. Re-encodes for codec/resolution uniformity.

    Tries the concat *demuxer* first (fast), then falls back to the concat *filter* (slower but
    robust — no list file, no path-quoting pitfalls on Windows). The filter path guarantees all
    clips make it into the final cut even when the demuxer chokes on a platform path quirk."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not clip_paths:
        raise ValueError("no clips to assemble")

    listing = out_path.with_suffix(".concat.txt")
    listing.write_text("".join(
        f"file '{Path(p).resolve().as_posix()}'\n" for p in clip_paths
    ))

    total_dur = sum(probe_duration(p) for p in clip_paths)
    _log.info("assembling %d clips (%.1fs total) -> %s", len(clip_paths), total_dur, out_path.name)

    try:
        _run([
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out_path),
        ])
        return str(out_path)
    except RuntimeError as exc:
        _log.warning("concat demuxer failed (%s) — using concat filter", exc)
        return _concat_filter(clip_paths, out_path)


def _concat_filter(clip_paths: list[str], out_path: str | Path) -> str:
    """Concatenate via the concat filter (each clip as a separate -i input). Windows-safe:
    paths are passed as argv, never written into a list file."""
    out_path = Path(out_path)
    cmd: list[str] = []
    for p in clip_paths:
        cmd += ["-i", str(Path(p).resolve())]
    n = len(clip_paths)
    streams = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n))
    cmd += [
        "-filter_complex", f"{streams}concat=n={n}:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path),
    ]
    _run(cmd)
    return str(out_path)


def concat_with_crossfade(
    clip_paths: list[str], out_path: str | Path, fade_s: float = 0.5,
) -> str:
    """Concatenate with video crossfade transitions between clips. Falls back to plain
    concat on error (some ffmpeg builds lack xfade)."""
    if len(clip_paths) < 2:
        return concat_clips(clip_paths, out_path)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    durations = [probe_duration(p) for p in clip_paths]

    n = len(clip_paths)
    offsets = []
    acc = 0.0
    for i in range(n - 1):
        acc += durations[i] - fade_s
        offsets.append(acc)

    # Wan clips render silent — only build the audio crossfade graph if EVERY clip has audio.
    all_have_audio = all(has_audio_stream(p) for p in clip_paths)

    vfilter_parts = []
    afilter_parts = []
    prev_v = "[0:v]"
    prev_a = "[0:a]"

    for i in range(n - 1):
        next_v = f"[{i + 1}:v]"
        next_a = f"[{i + 1}:a]"
        out_v = f"[v{i}]" if i < n - 2 else "[vout]"
        out_a = f"[a{i}]" if i < n - 2 else "[aout]"
        vfilter_parts.append(
            f"{prev_v}{next_v}xfade=transition=fade:duration={fade_s}:offset={offsets[i]:.3f}{out_v}"
        )
        if all_have_audio:
            afilter_parts.append(
                f"{prev_a}{next_a}acrossfade=d={fade_s}:c1=tri:c2=tri{out_a}"
            )
        prev_v = out_v
        prev_a = out_a

    fcomplex = ";".join(vfilter_parts + afilter_parts)

    # Build as argument list (not shell string) for cross-platform compatibility
    cmd: list[str] = [ffmpeg_exe(), "-y"]
    for p in clip_paths:
        cmd += ["-i", str(Path(p).resolve())]
    cmd += ["-filter_complex", fcomplex, "-map", "[vout]"]
    if all_have_audio:
        cmd += ["-map", "[aout]", "-c:a", "aac"]
    cmd += [
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(out_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=180)
        if result.returncode == 0:
            _log.info("crossfade assembly (%d clips, %.1fs fade) -> %s",
                      len(clip_paths), fade_s, out_path.name)
            return str(out_path)
        _log.warning("crossfade ffmpeg rc=%d: %s", result.returncode,
                     result.stderr.decode("utf-8", errors="replace")[-200:])
    except Exception as exc:
        _log.warning("crossfade exception: %s", exc)

    _log.warning("crossfade failed, falling back to plain concat")
    return concat_clips(clip_paths, out_path)
