"""Abstract base classes for Rogue players."""

import os
import select
import sys
import termios
import tty
from abc import abstractmethod
from io import StringIO

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from rogue_bench.game.base import PipeRogueGame
from rogue_bench.playback import PlaybackLog

_GAME_ROWS = 24
_GAME_COLS = 80
_GAME_PANEL_W = _GAME_COLS + 4
_GAME_PANEL_H = _GAME_ROWS + 2
_CONSOLE_W = _GAME_PANEL_W + 2

_HIDE_CURSOR = b"\x1b[?25l"
_SHOW_CURSOR = b"\x1b[?25h"
_HOME = b"\x1b[H"
_CLEAR = b"\x1b[2J"
_CLEAR_BELOW = b"\x1b[J"


def render_frame(
    console: Console,
    buf: StringIO,
    screen_chars: list[list[str]],
) -> bytes:
    """Render the game screen as a rich panel formatted for a raw-mode terminal.

    Newlines are converted to ``\\r\\n`` for raw-mode compatibility.
    """
    game_content = "\n".join("".join(row) for row in screen_chars)
    game_panel = Panel(
        Text(game_content, no_wrap=True, overflow="crop"),
        title="[bold yellow]Rogue[/bold yellow]",
        border_style="green",
        width=_GAME_PANEL_W,
        height=_GAME_PANEL_H,
    )

    buf.seek(0)
    buf.truncate()
    console.print(game_panel, end="")
    text = buf.getvalue()
    text = text.replace("\n", "\r\n")
    return _HIDE_CURSOR + _HOME + text.encode() + _CLEAR_BELOW + _SHOW_CURSOR


def _actions_text(labels: list[str], executed_count: int) -> Text:
    """Render a list of action labels with dim/bold styling for executed items."""
    txt = Text()
    for i, label in enumerate(labels):
        style = "dim" if i < executed_count else "bold white"
        txt.append(label, style=style)
        if i < len(labels) - 1:
            txt.append("  ", style="dim")
    return txt


def render_llm_frame(
    console: Console,
    buf: StringIO,
    screen_chars: list[list[str]],
    *,
    actions: list[str] | None = None,
    queue_length: int | None = None,
    executed_count: int = 0,
    reasoning: str | None = None,
    spinner: RenderableType | None = None,
) -> bytes:
    """Render game panel plus LLM status panels (actions, reasoning, spinner).

    Pass ``actions`` during live play to show each queued keystroke by
    name, or ``queue_length`` during replay to show placeholder glyphs
    when the originals aren't saved.  Returns raw bytes ready for
    ``os.write`` to a raw-mode terminal.
    """
    game_content = "\n".join("".join(row) for row in screen_chars)
    game_panel = Panel(
        Text(game_content, no_wrap=True, overflow="crop"),
        title="[bold yellow]Rogue[/bold yellow]",
        border_style="green",
        width=_GAME_PANEL_W,
        height=_GAME_PANEL_H,
    )

    # Build actions panel content
    actions_content: RenderableType
    if spinner is not None:
        actions_content = spinner
    elif actions is not None:
        actions_content = _actions_text(
            [repr(k) for k in actions], executed_count
        )
    elif queue_length is not None:
        actions_content = _actions_text(
            ["\u2022"] * queue_length, executed_count
        )
    else:
        actions_content = Text("Waiting...", style="dim")

    actions_panel = Panel(
        actions_content,
        title="[bold cyan]Actions[/bold cyan]",
        border_style="cyan",
        width=_GAME_PANEL_W,
    )

    parts: list[Panel] = [game_panel, actions_panel]

    if reasoning is not None:
        reasoning_panel = Panel(
            Text(reasoning, style="italic", overflow="ellipsis"),
            title="[bold magenta]Reasoning[/bold magenta]",
            border_style="magenta",
            width=_GAME_PANEL_W,
            height=6,
        )
        parts.append(reasoning_panel)

    group = Group(*parts)

    buf.seek(0)
    buf.truncate()
    console.print(group, end="")
    text = buf.getvalue()
    text = text.replace("\n", "\r\n")
    return _HIDE_CURSOR + _HOME + text.encode() + _CLEAR_BELOW + _SHOW_CURSOR


class PipeBasedPlayer:
    """Base class for players that communicate with Rogue over pipes.

    Handles terminal raw-mode setup/teardown and provides helpers for
    draining game output, feeding the VT100 parser, and rendering the
    screen via Rich panels.  Subclasses implement :meth:`_io_loop` to
    define how input is sourced (keyboard vs. LLM).
    """

    def play(self, game: PipeRogueGame) -> None:
        fd_in = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd_in)
        try:
            tty.setraw(fd_in)
            buf = StringIO()
            console = Console(file=buf, force_terminal=True, width=_CONSOLE_W)
            stdout_fd = sys.stdout.fileno()
            os.write(stdout_fd, _CLEAR + _HOME)
            self._io_loop(game, fd_in, stdout_fd, console, buf)
        finally:
            termios.tcsetattr(fd_in, termios.TCSADRAIN, old_settings)
            os.write(sys.stdout.fileno(), _SHOW_CURSOR)

    @abstractmethod
    def _io_loop(
        self,
        game: PipeRogueGame,
        fd_in: int,
        stdout_fd: int,
        console: Console,
        buf: StringIO,
    ) -> None:
        """Main I/O loop — subclasses define how input is produced."""

    @staticmethod
    def _redraw(
        game: PipeRogueGame,
        stdout_fd: int,
        console: Console,
        buf: StringIO,
    ) -> None:
        """Render the current game screen to the terminal."""
        frame = render_frame(console, buf, game.screen.characters)
        os.write(stdout_fd, frame)

    @staticmethod
    def _drain_game_output(game: PipeRogueGame) -> bool:
        """Read all available bytes from the game pipe and feed the parser.

        Returns False if the pipe is closed (game exited).
        """
        return game.drain_available()

    def playback_log(self) -> PlaybackLog | None:
        """Return per-turn playback info if the player produces one.

        Default implementation returns ``None``; subclasses that track
        reasoning / action queues (e.g. :class:`AgentPlayer`) override
        this so :func:`rogue_bench.play.play` can persist the log.
        """
        return None

    @staticmethod
    def _check_ctrl_c(fd_in: int) -> bool:
        """Non-blocking check for Ctrl-C on stdin. Returns True if detected."""
        r, _, _ = select.select([fd_in], [], [], 0)
        if r:
            data = os.read(fd_in, 1024)
            if not data or b"\x03" in data:
                return True
        return False
