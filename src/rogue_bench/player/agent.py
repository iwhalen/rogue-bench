"""Terminal-driving player that delegates decisions to a pluggable agent."""

from __future__ import annotations

import asyncio
import contextlib
import os
import select
from typing import TYPE_CHECKING

from rich.spinner import Spinner

from rogue_bench.player.base import PipeBasedPlayer, render_llm_frame

if TYPE_CHECKING:
    from io import StringIO

    from rich.console import Console

    from rogue_bench.agent.base import RogueAgent
    from rogue_bench.game.base import PipeRogueGame


class AgentPlayer(PipeBasedPlayer):
    """Runs the game loop and terminal plumbing; delegates moves to an agent."""

    def __init__(
        self,
        agent: RogueAgent,
        action_delay: float = 0.66,
    ) -> None:
        self._agent = agent
        self._action_delay = action_delay

    @property
    def agent(self) -> RogueAgent:
        return self._agent

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
        self._drain_initial(game)
        self._redraw_llm(game, stdout_fd, console, buf)

        turn = 0
        last_reasoning: str | None = None

        try:
            while game.is_running():
                if self._check_ctrl_c(fd_in):
                    break

                spinner_task = asyncio.create_task(
                    self._spin_while_thinking(
                        game, stdout_fd, console, buf, last_reasoning
                    )
                )
                ctrl_c_task = asyncio.create_task(self._watch_ctrl_c(fd_in))
                decide_task = asyncio.create_task(
                    self._agent.decide(game.screen, turn)
                )
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

                for i, key in enumerate(keys):
                    self._redraw_llm(
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

                    if self._check_ctrl_c(fd_in):
                        break

                self._redraw_llm(
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

    async def _watch_ctrl_c(self, fd_in: int) -> None:
        """Poll stdin for Ctrl-C until detected or cancelled."""
        while True:
            if self._check_ctrl_c(fd_in):
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
            self._redraw_llm(
                game,
                stdout_fd,
                console,
                buf,
                reasoning=reasoning,
                spinner=spinner,
            )
            await asyncio.sleep(0.1)

    @staticmethod
    def _redraw_llm(
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

    @staticmethod
    def _drain_initial(game: PipeRogueGame) -> None:
        """Wait for the game to produce its first screen output."""
        frogue = game.output_fd
        r, _, _ = select.select([frogue], [], [], 2.0)
        if r:
            PipeBasedPlayer._drain_game_output(game)
