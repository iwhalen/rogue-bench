"""Start and orchestrate a game of Rogue."""

import json
import os
import random
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path

from rogue_bench.config import PlayerType, PlaySettings
from rogue_bench.external.game import RogueGame
from rogue_bench.player.human import HumanPlayer
from rogue_bench.player.llm import LLMPlayer

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

    seed = config.seed if config.seed is not None else random.randint(0, 2**31 - 1)

    rogue_path = config.rogue_path.resolve()
    rogue_dir = str(rogue_path.parent)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = rogue_dir

    args = [config.rogue_version, "--seed", str(seed)]

    resolved_dir = None
    if config.output_path:
        resolved_dir = _resolve_output_dir(config).resolve()
        resolved_dir.mkdir(parents=True, exist_ok=True)

    game = RogueGame(
        rogue_executable=str(rogue_path),
        args=args,
        env=env,
    )

    original_cwd = os.getcwd()
    os.chdir(rogue_dir)
    try:
        with game:
            player.play(game)
    finally:
        os.chdir(original_cwd)
        if resolved_dir:
            _write_save_file(
                resolved_dir / "game.sav",
                str(config.rogue_version),
                seed,
                game.keylog,
            )
            _write_metadata(resolved_dir, config, seed)


def _resolve_output_dir(config: PlaySettings) -> Path:
    """Resolve the output directory, optionally appending a timestamp."""
    assert config.output_path is not None
    base = config.output_path
    if config.versioned:
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H.%M.%S.%f")[:-3] + "Z"
        return base / ts
    return base


def _write_save_file(
    path: Path, game_name: str, seed: int, keylog: bytes
) -> None:
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


def _write_metadata(
    output_dir: Path, config: PlaySettings, seed: int
) -> None:
    """Write metadata.json for the game recording."""
    metadata = {
        "timestamp": datetime.now(UTC).isoformat(),
        "seed": seed,
        "rogue_version": str(config.rogue_version),
        "player": str(config.player),
        "model": config.model,
        "args": sys.argv,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
