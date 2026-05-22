# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Summarize Rogue-Bench run directories."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_RESULTS_DIR = Path("results/gpt-5-4-mini")


@dataclass(frozen=True)
class Run:
    name: str
    metadata: dict[str, Any]
    statistics: dict[str, Any]
    playback: dict[str, Any] | None

    @property
    def turns(self) -> int | None:
        if self.playback is None:
            return None
        turns = self.playback.get("turns")
        if not isinstance(turns, list):
            return None
        return len(turns)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError as error:
        raise SystemExit(f"Missing required file: {path}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {path}: {error}") from error

    if not isinstance(data, dict):
        raise SystemExit(f"Expected a JSON object in {path}")
    return data


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return load_json(path)


def load_runs(results_dir: Path) -> list[Run]:
    if not results_dir.exists():
        raise SystemExit(f"Results directory does not exist: {results_dir}")
    if not results_dir.is_dir():
        raise SystemExit(f"Results path is not a directory: {results_dir}")

    runs: list[Run] = []
    for run_dir in sorted(path for path in results_dir.iterdir() if path.is_dir()):
        runs.append(
            Run(
                name=run_dir.name,
                metadata=load_json(run_dir / "metadata.json"),
                statistics=load_json(run_dir / "statistics.json"),
                playback=load_optional_json(run_dir / "playback.json"),
            )
        )

    if not runs:
        raise SystemExit(f"No run directories found in {results_dir}")
    return runs


def numeric_values(runs: list[Run], key: str) -> list[float]:
    values: list[float] = []
    for run in runs:
        value = run.statistics.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            values.append(float(value))
    return values


def optional_int(value: float | None) -> int | None:
    if value is None:
        return None
    if value.is_integer():
        return int(value)
    return None


def format_number(value: float | int | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return f"{value:,}"


def median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.fmean(values))


def row(label: str, values: list[float]) -> list[str]:
    return [
        label,
        str(len(values)),
        format_number(median(values)),
        format_number(mean(values)),
        format_number(min(values) if values else None),
        format_number(max(values) if values else None),
    ]


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    header_line = "  ".join(
        header.ljust(widths[index]) for index, header in enumerate(headers)
    )
    print(header_line)
    print("  ".join("-" * width for width in widths))
    for table_row in rows:
        print(
            "  ".join(
                value.rjust(widths[index]) if index else value.ljust(widths[index])
                for index, value in enumerate(table_row)
            )
        )


def print_summary(runs: list[Run], results_dir: Path) -> None:
    scores = numeric_values(runs, "score")
    print(f"Results: {results_dir}")
    print(f"Runs: {len(runs)}")
    print(f"Median score over {len(scores)} runs: {format_number(median(scores))}")

    model = first_metadata_value(runs, ("config", "model"))
    if model is not None:
        print(f"Model: {model}")
    print()

    metric_keys = [
        ("score", "Score"),
        ("dungeon_level", "Dungeon level"),
        ("gold", "Gold"),
        ("experience_level", "Experience level"),
        ("experience_points", "Experience points"),
        ("total_keys", "Keys pressed"),
        ("total_tokens", "Total tokens"),
        ("input_tokens", "Input tokens"),
        ("output_tokens", "Output tokens"),
        ("cache_read_tokens", "Cache read tokens"),
    ]
    rows = [row(label, numeric_values(runs, key)) for key, label in metric_keys]
    turns = [float(run.turns) for run in runs if run.turns is not None]
    rows.append(row("Agent turns", turns))
    print_table(["Metric", "n", "median", "mean", "min", "max"], rows)

    amulet_count = sum(run.statistics.get("has_amulet") is True for run in runs)
    print()
    print(f"Amulet found: {amulet_count}/{len(runs)}")

    terminations = Counter(
        str(run.metadata.get("terminated", "unknown")) for run in runs
    )
    print("Terminations: " + format_counter(terminations))

    print()
    print_per_run(runs)


def first_metadata_value(runs: list[Run], path: tuple[str, ...]) -> Any | None:
    for run in runs:
        value: Any = run.metadata
        for key in path:
            if not isinstance(value, dict) or key not in value:
                break
            value = value[key]
        else:
            return value
    return None


def format_counter(counter: Counter[str]) -> str:
    return ", ".join(f"{key}={count}" for key, count in counter.most_common())


def print_per_run(runs: list[Run]) -> None:
    rows: list[list[str]] = []
    for index, run in enumerate(runs, start=1):
        stats = run.statistics
        rows.append(
            [
                str(index),
                run.name,
                str(run.metadata.get("terminated", "unknown")),
                format_number(stats.get("score")),
                format_number(stats.get("dungeon_level")),
                format_number(stats.get("gold")),
                format_number(stats.get("experience_points")),
                format_number(stats.get("total_keys")),
                format_number(run.turns),
                format_number(stats.get("total_tokens")),
            ]
        )
    print_table(
        [
            "#",
            "Run",
            "terminated",
            "score",
            "dlvl",
            "gold",
            "xp",
            "keys",
            "turns",
            "tokens",
        ],
        rows,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate Rogue-Bench JSON logs for one result directory."
    )
    parser.add_argument(
        "results_dir",
        nargs="?",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help=(
            "Directory containing timestamped run folders "
            f"(default: {DEFAULT_RESULTS_DIR})"
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    runs = load_runs(args.results_dir)
    print_summary(runs, args.results_dir)


if __name__ == "__main__":
    main()
