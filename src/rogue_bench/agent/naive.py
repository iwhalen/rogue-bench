"""Naive single-shot Rogue agent: prompt the model, apply the returned keys."""

from __future__ import annotations

import dataclasses
from collections import deque
from typing import TYPE_CHECKING, cast

import httpx
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.usage import RunUsage
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rogue_bench.agent.base import LLMAgentConfig, RogueAction, RogueAgent

if TYPE_CHECKING:
    from pydantic_ai.agent import AgentRunResult

    from rogue_bench.game.screen import ScreenState


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
  H  left to wall or door
  l  right
  L  right to wall or door
  k  up
  K  up to wall or door
  j  down
  J  down to wall or door
  y  up-left
  Y  up-left to wall or door
  u  up-right
  U  up-right to wall or door
  b  down-left
  B  down-left to wall or door
  n  down-right
  N  down-right to wall or door

Uppercase directions continue moving until hitting a wall or door.

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

Plan ahead — return multiple actions when the path is clear. Only return a
single action when the situation is genuinely ambiguous (e.g. a "--More--"
prompt, an unexpected monster, or a yes/no question).

Example `keys` lists:
- Explore a corridor: ["l", "l", "l", "fj"]  (3 steps right, then run down)
- Eat then move: ["ea", "j", "j", "j"]  (eat item a, then 3 steps down)
- Search dead end: ["s", "s", "s"]  (search 3 times)
- Dismiss prompt: [" "]  (single space for --More--)

Keep your reasoning brief. Focus on what you see and what to do next."""


def strip_orphan_tool_returns(
    messages: list[ModelMessage],
) -> list[ModelMessage]:
    """Remove a leading orphan ToolReturnPart from the first ModelRequest.

    Structured-output tool calls leave a ToolReturnPart at the start of each
    follow-up ModelRequest. When older messages are evicted from the history
    deque, the first remaining request can start with a ToolReturnPart whose
    matching tool-call assistant message is gone. Providers will reject this
    empty tool call, so instead we strip it out.
    """
    if not messages:
        return messages
    first = messages[0]
    if not isinstance(first, ModelRequest):
        return messages
    clean_parts = [p for p in first.parts if not isinstance(p, ToolReturnPart)]
    if len(clean_parts) == len(first.parts):
        return messages
    if clean_parts:
        return [dataclasses.replace(first, parts=clean_parts), *messages[1:]]
    return messages[1:]


class NaiveAgent(RogueAgent):
    """Straightforward LLM agent: system prompt + screen dump + structured output."""

    def __init__(self, config: LLMAgentConfig) -> None:
        super().__init__(config)
        self._agent: Agent[RogueAction] = Agent(
            config.model,
            system_prompt=SYSTEM_PROMPT,
            output_type=RogueAction,
            history_processors=[strip_orphan_tool_returns],
        )
        self._retries = config.retries
        self._usage = RunUsage()
        self._history: deque[ModelMessage] = deque(maxlen=config.max_history * 2)

    async def decide(self, screen: ScreenState, turn: int) -> RogueAction:
        prompt = f"=== State from turn {turn} ===\n\n{screen.dump()}"
        history = list(self._history) if self._history else None
        result = await self._run_agent(prompt, history)
        self._usage += result.usage()
        self._history.extend(result.new_messages())
        return result.output

    def usage_stats(self) -> dict[str, int] | None:
        return {
            "input_tokens": self._usage.request_tokens or 0,
            "output_tokens": self._usage.response_tokens or 0,
            "total_tokens": self._usage.total_tokens or 0,
        }

    async def _run_agent(
        self,
        prompt: str,
        history: list[ModelMessage] | None,
    ) -> AgentRunResult[RogueAction]:
        """Run the agent with retries on transient HTTP/connection errors."""
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.HTTPStatusError, ConnectionError)),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            stop=stop_after_attempt(self._retries),
            reraise=True,
        ):
            with attempt:
                return cast(
                    "AgentRunResult[RogueAction]",
                    await self._agent.run(prompt, message_history=history),
                )

        raise RuntimeError("Something went really wrong! Failed retry loop.")
