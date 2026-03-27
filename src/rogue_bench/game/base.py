"""Abstract base classes defining the programmatic interface to a Rogue process."""

from __future__ import annotations

import os
import select
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Self

from rogue_bench.game.terminal_parser import TerminalParser

if TYPE_CHECKING:
    import subprocess

    from rogue_bench.game.screen import ScreenState, StatusLine


class RogueInterface(ABC):
    """Contract for sending input to and reading output from a Rogue game.

    Inspired by Rogomatic's I/O layer:
    * ``send_keypress`` mirrors ``sendcnow()`` (io.c)
    * ``read_screen``   mirrors ``getrogue()``  (io.c)
    """

    @abstractmethod
    def start(self) -> None:
        """Start (or connect to) the Rogue game session."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the Rogue game session and release resources."""

    @abstractmethod
    def send_keypress(self, key: str) -> None:
        """Send a single keypress to the Rogue process."""

    @abstractmethod
    def read_screen(self) -> ScreenState:
        """Read and return the current screen state from Rogue.

        Implementations may block briefly while waiting for output to
        arrive after a command.
        """

    @abstractmethod
    def is_running(self) -> bool:
        """Return True if the Rogue process is still alive."""

    def send_command(self, command: str) -> None:
        """Send a multi-character command string, one keypress at a time."""
        for key in command:
            self.send_keypress(key)

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.stop()


class PipeRogueGame(RogueInterface):
    """Shared pipe-based I/O for communicating with a Rogue process.

    Subclasses implement :meth:`start` and :meth:`stop` to control how
    the process is launched (local subprocess vs. Docker container).
    All pipe reading/writing, VT100 parsing, and keylog tracking live
    here.
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None
        self._frogue_fd: int | None = None
        self._trogue_fd: int | None = None
        self._parser = TerminalParser()
        self._keylog = bytearray()
        self._last_status: StatusLine | None = None

    @property
    def output_fd(self) -> int:
        """File descriptor for the frogue (game -> player) read end."""
        if self._frogue_fd is None:
            raise RuntimeError("Rogue process is not running")
        return self._frogue_fd

    @property
    def input_fd(self) -> int:
        """File descriptor for the trogue (player -> game) write end."""
        if self._trogue_fd is None:
            raise RuntimeError("Rogue process is not running")
        return self._trogue_fd

    @abstractmethod
    def start(self) -> None:
        """Start (or connect to) the Rogue game session."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the Rogue game session and release resources."""

    def send_keypress(self, key: str) -> None:
        self.send_raw(key.encode("latin-1"))

    def send_raw(self, data: bytes) -> None:
        """Send raw bytes to the game and record them in the keylog."""
        if self._trogue_fd is None:
            raise RuntimeError("Rogue process is not running")
        os.write(self._trogue_fd, data)
        self._keylog.extend(data)

    @property
    def keylog(self) -> bytes:
        """All input bytes sent to the game during this session."""
        return bytes(self._keylog)

    def read_screen(self) -> ScreenState:
        if self._frogue_fd is None:
            raise RuntimeError("Rogue process is not running")
        self._drain()
        return self._parser.screen

    @property
    def screen(self) -> ScreenState:
        """Current screen state without reading new data from the pipe."""
        return self._parser.screen

    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    @property
    def last_status(self) -> StatusLine | None:
        """Last successfully parsed status bar, surviving screen overwrites."""
        return self._last_status

    def feed(self, data: bytes) -> None:
        """Forward raw bytes to the internal VT100 parser.

        Use this when consuming output from :attr:`output_fd` directly
        (e.g. for terminal display) so that :meth:`read_screen` stays
        in sync.
        """
        self._parser.feed(data)
        self._update_status()

    def _update_status(self) -> None:
        """Cache the latest valid status bar."""
        status = self._parser.screen.status
        if status is not None:
            self._last_status = status

    def _drain(self, timeout: float = 0.05) -> None:
        """Read all currently-available bytes from the frogue pipe."""
        assert self._frogue_fd is not None
        while True:
            rlist, _, _ = select.select([self._frogue_fd], [], [], timeout)
            if not rlist:
                break
            try:
                data = os.read(self._frogue_fd, 4096)
            except OSError:
                break
            if not data:
                break
            self._parser.feed(data)
        self._update_status()
