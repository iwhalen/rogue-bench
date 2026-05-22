import asyncio

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import RunUsage

from rogue_bench.agent.base import LLMAgentConfig, RogueAction
from rogue_bench.agent.naive import NaiveAgent, strip_orphan_tool_returns
from rogue_bench.game.screen import ScreenState


def test_strip_orphan_tool_returns_leaves_non_orphan_history_unchanged() -> None:
    request = ModelRequest(parts=[UserPromptPart(content="look")])
    messages = [request]

    assert strip_orphan_tool_returns(messages) is messages


def test_strip_orphan_tool_returns_keeps_matching_tool_return() -> None:
    tool_call = ToolCallPart(
        tool_name="final_result",
        args={"keys": ["h"]},
        tool_call_id="call-1",
    )
    tool_return = ToolReturnPart(
        tool_name="final_result",
        content={"keys": ["h"]},
        tool_call_id="call-1",
    )
    messages = [
        ModelResponse(parts=[tool_call]),
        ModelRequest(parts=[tool_return]),
    ]

    assert strip_orphan_tool_returns(messages) is messages


def test_strip_orphan_tool_returns_removes_leading_tool_return() -> None:
    orphan = ToolReturnPart(tool_name="final_result", content={"keys": ["h"]})
    user_prompt = UserPromptPart(content="look")
    request = ModelRequest(parts=[orphan, user_prompt])

    cleaned = strip_orphan_tool_returns([request])

    assert len(cleaned) == 1
    assert isinstance(cleaned[0], ModelRequest)
    assert cleaned[0].parts == [user_prompt]


def test_strip_orphan_tool_returns_drops_empty_first_request() -> None:
    orphan = ToolReturnPart(tool_name="final_result", content={"keys": ["h"]})
    second = ModelRequest(parts=[UserPromptPart(content="next")])

    cleaned = strip_orphan_tool_returns([ModelRequest(parts=[orphan]), second])

    assert cleaned == [second]


def test_strip_orphan_tool_returns_removes_orphan_retry_prompt() -> None:
    orphan = RetryPromptPart(
        tool_name="final_result",
        content="try again",
        tool_call_id="missing-call",
    )
    user_prompt = UserPromptPart(content="look")

    cleaned = strip_orphan_tool_returns([ModelRequest(parts=[orphan, user_prompt])])

    assert len(cleaned) == 1
    assert isinstance(cleaned[0], ModelRequest)
    assert cleaned[0].parts == [user_prompt]


def test_naive_agent_retains_complete_run_message_groups(monkeypatch) -> None:
    agent = NaiveAgent(LLMAgentConfig(model="test", max_history=1))
    first_run = [
        ModelRequest(parts=[UserPromptPart(content="first")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={"reasoning": "first", "keys": ["h"]},
                    tool_call_id="call-1",
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="final_result",
                    content="Final result processed.",
                    tool_call_id="call-1",
                )
            ]
        ),
    ]
    second_run = [
        ModelRequest(parts=[UserPromptPart(content="second")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={"reasoning": "second", "keys": ["l"]},
                    tool_call_id="call-2",
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="final_result",
                    content="Final result processed.",
                    tool_call_id="call-2",
                )
            ]
        ),
    ]
    captured_history: list[list[ModelMessage] | None] = []
    runs = iter([first_run, second_run])

    async def fake_run_agent(
        prompt: str,
        history: list[ModelMessage] | None,
    ) -> "_FakeRunResult":
        captured_history.append(history)
        return _FakeRunResult(next(runs))

    monkeypatch.setattr(agent, "_run_agent", fake_run_agent)

    asyncio.run(agent.decide(ScreenState.empty(), 0))
    asyncio.run(agent.decide(ScreenState.empty(), 1))

    assert captured_history == [None, first_run]
    assert agent._message_history() == second_run


def test_naive_agent_max_history_zero_disables_retained_history(monkeypatch) -> None:
    agent = NaiveAgent(LLMAgentConfig(model="test", max_history=0))
    captured_history: list[list[ModelMessage] | None] = []

    async def fake_run_agent(
        prompt: str,
        history: list[ModelMessage] | None,
    ) -> "_FakeRunResult":
        captured_history.append(history)
        return _FakeRunResult([ModelRequest(parts=[UserPromptPart(content="first")])])

    monkeypatch.setattr(agent, "_run_agent", fake_run_agent)

    asyncio.run(agent.decide(ScreenState.empty(), 0))
    asyncio.run(agent.decide(ScreenState.empty(), 1))

    assert captured_history == [None, None]
    assert agent._message_history() is None


def test_rogue_action_accepts_reasoning_and_keys() -> None:
    action = RogueAction(reasoning="Move left to explore.", keys=["h", "h"])

    assert action.reasoning == "Move left to explore."
    assert action.keys == ["h", "h"]


class _FakeRunResult:
    output = RogueAction(reasoning="test", keys=["h"])

    def __init__(self, messages: list[ModelMessage]) -> None:
        self._messages = messages

    def usage(self) -> RunUsage:
        return RunUsage()

    def new_messages(self) -> list[ModelMessage]:
        return self._messages
