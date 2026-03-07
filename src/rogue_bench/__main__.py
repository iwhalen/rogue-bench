"""CLI definition."""

from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from rogue_bench.config import (
    DEFAULT_ACTION_DELAY,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MODEL,
    DEFAULT_ROGUE_PATH,
    DEFAULT_ROGUE_VERSION,
    PlayerType,
    PlaySettings,
    RogueVersion,
)
from rogue_bench.play import play

app = typer.Typer()


@app.command()
def main(
    player: Annotated[
        PlayerType,
        typer.Option(
            help="Type of player.",
            case_sensitive=False,
        ),
    ] = PlayerType.LLM,
    rogue_path: Annotated[
        Path,
        typer.Option(
            help="Path to the rogue executable.",
        ),
    ] = DEFAULT_ROGUE_PATH,
    rogue_version: Annotated[
        RogueVersion,
        typer.Option(
            help="Rogue version to play.",
            case_sensitive=False,
        ),
    ] = DEFAULT_ROGUE_VERSION,
    model: Annotated[
        str,
        typer.Option(
            help="PydanticAI compatible Agent model string.",
        ),
    ] = DEFAULT_MODEL,
    max_history: Annotated[
        int,
        typer.Option(
            help="Number of recent action/result pairs to retain in AI context.",
        ),
    ] = DEFAULT_MAX_HISTORY,
    action_delay: Annotated[
        float,
        typer.Option(
            help="Seconds to wait between actions in LLM mode.",
        ),
    ] = DEFAULT_ACTION_DELAY,
) -> None:
    """Main typer application. Starts the play session with the given options."""
    load_dotenv(".env", override=True)

    settings = PlaySettings(
        player=player,
        rogue_path=rogue_path,
        rogue_version=rogue_version,
        model=model,
        max_history=max_history,
        action_delay=action_delay,
    )

    play(settings)


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
