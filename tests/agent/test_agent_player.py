from rogue_bench.agent.base import AgentConfig, RogueAction, RogueAgent
from rogue_bench.game.screen import ScreenState
from rogue_bench.player.agent import AgentPlayer
from rogue_bench.player.base import PipeBasedPlayer


class DummyAgent(RogueAgent):
    async def decide(self, screen: ScreenState, turn: int) -> RogueAction:
        return RogueAction(reasoning="", keys=[])


def test_agent_player_stops_after_50_unchanged_position_updates() -> None:
    player = AgentPlayer(DummyAgent(AgentConfig()))
    screen = ScreenState.empty()
    screen.characters[2][3] = "@"
    player._reset_position_watch(screen)

    for _ in range(49):
        assert player._record_position_update(screen) is False
        assert player.stop_reason is None

    assert player._record_position_update(screen) is True
    assert player.stop_reason == "stalled_position"


def test_agent_player_resets_stationary_count_when_position_changes() -> None:
    player = AgentPlayer(DummyAgent(AgentConfig()))
    screen = ScreenState.empty()
    screen.characters[2][3] = "@"
    player._reset_position_watch(screen)

    for _ in range(49):
        assert player._record_position_update(screen) is False

    screen.characters[2][3] = "."
    screen.characters[2][4] = "@"

    assert player._record_position_update(screen) is False
    assert player.stop_reason is None


def test_noninteractive_stdin_cannot_trigger_ctrl_c() -> None:
    assert PipeBasedPlayer._check_ctrl_c(-1) is False
