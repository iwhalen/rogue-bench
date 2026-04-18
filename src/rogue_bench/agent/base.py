"""Abstract agent interface and shared action schema."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from rogue_bench.game.screen import ScreenState


class RogueAction(BaseModel):
    """One decision emitted by an agent: a list of keystrokes plus reasoning."""

    reasoning: str = Field(
        description="Brief analysis of the current situation and chosen action"
    )
    keys: list[str] = Field(
        description=(
            "List of actions to execute in order. Each element is one logical action."
        ),
    )


class AgentConfig(BaseModel):
    """Base config for every RogueAgent. Concrete agents extend with their fields."""


class LLMAgentConfig(AgentConfig):
    """Shared config for LLM-backed agents."""

    model: str = Field(
        description=(
            "Model identifier passed to Pydantic AI Agent constructor"
            "(e.g. 'openai:gpt-5.4', 'anthropic:claude-sonnet-4-6')."
        ),
    )
    max_history: int = Field(
        default=25,
        ge=0,
        description=(
            "Maximum number of request/response pairs retained across turns. "
            "Older messages are evicted from the in-memory history deque."
        ),
    )
    retries: int = Field(
        default=5,
        ge=1,
        description=(
            "Number of attempts for a single model call before giving up. "
            "Retries trigger only on transient HTTP / connection errors with "
            "exponential backoff."
        ),
    )


class RogueAgent(ABC):
    """Contract for an agent that chooses actions from a Rogue screen."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    @abstractmethod
    async def decide(self, screen: ScreenState, turn: int) -> RogueAction:
        """Return the next action(s) to execute given the current screen."""

    def usage_stats(self) -> dict[str, int] | None:
        """Agent-specific stats for statistics.json. Default: none."""
        return None
