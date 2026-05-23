import asyncio

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import RunUsage

from rogue_bench.agent.base import LLMAgentConfig, RogueAction
from rogue_bench.agent.naive import (
    SYSTEM_PROMPT,
    NaiveAgent,
    compact_action_history,
    strip_orphan_tool_returns,
)
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


def test_compact_action_history_uses_plain_request_response_messages() -> None:
    prompt = "screen"
    action = RogueAction(reasoning="Move left.", keys=["h"])

    history = compact_action_history(prompt, action)

    assert len(history) == 2
    assert isinstance(history[0], ModelRequest)
    assert isinstance(history[0].parts[0], UserPromptPart)
    assert history[0].parts[0].content == prompt
    assert isinstance(history[1], ModelResponse)
    assert history[1].tool_calls == []


def test_naive_agent_retains_compact_action_history(monkeypatch) -> None:
    agent = NaiveAgent(LLMAgentConfig(model="test", max_history=1))
    captured_history: list[list[ModelMessage] | None] = []
    actions = iter(
        [
            RogueAction(reasoning="first", keys=["h"]),
            RogueAction(reasoning="second", keys=["l"]),
        ]
    )

    async def fake_run_agent(
        prompt: str,
        history: list[ModelMessage] | None,
    ) -> "_FakeRunResult":
        action = next(actions)
        captured_history.append(history)
        return _FakeRunResult(
            [ModelRequest(parts=[UserPromptPart(content=prompt)])],
            action,
        )

    monkeypatch.setattr(agent, "_run_agent", fake_run_agent)

    asyncio.run(agent.decide(ScreenState.empty(), 0))
    asyncio.run(agent.decide(ScreenState.empty(), 1))

    first_prompt = "=== State from turn 0 ===\n\n" + ScreenState.empty().dump()
    second_prompt = "=== State from turn 1 ===\n\n" + ScreenState.empty().dump()
    first_history = compact_action_history(
        first_prompt, RogueAction(reasoning="first", keys=["h"])
    )
    second_history = compact_action_history(
        second_prompt, RogueAction(reasoning="second", keys=["l"])
    )

    assert captured_history[0] is None
    assert _history_content(captured_history[1]) == _history_content(
        _with_system_prompt(first_history)
    )
    assert _history_content(agent._message_history()) == _history_content(
        _with_system_prompt(second_history)
    )


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
    def __init__(
        self,
        messages: list[ModelMessage],
        output: RogueAction | None = None,
    ) -> None:
        self._messages = messages
        self.output = output or RogueAction(reasoning="test", keys=["h"])

    def usage(self) -> RunUsage:
        return RunUsage()

    def new_messages(self) -> list[ModelMessage]:
        return self._messages


def _history_content(history: list[ModelMessage] | None) -> list[tuple[str, str]]:
    assert history is not None
    compacted: list[tuple[str, str]] = []
    for message in history:
        part = message.parts[0]
        if isinstance(message, ModelRequest):
            assert isinstance(part, UserPromptPart | SystemPromptPart)
            compacted.append((part.part_kind, part.content))
        else:
            assert isinstance(part, TextPart)
            compacted.append(("response", part.content))
    return compacted


def _with_system_prompt(history: list[ModelMessage]) -> list[ModelMessage]:
    return [ModelRequest(parts=[SystemPromptPart(content=SYSTEM_PROMPT)]), *history]
