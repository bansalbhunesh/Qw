"""Shared data structures passed between agents during a production.

These dataclasses define the contract between pipeline stages: the Writer produces
a Script (beats + shots), the Art Director produces a StyleBible, the Cinematographer
fills in clip_path on each Shot, the Critic fills in critic_score, and the Production
aggregates everything into the final deliverable. All are serializable for the manifest.
"""

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
    """A complete screenplay: premise → logline → beat sheet → shot list."""

    premise: str              # the original one-line user premise
    logline: str              # Writer-generated dramatic question summary
    beats: list[Beat]         # structured narrative beats with importance weights
    shots: list[Shot]         # one shot per beat, with video prompts and dialogue


@dataclass
class Production:
    """Top-level container for a single production run's state and outputs."""

    premise: str                       # original user premise
    script: Script | None = None       # populated after the Writer phase
    style: StyleBible | None = None    # populated after the Art Director phase
    final_path: str | None = None      # path to the assembled final cut video
