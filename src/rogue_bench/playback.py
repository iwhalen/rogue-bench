"""Per-turn playback log written alongside a game recording.

Captures what the player was thinking and how many actions were queued
on each turn, so replays can re-show the Actions / Reasoning panels
without duplicating the raw keystrokes (those already live in
``game.sav``).
"""

from pydantic import BaseModel


class TurnPlayback(BaseModel):
    """Metadata for a single agent turn."""

    reasoning: str | None = None
    queue_length: int
    byte_length: int


class PlaybackLog(BaseModel):
    """Ordered per-turn playback metadata for one recording."""

    version: int = 1
    turns: list[TurnPlayback] = []
