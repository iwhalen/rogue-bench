from rogue_bench.game.screen import ScreenState
from rogue_bench.game.terminal_parser import TerminalParser


def test_feed_places_printable_characters_and_wraps_at_line_end() -> None:
    parser = TerminalParser()

    parser.feed(b"\x1b[1;79Habc")
    screen = parser.screen

    assert screen.characters[0][78] == "a"
    assert screen.characters[0][79] == "b"
    assert screen.characters[1][0] == "c"
    assert screen.cursor_row == 1
    assert screen.cursor_col == 1


def test_feed_handles_carriage_return_line_feed_and_backspace() -> None:
    parser = TerminalParser()

    parser.feed(b"ab\x08Z\rY\nQ")
    screen = parser.screen

    assert screen.characters[0][0] == "Y"
    assert screen.characters[0][1] == "Z"
    assert screen.characters[1][1] == "Q"


def test_feed_ctrl_l_clears_screen_and_resets_cursor() -> None:
    parser = TerminalParser()

    parser.feed(b"abc\x0c")
    screen = parser.screen

    assert all(ch == " " for row in screen.characters for ch in row)
    assert screen.cursor_row == 0
    assert screen.cursor_col == 0


def test_feed_moves_cursor_with_csi_sequence() -> None:
    parser = TerminalParser()

    parser.feed(b"\x1b[3;4HX")
    screen = parser.screen

    assert screen.characters[2][3] == "X"
    assert screen.cursor_row == 2
    assert screen.cursor_col == 4


def test_feed_clear_to_end_of_line() -> None:
    parser = TerminalParser()

    parser.feed(b"abcdef\x1b[1;3H\x1b[K")
    line = "".join(parser.screen.characters[0])

    assert line.startswith("ab")
    assert line[2:] == " " * (ScreenState.COLS - 2)


def test_feed_clear_to_end_of_screen() -> None:
    parser = TerminalParser()

    parser.feed(b"line1\r\nline2\r\nline3\x1b[2;3H\x1b[J")
    screen = parser.screen

    assert "".join(screen.characters[0]).startswith("line1")
    assert screen.characters[1][0] == "l"
    assert screen.characters[1][1] == "i"
    assert screen.characters[1][2:] == [" "] * (ScreenState.COLS - 2)
    assert all(ch == " " for row in screen.characters[2:] for ch in row)


def test_screen_property_returns_deep_copy() -> None:
    parser = TerminalParser()
    parser.feed(b"A")

    snapshot = parser.screen
    snapshot.characters[0][0] = "Z"

    assert parser.screen.characters[0][0] == "A"
