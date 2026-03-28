"""Rogue game process managed via the rogomatic pipe protocol."""

import contextlib
import os
import subprocess

from rogue_bench.game.base import PipeRogueGame


class LocalRogueGame(PipeRogueGame):
    """Spawn and communicate with a local Rogue process over pipes.

    Creates two pipe pairs for bidirectional communication:

    * **trogue** (to-rogue): player commands -> game
    * **frogue** (from-rogue): game screen (VT100) -> player
    """

    def __init__(
        self,
        rogue_executable: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self._executable = rogue_executable
        self._args = args or []
        self._env = env

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
