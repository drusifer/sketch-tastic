"""Generic ranked skits, original sample export and weighted corpus coverage.

Identity always comes from the profile. Coverage measures represented baseline
observations, never test execution, branch coverage or population completeness.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator

from sketchtastic.profile import load_profile
from sketchtastic.sketch import Sketch, SketchError, Skit, _read_set_file, skit_id

MAX_LINE_BYTES = 4 * 1024 * 1024


def safe_text(value: Any) -> str:
    """Escape terminal controls and non-ASCII characters without changing stored records."""
    return json.dumps(str(value), ensure_ascii=True)[1:-1]


def _limit(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("limit must be a nonnegative integer (0 means all)")


def _ranked(path: Path | str, profile_id: str | None = None) -> list[tuple[str, Skit]]:
    """Load through the normal sketch API, then validate the metadata used here."""
    sketch = Sketch(profile_id=profile_id)
    try:
        if profile_id is not None:
            stored = _read_set_file(str(path)).get("profile_id")
            if stored != profile_id:
                raise ValueError(
                    f"Baseline profile {stored!r} does not match profile {profile_id!r}"
                )
        sketch.load(str(path))
        rows = [(key, sketch.get(key)) for key in sketch]
        for key, skit in rows:
            if not isinstance(key, str) or not isinstance(skit.tokens, dict):
                raise ValueError("Malformed skit identity")
            if any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in skit.tokens.items()
            ):
                raise ValueError(f"Malformed tokens for skit {key!r}")
            if key != skit_id(skit.tokens):
                raise ValueError(f"Skit ID {key!r} does not match its tokens")
            count = skit.meta.get("count")
            if type(count) is not int or count < 0:
                raise ValueError(f"Invalid count for skit {key!r}: expected nonnegative integer")
    except (AttributeError, KeyError, TypeError) as exc:
        raise SketchError(f"Malformed sketch: {path}") from exc
    return sorted(rows, key=lambda item: (-item[1].meta["count"], item[0]))


def _fraction(numerator: int, denominator: int) -> str:
    percent = f"{100 * numerator / denominator:.1f}%" if denominator else "N/A"
    return f"{percent} ({numerator:,} / {denominator:,})"


def _tokens(skit: Skit) -> str:
    return json.dumps(skit.tokens, ensure_ascii=True, separators=(",", ":"))


def _locator(path: Path | str, key: str) -> str:
    return f"{safe_text(path)}:skits[{safe_text(key)}].meta.first[0].record"


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
        lines.append(f"  sample: {_locator(path, key)}")
    if not rows:
        lines.append("No kinds.")
    elif limit and len(rows) > limit:
        lines.append(f"Showing {limit:,} of {len(rows):,} kinds; --limit 0 shows all.")
    return lines


def report(sketch_path: Path | str, limit: int = 20) -> str:
    """Rank generic skits by observed frequency, with copyable IDs and retained sample paths."""
    _limit(limit)
    rows = _ranked(sketch_path)
    total = sum(skit.meta["count"] for _, skit in rows)
    lines = [
        "SKETCH KIND REPORT",
        f"Sketch: {safe_text(sketch_path)}",
        f"Baseline observations: {total:,}; kinds: {len(rows):,}",
        "Scope: observations in this sketch; not a complete population inventory.",
    ]
    lines.extend(_rows_text(rows, total, sketch_path, limit))
    return "\n".join(lines)


def _sample(key: str, skit: Skit) -> dict:
    try:
        record = skit.meta["first"][0]["record"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Skit {key} has no retained first record") from exc
    if not isinstance(record, dict):
        raise ValueError(f"Skit {key} does not retain a JSON object")
    return record


def export_samples(
    sketch_path: Path | str, output: Path | str, ids: list[str] | None = None
) -> list[str]:
    """Publish one original retained object per selected kind, never replacing output."""
    rows = _ranked(sketch_path)
    available = {key for key, _ in rows}
    selected = available if ids is None else set(ids)
    unknown = selected - available
    if unknown:
        raise ValueError(f"Unknown skit IDs: {', '.join(sorted(unknown))}")
    rows = [(key, skit) for key, skit in rows if key in selected]
    # Validate every selected record before creating even a temporary output.
    records = [_sample(key, skit) for key, skit in rows]
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}")
    with tempfile.TemporaryDirectory(prefix=".skt-export-", dir=output.parent) as staging:
        staged = Path(staging) / "samples.jsonl"
        with staged.open("w", encoding="utf-8") as stream:
            for (key, _), record in zip(rows, records):
                try:
                    line = json.dumps(record, ensure_ascii=True, allow_nan=False)
                except (TypeError, ValueError, RecursionError) as exc:
                    raise ValueError(f"Skit {key} retained record is not JSON: {exc}") from exc
                stream.write(line + "\n")
        os.link(staged, output)
    return [key for key, _ in rows]


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant {value}")


def _objects(path: Path | str) -> Iterator[dict]:
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


def coverage(
    baseline_path: Path | str,
    profile_path: Path | str,
    regression_path: Path | str,
    limit: int = 20,
) -> str:
    """Measure distinct-kind and baseline-frequency representation of a regression corpus."""
    _limit(limit)
    profile = load_profile(str(profile_path))
    rows = _ranked(baseline_path, profile.profile_id)
    baseline = {key for key, _ in rows}
    candidate: dict[str, dict[str, str]] = {}
    for record in _objects(regression_path):
        tokens = profile.tokens(record)
        candidate[skit_id(tokens)] = tokens
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
    lines.extend(["", f"Unknown regression kinds: {len(unknown):,}"])
    for key in unknown[: limit or None]:
        lines.append(f"{key}  {json.dumps(candidate[key], ensure_ascii=True)}")
    if limit and len(unknown) > limit:
        lines.append(f"Showing {limit:,} of {len(unknown):,} unknown kinds; --limit 0 shows all.")
    return "\n".join(lines)


def analyze_to_html(
    sketch_path: Path | str,
    output: Path | str,
    *,
    history_dir: Path | str | None = None,
    title: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Analyze a sketch (and optional history) and atomically write an offline HTML dashboard."""
    from sketchtastic.analysis import analyze_sketch
    from sketchtastic.dashboard import render_dashboard

    out = Path(output)
    if out.is_symlink():
        raise ValueError(f"Output must not be a symlink: {out}")
    if out.is_dir():
        raise IsADirectoryError(f"Output is a directory: {out}")
    if not force and out.exists():
        raise FileExistsError(f"Output already exists: {out} (pass --force to overwrite)")
    if not out.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {out.parent}")

    payload = analyze_sketch(sketch_path, history_dir=history_dir)
    document = render_dashboard(payload, title=title)

    with tempfile.TemporaryDirectory(prefix=".skt-analyze-", dir=out.parent) as staging:
        staged = Path(staging) / "dashboard.html"
        staged.write_text(document, encoding="utf-8")
        if out.is_symlink():
            raise ValueError(f"Output must not be a symlink: {out}")
        if force:
            os.replace(staged, out)
        else:
            os.link(staged, out)

    return {
        "total_observations": payload["meta"]["total_observations"],
        "total_skits": payload["meta"]["total_skits"],
        "history_runs": len(payload["history"]["runs"]),
    }


def _command(args: argparse.Namespace) -> int:
    try:
        if args.command == "report":
            text = report(args.sketch_path, args.limit)
        elif args.command == "export":
            ids = export_samples(args.sketch_path, args.output, args.ids)
            lines = [f"Exported {len(ids):,} original samples to {safe_text(args.output)}"]
            lines.extend(
                f"{key}  {safe_text(args.output)}:{index}" for index, key in enumerate(ids, 1)
            )
            text = "\n".join(lines)
        elif args.command == "analyze":
            summary = analyze_to_html(
                args.sketch_path,
                args.output,
                history_dir=args.history,
                title=args.title,
                force=args.force,
            )
            text = (
                f"Wrote interactive dashboard to {safe_text(args.output)} "
                f"({summary['total_observations']:,} observations, "
                f"{summary['total_skits']:,} skits, "
                f"{summary['history_runs']:,} history runs)"
            )
        else:
            text = coverage(args.sketch_path, args.profile, args.regression, args.limit)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"sketchtastic: {safe_text(exc)}", file=sys.stderr)
        return 2
    print(text)
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:
    """Register generic commands without coupling reporting to the merge implementation."""
    for name, help_text in (
        ("report", "rank skits by frequency and locate original samples"),
        ("export", "export original representative JSON objects to a new JSONL file"),
        ("coverage", "measure regression sample representation against a baseline sketch"),
        ("analyze", "generate an interactive offline HTML analysis dashboard for a sketch"),
    ):
        parser = commands.add_parser(name, help=help_text, description=help_text)
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
        parser.set_defaults(func=_command)
