"""Global configuration for the Rogomatic for LLMs package."""

from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

DEFAULT_ROGUE_PATH = (
    Path(__file__).resolve().parents[2]
    / "rogue-collection"
    / "build"
    / "release"
    / "rogue-collection-headless"
)


class PlayerType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    ROGOMATIC = "rogomatic"


ROGUE_VERSION = "Unix Rogue 5.4.2"

# Delay between executing agent actions (in seconds).
DEFAULT_ACTION_DELAY = 0.5

# Maximum wall-clock seconds for a single game run.
DEFAULT_TIMEOUT = 1200


class Settings(BaseSettings):
    """Global config for Rogomatic for LLMs."""

    player: PlayerType = Field(
        description="Type of player controlling the game.",
    )
    rogue_path: Path = Field(
        default=DEFAULT_ROGUE_PATH,
        description="Path to the rogue-collection headless executable.",
    )
    agent_class: str | None = Field(
        default=None,
        description="Import path for the RogueAgent class to use in agent mode.",
    )
    agent_config_path: Path | None = Field(
        default=None,
        description="Path to the config object for the agent.",
    )
    action_delay: float = Field(
        default=DEFAULT_ACTION_DELAY,
        description="Seconds to wait between actions in agent mode.",
    )
    seed: int | None = Field(
        default=None,
        description="RNG seed for the Rogue game. "
        "Generated from current time if not provided.",
    )
    output_path: Path | None = Field(
        default=None,
        description="Directory to save game recording. Created if it doesn't exist.",
    )
    versioned: bool = Field(
        default=False,
        description="Append ISO timestamp subdirectory to output path.",
    )
    input_path: Path | None = Field(
        default=None,
        description="Directory containing a game.sav to replay. "
        "Mutually exclusive with --output-path.",
    )
    replay_speed: float = Field(
        default=0.05,
        description="Seconds between keystrokes during replay.",
    )
    no_display: bool = Field(
        default=False,
        description="Skip visual replay; run at max speed and "
        "print final statistics as JSON.",
    )
    timeout: int = Field(
        default=DEFAULT_TIMEOUT,
        description="Maximum wall-clock seconds for a single game run. "
        "Default: 20 minutes.",
    )
    docker_image: str | None = Field(
        default=None,
        description="Docker image name for running Rogue in a container. "
        "When set, the game runs inside Docker instead of using a local binary.",
    )
    fresh_rogomatic_run: bool = Field(
        default=False,
        description="Delete the rogomatic rlog/ directory before starting, "
        "so genetic pool and long-term memory from prior runs don't carry over. "
        "Local rogomatic only (Docker runs always use a fresh container).",
    )
    rogomatic_use_ltm: bool = Field(
        default=True,
        description="Let rogomatic read and write its long-term-memory files "
        "(per-seed monster knowledge). Disable to make each run independent.",
    )
    rogomatic_genes: str | None = Field(
        default=None,
        description="Fixed rogomatic knobs, as a space-separated string of "
        "9 integers. When set, rogomatic skips its gene pool entirely and "
        "uses these values, making runs deterministic per seed.",
    )

    @model_validator(mode="after")
    def check_path_exclusivity(self) -> Self:
        if self.input_path is not None and self.output_path is not None:
            raise ValueError("--input-path and --output-path are mutually exclusive")
        if self.player == PlayerType.AGENT and self.agent_class is None:
            raise ValueError("--agent-class is required when --player agent")
        return self
