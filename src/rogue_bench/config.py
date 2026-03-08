"""Global configuration for the Rogomatic for LLMs package."""

from enum import StrEnum
from pathlib import Path

from pydantic import Field
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


class RogueVersion(StrEnum):
    V3_6_3 = "Unix Rogue 3.6.3"
    V5_2_1 = "Unix Rogue 5.2.1"
    V5_3 = "Unix Rogue 5.3"
    V5_4_2 = "Unix Rogue 5.4.2"


DEFAULT_ROGUE_VERSION = RogueVersion.V5_4_2

# Must be a valid PydanticAI model that support structured output.
DEFAULT_MODEL = "anthropic:claude-sonnet-4-6"

# Maximum number of previous frames in LLM prompt.
DEFAULT_MAX_HISTORY = 25

# Delay between executing LLM actions (in seconds).
DEFAULT_ACTION_DELAY = 0.5


class PlaySettings(BaseSettings):
    """Global config for Rogomatic for LLMs."""

    player: PlayerType = Field(
        description="Type of player controlling the game.",
    )
    rogue_path: Path = Field(
        default=DEFAULT_ROGUE_PATH,
        description="Path to the rogue-collection headless executable.",
    )
    rogue_version: RogueVersion = Field(
        default=DEFAULT_ROGUE_VERSION,
        description="Rogue version to play.",
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
