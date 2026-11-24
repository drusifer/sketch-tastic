"""Generic original sample export and dashboard (with regression coverage) CLI commands.

Identity always comes from the profile. Coverage measures represented baseline
observations, never test execution, branch coverage or population completeness.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sketchtastic._io import (
    publish_file,
    publish_new_file,
    safe_text,
    validate_output_target,
)
from sketchtastic.analysis import analyze_sketch
from sketchtastic.dashboard import render_dashboard
from sketchtastic.sketch import Skit, load_ranked_skits


@dataclass(frozen=True)
class AnalyzeOptions:
    """Optional configuration for `analyze_to_html`."""

    history_dir: Path | str | None = None
    title: str | None = None
    default_weight: str | None = None
    force: bool = False
    profile: Path | str | None = None
    regression: Path | str | None = None


def _sample(key: str, skit: Skit) -> dict[str, Any]:
    try:
        record = skit.meta["first"][0]["record"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Skit {key} has no retained first record") from exc
    if not isinstance(record, dict):
        raise ValueError(f"Skit {key} does not retain a JSON object")
    return record


def _select_rows(rows: list[tuple[str, Skit]], ids: list[str] | None) -> list[tuple[str, Skit]]:
    if ids is None:
        return rows
    available = {key for key, _ in rows}
    selected = set(ids)
    unknown = selected - available
    if unknown:
        raise ValueError(f"Unknown skit IDs: {', '.join(sorted(unknown))}")
    return [(key, skit) for key, skit in rows if key in selected]


def _serialize_sample_lines(rows: list[tuple[str, Skit]]) -> list[str]:
    records = [_sample(key, skit) for key, skit in rows]
    lines: list[str] = []
    for (key, _), record in zip(rows, records):
        try:
            lines.append(json.dumps(record, ensure_ascii=True, allow_nan=False))
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError(f"Skit {key} retained record is not JSON: {exc}") from exc
    return lines


def export_samples(
    sketch_path: Path | str, output: Path | str, ids: list[str] | None = None
) -> list[str]:
    """Publish one original retained object per selected kind, never replacing output."""
    _, all_rows = load_ranked_skits(sketch_path)
    rows = _select_rows(all_rows, ids)
    # Validate and serialize every selected record before creating even a temporary output.
    lines = _serialize_sample_lines(rows)
    content = "".join(line + "\n" for line in lines)
    publish_new_file(
        output,
        ".skt-export-",
        "samples.jsonl",
        lambda staged: staged.write_text(content, encoding="utf-8"),
    )
    return [key for key, _ in rows]


def analyze_to_html(
    sketch_path: Path | str,
    output: Path | str,
    options: AnalyzeOptions | None = None,
) -> dict[str, Any]:
    """Analyze a sketch (and optional history) and atomically write an offline HTML dashboard."""
    opts = options or AnalyzeOptions()
    # Validate target before running analysis so bad paths fail fast.
    if (opts.profile is None) != (opts.regression is None):
        raise ValueError("--regression and --profile must be given together")
    out = validate_output_target(output, force=opts.force)

    payload = analyze_sketch(
        sketch_path,
        history_dir=opts.history_dir,
        default_weight=opts.default_weight,
        regression=(opts.profile, opts.regression) if opts.regression is not None else None,
    )
    document = render_dashboard(payload, title=opts.title)
    publish_file(
        out,
        ".skt-analyze-",
        "dashboard.html",
        lambda staged: staged.write_text(document, encoding="utf-8"),
        force=opts.force,
    )
    return {
        "total_observations": payload["meta"]["total_observations"],
        "total_skits": payload["meta"]["total_skits"],
        "history_runs": len(payload["history"]["runs"]),
        "coverage": payload["coverage"],
    }


def _dispatch_command(args: argparse.Namespace) -> str:
    if args.command == "export":
        ids = export_samples(args.sketch_path, args.output, args.ids)
        lines = [f"Exported {len(ids):,} original samples to {safe_text(args.output)}"]
        lines.extend(f"{key}  {safe_text(args.output)}:{index}" for index, key in enumerate(ids, 1))
        return "\n".join(lines)
    if args.command == "analyze":
        opts = AnalyzeOptions(
            history_dir=args.history,
            title=args.title,
            default_weight=args.weight,
            force=args.force,
            profile=args.profile,
            regression=args.regression,
        )
        summary = analyze_to_html(args.sketch_path, args.output, opts)
        text = (
            f"Wrote interactive dashboard to {safe_text(args.output)} "
            f"({summary['total_observations']:,} observations, "
            f"{summary['total_skits']:,} skits, "
            f"{summary['history_runs']:,} history runs)"
        )
        cov = summary["coverage"]
        if cov is not None:
            text += (
                f"\nRegression coverage: {len(cov['covered_ids']):,} of "
                f"{summary['total_skits']:,} kinds covered; "
                f"{cov['unknown_count']:,} regression kinds not in the baseline"
            )
        return text
    raise AssertionError(f"unknown command {args.command}")


def _command(args: argparse.Namespace) -> int:
    try:
        text = _dispatch_command(args)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"sketch: {safe_text(exc)}", file=sys.stderr)
        return 2
    print(text)
    return 0


def _configure_subparser(name: str, parser: argparse.ArgumentParser) -> None:
    parser.add_argument("sketch_path", metavar="SKETCH")
    if name == "export":
        parser.add_argument("--output", required=True, metavar="NEW.jsonl")
        parser.add_argument(
            "--id",
            dest="ids",
            action="append",
            metavar="FULL_ID",
            help="select this full skit ID; repeat to select several (default all)",
        )
    elif name == "analyze":
        parser.add_argument("-o", "--output", required=True, metavar="REPORT.html")
        parser.add_argument(
            "--history",
            metavar="DIR",
            help="history directory of run files (default: auto-detect <sketch>.history)",
        )
        parser.add_argument(
            "--title",
            metavar="TEXT",
            help="dashboard page title (default: sketch filename)",
        )
        parser.add_argument(
            "--weight",
            metavar="KEY",
            help="initial dashboard weighting: 'count' or any additive numeric aggregate key",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="overwrite an existing regular output file",
        )
        parser.add_argument(
            "--regression",
            metavar="REGRESSION.jsonl",
            help="regression corpus of original records: show which kinds it covers, "
            "for the sketch and for every history run (needs --profile)",
        )
        parser.add_argument(
            "-p",
            "--profile",
            metavar="PROFILE",
            help="the sketch's profile, used to tokenize --regression records",
        )


def add_commands(commands: argparse._SubParsersAction) -> None:
    """Register generic commands without coupling reporting to the merge implementation."""
    for name, help_text in (
        ("export", "export original representative JSON objects to a new JSONL file"),
        ("analyze", "generate an interactive offline HTML analysis dashboard for a sketch"),
    ):
        parser = commands.add_parser(name, help=help_text, description=help_text)
        _configure_subparser(name, parser)
        parser.set_defaults(func=_command)
