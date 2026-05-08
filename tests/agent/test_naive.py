from pydantic_ai.messages import ModelRequest, ToolReturnPart, UserPromptPart

from rogue_bench.agent.base import RogueAction
from rogue_bench.agent.naive import strip_orphan_tool_returns


def test_strip_orphan_tool_returns_leaves_non_orphan_history_unchanged() -> None:
    request = ModelRequest(parts=[UserPromptPart(content="look")])
    messages = [request]

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


def test_rogue_action_accepts_reasoning_and_keys() -> None:
    action = RogueAction(reasoning="Move left to explore.", keys=["h", "h"])

    assert action.reasoning == "Move left to explore."
    assert action.keys == ["h", "h"]
