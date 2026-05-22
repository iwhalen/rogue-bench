import os

import pytest


def test_send_raw_writes_bytes_and_records_keylog(
    pipe_game,
) -> None:
    pipe_game.game.send_raw(b"hj")

    assert os.read(pipe_game.read_fd, 2) == b"hj"
    assert pipe_game.game.keylog == b"hj"


def test_send_keypress_encodes_latin_1(pipe_game) -> None:
    pipe_game.game.send_keypress("\xa3")

    assert os.read(pipe_game.read_fd, 1) == b"\xa3"
    assert pipe_game.game.keylog == b"\xa3"


def test_feed_updates_last_status(
    dummy_game,
    valid_status_line: str,
) -> None:
    dummy_game.feed(f"\x1b[24;1H{valid_status_line}".encode())

    assert dummy_game.last_status is not None
    assert dummy_game.last_status.gold == 250


def test_feed_tracks_amulet_message(dummy_game) -> None:
    dummy_game.feed(b"You found the Amulet of Yendor!")

    assert dummy_game.has_amulet is True


def test_final_score_prefers_parsed_score(dummy_game) -> None:
    dummy_game.feed(b" 1  4321 rogomatic: killed on level 5 by a hobgoblin.")

    assert dummy_game.final_score == 4321


def test_final_score_falls_back_to_gold_penalty(
    dummy_game,
    valid_status_line: str,
) -> None:
    dummy_game.feed(f"\x1b[24;1H{valid_status_line}".encode())

    assert dummy_game.final_score == 225


def test_final_score_returns_none_without_score_or_status(
    dummy_game,
) -> None:
    assert dummy_game.final_score is None


def test_pipe_methods_raise_when_process_is_not_running(
    dummy_game,
) -> None:
    with pytest.raises(RuntimeError, match="Rogue process is not running"):
        _ = dummy_game.output_fd

    with pytest.raises(RuntimeError, match="Rogue process is not running"):
        dummy_game.send_raw(b"h")

    with pytest.raises(RuntimeError, match="Rogue process is not running"):
        dummy_game.read_screen()


def test_is_running_returns_false_on_death_screen(dummy_game) -> None:
    dummy_game.feed(
        b"\x1b[11;26HREST"
        b"\x1b[13;25HPEACE"
        b"\x1b[24;1H[Press return to continue]"
    )

    assert dummy_game.is_running() is False
