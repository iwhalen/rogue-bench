"""Start and orchestrate a game of Rogue."""

import os

from rogue_bench.config import PlayerType, PlaySettings
from rogue_bench.external.game import RogueGame
from rogue_bench.player.human import HumanPlayer
from rogue_bench.player.llm import LLMPlayer


def play(config: PlaySettings) -> None:
    """Play a game of Rogue given the config."""
    rogue_path = config.rogue_path.resolve()

    if not rogue_path.exists():
        raise FileNotFoundError(
            f"Rogue executable not found at {rogue_path}. "
            "Run 'make build' first to compile the rogue binary."
        )

    if config.player == PlayerType.HUMAN:
        player = HumanPlayer()
    elif config.player == PlayerType.LLM:
        player = LLMPlayer(
            model=config.model,
            max_history=config.max_history,
            action_delay=config.action_delay,
        )
    else:
        raise NotImplementedError(f"Invalid player type: {config.player}")

    rogue_path = config.rogue_path.resolve()
    rogue_dir = str(rogue_path.parent)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = rogue_dir

    original_cwd = os.getcwd()
    os.chdir(rogue_dir)
    try:
        with RogueGame(
            rogue_executable=str(rogue_path),
            args=[config.rogue_version],
            env=env,
        ) as game:
            player.play(game)
    finally:
        os.chdir(original_cwd)
