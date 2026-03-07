"""Human player that relays terminal I/O to and from a Rogue game."""

from __future__ import annotations

import os
import select
from typing import TYPE_CHECKING

from rogue_bench.player.base import PipeBasedPlayer

if TYPE_CHECKING:
    from io import StringIO

    from rich.console import Console

    from rogue_bench.external.game import RogueGame

_ESC = 0x1B

_ANSI_TO_ROGUE: dict[bytes, bytes] = {
    b"\x1b[A": b"k",  # Up
    b"\x1b[B": b"j",  # Down
    b"\x1b[C": b"l",  # Right
    b"\x1b[D": b"h",  # Left
    b"\x1bOA": b"k",  # Up    (application mode)
    b"\x1bOB": b"j",  # Down  (application mode)
    b"\x1bOC": b"l",  # Right (application mode)
    b"\x1bOD": b"h",  # Left  (application mode)
    b"\x1b[H": b"y",  # Home  (xterm)
    b"\x1b[F": b"b",  # End   (xterm)
    b"\x1bOH": b"y",  # Home  (application mode)
    b"\x1bOF": b"b",  # End   (application mode)
    b"\x1b[1~": b"y",  # Home  (vt220)
    b"\x1b[4~": b"b",  # End   (vt220)
    b"\x1b[5~": b"u",  # Page Up
    b"\x1b[6~": b"n",  # Page Down
}

_MAX_SEQ_LEN = max(len(s) for s in _ANSI_TO_ROGUE)


def _translate_keys(data: bytes) -> bytes:
    """Replace ANSI arrow/nav escape sequences with rogue vi-keys."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        if data[i] == _ESC and i + 1 < n:
            matched = False
            for length in range(min(_MAX_SEQ_LEN, n - i), 1, -1):
                seq = data[i : i + length]
                replacement = _ANSI_TO_ROGUE.get(seq)
                if replacement is not None:
                    out.extend(replacement)
                    i += length
                    matched = True
                    break
            if not matched:
                out.append(data[i])
                i += 1
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


class HumanPlayer(PipeBasedPlayer):
    """Interactive terminal player with rich display.

    Puts the terminal in raw mode, relays keystrokes to the game,
    and renders the parsed game screen inside bordered panels using
    the ``rich`` library.
    """

    def _io_loop(
        self,
        game: RogueGame,
        fd_in: int,
        stdout_fd: int,
        console: Console,
        buf: StringIO,
    ) -> None:
        """Bidirectional relay between the human's terminal and Rogue."""
        frogue = game.output_fd
        trogue = game.input_fd

        self._redraw(game, stdout_fd, console, buf)

        try:
            while game.is_running():
                rlist, _, _ = select.select([frogue, fd_in], [], [], 0.1)
                if not rlist:
                    continue

                if frogue in rlist:
                    if not self._drain_game_output(game):
                        break
                    self._redraw(game, stdout_fd, console, buf)

                if fd_in in rlist:
                    data = os.read(fd_in, 1024)
                    if not data or b"\x03" in data:
                        break
                    os.write(trogue, _translate_keys(data))
        except KeyboardInterrupt:
            pass
        finally:
            os.write(stdout_fd, b"\x1b[2J\x1b[H\x1b[?25h")
