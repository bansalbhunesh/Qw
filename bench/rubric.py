"""Qwen-VL-as-judge rubric for scoring a finished short.

The same rubric scores both the naive baseline and Auteur, so the comparison is apples-to-apples.
We sample frames from the final cut and ask Qwen-VL to grade four dimensions.
"""

from __future__ import annotations

RUBRIC_SYS = (
    "You are an impartial film judge for a short-drama competition. Grade the submission on a "
    "0-10 scale for each dimension. Be consistent and strict.\n\n"
    "Dimensions:\n"
    "- narrative_coherence: Does the story have a clear arc? Hook, escalation, payoff?\n"
    "- visual_quality: Cinematic framing, lighting, composition, visual appeal?\n"
    "- character_consistency: Do characters look and feel consistent across shots?\n"
    "- emotional_impact: Does the film make you FEEL something? Surprise, tension, tenderness?\n"
    "- shot_flow: Do the shots feel like they belong in the same film? Smooth transitions?\n"
    "- overall: Your overall impression as a competition judge.\n\n"
    "Return ONLY JSON: "
    '{"narrative_coherence": n, "visual_quality": n, "character_consistency": n, '
    '"emotional_impact": n, "shot_flow": n, "overall": n, "notes": "one sentence"}'
)

DIMENSIONS = [
    "narrative_coherence",
    "visual_quality",
    "character_consistency",
    "emotional_impact",
    "shot_flow",
    "overall",
]


def quality_per_token(overall: float, tokens_used: int) -> float:
    """The headline efficiency metric: quality delivered per 1k tokens."""
    if tokens_used <= 0:
        return 0.0
    return overall / (tokens_used / 1000.0)
