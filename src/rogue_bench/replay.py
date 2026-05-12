"""Replay a previously recorded game from a game.sav file."""

from __future__ import annotations

import json
import os
import select
import struct
import sys
import termios
import time
import tty
from dataclasses import asdict
from io import BytesIO, StringIO
from typing import TYPE_CHECKING

from rich.console import Console

from rogue_bench.game.docker import DockerRogueGame
from rogue_bench.game.local import LocalRogueGame
from rogue_bench.playback import PlaybackLog

if TYPE_CHECKING:
    from pathlib import Path

    from rogue_bench.config import Settings
    from rogue_bench.game.base import PipeRogueGame
from rogue_bench.player.base import (
    _CLEAR,
    _CONSOLE_W,
    _HOME,
    _SHOW_CURSOR,
    render_frame,
    render_llm_frame,
)


def replay(settings: Settings) -> None:
    """Replay a saved game recording from a ``game.sav`` file.

    Parses the binary save file to extract the game name, seed, and
    keylog, then starts a fresh headless game and feeds the recorded
    keystrokes back in.  In visual mode the screen is rendered to the
    terminal with a configurable delay between keys; in headless mode
    the keylog is fed at max speed and final game statistics are
    printed as JSON to stdout.

    If a ``playback.json`` sidecar exists next to ``game.sav`` (written
    when an agent played), the Actions and Reasoning panels from the
    live run are re-shown as the keylog is replayed.

    Args:
        settings: Application settings. Must have ``input_path``
            set to the directory containing a ``game.sav`` file.
            Uses ``rogue_path``, ``replay_speed``, and
            ``no_display`` from the settings.
    """
    assert settings.input_path is not None
    sav_path = settings.input_path / "game.sav"
    if not sav_path.exists():
        raise FileNotFoundError(f"No game.sav found in {settings.input_path}")

    game_name, env, keylog = _parse_save_file(sav_path)
    seed = env.get("seed", "0")

    playback = _load_playback(settings.input_path / "playback.json")

    args = [game_name, "--seed", seed]
    game = _create_replay_game(settings, args)

    with game:
        game.drain_initial()
        if settings.no_display:
            _replay_headless(game, keylog)
        else:
            _replay_visual(game, keylog, settings.replay_speed, playback)


def _create_replay_game(
    settings: Settings,
    args: list[str],
) -> PipeRogueGame:
    """Instantiate the right game backend for replay."""
    if settings.docker_image:
        return DockerRogueGame(
            docker_image=settings.docker_image,
            args=args,
        )

    rogue_path = settings.rogue_path.resolve()
    if not rogue_path.exists():
        raise FileNotFoundError(
            f"Rogue executable not found at {rogue_path}. "
            "Run 'make build' first to compile the rogue binary."
        )
    rogue_dir = str(rogue_path.parent)
    proc_env = os.environ.copy()
    proc_env["LD_LIBRARY_PATH"] = rogue_dir
    return LocalRogueGame(
        rogue_executable=str(rogue_path),
        args=args,
        env=proc_env,
        cwd=rogue_dir,
    )


def _parse_save_file(
    path: Path,
) -> tuple[str, dict[str, str], bytes]:
    """Parse a game.sav and return (game_name, env_dict, keylog)."""
    data = path.read_bytes()
    f = BytesIO(data)

    # version (uint8)
    (version,) = struct.unpack("B", f.read(1))
    if version != 2:
        raise ValueError(f"Unsupported save file version: {version}")

    # restore_count (uint16 LE) — unused for replay
    f.read(2)

    game_name = _read_short_string(f)
    env = _read_environment(f)
    keylog = f.read()

    return game_name, env, keylog


def _read_short_string(f: BytesIO) -> str:
    """Read a ShortString (1-byte length prefix + data)."""
    (length,) = struct.unpack("B", f.read(1))
    return f.read(length).decode("ascii")


def _read_environment(f: BytesIO) -> dict[str, str]:
    """Read environment entries (uint16 LE count + ShortString pairs)."""
    (count,) = struct.unpack("<H", f.read(2))
    env: dict[str, str] = {}
    for _ in range(count):
        key = _read_short_string(f)
        value = _read_short_string(f)
        env[key] = value
    return env


def _load_playback(path: Path) -> PlaybackLog | None:
    """Load a playback.json sidecar if present; return None otherwise."""
    if not path.exists():
        return None
    return PlaybackLog.model_validate(json.loads(path.read_text()))


def _replay_visual(
    game: PipeRogueGame,
    keylog: bytes,
    replay_speed: float,
    playback: PlaybackLog | None,
) -> None:
    """Replay with terminal display, optionally showing agent panels."""
    fd_in = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd_in)
    stdout_fd = sys.stdout.fileno()
    try:
        tty.setraw(fd_in)
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=_CONSOLE_W)
        os.write(stdout_fd, _CLEAR + _HOME)

        if playback is not None and playback.turns:
            _replay_visual_with_playback(
                game,
                keylog,
                replay_speed,
                playback,
                fd_in,
                stdout_fd,
                console,
                buf,
            )
        else:
            _replay_visual_plain(
                game,
                keylog,
                replay_speed,
                fd_in,
                stdout_fd,
                console,
                buf,
            )
    finally:
        termios.tcsetattr(fd_in, termios.TCSADRAIN, old_settings)
        os.write(sys.stdout.fileno(), _SHOW_CURSOR)


def _replay_visual_plain(
    game: PipeRogueGame,
    keylog: bytes,
    replay_speed: float,
    fd_in: int,
    stdout_fd: int,
    console: Console,
    buf: StringIO,
) -> None:
    """Render the game panel only — original pre-playback behavior."""
    frame = render_frame(console, buf, game.screen.characters)
    os.write(stdout_fd, frame)

    for byte in keylog:
        game.send_raw(bytes([byte]))
        time.sleep(replay_speed)
        game.read_screen()
        frame = render_frame(console, buf, game.screen.characters)
        os.write(stdout_fd, frame)
        if _ctrl_c_pressed(fd_in):
            break


def _replay_visual_with_playback(
    game: PipeRogueGame,
    keylog: bytes,
    replay_speed: float,
    playback: PlaybackLog,
    fd_in: int,
    stdout_fd: int,
    console: Console,
    buf: StringIO,
) -> None:
    """Render game + Actions + Reasoning panels using the playback log.

    Per-turn action labels are reconstructed from the keylog slice so
    the Actions panel matches what the live run displayed — the keys
    themselves are not stored in ``playback.json``.
    """
    turns = playback.turns
    turn_idx = 0
    bytes_in_turn = 0
    executed_in_turn = 0
    turn_start = 0

    def current() -> tuple[list[str] | None, int | None, str | None, int]:
        if turn_idx >= len(turns):
            return None, None, None, 0
        t = turns[turn_idx]
        labels = _action_labels(
            keylog[turn_start : turn_start + t.byte_length], t.queue_length
        )
        queue_len = t.queue_length if labels is None else None
        return labels, queue_len, t.reasoning, t.byte_length

    actions, queue_length, reasoning, byte_length = current()
    frame = render_llm_frame(
        console,
        buf,
        game.screen.characters,
        actions=actions,
        queue_length=queue_length,
        executed_count=0,
        reasoning=reasoning,
    )
    os.write(stdout_fd, frame)

    total_steps = (
        len(actions)
        if actions is not None
        else (queue_length if queue_length is not None else 0)
    )

    for byte in keylog:
        game.send_raw(bytes([byte]))
        time.sleep(replay_speed)
        game.read_screen()

        bytes_in_turn += 1
        if total_steps > 0:
            executed_in_turn = min(executed_in_turn + 1, total_steps)

        frame = render_llm_frame(
            console,
            buf,
            game.screen.characters,
            actions=actions,
            queue_length=queue_length,
            executed_count=executed_in_turn,
            reasoning=reasoning,
        )
        os.write(stdout_fd, frame)

        if byte_length > 0 and bytes_in_turn >= byte_length:
            turn_start += byte_length
            turn_idx += 1
            bytes_in_turn = 0
            executed_in_turn = 0
            actions, queue_length, reasoning, byte_length = current()
            total_steps = (
                len(actions)
                if actions is not None
                else (queue_length if queue_length is not None else 0)
            )

        if _ctrl_c_pressed(fd_in):
            break


def _action_labels(slice_: bytes, queue_length: int) -> list[str] | None:
    """Reconstruct per-key labels from a turn's keylog slice.

    Returns a list of single-character labels when each byte maps 1:1
    to a queued key (the common case — each ``send_keypress`` is one
    byte).  Returns ``None`` when the mapping is ambiguous, so callers
    fall back to length-only placeholder rendering.
    """
    if queue_length == 0 or len(slice_) != queue_length:
        return None
    return [chr(b) for b in slice_]


def _ctrl_c_pressed(fd_in: int) -> bool:
    r, _, _ = select.select([fd_in], [], [], 0)
    if r:
        data = os.read(fd_in, 1024)
        if not data or b"\x03" in data:
            return True
    return False


def _replay_headless(game: PipeRogueGame, keylog: bytes) -> None:
    """Replay at max speed without display, print JSON stats."""
    for byte in keylog:
        game.send_raw(bytes([byte]))
        r, _, _ = select.select([game.output_fd], [], [], 0.05)
        if r:
            game.read_screen()

    # Final drain to capture remaining output
    game.read_screen()

    stats: dict[str, object] = {
        "total_keys": len(keylog),
        "score": game.final_score,
        "has_amulet": game.has_amulet,
    }
    status = game.last_status
    if status is not None:
        stats.update(asdict(status))
    print(json.dumps(stats, indent=2))
