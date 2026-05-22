# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "rogue-bench"
# ]
# [tool.uv.sources]
# rogue-bench = { path = "../", editable = true}
# ///
"""Thin serial-runner wrapper around the Rogue-Bench CLI.

Accepts all the same flags as the Rogue-Bench CLI, but adds `--n-replicas`.

This runs `n` Rogue-Bench replicas one after another.
"""

from collections.abc import Callable

import click
from typer.main import get_command

from rogue_bench.__main__ import app as rogue_bench_app


def run_replicas(
    n_replicas: int,
    callback: Callable[..., object],
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    for _ in range(n_replicas):
        callback(*args, **kwargs)


def build_command() -> click.Command:
    command = get_command(rogue_bench_app)
    original_callback = command.callback

    if original_callback is None:
        raise RuntimeError("Rogue-Bench CLI command has no callback.")

    command.params.insert(
        0,
        click.Option(
            ["--n-replicas"],
            default=1,
            help="Number of Rogue-Bench replicas to run.",
            show_default=True,
            type=click.IntRange(min=1),
        ),
    )

    def callback(*args: object, n_replicas: int, **kwargs: object) -> None:
        run_replicas(n_replicas, original_callback, args, kwargs)

    command.callback = callback
    return command


if __name__ == "__main__":
    build_command()()
