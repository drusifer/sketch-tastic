"""Generic ranked skits, original sample export, coverage and dashboard CLI commands.

Identity always comes from the profile. Coverage measures represented baseline
observations, never test execution, branch coverage or population completeness.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sketchtastic._io import (
    publish_file,
    publish_new_file,
    safe_text,
    sample_locator,
    validate_output_target,
)
from sketchtastic.analysis import analyze_sketch
from sketchtastic.dashboard import render_dashboard
from sketchtastic.profile import load_profile
from sketchtastic.sketch import Skit, load_ranked_skits, skit_id

MAX_LINE_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class AnalyzeOptions:
    """Optional configuration for `analyze_to_html`."""

    history_dir: Path | str | None = None
    title: str | None = None
    default_weight: str | None = None
    force: bool = False


def _limit(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("limit must be a nonnegative integer (0 means all)")


def _fraction(numerator: int, denominator: int) -> str:
    percent = f"{100 * numerator / denominator:.1f}%" if denominator else "N/A"
    return f"{percent} ({numerator:,} / {denominator:,})"


def _tokens(skit: Skit) -> str:
    return json.dumps(skit.tokens, ensure_ascii=True, separators=(",", ":"))


def _rows_text(rows: list[tuple[str, Skit]], total: int, path: Path | str, limit: int) -> list[str]:
    lines = ["SKIT ID                           COUNT    WEIGHT  CUMULATIVE  TOKENS"]
    cumulative = 0
    for key, skit in rows[: limit or None]:
        count = skit.meta["count"]
        cumulative += count
        weight = f"{100 * count / total:.1f}%" if total else "N/A"
        share = f"{100 * cumulative / total:.1f}%" if total else "N/A"
        lines.append(f"{key} {count:9,} {weight:>9} {share:>11}  {_tokens(skit)}")
        if skit.aggregates:
            values = json.dumps(
                skit.aggregates, ensure_ascii=True, default=str, separators=(",", ":")
            )
            lines.append(f"  aggregates: {values}")
        lines.append(f"  sample: {sample_locator(path, key)}")
    if not rows:
        lines.append("No kinds.")
    elif limit and len(rows) > limit:
        lines.append(f"Showing {limit:,} of {len(rows):,} kinds; --limit 0 shows all.")
    return lines


def report(sketch_path: Path | str, limit: int = 20) -> str:
    """Rank generic skits by observed frequency, with copyable IDs and retained sample paths."""
    _limit(limit)
    _, rows = load_ranked_skits(sketch_path)
    total = sum(skit.meta["count"] for _, skit in rows)
    lines = [
        "SKETCH KIND REPORT",
        f"Sketch: {safe_text(sketch_path)}",
        f"Baseline observations: {total:,}; kinds: {len(rows):,}",
        "Scope: observations in this sketch; not a complete population inventory.",
    ]
    lines.extend(_rows_text(rows, total, sketch_path, limit))
    return "\n".join(lines)


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


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant {value}")


def _objects(path: Path | str) -> Iterator[dict[str, Any]]:
    """Read bounded, strict UTF-8 JSON object lines; a bad line aborts the whole comparison."""
    with open(path, "rb") as stream:
        line_number = 0
        while raw := stream.readline(MAX_LINE_BYTES + 1):
            line_number += 1
            try:
                if len(raw) > MAX_LINE_BYTES:
                    raise ValueError("exceeds 4 MiB line limit")
                if not raw.strip():
                    continue
                record = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
                if not isinstance(record, dict):
                    raise ValueError("expected a JSON object")
            except (ValueError, RecursionError) as exc:
                raise ValueError(f"{path}: line {line_number}: {exc}") from exc
            yield record


def _unknown_section(
    unknown: list[str], candidate: dict[str, dict[str, str]], limit: int
) -> list[str]:
    lines = ["", f"Unknown regression kinds: {len(unknown):,}"]
    for key in unknown[: limit or None]:
        lines.append(f"{key}  {json.dumps(candidate[key], ensure_ascii=True)}")
    if limit and len(unknown) > limit:
        lines.append(f"Showing {limit:,} of {len(unknown):,} unknown kinds; --limit 0 shows all.")
    return lines


def coverage(
    baseline_path: Path | str,
    profile_path: Path | str,
    regression_path: Path | str,
    limit: int = 20,
) -> str:
    """Measure distinct-kind and baseline-frequency representation of a regression corpus."""
    _limit(limit)
    profile = load_profile(str(profile_path))
    _, rows = load_ranked_skits(baseline_path, profile.profile_id)
    baseline = {key for key, _ in rows}
    candidate = {
        skit_id(tokens): tokens
        for record in _objects(regression_path)
        for tokens in (profile.tokens(record),)
    }
    covered = baseline.intersection(candidate)
    unknown = sorted(set(candidate) - baseline)
    total = sum(skit.meta["count"] for _, skit in rows)
    weight = sum(skit.meta["count"] for key, skit in rows if key in covered)
    missing = [(key, skit) for key, skit in rows if key not in covered]
    lines = [
        "REGRESSION SAMPLE COVERAGE",
        f"Baseline: {safe_text(baseline_path)}",
        f"Regression: {safe_text(regression_path)}",
        f"Profile: {profile.profile_id}",
        "Scope: observations in the baseline sketch, not the whole population.",
        f"Baseline-frequency coverage: {_fraction(weight, total)}",
        f"Distinct-kind coverage: {_fraction(len(covered), len(baseline))}",
        "This measures sample representation, not test execution or branch coverage.",
        "Repeated regression samples do not add coverage.",
        "",
        "UNCOVERED BASELINE KINDS",
    ]
    lines.extend(_rows_text(missing, total, baseline_path, limit))
    lines.extend(_unknown_section(unknown, candidate, limit))
    return "\n".join(lines)


def analyze_to_html(
    sketch_path: Path | str,
    output: Path | str,
    options: AnalyzeOptions | None = None,
) -> dict[str, Any]:
    """Analyze a sketch (and optional history) and atomically write an offline HTML dashboard."""
    opts = options or AnalyzeOptions()
    # Validate target before running analysis so bad paths fail fast.
    out = validate_output_target(output, force=opts.force)

    payload = analyze_sketch(
        sketch_path, history_dir=opts.history_dir, default_weight=opts.default_weight
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
    }


def _dispatch_command(args: argparse.Namespace) -> str:
    if args.command == "report":
        return report(args.sketch_path, args.limit)
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
        )
        summary = analyze_to_html(args.sketch_path, args.output, opts)
        return (
            f"Wrote interactive dashboard to {safe_text(args.output)} "
            f"({summary['total_observations']:,} observations, "
            f"{summary['total_skits']:,} skits, "
            f"{summary['history_runs']:,} history runs)"
        )
    return coverage(args.sketch_path, args.profile, args.regression, args.limit)


def _command(args: argparse.Namespace) -> int:
    try:
        text = _dispatch_command(args)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"sketch: {safe_text(exc)}", file=sys.stderr)
        return 2
    print(text)
    return 0


def _configure_subparser(name: str, parser: argparse.ArgumentParser) -> None:
    parser.add_argument("sketch_path", metavar="BASELINE" if name == "coverage" else "SKETCH")
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
    else:
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="maximum rows per list (default 20; 0 means all)",
        )
    if name == "coverage":
        parser.add_argument("-p", "--profile", required=True, metavar="PROFILE")
        parser.add_argument("regression", metavar="REGRESSION.jsonl")


def add_commands(commands: argparse._SubParsersAction) -> None:
    """Register generic commands without coupling reporting to the merge implementation."""
    for name, help_text in (
        ("report", "rank skits by frequency and locate original samples"),
        ("export", "export original representative JSON objects to a new JSONL file"),
        ("coverage", "measure regression sample representation against a baseline sketch"),
        ("analyze", "generate an interactive offline HTML analysis dashboard for a sketch"),
    ):
        parser = commands.add_parser(name, help=help_text, description=help_text)
        _configure_subparser(name, parser)
        parser.set_defaults(func=_command)
