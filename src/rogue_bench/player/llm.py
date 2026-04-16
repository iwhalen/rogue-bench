"""AI player powered by an LLM via Pydantic AI."""

from __future__ import annotations

import asyncio
import contextlib
import os
import select
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from rich.spinner import Spinner
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rogue_bench.player.base import PipeBasedPlayer, render_llm_frame

if TYPE_CHECKING:
    from io import StringIO

    from pydantic_ai.agent import AgentRunResult
    from pydantic_ai.messages import ModelMessage
    from rich.console import Console

    from rogue_bench.game.base import PipeRogueGame


SYSTEM_PROMPT = """You are an expert player of the classic dungeon crawler Rogue.
You are controlling the game by issuing keystrokes. Your goal is to descend through the
Dungeons of Doom, find the Amulet of Yendor on the deepest level, and return
to the surface alive.

## Screen Layout

You receive a 24x80 character grid each turn:
- Row 0: message line (game prompts, combat results, item descriptions)
- Rows 1-22: dungeon map
- Row 23: status bar

## Status Bar Format

  Level: <dungeon_level>  Gold: <gold>  Hp: <cur>(<max>)
  Str: <cur>(<max>)  Arm: <class>  Exp: <level>/<points>

Higher armor class = better protection. Keep Hp above 50% when possible.

## Map Symbols

  @  you (the rogue)
  .  floor
  #  passage/corridor
  +  door
  -  horizontal wall
  |  vertical wall
  %  staircase (use > to descend, < to ascend)
  *  gold
  !  potion
  ?  scroll
  :  food
  )  weapon
  ]  armor
  /  wand or staff
  =  ring
  ^  trap (avoid stepping on these)
  ,  the Amulet of Yendor
  A-Z  monsters (later letters = stronger creatures)

## Movement Commands

  h  left
  l  right
  k  up
  j  down
  y  up-left
  u  up-right
  b  down-left
  n  down-right

Prefix with f to run until hitting something (e.g. fj = run down).
Uppercase runs until wall/door (e.g. H = run left to wall).

Move directly into a monster to attack it in melee.

## Action Commands

  s      search adjacent squares for hidden doors/traps
  .      rest one turn (regain some HP)
  >      descend stairs (must be standing on %)
  <      ascend stairs (must be standing on %)
  i      show inventory
  e      eat food from pack
  q      quaff (drink) a potion — followed by item letter
  r      read a scroll — followed by item letter
  w      wield a weapon — followed by item letter
  W      wear armor — followed by item letter
  T      take off current armor
  P      put on a ring — followed by item letter
  R      remove a ring
  d      drop an item — followed by item letter
  t      throw an item — followed by direction key, then item letter
  z      zap a wand/staff — followed by direction key
  ,      pick up item on floor (if auto-pickup is off)

## Message Handling

When "--More--" appears on the message line, you MUST respond with a single
space " " to continue. When you see "[press return to continue]", respond
with a newline (Enter key = "\\r").

When the game asks a yes/no question (e.g. "Do you wish to see the inventory?"),
respond with "n" unless you need the information.

When the game presents a menu or inventory screen and is waiting for input,
respond with the appropriate item letter or " " / Escape to dismiss.

## Strategy

1. EXPLORE: Move through rooms and corridors systematically. Search walls
(press s multiple times) near dead ends to find hidden doors.
2. COLLECT: Pick up gold, food, weapons, armor, potions, scrolls, and rings.
Wield better weapons (w) and wear better armor (W) when found.
3. SURVIVE: Eat food when you see "hungry" or "weak" on the message line —
starvation kills. Rest with . when HP is low and no enemies are near.
4. FIGHT SMART: Engage weak monsters (early alphabet) in melee. For dangerous
monsters (late alphabet), use ranged attacks (throw items with t, zap wands
with z) or retreat through corridors where they can only approach one at a time.
5. DESCEND: Once a level is explored and cleared, find stairs (%) and descend
with >. Your goal is to reach the bottom.
6. IDENTIFY: Use scrolls and potions to discover their effects. Remember what
each color/label does across the session.

## Response Format

Return a **list of multiple actions** to execute in sequence. Each element
in the `keys` list is one logical action (one or more keystrokes).

Plan ahead — return 3-8 actions when the path is clear. Only return a
single action when the situation is genuinely ambiguous (e.g. a "--More--"
prompt, an unexpected monster, or a yes/no question).

Example `keys` lists:
- Explore a corridor: ["l", "l", "l", "fj"]  (3 steps right, then run down)
- Eat then move: ["ea", "j", "j", "j"]  (eat item a, then 3 steps down)
- Search dead end: ["s", "s", "s"]  (search 3 times)
- Dismiss prompt: [" "]  (single space for --More--)

Keep your reasoning brief. Focus on what you see and what to do next."""


class RogueAction(BaseModel):
    """Structured output from the LLM."""

    reasoning: str = Field(
        description="Brief analysis of the current situation and chosen action"
    )
    keys: list[str] = Field(
        description=(
            "List of actions to execute in order. Each element is one"
            " logical action (e.g. 'h', 'fj', 'ea')."
        ),
    )


class LLMPlayer(PipeBasedPlayer):
    """LLM-powered Rogue player using Pydantic AI."""

    def __init__(
        self,
        model: str,
        max_history: int = 25,
        action_delay: float = 0.66,
        retries: int = 5,
    ) -> None:
        self._agent = Agent(
            model,
            system_prompt=SYSTEM_PROMPT,
            output_type=RogueAction,
        )
        self._max_history = max_history
        self._action_delay = action_delay
        self._retries = retries

    def _io_loop(
        self,
        game: PipeRogueGame,
        fd_in: int,
        stdout_fd: int,
        console: Console,
        buf: StringIO,
    ) -> None:
        """AI-driven game loop — delegates to async implementation."""
        asyncio.run(self._async_io_loop(game, fd_in, stdout_fd, console, buf))

    async def _async_io_loop(
        self,
        game: PipeRogueGame,
        fd_in: int,
        stdout_fd: int,
        console: Console,
        buf: StringIO,
    ) -> None:
        """Async AI-driven game loop with spinner and per-key execution."""
        self._drain_initial(game)
        self._redraw_llm(game, stdout_fd, console, buf)

        history: list[ModelMessage] = []
        turn = 0
        last_reasoning: str | None = None

        try:
            while game.is_running():
                if self._check_ctrl_c(fd_in):
                    break

                prompt = self._build_prompt(game, turn=turn)

                # Run LLM call concurrently with spinner + Ctrl-C watcher
                spinner_task = asyncio.create_task(
                    self._spin_while_thinking(
                        game, stdout_fd, console, buf, last_reasoning
                    )
                )
                ctrl_c_task = asyncio.create_task(self._watch_ctrl_c(fd_in))
                llm_task = asyncio.create_task(self._run_agent(prompt, history))
                try:
                    done, _ = await asyncio.wait(
                        [llm_task, ctrl_c_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if ctrl_c_task in done:
                        llm_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await llm_task
                        break
                    result = llm_task.result()
                    ctrl_c_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await ctrl_c_task
                finally:
                    spinner_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await spinner_task

                history = self._trim_history(result.all_messages())
                action: RogueAction = result.output
                last_reasoning = action.reasoning
                keys = action.keys

                # Execute keys one at a time with visual progress
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

                    # Drain game output after each key
                    frogue = game.output_fd
                    r, _, _ = select.select([frogue], [], [], 0.1)
                    if r:
                        self._drain_game_output(game)

                    if self._check_ctrl_c(fd_in):
                        break

                # Final render with all keys executed
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

    async def _run_agent(
        self,
        prompt: str,
        history: list[ModelMessage],
    ) -> AgentRunResult:
        """Run the agent with retries on transient HTTP/connection errors."""
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.HTTPStatusError, ConnectionError)),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            stop=stop_after_attempt(self._retries),
            reraise=True,
        ):
            with attempt:
                return await self._agent.run(
                    prompt,
                    message_history=history or None,
                )

        raise RuntimeError("Something went really wrong! Failed retry loop.")

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
        """Animate a Rich spinner while the LLM is thinking."""
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
        """Render the game screen plus LLM status panels."""
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

    def _trim_history(self, messages: list[ModelMessage]) -> list[ModelMessage]:
        """Keep only the last max_history request/response pairs.

        Pydantic AI messages alternate: system parts are re-injected
        automatically, so we skip any leading system/setup messages and
        keep the trailing user+assistant pairs.
        """
        pair_count = self._max_history * 2
        if len(messages) <= pair_count:
            return list(messages)
        return list(messages[-pair_count:])

    @staticmethod
    def _build_prompt(game: PipeRogueGame, turn: int = 0) -> str:
        """Build the user prompt from the current game screen."""
        screen = game.screen
        heading = f"=== State from turn {turn} ==="
        return f"{heading}\n\n{screen.dump()}"

    @staticmethod
    def _drain_initial(game: PipeRogueGame) -> None:
        """Wait for the game to produce its first screen output."""
        frogue = game.output_fd
        r, _, _ = select.select([frogue], [], [], 2.0)
        if r:
            PipeBasedPlayer._drain_game_output(game)
