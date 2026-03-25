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

if TYPE_CHECKING:
    from pathlib import Path

from rogue_bench.external.game import RogueGame
from rogue_bench.player.base import (
    _CLEAR,
    _CONSOLE_W,
    _HOME,
    _SHOW_CURSOR,
    render_frame,
)


def replay(
    input_path: Path,
    rogue_path: Path,
    replay_speed: float,
    no_display: bool,
) -> None:
    """Replay a saved game recording."""
    sav_path = input_path / "game.sav"
    if not sav_path.exists():
        raise FileNotFoundError(
            f"No game.sav found in {input_path}"
        )

    game_name, env, keylog = _parse_save_file(sav_path)
    seed = env.get("seed", "0")

    rogue_path = rogue_path.resolve()
    if not rogue_path.exists():
        raise FileNotFoundError(
            f"Rogue executable not found at {rogue_path}. "
            "Run 'make build' first to compile the rogue binary."
        )

    rogue_dir = str(rogue_path.parent)
    proc_env = os.environ.copy()
    proc_env["LD_LIBRARY_PATH"] = rogue_dir

    args = [game_name, "--seed", seed]

    game = RogueGame(
        rogue_executable=str(rogue_path),
        args=args,
        env=proc_env,
    )

    original_cwd = os.getcwd()
    os.chdir(rogue_dir)
    try:
        with game:
            _drain_initial(game)
            if no_display:
                _replay_headless(game, keylog)
            else:
                _replay_visual(game, keylog, replay_speed)
    finally:
        os.chdir(original_cwd)


# ── Save file parsing ───────────────────────────────────────────


def _parse_save_file(
    path: Path,
) -> tuple[str, dict[str, str], bytes]:
    """Parse a game.sav and return (game_name, env_dict, keylog)."""
    data = path.read_bytes()
    f = BytesIO(data)

    # version (uint8)
    (version,) = struct.unpack("B", f.read(1))
    if version != 2:
        raise ValueError(
            f"Unsupported save file version: {version}"
        )

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


# ── Draining ────────────────────────────────────────────────────


def _drain_initial(game: RogueGame) -> None:
    """Wait for the game to produce its first screen output."""
    frogue = game.output_fd
    r, _, _ = select.select([frogue], [], [], 2.0)
    if r:
        _drain_game_output(game)


def _drain_game_output(game: RogueGame) -> bool:
    """Read all available bytes from the game pipe and feed the parser."""
    frogue = game.output_fd
    try:
        data = os.read(frogue, 4096)
    except OSError:
        return False
    if not data:
        return False
    game.feed(data)
    while True:
        r, _, _ = select.select([frogue], [], [], 0.02)
        if not r:
            break
        try:
            more = os.read(frogue, 4096)
        except OSError:
            break
        if not more:
            break
        game.feed(more)
    return True


# ── Visual replay ───────────────────────────────────────────────


def _replay_visual(
    game: RogueGame,
    keylog: bytes,
    replay_speed: float,
) -> None:
    """Replay with terminal display."""
    fd_in = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd_in)
    stdout_fd = sys.stdout.fileno()
    try:
        tty.setraw(fd_in)
        buf = StringIO()
        console = Console(
            file=buf, force_terminal=True, width=_CONSOLE_W
        )
        os.write(stdout_fd, _CLEAR + _HOME)

        # Show initial screen
        frame = render_frame(
            console, buf, game.screen.characters
        )
        os.write(stdout_fd, frame)

        for byte in keylog:
            game.send_raw(bytes([byte]))
            time.sleep(replay_speed)
            game.read_screen()
            frame = render_frame(
                console, buf, game.screen.characters
            )
            os.write(stdout_fd, frame)
            # Check for Ctrl-C
            r, _, _ = select.select([fd_in], [], [], 0)
            if r:
                data = os.read(fd_in, 1024)
                if not data or b"\x03" in data:
                    break
    finally:
        termios.tcsetattr(fd_in, termios.TCSADRAIN, old_settings)
        os.write(sys.stdout.fileno(), _SHOW_CURSOR)


# ── Headless replay ────────────────────────────────────────────


def _replay_headless(game: RogueGame, keylog: bytes) -> None:
    """Replay at max speed without display, print JSON stats."""
    for byte in keylog:
        game.send_raw(bytes([byte]))
        r, _, _ = select.select([game.output_fd], [], [], 0.05)
        if r:
            game.read_screen()

    # Final drain to capture remaining output
    game.read_screen()

    stats: dict[str, object] = {"total_keys": len(keylog)}
    status = game.last_status
    if status is not None:
        stats.update(asdict(status))
    print(json.dumps(stats, indent=2))
