import contextlib
import os
from collections.abc import Generator
from dataclasses import dataclass

import pytest

from rogue_bench.game.base import PipeRogueGame
from rogue_bench.game.screen import ScreenState

VALID_STATUS_LINE = "Level: 3  Gold: 250  Hp: 8(14)  Str: 15(16)  Arm: -1  Exp: 4/123"


class DummyPipeRogueGame(PipeRogueGame):
    """Concrete test double exposing public setup helpers for pipe-backed tests."""

    def start(self) -> None:
        return None

    def stop(self) -> None:
        self.close_fds()

    def attach_output_fd(self, fd: int) -> None:
        self._frogue_fd = fd

    def attach_input_fd(self, fd: int) -> None:
        self._trogue_fd = fd

    def close_fds(self) -> None:
        for attr in ("_frogue_fd", "_trogue_fd"):
            fd = getattr(self, attr)
            if fd is not None:
                with contextlib.suppress(OSError):
                    os.close(fd)
                setattr(self, attr, None)


@dataclass
class PipeGameHarness:
    game: DummyPipeRogueGame
    read_fd: int


@pytest.fixture
def valid_status_line() -> str:
    return VALID_STATUS_LINE


@pytest.fixture
def populated_screen(valid_status_line: str) -> ScreenState:
    screen = ScreenState.empty()
    message = "You see a scroll here."
    screen.characters[0][: len(message)] = list(message)
    screen.characters[ScreenState.STATUS_ROW][: len(valid_status_line)] = list(
        valid_status_line
    )
    return screen


@pytest.fixture
def dummy_game() -> DummyPipeRogueGame:
    return DummyPipeRogueGame()


@pytest.fixture
def pipe_game() -> Generator[PipeGameHarness]:
    read_fd, write_fd = os.pipe()
    game = DummyPipeRogueGame()
    game.attach_input_fd(write_fd)
    try:
        yield PipeGameHarness(game=game, read_fd=read_fd)
    finally:
        game.close_fds()
        with contextlib.suppress(OSError):
            os.close(read_fd)


def write_screen_line(
    screen: ScreenState,
    row: int,
    text: str,
    *,
    col: int = 0,
) -> None:
    screen.characters[row][col : col + len(text)] = list(text)
