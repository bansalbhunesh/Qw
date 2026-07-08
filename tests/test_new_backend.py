"""Tests for the newest hard backend features: Auto-Trimmer and Production Vault."""

import os
from pathlib import Path
from unittest.mock import patch

os.environ["AUTEUR_MOCK"] = "1"

from auteur.agents.showrunner import Showrunner
from auteur.config import ProductionConfig
from auteur.models import Shot


def _cfg(shots=2):
    cfg = ProductionConfig(shots=shots)
    cfg.budget.max_clips = 6
    cfg.budget.max_retakes = 0
    return cfg


def test_auto_trimmer_trims_temporal_degradation(tmp_path):
    """Test that Editor.assemble correctly trims a clip based on usable_duration."""
    from auteur.agents.editor import Editor
    from auteur.llm import QwenClient
    from auteur.budget import BudgetGovernor

    # Setup dummy clips
    dummy1 = tmp_path / "shot_1.mp4"
    dummy2 = tmp_path / "shot_2.mp4"
    # Create valid mock clips
    from auteur.media import make_placeholder_clip, probe_duration
    make_placeholder_clip(dummy1, 1, seconds=5.0)
    make_placeholder_clip(dummy2, 2, seconds=5.0)

    # Shot 1 has no degradation
    shot1 = Shot(index=1, beat_index=1, description="", dialogue="", video_prompt="", importance=1.0)
    shot1.clip_path = str(dummy1)
    shot1.usable_duration = 5.0

    # Shot 2 degrades at 3.0s
    shot2 = Shot(index=2, beat_index=2, description="", dialogue="", video_prompt="", importance=1.0)
    shot2.clip_path = str(dummy2)
    shot2.usable_duration = 3.0

    editor = Editor(QwenClient(BudgetGovernor(_cfg().budget)), BudgetGovernor(_cfg().budget))
    
    out_path = tmp_path / "final_trimmed.mp4"
    final = editor.assemble([shot1, shot2], out_path, crossfade=False)
    
    assert Path(final).exists()
    
    # Check that trimmed fragments exist and their durations are correct
    trimmed1 = tmp_path / "trimmed_0.mp4"
    trimmed2 = tmp_path / "trimmed_1.mp4"
    
    # dummy1 was 5s and usable_duration=5, so it shouldn't be trimmed (or trimmed closely)
    dur2 = probe_duration(trimmed2) if trimmed2.exists() else probe_duration(tmp_path / "merged_1.mp4")
    # Due to ffmpeg inexactness, allow some tolerance, but it should be close to 3s
    assert dur2 <= 3.5, f"Expected shot 2 to be trimmed to ~3s, got {dur2}"


def test_production_vault_saves_and_resumes(tmp_path):
    """Test that Showrunner checkpointing works and can be resumed."""
    # 1. Run a partial production that fails halfway
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    
    # Give valid paths so we don't hit media errors
    from auteur.media import make_placeholder_clip
    clip0 = str(tmp_path / "dummy_clip_0.mp4")
    make_placeholder_clip(clip0, 0, 4.0)
    
    # We will patch the dp.render to fail on shot index 1 (second shot)
    with patch.object(show.dp, "render") as mock_render:
        mock_render.side_effect = [clip0, Exception("Simulated crash!"), "dummy_clip_2.mp4"]
        
        # This run will generate the script, style, and shot 0, then crash on shot 1.
        prod = show.run("A Vault Test")
        
        # The crash was handled, it skipped shot 1 and 2, but saved the vault.
        assert (tmp_path / "vault.pkl").exists(), "Vault should be saved"
        assert prod.script is not None
        assert prod.style is not None

    # 2. Resume the production
    show2 = Showrunner(_cfg(shots=3), workdir=tmp_path)
    with patch.object(show2.dp, "render") as mock_render2:
        # Give valid paths so we don't hit media errors
        from auteur.media import make_placeholder_clip
        clip1 = str(tmp_path / "dummy_clip_1.mp4")
        clip2 = str(tmp_path / "dummy_clip_2.mp4")
        make_placeholder_clip(clip1, 1, 4.0)
        make_placeholder_clip(clip2, 2, 4.0)
        
        mock_render2.side_effect = [clip1, clip2]
        
        # Pass resume=True
        prod2 = show2.run("A Vault Test", resume=True)
        
        # Since shot 0 was already rendered in the first run, render should only be called twice (for shot 1 and 2)
        assert mock_render2.call_count == 2
        assert prod2.final_path is not None
        assert Path(prod2.final_path).exists()
