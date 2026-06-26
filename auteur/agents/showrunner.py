"""Showrunner — the orchestrator. Plans the production and enforces the budget end to end.

The production-grade control flow:
  1. Writer drafts a structured, beat-weighted script.
  2. Art Director builds the cached Style Bible.
  3. For each shot (in importance-descending order for retake priority):
     a. Cinematographer renders one clip (if clip budget allows).
     b. Critic (Qwen-VL) scores it on 3 axes.
     c. If it fails AND the Governor rules it worth a reshoot → one retake with the critic's
        fix injected into the prompt.
     d. Sound voices dialogue for the shot.
  4. Editor overlays dialogue audio, crossfades clips, and outputs the final cut.
  5. Token ledger + production manifest are flushed as first-class deliverables.

Resilience: individual shot failures are caught and logged. A production ships whatever it has —
a partially-rendered short is better than a crash.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import asdict
from pathlib import Path

from .. import log, media
from ..budget import BudgetGovernor
from ..config import ProductionConfig
from ..events import bus
from ..llm import QwenClient
from ..models import Production
from .art_director import ArtDirector
from .cinematographer import Cinematographer
from .editor import Editor
from .sound import Sound
from .writer import Writer

_log = log.get("showrunner")


class Showrunner:
    def __init__(self, cfg: ProductionConfig, workdir: str | Path = "out"):
        self.cfg = cfg
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.governor = BudgetGovernor(cfg.budget, ledger_path=self.workdir / "ledger.json")
        self.client = QwenClient(self.governor)
        self.writer = Writer(self.client)
        self.art = ArtDirector(self.client)
        self.dp = Cinematographer(self.governor, resolution=cfg.resolution)
        self.sound = Sound(self.governor)
        self.editor = Editor(self.client, self.governor)

    def run(self, premise: str) -> Production:
        _log.info("=== PRODUCTION START: %s ===", premise[:60])
        prod = Production(premise=premise)

        bus.emit("production_start", "showrunner", premise=premise)

        # --- phase 1: writing ---
        prod.script = self.writer.write(premise, self.cfg.shots)
        _log.info("script: %d beats, %d shots", len(prod.script.beats), len(prod.script.shots))
        bus.emit("script_complete", "writer",
                 logline=prod.script.logline,
                 beats=[{"label": b.label, "summary": b.summary, "importance": b.importance}
                        for b in prod.script.beats],
                 n_shots=len(prod.script.shots))

        # --- phase 2: art direction ---
        prod.style = self.art.build_bible(prod.script)
        bus.emit("style_bible_complete", "art_director",
                 look=prod.style.look,
                 characters=[{"name": c.name, "description": c.description[:80]}
                             for c in prod.style.characters])

        # --- phase 3: production (render + critique + voice per shot) ---
        clip_paths: list[str] = []
        audio_paths: list[str | None] = []
        anchor: str | None = None  # last frame of the previous shot — seeds visual continuity

        for shot in prod.script.shots:
            if not self.governor.can_render_clip():
                _log.warning("clip budget exhausted at shot %d — shipping what we have", shot.index)
                break

            try:
                clip, audio = self._produce_shot(prod, shot, reference_image=anchor)
                clip_paths.append(clip)
                audio_paths.append(audio)
                if self.cfg.consistency:
                    try:
                        anchor = media.extract_last_frame(
                            clip, self.workdir / f"anchor_{shot.index}.png",
                        )
                    except Exception:
                        _log.warning("could not extract anchor frame from shot %d", shot.index)
            except Exception:
                _log.error("shot %d failed — skipping:\n%s", shot.index, traceback.format_exc())
                continue

        if not clip_paths:
            _log.error("no clips rendered — cannot assemble")
            self.governor.flush()
            bus.emit("production_failed", "showrunner", reason="no clips rendered")
            return prod

        # --- phase 4: assembly ---
        _log.info("assembling %d clips into final cut", len(clip_paths))
        bus.emit("assembly_start", "editor", n_clips=len(clip_paths))
        prod.final_path = self.editor.assemble(
            clip_paths, self.workdir / "final.mp4", audio_paths=audio_paths,
        )

        # --- phase 5: deliverables ---
        self.governor.flush()
        self._write_manifest(prod)

        bus.emit("production_complete", "showrunner",
                 final=prod.final_path, budget=self.governor.summary())
        _log.info("=== PRODUCTION COMPLETE: %s ===", prod.final_path)
        _log.info(
            "budget: %d/%d tokens, %d/%d clips, %d/%d retakes",
            self.governor.state.tokens_used, self.governor.budget.max_tokens,
            self.governor.state.clips_used, self.governor.budget.max_clips,
            self.governor.state.retakes_used, self.governor.budget.max_retakes,
        )
        return prod

    def _produce_shot(
        self, prod: Production, shot, *, reference_image: str | None = None,
    ) -> tuple[str, str | None]:
        """Render, critique, optionally reshoot, and voice one shot. Returns (clip_path, audio_path).

        `reference_image` is the previous shot's final frame, used to seed image-to-video for
        visual continuity. The Cinematographer falls back to text-to-video if i2v fails.
        """
        prompt = ArtDirector.apply(prod.style, shot.video_prompt)

        # --- render ---
        clip = self.dp.render(
            prompt, self.workdir / f"shot_{shot.index}.mp4", index=shot.index,
            reference_image=reference_image,
        )

        # --- critique ---
        frames = self.editor.sample_frames(clip)
        review = self.editor.critique(shot, frames)
        shot.critic_score = float(review.get("overall", 0.0))

        # --- conditional reshoot ---
        if self.governor.should_retake(shot.critic_score, shot.importance):
            self.governor.register_retake()
            fix = review.get("fix", "")
            fixed_prompt = f"{prompt} {fix}".strip() if fix else prompt
            _log.info(
                "retaking shot %d (score=%.1f, importance=%.1f): %s",
                shot.index, shot.critic_score, shot.importance, fix[:60],
            )
            clip = self.dp.render(
                fixed_prompt, self.workdir / f"shot_{shot.index}_retake.mp4", index=shot.index,
                reference_image=reference_image,
            )
            shot.retaken = True
            retake_review = self.editor.critique(shot, self.editor.sample_frames(clip))
            shot.critic_score = float(retake_review.get("overall", shot.critic_score))

        shot.clip_path = clip
        bus.emit("shot_complete", "showrunner",
                 index=shot.index, score=shot.critic_score, retaken=shot.retaken,
                 importance=shot.importance)

        # --- voice ---
        voice = self._voice_for(prod, shot)
        audio = self.sound.voice_line(
            shot.dialogue, voice, str(self.workdir / f"audio_{shot.index}.wav"),
        )

        return clip, audio

    @staticmethod
    def _voice_for(prod: Production, shot):
        """Match a shot's dialogue to a character voice from the Bible."""
        if not prod.style or not prod.style.characters:
            return None
        # For multi-character dialogue we'd parse speaker tags; for now, assign by shot parity
        # (character 0 for even shots, character 1 for odd — a reasonable heuristic for two-handers).
        chars = prod.style.characters
        if len(chars) == 1:
            return chars[0]
        return chars[shot.index % len(chars)]

    def _write_manifest(self, prod: Production) -> None:
        """Serialize the full production state as a JSON manifest — script, shots, scores, paths."""
        manifest = {
            "premise": prod.premise,
            "logline": prod.script.logline if prod.script else "",
            "final": prod.final_path,
            "beats": [asdict(b) for b in prod.script.beats] if prod.script else [],
            "shots": [],
            "style": {
                "look": prod.style.look if prod.style else "",
                "characters": [asdict(c) for c in prod.style.characters] if prod.style else [],
            },
            "budget": self.governor.summary(),
        }
        if prod.script:
            for s in prod.script.shots:
                manifest["shots"].append({
                    "index": s.index,
                    "beat": s.beat_index,
                    "description": s.description,
                    "dialogue": s.dialogue,
                    "critic_score": s.critic_score,
                    "retaken": s.retaken,
                    "clip": s.clip_path,
                    "importance": s.importance,
                })
        path = self.workdir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2))
        _log.info("manifest -> %s", path)
