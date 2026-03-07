"""Abstract base class defining the programmatic interface to a Rogue process."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from rogue_bench.external.screen import ScreenState


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
