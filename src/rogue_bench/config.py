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
    LLM = "llm"


ROGUE_VERSION = "Unix Rogue 5.4.2"

# Must be a valid PydanticAI model that support structured output.
DEFAULT_MODEL = "anthropic:claude-sonnet-4-6"

# Maximum number of previous frames in LLM prompt.
DEFAULT_MAX_HISTORY = 25

# Delay between executing LLM actions (in seconds).
DEFAULT_ACTION_DELAY = 0.5


class Settings(BaseSettings):
    """Global config for Rogomatic for LLMs."""

    player: PlayerType = Field(
        description="Type of player controlling the game.",
    )
    rogue_path: Path = Field(
        default=DEFAULT_ROGUE_PATH,
        description="Path to the rogue-collection headless executable.",
    )
    model: str = Field(
        default=DEFAULT_MODEL,
        description="PydanticAI compatible model string.",
    )
    max_history: int = Field(
        default=DEFAULT_MAX_HISTORY,
        description="Number of recent action/result pairs to retain in AI context.",
    )
    action_delay: float = Field(
        default=DEFAULT_ACTION_DELAY,
        description="Seconds to wait between actions in LLM mode.",
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
    docker_image: str | None = Field(
        default=None,
        description="Docker image name for running Rogue in a container. "
        "When set, the game runs inside Docker instead of using a local binary.",
    )

    @model_validator(mode="after")
    def check_path_exclusivity(self) -> Self:
        if self.input_path is not None and self.output_path is not None:
            raise ValueError("--input-path and --output-path are mutually exclusive")
        return self
