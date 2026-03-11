"""Rogue game process managed via the rogomatic pipe protocol."""

from __future__ import annotations

import contextlib
import os
import select
import subprocess
from typing import TYPE_CHECKING

from rogue_bench.external.base import RogueInterface
from rogue_bench.external.screen import StatusLine
from rogue_bench.external.terminal_parser import TerminalParser

if TYPE_CHECKING:
    from rogue_bench.external.screen import ScreenState


class RogueGame(RogueInterface):
    """Spawn and communicate with a Rogue process over pipes.

    Creates two pipe pairs for bidirectional communication:

    * **trogue** (to-rogue): player commands -> game
    * **frogue** (from-rogue): game screen (VT100) -> player

    The game outputs VT100 escape sequences through the frogue pipe,
    which are parsed by a :class:`TerminalParser` so callers can inspect
    :meth:`read_screen` at any time.
    """

    def __init__(
        self,
        rogue_executable: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._executable = rogue_executable
        self._args = args or []
        self._env = env
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

    def start(self) -> None:
        trogue_r, trogue_w = os.pipe()
        frogue_r, frogue_w = os.pipe()

        os.set_inheritable(trogue_r, True)
        os.set_inheritable(frogue_w, True)

        try:
            self._process = subprocess.Popen(
                [
                    self._executable,
                    *self._args,
                    "--pipe-io",
                    "--trogue-fd",
                    str(trogue_r),
                    "--frogue-fd",
                    str(frogue_w),
                ],
                env=self._env,
                pass_fds=(trogue_r, frogue_w),
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            for fd in (trogue_r, trogue_w, frogue_r, frogue_w):
                os.close(fd)
            raise

        os.close(trogue_r)
        os.close(frogue_w)

        self._frogue_fd = frogue_r
        self._trogue_fd = trogue_w

    def stop(self) -> None:
        # Close pipe fds first so the game process won't block on pipe
        # writes (e.g. in its auto_save/save_file signal handler) after
        # we send SIGTERM.  With the read end closed, writes fail with
        # EPIPE instead of blocking on a full buffer.
        for fd_attr in ("_frogue_fd", "_trogue_fd"):
            fd = getattr(self, fd_attr)
            if fd is not None:
                with contextlib.suppress(OSError):
                    os.close(fd)
                setattr(self, fd_attr, None)
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None

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
