"""Data models for representing the Rogue game screen state."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar

_STATUS_RE = re.compile(
    r"Level:\s*(\d+)\s+"
    r"Gold:\s*(\d+)\s+"
    r"Hp:\s*(\d+)\((\d+)\)\s+"
    r"Str:\s*(\d+)\((\d+)\)\s+"
    r"Arm:\s*(-?\d+)\s+"
    r"Exp:\s*(\d+)/(\d+)"
)


@dataclass(frozen=True)
class StatusLine:
    """Parsed Rogue status bar (row 23). Matches Rogue 5.3+ format."""

    dungeon_level: int
    gold: int
    current_hp: int
    max_hp: int
    current_strength: int
    max_strength: int
    armor_class: int
    experience_level: int
    experience_points: int

    @classmethod
    def parse(cls, raw_line: str) -> StatusLine | None:
        """Parse a status line string.

        Expected format (Rogue 5.3+):
            Level: 1  Gold: 0  Hp: 12(12)  Str: 16(16)  Arm: 4  Exp: 1/0

        Returns None when the line cannot be parsed.
        """
        m = _STATUS_RE.search(raw_line)
        if m is None:
            return None
        return cls(
            dungeon_level=int(m.group(1)),
            gold=int(m.group(2)),
            current_hp=int(m.group(3)),
            max_hp=int(m.group(4)),
            current_strength=int(m.group(5)),
            max_strength=int(m.group(6)),
            armor_class=int(m.group(7)),
            experience_level=int(m.group(8)),
            experience_points=int(m.group(9)),
        )


def _empty_grid(rows: int, cols: int) -> list[list[str]]:
    return [[" "] * cols for _ in range(rows)]


@dataclass
class ScreenState:
    """24x80 character grid mirroring the Rogue terminal display.

    Row 0 is the message line, rows 1-22 are the dungeon map,
    and row 23 is the status bar.
    """

    ROWS: ClassVar[int] = 24
    COLS: ClassVar[int] = 80
    STATUS_ROW: ClassVar[int] = 23

    characters: list[list[str]] = field(default_factory=lambda: _empty_grid(24, 80))
    cursor_row: int = 0
    cursor_col: int = 0

    @staticmethod
    def empty() -> ScreenState:
        """Create a blank 24x80 screen filled with spaces."""
        return ScreenState()

    @property
    def status(self) -> StatusLine | None:
        """Parse the status bar from row 23."""
        raw = "".join(self.characters[self.STATUS_ROW])
        return StatusLine.parse(raw)

    @property
    def message_line(self) -> str:
        """Return the message area (row 0) as a string, trailing spaces stripped."""
        return "".join(self.characters[0]).rstrip()

    def find_player(self) -> tuple[int, int] | None:
        """Locate the player '@' in the map area (rows 1-22).

        Returns (row, col) or None if not found.
        """
        for r in range(1, self.STATUS_ROW):
            for c in range(self.COLS):
                if self.characters[r][c] == "@":
                    return (r, c)
        return None

    def dump(self) -> str:
        """Serialize the full screen as a newline-delimited string.

        Each of the 24 rows is joined into a single line, and lines are
        joined with ``\\n``.  Suitable for logging or sending to an LLM.
        """
        return "\n".join("".join(row) for row in self.characters)
