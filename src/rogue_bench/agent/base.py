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
            "List of actions to execute in order. Each element is one"
            " logical action (e.g. 'h', 'fj', 'ea')."
        ),
    )


class RogueAgent(ABC):
    """Contract for an agent that chooses actions from a Rogue screen."""

    @abstractmethod
    async def decide(self, screen: ScreenState, turn: int) -> RogueAction:
        """Return the next action(s) to execute given the current screen."""

    def usage_stats(self) -> dict[str, int] | None:
        """Agent-specific stats for statistics.json. Default: none."""
        return None
