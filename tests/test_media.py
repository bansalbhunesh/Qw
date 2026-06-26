"""Media layer tests — ffmpeg operations, frame sampling, assembly."""

import os
from pathlib import Path

os.environ["AUTEUR_MOCK"] = "1"

from auteur import media


def test_placeholder_clip_is_valid(tmp_path):
    clip = media.make_placeholder_clip(tmp_path / "test.mp4", index=0, seconds=3)
    assert Path(clip).exists()
    assert Path(clip).stat().st_size > 1000
    dur = media.probe_duration(clip)
    assert 2.5 <= dur <= 3.5


def test_extract_frames_returns_pngs(tmp_path):
    clip = media.make_placeholder_clip(tmp_path / "test.mp4", index=0, seconds=3)
    frames = media.extract_frames(clip, n=3)
    assert len(frames) >= 1
    assert all(f.endswith(".png") for f in frames)
    assert all(Path(f).stat().st_size > 100 for f in frames)


def test_frame_to_data_uri(tmp_path):
    clip = media.make_placeholder_clip(tmp_path / "test.mp4", index=0, seconds=2)
    frames = media.extract_frames(clip, n=1)
    uri = media.frame_to_data_uri(frames[0])
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 100


def test_extract_last_frame(tmp_path):
    clip = media.make_placeholder_clip(tmp_path / "test.mp4", index=0, seconds=3)
    last = media.extract_last_frame(clip)
    assert Path(last).exists()
    assert Path(last).stat().st_size > 100
    assert last.endswith(".png")


def test_concat_clips(tmp_path):
    clips = [
        media.make_placeholder_clip(tmp_path / f"c{i}.mp4", index=i, seconds=2)
        for i in range(3)
    ]
    final = media.concat_clips(clips, tmp_path / "final.mp4")
    assert Path(final).exists()
    dur = media.probe_duration(final)
    assert dur >= 5.0  # 3 clips * 2s minus possible rounding


def test_concat_filter_keeps_all_clips(tmp_path):
    clips = [
        media.make_placeholder_clip(tmp_path / f"c{i}.mp4", index=i, seconds=2)
        for i in range(4)
    ]
    final = media._concat_filter(clips, tmp_path / "filter.mp4")
    assert Path(final).exists()
    dur = media.probe_duration(final)
    assert dur >= 7.0  # 4 clips * 2s, all present (not just one)


def test_concat_with_crossfade(tmp_path):
    clips = [
        media.make_placeholder_clip(tmp_path / f"c{i}.mp4", index=i, seconds=3)
        for i in range(3)
    ]
    final = media.concat_with_crossfade(clips, tmp_path / "xfade.mp4", fade_s=0.5)
    assert Path(final).exists()
    assert Path(final).stat().st_size > 1000


def test_overlay_audio(tmp_path):
    clip = media.make_placeholder_clip(tmp_path / "v.mp4", index=0, seconds=2)
    media._run(["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-c:a", "pcm_s16le", str(tmp_path / "a.wav")])
    result = media.overlay_audio(clip, str(tmp_path / "a.wav"), tmp_path / "merged.mp4")
    assert Path(result).exists()
    assert Path(result).stat().st_size > 1000


def test_overlay_audio_no_audio_copies(tmp_path):
    clip = media.make_placeholder_clip(tmp_path / "v.mp4", index=0, seconds=2)
    result = media.overlay_audio(clip, None, tmp_path / "copy.mp4")
    assert Path(result).exists()


def test_mix_music(tmp_path):
    clip = media.make_placeholder_clip(tmp_path / "v.mp4", index=0, seconds=3)
    media._run(["-f", "lavfi", "-i", "sine=frequency=300:duration=3",
                "-c:a", "pcm_s16le", str(tmp_path / "score.wav")])
    out = media.mix_music(clip, tmp_path / "score.wav", tmp_path / "scored.mp4")
    assert Path(out).exists()
    assert Path(out).stat().st_size > 1000
