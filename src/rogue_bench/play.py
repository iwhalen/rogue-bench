"""Start and orchestrate a game of Rogue."""

import importlib
import inspect
import json
import os
import random
import struct
import sys
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from json import JSONDecodeError
from pathlib import Path
from typing import cast, get_type_hints

from pydantic import ValidationError

from rogue_bench.agent.base import AgentConfig, RogueAgent
from rogue_bench.config import ROGUE_VERSION, PlayerType, Settings
from rogue_bench.game.base import PipeRogueGame
from rogue_bench.game.docker import DockerRogueGame
from rogue_bench.game.local import LocalRogueGame
from rogue_bench.player.agent import AgentPlayer
from rogue_bench.player.base import PipeBasedPlayer
from rogue_bench.player.human import HumanPlayer
from rogue_bench.player.rogomatic import RogomaticPlayer

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
    elif config.player == PlayerType.AGENT:
        agent = load_agent(config)
        player = AgentPlayer(agent, action_delay=config.action_delay)
    elif config.player == PlayerType.ROGOMATIC:
        player = RogomaticPlayer(config)
    else:
        raise NotImplementedError(f"Invalid player type: {config.player}")

    seed = config.seed if config.seed is not None else random.randint(0, 2**31 - 1)
    # Rogomatic drives the game itself; rogue must not be pre-seeded with
    # --seed in that case or it won't match the bot's own RNG.
    if config.player == PlayerType.ROGOMATIC:
        args = [ROGUE_VERSION]
    else:
        args = [ROGUE_VERSION, "--seed", str(seed)]

    resolved_dir = None
    if config.output_path:
        resolved_dir = resolve_output_dir(config).resolve()
        resolved_dir.mkdir(parents=True, exist_ok=True)

    game = create_game(config, args)

    watchdog = threading.Timer(
        config.timeout, lambda: player.request_stop("timeout")
    )
    watchdog.daemon = True
    watchdog.start()

    try:
        with game:
            try:
                player.play(game)
                game.drain_remaining()
            finally:
                if resolved_dir is not None:
                    player.collect_artifacts(resolved_dir)
    finally:
        watchdog.cancel()
        if resolved_dir:
            terminated = player.stop_reason or "completed"
            write_save_file(
                resolved_dir / "game.sav",
                ROGUE_VERSION,
                seed,
                game.keylog,
            )
            write_metadata(resolved_dir, config, seed, terminated, player)
            write_statistics(resolved_dir, game, player)
            write_playback(resolved_dir, player)


def create_game(
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


def resolve_output_dir(config: Settings) -> Path:
    """Resolve the output directory, optionally appending a timestamp."""
    assert config.output_path is not None
    base = config.output_path
    if config.versioned:
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H.%M.%S.%f")[:-3] + "Z"
        return base / ts
    return base


def write_save_file(path: Path, game_name: str, seed: int, keylog: bytes) -> None:
    """Write a game recording in Rogue Collection save format."""
    game_env = {**_ROGOMATIC_ENV, "seed": str(seed)}

    with open(path, "wb") as f:
        # Version (uint8) — matches SDL/QML kSaveVersion = 2
        f.write(struct.pack("B", 2))
        # Restore count (uint16 LE)
        f.write(struct.pack("<H", 0))
        # Game name (ShortString: uint8 length + bytes)
        write_short_string(f, game_name)
        # Environment (uint16 LE count + ShortString pairs)
        f.write(struct.pack("<H", len(game_env)))
        for key, value in game_env.items():
            write_short_string(f, key)
            write_short_string(f, value)
        # Raw keylog
        f.write(keylog)


def write_short_string(f: object, s: str) -> None:
    """Write a Rogue Collection ShortString (1-byte length prefix + data)."""
    encoded = s.encode("ascii")
    f.write(struct.pack("B", len(encoded)))  # type: ignore[union-attr]
    f.write(encoded)  # type: ignore[union-attr]


def write_metadata(
    output_dir: Path,
    config: Settings,
    seed: int,
    terminated: str,
    player: PipeBasedPlayer,
) -> None:
    """Write metadata.json for the game recording."""
    metadata = {
        "timestamp": datetime.now(UTC).isoformat(),
        "seed": seed,
        "rogue_version": ROGUE_VERSION,
        "player": str(config.player),
        "agent_class": config.agent_class,
        "agent_config_path": (
            str(config.agent_config_path)
            if config.agent_config_path is not None
            else None
        ),
        "config": agent_config_metadata(player),
        "args": sys.argv,
        "terminated": terminated,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))


def agent_config_metadata(player: PipeBasedPlayer) -> dict[str, object]:
    """Return the agent config for metadata output, if this run used an agent."""
    if not isinstance(player, AgentPlayer):
        return {}
    return player.agent.config.model_dump(mode="json")


def load_agent(config: Settings) -> RogueAgent:
    """Load the configured RogueAgent class and instantiate it."""
    if config.agent_class is None:
        raise ValueError("--agent-class is required when --player agent")

    agent_class = load_agent_class(config.agent_class)
    config_class = find_agent_config_class(agent_class)
    agent_config = load_agent_config(config_class, config.agent_config_path)
    return agent_class(agent_config)


def load_agent_class(class_path: str) -> type[RogueAgent]:
    """Import a RogueAgent class from rogue_bench.agent."""
    module_path, _, class_name = class_path.rpartition(".")
    if not class_name:
        module_path = "rogue_bench.agent"
        class_name = class_path
    elif not module_path.startswith("rogue_bench.agent"):
        module_path = f"rogue_bench.agent.{module_path}"

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise ValueError(f"Agent module could not be imported: {module_path}") from exc

    try:
        agent_class = getattr(module, class_name)
    except AttributeError as exc:
        raise ValueError(
            f"Agent class {class_name!r} was not found in {module_path!r}"
        ) from exc

    if not inspect.isclass(agent_class) or not issubclass(agent_class, RogueAgent):
        raise TypeError(f"{class_path!r} is not a RogueAgent class")

    return cast("type[RogueAgent]", agent_class)


def find_agent_config_class(agent_class: type[RogueAgent]) -> type[AgentConfig]:
    """Find the first constructor argument annotated as an AgentConfig subclass."""
    hints = get_type_hints(agent_class.__init__)
    for parameter in inspect.signature(agent_class.__init__).parameters.values():
        if parameter.name == "self":
            continue
        annotation = hints.get(parameter.name)
        if inspect.isclass(annotation) and issubclass(annotation, AgentConfig):
            return cast("type[AgentConfig]", annotation)

    raise TypeError(
        f"{agent_class.__module__}.{agent_class.__name__} must have a constructor "
        "argument annotated with AgentConfig or a subclass"
    )


def load_agent_config(
    config_class: type[AgentConfig],
    path: Path | None,
) -> AgentConfig:
    """Load and validate a JSON agent config file, or instantiate defaults."""
    if path is None:
        return config_class()

    try:
        config_data = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Agent config file not found: {path}") from exc
    except JSONDecodeError as exc:
        raise ValueError(f"Agent config file is not valid JSON: {path}") from exc

    try:
        return config_class.model_validate(config_data)
    except ValidationError as exc:
        raise ValueError(
            f"Agent config file failed validation for {config_class.__name__}: {path}"
        ) from exc


def write_playback(output_dir: Path, player: PipeBasedPlayer) -> None:
    """Write playback.json if the player tracked per-turn reasoning/queue info."""
    log = player.playback_log()
    if log is None or not log.turns:
        return
    (output_dir / "playback.json").write_text(
        json.dumps(log.model_dump(), indent=2)
    )


def write_statistics(
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
