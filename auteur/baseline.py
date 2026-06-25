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

from .budget import BudgetGovernor
from .config import ProductionConfig, Tier
from .llm import QwenClient
from .models import Production, Script, Shot
from .agents.cinematographer import Cinematographer
from .agents.editor import Editor

STAGE = "naive"

_SYS = "You are a screenwriter. Return ONLY JSON."
_USER = """Write a {shots}-shot vertical short drama for this premise: {premise}

Return JSON:
{{"shots": [{{"description": "...", "dialogue": "...", "video_prompt": "..."}}]}}
Describe each character's full appearance in every video_prompt."""


class NaiveShowrunner:
    def __init__(self, cfg: ProductionConfig, workdir: str | Path = "out_naive"):
        self.cfg = cfg
        self.workdir = Path(workdir)
        self.governor = BudgetGovernor(cfg.budget, ledger_path=self.workdir / "ledger.json")
        self.client = QwenClient(self.governor)
        self.dp = Cinematographer(self.governor, resolution=cfg.resolution)
        self.editor = Editor(self.client, self.governor)

    def run(self, premise: str) -> Production:
        # One-shot script, qwen-max for everything.
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
            clip = self.dp.render(
                shot.video_prompt, self.workdir / f"shot_{shot.index}.mp4", index=shot.index
            )
            shot.clip_path = clip
            clip_paths.append(clip)  # no critic, no retake — ship the first take

        final = self.editor.assemble(clip_paths, self.workdir / "final.mp4")
        self.governor.flush()
        return Production(premise=premise, script=script, final_path=final)
