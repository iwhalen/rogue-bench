from rogue_bench.game.screen import ScreenState, StatusLine


def test_status_line_parse_valid_status(valid_status_line: str) -> None:
    status = StatusLine.parse(valid_status_line)

    assert status == StatusLine(
        dungeon_level=3,
        gold=250,
        current_hp=8,
        max_hp=14,
        current_strength=15,
        max_strength=16,
        armor_class=-1,
        experience_level=4,
        experience_points=123,
    )


def test_status_line_parse_returns_none_for_invalid_input() -> None:
    assert StatusLine.parse("not a Rogue status line") is None


def test_screen_properties_parse_message_status_and_dump(
    populated_screen: ScreenState,
    valid_status_line: str,
) -> None:
    assert populated_screen.message_line == "You see a scroll here."
    assert populated_screen.status is not None
    assert populated_screen.status.gold == 250

    dumped = populated_screen.dump()
    assert len(dumped.splitlines()) == ScreenState.ROWS
    assert dumped.splitlines()[ScreenState.STATUS_ROW].startswith(valid_status_line)


def test_parse_final_score_returns_first_rogomatic_score() -> None:
    screen = ScreenState.empty()
    score_line = " 1  1234 rogomatic: killed on level 5 by a hobgoblin."
    screen.characters[5][: len(score_line)] = list(score_line)

    assert screen.parse_final_score() == 1234


def test_parse_final_score_returns_none_when_score_is_absent() -> None:
    assert ScreenState.empty().parse_final_score() is None
