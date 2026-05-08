from typing import Any

import pytest
from pydantic import ValidationError

from rogue_bench.agent.base import LLMAgentConfig
from rogue_bench.config import PlayerType, Settings


def test_agent_player_requires_agent_class() -> None:
    with pytest.raises(ValidationError, match="--agent-class is required"):
        Settings(player=PlayerType.AGENT)


def test_input_path_and_output_path_are_mutually_exclusive(tmp_path) -> None:
    with pytest.raises(
        ValidationError,
        match="--input-path and --output-path are mutually exclusive",
    ):
        Settings(
            player=PlayerType.HUMAN,
            input_path=tmp_path / "input",
            output_path=tmp_path / "output",
        )


def test_valid_non_agent_settings_use_defaults() -> None:
    settings = Settings(player=PlayerType.HUMAN)

    assert settings.player == PlayerType.HUMAN
    assert settings.agent_class is None
    assert settings.action_delay == 0.5
    assert settings.timeout == 1200


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_history": -1}, "greater than or equal to 0"),
        ({"retries": 0}, "greater than or equal to 1"),
    ],
)
def test_llm_agent_config_validates_numeric_bounds(
    kwargs: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        LLMAgentConfig(**kwargs)
