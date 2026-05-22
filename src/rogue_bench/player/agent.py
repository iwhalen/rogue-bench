"""Terminal-driving player that delegates decisions to a pluggable agent."""

from __future__ import annotations

import asyncio
import contextlib
import os
import select
from typing import TYPE_CHECKING

from rich.spinner import Spinner

from rogue_bench.playback import PlaybackLog, TurnPlayback
from rogue_bench.player.base import PipeBasedPlayer, render_llm_frame

if TYPE_CHECKING:
    from io import StringIO

    from rich.console import Console

    from rogue_bench.agent.base import RogueAgent
    from rogue_bench.game.base import PipeRogueGame
    from rogue_bench.game.screen import ScreenState

_STATIONARY_POSITION_UPDATE_LIMIT = 50
_STATIONARY_POSITION_STOP_REASON = "stalled_position"


class AgentPlayer(PipeBasedPlayer):
    """Runs the game loop and terminal plumbing; delegates moves to an agent."""

    def __init__(
        self,
        agent: RogueAgent,
        action_delay: float = 0.66,
    ) -> None:
        super().__init__()
        self._agent = agent
        self._action_delay = action_delay
        self._turns: list[TurnPlayback] = []
        self._last_player_position: int | None = None
        self._stationary_position_updates = 0

    @property
    def agent(self) -> RogueAgent:
        return self._agent

    def playback_log(self) -> PlaybackLog | None:
        if not self._turns:
            return None
        return PlaybackLog(turns=list(self._turns))

    def _io_loop(
        self,
        game: PipeRogueGame,
        fd_in: int,
        stdout_fd: int,
        console: Console,
        buf: StringIO,
    ) -> None:
        asyncio.run(self._async_io_loop(game, fd_in, stdout_fd, console, buf))

    async def _async_io_loop(
        self,
        game: PipeRogueGame,
        fd_in: int,
        stdout_fd: int,
        console: Console,
        buf: StringIO,
    ) -> None:
        game.drain_initial()
        self._reset_position_watch(game.screen)
        self._redraw_agent(game, stdout_fd, console, buf)

        turn = 0
        last_reasoning: str | None = None

        try:
            while game.is_running():
                if self._check_ctrl_c(fd_in):
                    self.request_stop("ctrl_c")
                    break
                if self.stop_reason is not None:
                    break

                spinner_task = asyncio.create_task(
                    self._spin_while_thinking(
                        game, stdout_fd, console, buf, last_reasoning
                    )
                )
                ctrl_c_task = asyncio.create_task(self._watch_ctrl_c(fd_in))
                decide_task = asyncio.create_task(self._agent.decide(game.screen, turn))
                try:
                    done, _ = await asyncio.wait(
                        [decide_task, ctrl_c_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if ctrl_c_task in done:
                        decide_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await decide_task
                        break
                    action = decide_task.result()
                    ctrl_c_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await ctrl_c_task
                finally:
                    spinner_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await spinner_task

                last_reasoning = action.reasoning
                keys = action.keys

                start_bytes = len(game.keylog)
                for i, key in enumerate(keys):
                    self._redraw_agent(
                        game,
                        stdout_fd,
                        console,
                        buf,
                        actions=keys,
                        executed_count=i,
                        reasoning=last_reasoning,
                    )
                    game.send_keypress(key)
                    await asyncio.sleep(self._action_delay)

                    frogue = game.output_fd
                    r, _, _ = select.select([frogue], [], [], 0.1)
                    if r:
                        self._drain_game_output(game)

                    if self._record_position_update(game.screen):
                        break
                    if self._check_ctrl_c(fd_in):
                        self.request_stop("ctrl_c")
                        break
                    if self.stop_reason is not None:
                        break

                self._turns.append(
                    TurnPlayback(
                        reasoning=last_reasoning,
                        queue_length=len(keys),
                        byte_length=len(game.keylog) - start_bytes,
                    )
                )

                self._redraw_agent(
                    game,
                    stdout_fd,
                    console,
                    buf,
                    actions=keys,
                    executed_count=len(keys),
                    reasoning=last_reasoning,
                )
                turn += 1
        except KeyboardInterrupt:
            pass
        finally:
            os.write(stdout_fd, b"\x1b[2J\x1b[H\x1b[?25h")

    def _reset_position_watch(self, screen: ScreenState) -> None:
        """Initialize the stationary-position watchdog from the current screen."""
        self._last_player_position = screen.player_regex_position
        self._stationary_position_updates = 0

    def _record_position_update(self, screen: ScreenState) -> bool:
        """Track player movement and stop after too many unchanged updates."""
        position = screen.player_regex_position
        if position is None:
            self._last_player_position = None
            self._stationary_position_updates = 0
            return False

        if self._last_player_position is None or position != self._last_player_position:
            self._last_player_position = position
            self._stationary_position_updates = 0
            return False

        self._stationary_position_updates += 1
        if self._stationary_position_updates >= _STATIONARY_POSITION_UPDATE_LIMIT:
            self.request_stop(_STATIONARY_POSITION_STOP_REASON)
            return True
        return False

    async def _watch_ctrl_c(self, fd_in: int) -> None:
        """Poll stdin for Ctrl-C or external stop until cancelled."""
        while True:
            if self._check_ctrl_c(fd_in):
                self.request_stop("ctrl_c")
                return
            if self.stop_reason is not None:
                return
            await asyncio.sleep(0.1)

    async def _spin_while_thinking(
        self,
        game: PipeRogueGame,
        stdout_fd: int,
        console: Console,
        buf: StringIO,
        reasoning: str | None,
    ) -> None:
        """Animate a Rich spinner while the agent is deciding."""
        spinner = Spinner("dots", text="Thinking...", style="cyan")
        while True:
            self._redraw_agent(
                game,
                stdout_fd,
                console,
                buf,
                reasoning=reasoning,
                spinner=spinner,
            )
            await asyncio.sleep(0.1)

    @staticmethod
    def _redraw_agent(
        game: PipeRogueGame,
        stdout_fd: int,
        console: Console,
        buf: StringIO,
        *,
        actions: list[str] | None = None,
        executed_count: int = 0,
        reasoning: str | None = None,
        spinner: Spinner | None = None,
    ) -> None:
        """Render the game screen plus agent status panels."""
        frame = render_llm_frame(
            console,
            buf,
            game.screen.characters,
            actions=actions,
            executed_count=executed_count,
            reasoning=reasoning,
            spinner=spinner,
        )
        os.write(stdout_fd, frame)
