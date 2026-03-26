"""Rogue game running inside a Docker container."""

from __future__ import annotations

import subprocess

from rogue_bench.game.base import PipeRogueGame


class DockerRogueGame(PipeRogueGame):
    """Communicate with a Rogue process running in a Docker container.

    Launches ``docker run --rm -i <image>`` and uses the container's
    stdin/stdout as the pipe transport.  A wrapper entrypoint inside the
    image remaps stdin/stdout to the file-descriptor numbers the C++
    binary expects.
    """

    def __init__(
        self,
        docker_image: str,
        args: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._docker_image = docker_image
        self._args = args or []

    def start(self) -> None:
        cmd = [
            "docker",
            "run",
            "--rm",
            "-i",
            self._docker_image,
            *self._args,
        ]
        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                "Docker is not installed or not on PATH. "
                "Install Docker to use --docker-image."
            ) from None

        assert self._process.stdin is not None
        assert self._process.stdout is not None
        self._trogue_fd = self._process.stdin.fileno()
        self._frogue_fd = self._process.stdout.fileno()

    def stop(self) -> None:
        if self._process is not None:
            # Close the subprocess stream objects (they own the FDs).
            if self._process.stdin:
                self._process.stdin.close()
            self._trogue_fd = None
            if self._process.stdout:
                self._process.stdout.close()
            self._frogue_fd = None
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None
