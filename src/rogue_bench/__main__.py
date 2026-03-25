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
    seed: Annotated[
        int | None,
        typer.Option(
            help="RNG seed for the Rogue game. "
            "Generated from current time if not provided.",
        ),
    ] = None,
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to save game recording. Created if it doesn't exist.",
        ),
    ] = None,
    versioned: Annotated[
        bool,
        typer.Option(
            help="Append ISO timestamp subdirectory to output path.",
        ),
    ] = False,
    input_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory containing a game.sav to replay. "
            "Mutually exclusive with --output-path.",
        ),
    ] = None,
    replay_speed: Annotated[
        float,
        typer.Option(
            help="Seconds between keystrokes during replay.",
        ),
    ] = 0.05,
    no_display: Annotated[
        bool,
        typer.Option(
            help="Skip visual replay; run at max speed and "
            "print final statistics as JSON.",
        ),
    ] = False,
) -> None:
    """Main CLI application. Starts the play session with the given options."""
    load_dotenv(".env", override=True)

    if input_path is not None:
        from rogue_bench.replay import replay

        replay(input_path, rogue_path, replay_speed, no_display)
        return

    settings = PlaySettings(
        player=player,
        rogue_path=rogue_path,
        rogue_version=rogue_version,
        model=model,
        max_history=max_history,
        action_delay=action_delay,
        seed=seed,
        output_path=output_path,
        versioned=versioned,
    )

    play(settings)


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
