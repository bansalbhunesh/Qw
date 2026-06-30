"""Prompt Optimizer — refines video prompts for Wan model compatibility.

Text-to-video models have specific strengths (clear composition, single-subject, strong
lighting cues) and weaknesses (complex multi-character interactions, abstract concepts,
rapid motion). This agent takes the Writer's raw video prompt and refines it for maximum
Wan render quality — a cheap grunt-tier call that pays for itself in fewer retakes.
"""

from __future__ import annotations

from .. import log
from ..config import Tier
from ..llm import QwenClient

STAGE = "prompt_optimizer"
_log = log.get("prompt_opt")

_SYS = """\
You are a text-to-video prompt engineer specializing in the Wan video generation model. \
You take raw cinematic shot descriptions and rewrite them for maximum render quality.

Rules for optimized prompts:
- FRONT-LOAD the most important visual element (the model weights early tokens more heavily).
- ONE clear subject per prompt. If there are two characters, describe the PRIMARY one \
in detail and reduce the secondary to spatial context ("another figure in the background").
- CONCRETE over abstract: replace "emotional" with specific visual cues — tears, clenched \
fists, averted gaze. The model renders pixels, not feelings.
- LIGHTING is king: specify direction (rim-lit, top-lit, side-lit), quality (hard/soft), \
and color temperature (warm amber, cool blue). Lighting sells cinematic quality more than \
any other single factor.
- AVOID: rapid cuts, multiple simultaneous actions, text/writing, mirror reflections, \
extreme close-ups of eyes/mouths (common failure modes).
- KEEP the aspect ratio and style tags from the original prompt.
- KEEP the prompt under 200 words — longer prompts degrade Wan output quality.

Return ONLY the refined prompt text. No JSON, no explanation."""


class PromptOptimizer:
    """Rewrites raw video prompts for maximum Wan render quality.

    A cheap grunt-tier LLM call that front-loads key visuals, specifies lighting,
    and avoids known Wan failure modes. Pays for itself in fewer retakes.
    """

    def __init__(self, client: QwenClient):
        self.client = client

    def refine(self, raw_prompt: str, shot_description: str, beat_label: str = "") -> str:
        context = f"Beat: {beat_label}\n" if beat_label else ""
        result = self.client.chat(
            STAGE,
            Tier.GRUNT,
            [
                {"role": "system", "content": _SYS},
                {"role": "user", "content": (
                    f"{context}Shot description: {shot_description}\n\n"
                    f"Raw video prompt:\n{raw_prompt}\n\n"
                    "Rewrite this prompt for maximum Wan render quality."
                )},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        refined = result.strip().strip('"').strip("'")
        _log.info("refined prompt (%d -> %d chars)", len(raw_prompt), len(refined))
        return refined if refined else raw_prompt
