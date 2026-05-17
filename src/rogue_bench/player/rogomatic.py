"""Rogomatic-driven player: proxies bytes between rogue and the 1980s bot."""

from __future__ import annotations

import contextlib
import os
import select
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from rogue_bench.game.docker import DockerRogueGame
from rogue_bench.game.local import LocalRogueGame
from rogue_bench.player.base import PipeBasedPlayer, render_llm_frame

if TYPE_CHECKING:
    from io import StringIO
    from pathlib import Path

    from rich.console import Console

    from rogue_bench.config import RogomaticConfig, Settings
    from rogue_bench.game.base import PipeRogueGame

_ROGOMATIC_LOG_FILES = ("rogomatic.log", "rogomatic.frogue")
_ROGOMATIC_BUG_FIXES = "15"


def _rogomatic_genes_env(genes: list[int] | None) -> str | None:
    """Return the internal GENES value expected by Rog-O-Matic."""
    if genes is None:
        return None
    values = [str(gene) for gene in genes]
    values.append(_ROGOMATIC_BUG_FIXES)
    return " ".join(values)


class RogomaticLauncher(ABC):
    """Starts a ``--rogomatic-player`` subprocess and exposes its pipe FDs."""

    @abstractmethod
    def start(self, game_name: str, seed: int) -> None:
        """Spawn rogomatic and set up the byte-proxy file descriptors."""

    @abstractmethod
    def stop(self) -> None:
        """Terminate rogomatic and release its pipe FDs."""

    @abstractmethod
    def collect_artifacts(self, output_dir: Path) -> None:
        """Copy ``rogomatic.log`` / ``rogomatic.frogue`` into ``output_dir``."""

    @property
    @abstractmethod
    def frogue_write_fd(self) -> int:
        """FD Python writes to to feed rogue's screen into rogomatic."""

    @property
    @abstractmethod
    def trogue_read_fd(self) -> int:
        """FD Python reads rogomatic's keystrokes from."""


class LocalRogomaticLauncher(RogomaticLauncher):
    """Run rogomatic as a local subprocess next to the rogue subprocess."""

    def __init__(
        self,
        rogue_executable: str,
        env: dict[str, str] | None,
        cwd: str,
        fresh_run: bool = False,
    ) -> None:
        self._executable = rogue_executable
        self._env = env
        self._cwd = cwd
        self._fresh_run = fresh_run
        self._process: subprocess.Popen[bytes] | None = None
        self._frogue_w: int | None = None
        self._trogue_r: int | None = None

    def start(self, game_name: str, seed: int) -> None:
        # Rogomatic expects an rlog/ directory in its cwd for its lock file
        # and long-term-memory store; it hangs for 60s in lock_file() if
        # missing.
        rlog_dir = os.path.join(self._cwd, "rlog")
        if self._fresh_run and os.path.isdir(rlog_dir):
            shutil.rmtree(rlog_dir)
        os.makedirs(rlog_dir, exist_ok=True)

        frogue_r, frogue_w = os.pipe()
        trogue_r, trogue_w = os.pipe()
        os.set_inheritable(frogue_r, True)
        os.set_inheritable(trogue_w, True)
        try:
            self._process = subprocess.Popen(
                [
                    self._executable,
                    "--rogomatic-player",
                    "--frogue-fd",
                    str(frogue_r),
                    "--trogue-fd",
                    str(trogue_w),
                    "--seed",
                    str(seed),
                    game_name,
                ],
                env=self._env,
                cwd=self._cwd,
                pass_fds=(frogue_r, trogue_w),
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            for fd in (frogue_r, frogue_w, trogue_r, trogue_w):
                with contextlib.suppress(OSError):
                    os.close(fd)
            raise

        os.close(frogue_r)
        os.close(trogue_w)
        self._frogue_w = frogue_w
        self._trogue_r = trogue_r

    def stop(self) -> None:
        for attr in ("_frogue_w", "_trogue_r"):
            fd = getattr(self, attr)
            if fd is not None:
                with contextlib.suppress(OSError):
                    os.close(fd)
                setattr(self, attr, None)
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None

    def collect_artifacts(self, output_dir: Path) -> None:
        if str(output_dir) == self._cwd:
            return
        for name in _ROGOMATIC_LOG_FILES:
            src = os.path.join(self._cwd, name)
            if os.path.exists(src):
                shutil.copy(src, output_dir / name)

    @property
    def frogue_write_fd(self) -> int:
        assert self._frogue_w is not None
        return self._frogue_w

    @property
    def trogue_read_fd(self) -> int:
        assert self._trogue_r is not None
        return self._trogue_r


class DockerExecRogomaticLauncher(RogomaticLauncher):
    """Run rogomatic via ``docker exec`` inside the rogue container."""

    def __init__(self, container_name: str, env: dict[str, str] | None = None) -> None:
        self._container_name = container_name
        self._env = env or {}
        self._process: subprocess.Popen[bytes] | None = None

    def start(self, game_name: str, seed: int) -> None:
        self._wait_for_container(timeout=10.0)
        cmd = [
            "docker",
            "exec",
            "-i",
        ]
        for key, value in self._env.items():
            cmd.extend(["-e", f"{key}={value}"])
        cmd.extend(
            [
                self._container_name,
                "/app/rogomatic-entrypoint.sh",
                "--seed",
                str(seed),
                game_name,
            ]
        )
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def _wait_for_container(self, timeout: float) -> None:
        """Block until the named container is reported as running.

        ``docker run`` returns before the container is fully registered
        with the daemon, so a naive ``docker exec`` races and fails with
        "No such container". Poll ``docker inspect`` until it succeeds.
        """

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", self._container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip() == b"true":
                return
            time.sleep(0.05)
        raise RuntimeError(
            f"Timed out waiting for container {self._container_name} to start"
        )

    def stop(self) -> None:
        if self._process is None:
            return
        if self._process.stdin is not None:
            with contextlib.suppress(OSError):
                self._process.stdin.close()
        if self._process.stdout is not None:
            with contextlib.suppress(OSError):
                self._process.stdout.close()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
        self._process = None

    def collect_artifacts(self, output_dir: Path) -> None:
        for name in _ROGOMATIC_LOG_FILES:
            subprocess.run(
                [
                    "docker",
                    "cp",
                    f"{self._container_name}:/app/rogue/{name}",
                    str(output_dir / name),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )

    @property
    def frogue_write_fd(self) -> int:
        assert self._process is not None and self._process.stdin is not None
        return self._process.stdin.fileno()

    @property
    def trogue_read_fd(self) -> int:
        assert self._process is not None and self._process.stdout is not None
        return self._process.stdout.fileno()


class RogomaticPlayer(PipeBasedPlayer):
    """Drive a Rogue game by proxying bytes to/from a rogomatic subprocess."""

    def __init__(
        self,
        settings: Settings,
        rogomatic_config: RogomaticConfig,
        gene_seed: int,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._rogomatic_config = rogomatic_config
        self._gene_seed = gene_seed
        self._launcher: RogomaticLauncher | None = None

    @property
    def config(self) -> RogomaticConfig:
        return self._rogomatic_config

    def _build_launcher(self, game: PipeRogueGame) -> RogomaticLauncher:
        if isinstance(game, DockerRogueGame):
            name = game.container_name
            if name is None:
                raise RuntimeError("Docker container not started before rogomatic")
            return DockerExecRogomaticLauncher(
                name,
                env=self._rogomatic_env(),
            )
        if isinstance(game, LocalRogueGame):
            rogue_path = self._settings.rogue_path.resolve()
            rogue_dir = str(rogue_path.parent)
            env = os.environ.copy()
            env["LD_LIBRARY_PATH"] = rogue_dir
            env.pop("GENES", None)
            env.pop("NOLTM", None)
            env.update(self._rogomatic_env())
            # cwd must be rogue_dir: RunGame dlopens "./lib-rogomatic-player.so"
            # as a relative path, so the .so must be in the process's cwd.
            return LocalRogomaticLauncher(
                rogue_executable=str(rogue_path),
                env=env,
                cwd=rogue_dir,
                fresh_run=self._rogomatic_config.fresh_run,
            )
        raise TypeError(f"Unsupported game backend for rogomatic: {type(game)}")

    def _rogomatic_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        rogomatic_genes = _rogomatic_genes_env(self._rogomatic_config.genes)
        if rogomatic_genes is not None:
            env["GENES"] = rogomatic_genes
        if not self._rogomatic_config.use_ltm:
            env["NOLTM"] = "1"
        return env

    def collect_artifacts(self, output_dir: Path) -> None:
        if self._launcher is not None:
            self._launcher.collect_artifacts(output_dir)

    def _io_loop(
        self,
        game: PipeRogueGame,
        fd_in: int,
        stdout_fd: int,
        console: Console,
        buf: StringIO,
    ) -> None:
        # Start rogomatic *before* draining any bytes so rogomatic sees
        # the full VT100 stream from rogue, byte-for-byte identical to
        # what our parser receives.
        self._launcher = self._build_launcher(game)
        self._launcher.start(game_name="Unix Rogue 5.4.2", seed=self._gene_seed)
        frogue_w = self._launcher.frogue_write_fd
        trogue_r = self._launcher.trogue_read_fd

        try:
            while game.is_running():
                if self._check_ctrl_c(fd_in):
                    self.request_stop("ctrl_c")
                    break
                if self.stop_reason is not None:
                    break

                rlist, _, _ = select.select([game.output_fd, trogue_r], [], [], 0.1)

                if game.output_fd in rlist:
                    if not self._forward_to_rogomatic(game, frogue_w):
                        break
                    self._redraw(game, stdout_fd, console, buf)

                if trogue_r in rlist:
                    if not self._forward_to_game(trogue_r, game):
                        break
                    self._redraw(game, stdout_fd, console, buf)
        finally:
            os.write(stdout_fd, b"\x1b[2J\x1b[H\x1b[?25h")
            if self._launcher is not None:
                self._launcher.stop()

    @staticmethod
    def _forward_to_rogomatic(game: PipeRogueGame, frogue_w: int) -> bool:
        """Read from rogue, update the parser, forward to rogomatic."""
        try:
            data = os.read(game.output_fd, 4096)
        except OSError:
            return False
        if not data:
            return False
        game.feed(data)
        try:
            os.write(frogue_w, data)
        except (OSError, BrokenPipeError):
            return False
        return True

    @staticmethod
    def _forward_to_game(trogue_r: int, game: PipeRogueGame) -> bool:
        """Read keystrokes from rogomatic, deliver to rogue (and keylog)."""
        try:
            data = os.read(trogue_r, 4096)
        except OSError:
            return False
        if not data:
            return False
        try:
            game.send_raw(data)
        except (OSError, BrokenPipeError):
            return False
        return True

    @staticmethod
    def _redraw(
        game: PipeRogueGame,
        stdout_fd: int,
        console: Console,
        buf: StringIO,
    ) -> None:
        frame = render_llm_frame(
            console,
            buf,
            game.screen.characters,
        )
        os.write(stdout_fd, frame)
