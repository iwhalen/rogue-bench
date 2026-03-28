"""Rogue game running inside a Docker container."""

import atexit
import contextlib
import subprocess
import uuid

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
        self._container_name: str | None = None

    def start(self) -> None:
        self._container_name = f"rogue-bench-{uuid.uuid4().hex[:12]}"
        cmd = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--name",
            self._container_name,
            self._docker_image,
            *self._args,
        ]
        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            self._container_name = None
            raise FileNotFoundError(
                "Docker is not installed or not on PATH. "
                "Install Docker to use --docker-image."
            ) from None

        atexit.register(self._force_remove_container)

        assert self._process.stdin is not None
        assert self._process.stdout is not None
        self._trogue_fd = self._process.stdin.fileno()
        self._frogue_fd = self._process.stdout.fileno()

    def stop(self) -> None:
        try:
            if self._process is not None:
                # Close the subprocess stream objects (they own the FDs).
                if self._process.stdin:
                    self._process.stdin.close()
                self._trogue_fd = None
                if self._process.stdout:
                    self._process.stdout.close()
                self._frogue_fd = None
                # Kill immediately — _force_remove_container() handles
                # the actual container cleanup, so there is no need to
                # wait for a graceful SIGTERM shutdown of `docker run`.
                self._process.kill()
                self._process.wait()
                self._process = None
        finally:
            self._force_remove_container()

    def _force_remove_container(self) -> None:
        """Force-remove the Docker container if it is still running.

        Runs in its own session so it is unaffected by signals sent to
        our process group.  Also registered as an ``atexit`` handler so
        the container is cleaned up even if ``stop()`` is never called.
        """
        if self._container_name is None:
            return
        name = self._container_name
        self._container_name = None
        atexit.unregister(self._force_remove_container)
        with contextlib.suppress(Exception):
            subprocess.run(
                ["docker", "rm", "-f", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                start_new_session=True,
            )
