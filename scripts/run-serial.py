# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "rogue-bench",
#   "rich"
# ]
# [tool.uv.sources]
# rogue-bench = { path = "../", editable = true}
# ///
"""Thin serial-runner wrapper around the Rogue-Bench CLI.

Accepts all the same flags as the Rogue-Bench CLI, but adds `--n-replicas`.

This runs `n` Rogue-Bench replicas one after another.
"""

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from typer.main import get_command

from rogue_bench.__main__ import app as rogue_bench_app


def run_replicas(
    n_replicas: int,
    callback: click.Command.callback,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    console = Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Rogue-Bench serial run[/bold cyan]"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} completed"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
        refresh_per_second=8,
    ) as progress:
        task_id = progress.add_task("replicas", total=n_replicas)

        for index in range(1, n_replicas + 1):
            progress.update(
                task_id,
                description=f"replica {index}",
            )
            callback(*args, **kwargs)
            progress.advance(task_id)


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
