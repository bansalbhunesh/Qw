"""NaiveShowrunner — the baseline Auteur is measured against.

This is deliberately the "obvious" build a typical Track 2 entry ships:
  * one-shot scripting (no beat sheet, no importance weighting),
  * qwen-max for EVERYTHING (no tier routing),
  * no Style Bible caching (characters re-described per shot),
  * render every shot once, NO critic loop, NO retakes, NO early-exit.

Same Wan renders, same assembly — the only differences are the ones Auteur adds. That makes the
benchmark a clean A/B on the Budget Governor + critic loop, not on incidental factors.
"""

from __future__ import annotations

from pathlib import Path

from . import log
from .budget import BudgetGovernor
from .config import ProductionConfig, Tier
from .llm import QwenClient
from .models import Production, Script, Shot
from .agents.cinematographer import Cinematographer
from .agents.editor import Editor

STAGE = "naive"
_log = log.get("baseline")

_SYS = "You are a screenwriter. Return ONLY valid JSON."
_USER = """Write a {shots}-shot vertical short drama for this premise: {premise}

Return JSON:
{{"shots": [{{"description": "...", "dialogue": "...", "video_prompt": "a complete, \
self-contained text-to-video prompt describing everything in the shot including all character \
appearances in full detail"}}]}}
Describe each character's FULL physical appearance in every single video_prompt — no references \
to other shots. Each prompt must stand alone."""


class NaiveShowrunner:
    """Minimal baseline showrunner — no budget optimization, no critic loop.

    Used as the control group in A/B benchmarks against the full Auteur pipeline.
    Every difference in output quality or token spend is attributable to Auteur's
    Budget Governor, critic loop, and tier routing.
    """

    def __init__(self, cfg: ProductionConfig, workdir: str | Path = "out_naive"):
        self.cfg = cfg
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.governor = BudgetGovernor(cfg.budget, ledger_path=self.workdir / "ledger.json")
        self.client = QwenClient(self.governor)
        self.dp = Cinematographer(self.governor, resolution=cfg.resolution)
        self.editor = Editor(self.client, self.governor)

    def run(self, premise: str) -> Production:
        """Run a single-pass production: script → render all shots → assemble. No critic."""
        _log.info("naive baseline: %s", premise[:60])
        data = self.client.chat_json(
            STAGE, Tier.CREATIVE,
            [
                {"role": "system", "content": _SYS},
                {"role": "user", "content": _USER.format(premise=premise, shots=self.cfg.shots)},
            ],
        )
        shots = [
            Shot(index=i, beat_index=i, description=s.get("description", ""),
                 dialogue=s.get("dialogue", ""), video_prompt=s.get("video_prompt", ""),
                 importance=0.5)
            for i, s in enumerate(data.get("shots", []))
        ]
        script = Script(premise=premise, logline="", beats=[], shots=shots)

        clip_paths: list[str] = []
        for shot in shots:
            if not self.governor.can_render_clip():
                break
            try:
                clip = self.dp.render(
                    shot.video_prompt, self.workdir / f"shot_{shot.index}.mp4", index=shot.index,
                )
                shot.clip_path = clip
                clip_paths.append(clip)
            except Exception:
                _log.error("naive: shot %d failed, skipping", shot.index)
                continue

        kept_shots = [s for s in shots if s.clip_path in clip_paths]
        final = self.editor.assemble(kept_shots, self.workdir / "final.mp4") if kept_shots else ""
        self.governor.flush()
        return Production(premise=premise, script=script, final_path=final)
