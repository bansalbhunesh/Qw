"""Showrunner — the orchestrator. Plans the production and enforces the budget end to end.

The control flow that makes Auteur "budget-aware":
  1. Writer drafts a structured, beat-weighted script.
  2. Art Director builds the cached Style Bible.
  3. For each shot, Cinematographer renders one clip (if clip budget allows).
  4. Critic scores it. If it fails AND the Governor rules the shot important enough to spend a
     scarce retake, we reshoot ONCE with the critic's suggested fix. Otherwise we keep the take.
  5. Sound voices dialogue; Editor assembles the approved clips.
  6. The token ledger is flushed as a first-class deliverable.
"""

from __future__ import annotations

from pathlib import Path

from ..budget import BudgetGovernor
from ..config import ProductionConfig
from ..llm import QwenClient
from ..models import Production
from .art_director import ArtDirector
from .cinematographer import Cinematographer
from .editor import Editor
from .sound import Sound
from .writer import Writer


class Showrunner:
    def __init__(self, cfg: ProductionConfig, workdir: str | Path = "out"):
        self.cfg = cfg
        self.workdir = Path(workdir)
        self.governor = BudgetGovernor(cfg.budget, ledger_path=self.workdir / "ledger.json")
        self.client = QwenClient(self.governor)
        self.writer = Writer(self.client)
        self.art = ArtDirector(self.client)
        self.dp = Cinematographer(self.governor, resolution=cfg.resolution)
        self.sound = Sound(self.governor)
        self.editor = Editor(self.client, self.governor)

    def run(self, premise: str) -> Production:
        prod = Production(premise=premise)

        prod.script = self.writer.write(premise, self.cfg.shots)
        prod.style = self.art.build_bible(prod.script)

        clip_paths: list[str] = []
        audio_paths: list[str | None] = []

        for shot in prod.script.shots:
            if not self.governor.can_render_clip():
                break  # ran out of budget — ship what we have

            prompt = ArtDirector.apply(prod.style, shot.video_prompt)
            clip_url = self.dp.render(prompt)
            frames = _sample_frames(clip_url)
            review = self.editor.critique(shot, frames)
            shot.critic_score = float(review.get("overall", 0.0))

            if self.governor.should_retake(shot.critic_score, shot.importance):
                self.governor.register_retake()
                fixed = f"{prompt} {review.get('fix', '')}".strip()
                clip_url = self.dp.render(fixed)
                shot.retaken = True
                shot.critic_score = float(
                    self.editor.critique(shot, _sample_frames(clip_url)).get("overall", shot.critic_score)
                )

            shot.clip_path = clip_url
            clip_paths.append(clip_url)

            voice = _voice_for(prod, shot)
            audio_paths.append(
                self.sound.voice_line(shot.dialogue, voice, str(self.workdir / f"a{shot.index}.wav"))
            )

        prod.final_path = self.editor.assemble(
            clip_paths, audio_paths, self.workdir / "final.mp4"
        )
        self.governor.flush()
        return prod


def _sample_frames(clip_url: str) -> list[str]:
    """Pull a few representative frames from a clip for the Qwen-VL critic.

    Hardened during the build (ffmpeg frame extraction -> OSS URLs). For now returns the clip
    URL so the critic interface is exercised end to end.
    """
    return [clip_url]


def _voice_for(prod: Production, shot):
    if not prod.style or not prod.style.characters:
        return None
    return prod.style.characters[0]
