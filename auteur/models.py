"""Shared data structures passed between agents during a production."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Character:
    name: str
    description: str          # canonical look, kept verbatim across shots for consistency
    voice: str = "neutral"   # TTS voice id / persona


@dataclass
class StyleBible:
    """The visual contract every shot must honour. Generated once, cached, reused."""

    look: str                # e.g. "muted teal grade, 35mm, shallow depth of field"
    palette: str = ""        # e.g. "slate blue, warm amber, deep charcoal"
    characters: list[Character] = field(default_factory=list)
    reference_image_url: str | None = None  # OSS URL of a key-frame anchor, if any


@dataclass
class Beat:
    """One narrative beat from the beat sheet."""

    index: int
    label: str               # e.g. "Hook", "Turn", "Button"
    summary: str
    importance: float        # 0..1 — drives retake priority (the hook earns reshoots)
    tone: str = ""           # emotional register (tense|melancholy|tender|...) — drives the score


@dataclass
class Shot:
    index: int
    beat_index: int
    description: str          # what happens on screen
    dialogue: str            # spoken line(s) for this shot, may be empty
    video_prompt: str        # the prompt handed to Wan
    importance: float        # inherited from the beat
    # filled in during production:
    clip_path: str | None = None
    critic_score: float | None = None
    retaken: bool = False


@dataclass
class Script:
    premise: str
    logline: str
    beats: list[Beat]
    shots: list[Shot]


@dataclass
class Production:
    premise: str
    script: Script | None = None
    style: StyleBible | None = None
    final_path: str | None = None
