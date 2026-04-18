"""Start and orchestrate a game of Rogue."""

import json
import os
import random
import struct
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from rogue_bench.agent.base import LLMAgentConfig
from rogue_bench.agent.naive import NaiveAgent
from rogue_bench.config import ROGUE_VERSION, PlayerType, Settings
from rogue_bench.game.base import PipeRogueGame
from rogue_bench.game.docker import DockerRogueGame
from rogue_bench.game.local import LocalRogueGame
from rogue_bench.player.agent import AgentPlayer
from rogue_bench.player.base import PipeBasedPlayer
from rogue_bench.player.human import HumanPlayer

# Environment key-value pairs matching C++ Environment::SetRogomaticValues().
_ROGOMATIC_ENV: dict[str, str] = {
    "prompt_for_name": "false",
    "prompt_for_help": "true",
    "unix_output": "true",
    "name": "rogomatic",
    "fruit": "apricot",
    "terse": "true",
    "jump": "true",
    "seefloor": "true",
    "flush": "false",
    "askme": "false",
    "passgo": "false",
    "step": "true",
    "inven": "slow",
    "menu": "false",
}


def play(config: Settings) -> None:
    """Play a game of Rogue given the config."""
    if config.player == PlayerType.HUMAN:
        player = HumanPlayer()
    elif config.player == PlayerType.LLM:
        agent = NaiveAgent(
            LLMAgentConfig(
                model=config.model,
                max_history=config.max_history,
            )
        )
        player = AgentPlayer(agent, action_delay=config.action_delay)
    else:
        raise NotImplementedError(f"Invalid player type: {config.player}")

    seed = config.seed if config.seed is not None else random.randint(0, 2**31 - 1)
    args = [ROGUE_VERSION, "--seed", str(seed)]

    resolved_dir = None
    if config.output_path:
        resolved_dir = _resolve_output_dir(config).resolve()
        resolved_dir.mkdir(parents=True, exist_ok=True)

    game = _create_game(config, args)

    try:
        with game:
            player.play(game)
            game.drain_remaining()
    finally:
        if resolved_dir:
            _write_save_file(
                resolved_dir / "game.sav",
                ROGUE_VERSION,
                seed,
                game.keylog,
            )
            _write_metadata(resolved_dir, config, seed)
            _write_statistics(resolved_dir, game, player)
            _write_playback(resolved_dir, player)


def _create_game(
    config: Settings,
    args: list[str],
) -> PipeRogueGame:
    """Instantiate the right game backend based on config."""
    if config.docker_image:
        return DockerRogueGame(
            docker_image=config.docker_image,
            args=args,
        )

    rogue_path = config.rogue_path.resolve()
    if not rogue_path.exists():
        raise FileNotFoundError(
            f"Rogue executable not found at {rogue_path}. "
            "Run 'make build' first to compile the rogue binary."
        )
    rogue_dir = str(rogue_path.parent)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = rogue_dir
    return LocalRogueGame(
        rogue_executable=str(rogue_path),
        args=args,
        env=env,
        cwd=rogue_dir,
    )


def _resolve_output_dir(config: Settings) -> Path:
    """Resolve the output directory, optionally appending a timestamp."""
    assert config.output_path is not None
    base = config.output_path
    if config.versioned:
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H.%M.%S.%f")[:-3] + "Z"
        return base / ts
    return base


def _write_save_file(path: Path, game_name: str, seed: int, keylog: bytes) -> None:
    """Write a game recording in Rogue Collection save format."""
    game_env = {**_ROGOMATIC_ENV, "seed": str(seed)}

    with open(path, "wb") as f:
        # Version (uint8) — matches SDL/QML kSaveVersion = 2
        f.write(struct.pack("B", 2))
        # Restore count (uint16 LE)
        f.write(struct.pack("<H", 0))
        # Game name (ShortString: uint8 length + bytes)
        _write_short_string(f, game_name)
        # Environment (uint16 LE count + ShortString pairs)
        f.write(struct.pack("<H", len(game_env)))
        for key, value in game_env.items():
            _write_short_string(f, key)
            _write_short_string(f, value)
        # Raw keylog
        f.write(keylog)


def _write_short_string(f: object, s: str) -> None:
    """Write a Rogue Collection ShortString (1-byte length prefix + data)."""
    encoded = s.encode("ascii")
    f.write(struct.pack("B", len(encoded)))  # type: ignore[union-attr]
    f.write(encoded)  # type: ignore[union-attr]


def _write_metadata(output_dir: Path, config: Settings, seed: int) -> None:
    """Write metadata.json for the game recording."""
    metadata = {
        "timestamp": datetime.now(UTC).isoformat(),
        "seed": seed,
        "rogue_version": ROGUE_VERSION,
        "player": str(config.player),
        "model": config.model,
        "args": sys.argv,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))


def _write_playback(output_dir: Path, player: PipeBasedPlayer) -> None:
    """Write playback.json if the player tracked per-turn reasoning/queue info."""
    log = player.playback_log()
    if log is None or not log.turns:
        return
    (output_dir / "playback.json").write_text(
        json.dumps(log.model_dump(), indent=2)
    )


def _write_statistics(
    output_dir: Path,
    game: PipeRogueGame,
    player: PipeBasedPlayer | None = None,
) -> None:
    """Write statistics.json with final game stats."""
    stats: dict[str, object] = {
        "total_keys": len(game.keylog),
        "score": game.final_score,
        "has_amulet": game.has_amulet,
        "final_screen": game.screen.dump(),
    }
    status = game.last_status
    if status is not None:
        stats.update(asdict(status))
    if isinstance(player, AgentPlayer):
        agent_stats = player.agent.usage_stats()
        if agent_stats:
            stats.update(agent_stats)
    (output_dir / "statistics.json").write_text(json.dumps(stats, indent=2))
