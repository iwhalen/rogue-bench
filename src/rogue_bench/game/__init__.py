"""Module for communicating with a Rogue game process."""

from rogue_bench.game.base import PipeRogueGame, RogueInterface
from rogue_bench.game.docker import DockerRogueGame
from rogue_bench.game.local import LocalRogueGame
from rogue_bench.game.screen import ScreenState, StatusLine
from rogue_bench.game.terminal_parser import TerminalParser

__all__ = [
    "DockerRogueGame",
    "LocalRogueGame",
    "PipeRogueGame",
    "RogueInterface",
    "ScreenState",
    "StatusLine",
    "TerminalParser",
]
