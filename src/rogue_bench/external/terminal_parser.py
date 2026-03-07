"""Stateful VT100 escape-sequence parser.

Inspired by Rogomatic's ``getroguetoken()`` in *getroguetoken.c*.
Processes a raw byte stream from a Rogue process and maintains an
internal :class:`ScreenState` that mirrors the terminal display.
"""

from __future__ import annotations

import copy
from enum import Enum, auto

from rogue_bench.external.screen import ScreenState


class _State(Enum):
    GROUND = auto()
    ESC = auto()
    CSI = auto()


class TerminalParser:
    """Incremental VT100 parser that builds up a :class:`ScreenState`."""

    def __init__(self) -> None:
        self._screen = ScreenState.empty()
        self._state = _State.GROUND
        self._params: str = ""

    def feed(self, data: bytes) -> None:
        """Process *data* (raw bytes from the Rogue process).

        The internal screen state is updated in-place.  Call
        :pyattr:`screen` afterwards to obtain a snapshot.
        """
        for byte in data:
            ch = chr(byte)
            if self._state is _State.GROUND:
                self._ground(ch)
            elif self._state is _State.ESC:
                self._esc(ch)
            elif self._state is _State.CSI:
                self._csi(ch)

    @property
    def screen(self) -> ScreenState:
        """Return a deep copy of the current screen state."""
        return copy.deepcopy(self._screen)

    # -- private dispatch ----------------------------------------------------

    def _ground(self, ch: str) -> None:
        if ch == "\x1b":
            self._state = _State.ESC
            self._params = ""
        elif ch == "\x0c":  # Ctrl-L  →  clear screen
            self._clear_screen()
        elif ch == "\n":  # LF
            self._line_feed()
        elif ch == "\r":  # CR
            self._screen.cursor_col = 0
        elif ch == "\x08":  # BS
            self._screen.cursor_col = max(0, self._screen.cursor_col - 1)
        elif ch >= " " and ch != "\x7f":
            self._put_char(ch)

    def _esc(self, ch: str) -> None:
        if ch == "[":
            self._state = _State.CSI
            self._params = ""
        else:
            self._state = _State.GROUND

    def _csi(self, ch: str) -> None:
        if ch.isdigit() or ch == ";":
            self._params += ch
            return

        self._state = _State.GROUND

        if ch == "H" or ch == "f":
            self._cursor_move()
        elif ch == "K":
            self._clear_to_eol()
        elif ch == "J":
            self._clear_to_eos()
        elif ch == "m":
            pass  # standout on/off - ignored for now

    # -- terminal operations -------------------------------------------------

    def _put_char(self, ch: str) -> None:
        s = self._screen
        if 0 <= s.cursor_row < s.ROWS and 0 <= s.cursor_col < s.COLS:
            s.characters[s.cursor_row][s.cursor_col] = ch
            s.cursor_col += 1
            if s.cursor_col >= s.COLS:
                s.cursor_col = 0
                s.cursor_row = min(s.cursor_row + 1, s.ROWS - 1)

    def _clear_screen(self) -> None:
        s = self._screen
        for r in range(s.ROWS):
            for c in range(s.COLS):
                s.characters[r][c] = " "
        s.cursor_row = 0
        s.cursor_col = 0

    def _line_feed(self) -> None:
        s = self._screen
        if s.cursor_row < s.ROWS - 1:
            s.cursor_row += 1

    def _cursor_move(self) -> None:
        """Handle ``ESC[row;colH`` (1-based to 0-based)."""
        parts = self._params.split(";") if self._params else []
        row = (int(parts[0]) - 1) if len(parts) >= 1 and parts[0] else 0
        col = (int(parts[1]) - 1) if len(parts) >= 2 and parts[1] else 0
        s = self._screen
        s.cursor_row = max(0, min(row, s.ROWS - 1))
        s.cursor_col = max(0, min(col, s.COLS - 1))

    def _clear_to_eol(self) -> None:
        s = self._screen
        for c in range(s.cursor_col, s.COLS):
            s.characters[s.cursor_row][c] = " "

    def _clear_to_eos(self) -> None:
        s = self._screen
        for c in range(s.cursor_col, s.COLS):
            s.characters[s.cursor_row][c] = " "
        for r in range(s.cursor_row + 1, s.ROWS):
            for c in range(s.COLS):
                s.characters[r][c] = " "
