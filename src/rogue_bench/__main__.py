"""CLI definition."""

from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from rogue_bench.config import (
    DEFAULT_ACTION_DELAY,
    DEFAULT_ROGUE_PATH,
    DEFAULT_TIMEOUT,
    PlayerType,
    Settings,
)
from rogue_bench.play import play
from rogue_bench.replay import replay

app = typer.Typer()


@app.command()
def main(
    player: Annotated[
        PlayerType,
        typer.Option(
            help="Type of player.",
            case_sensitive=False,
        ),
    ] = PlayerType.HUMAN,
    rogue_path: Annotated[
        Path,
        typer.Option(
            help="Path to the rogue executable.",
        ),
    ] = DEFAULT_ROGUE_PATH,
    agent_class: Annotated[
        str | None,
        typer.Option(
            help=(
                "Import path for the RogueAgent class to use in agent mode. "
                "Short paths are resolved under rogue_bench.agent."
            ),
        ),
    ] = None,
    agent_config: Annotated[
        Path | None,
        typer.Option(
            help="Optional path to a JSON config object for the agent.",
        ),
    ] = None,
    action_delay: Annotated[
        float,
        typer.Option(
            help="Seconds to wait between actions in agent mode.",
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
    docker_image: Annotated[
        str | None,
        typer.Option(
            help="Docker image to run the Rogue binary in. "
            "When set, uses Docker instead of a local binary.",
        ),
    ] = None,
    timeout: Annotated[
        int,
        typer.Option(
            help="Maximum wall-clock seconds for a single game run.",
        ),
    ] = DEFAULT_TIMEOUT,
    fresh_rogomatic_run: Annotated[
        bool,
        typer.Option(
            help="Delete rogomatic's rlog/ directory before starting so state "
            "from prior runs doesn't carry over. Local rogomatic only.",
        ),
    ] = True,
    rogomatic_use_ltm: Annotated[
        bool,
        typer.Option(
            help="Let rogomatic read/write long-term-memory files across runs.",
        ),
    ] = True,
    rogomatic_genes: Annotated[
        str | None,
        typer.Option(
            help="Fixed rogomatic knobs (9 space-separated integers). "
            "When set, rogomatic skips its gene pool and uses these values.",
        ),
    ] = None,
) -> None:
    """Main CLI application. Starts the play session with the given options."""
    load_dotenv(".env", override=True)

    settings = Settings(
        player=player,
        rogue_path=rogue_path,
        agent_class=agent_class,
        agent_config_path=agent_config,
        action_delay=action_delay,
        seed=seed,
        output_path=output_path,
        versioned=versioned,
        input_path=input_path,
        replay_speed=replay_speed,
        no_display=no_display,
        docker_image=docker_image,
        timeout=timeout,
        fresh_rogomatic_run=fresh_rogomatic_run,
        rogomatic_use_ltm=rogomatic_use_ltm,
        rogomatic_genes=rogomatic_genes,
    )

    if settings.input_path is not None:
        replay(settings)
    else:
        play(settings)


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
