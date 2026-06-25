"""Qwen-VL-as-judge rubric for scoring a finished short.

The same rubric scores both the naive baseline and Auteur, so the comparison is apples-to-apples.
We sample frames from the final cut and ask Qwen-VL to grade four dimensions.
"""

from __future__ import annotations

RUBRIC_SYS = (
    "You are an impartial film judge for a short-drama competition. Grade the submission on a "
    "0-10 scale for each dimension. Be consistent and strict. Return ONLY JSON: "
    '{"narrative_coherence": n, "visual_quality": n, "character_consistency": n, '
    '"emotional_impact": n, "overall": n, "notes": "one sentence"}'
)

DIMENSIONS = [
    "narrative_coherence",
    "visual_quality",
    "character_consistency",
    "emotional_impact",
    "overall",
]


def quality_per_token(overall: float, tokens_used: int) -> float:
    """The headline efficiency metric: quality delivered per 1k tokens."""
    if tokens_used <= 0:
        return 0.0
    return overall / (tokens_used / 1000.0)
