"""Command-line interface.

    fingerprint merge --profile P --set S [EVENTS|-]
    fingerprint check PROFILE [PROFILE ...]
    fingerprint show SET

Folds a stream of JSONL events into a fingerprint set that grows across runs.
Knows nothing about where the events came from.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import AbstractContextManager, nullcontext
from datetime import UTC, datetime
from typing import IO, Any, Iterable

from fingerprint_sampler import __version__
from fingerprint_sampler.fingerprint_set import (
    Fingerprint,
    FingerprintSet,
    FingerprintSetError,
    ProfileMismatchError,
)
from fingerprint_sampler.profile import Profile, ProfileError, load_profile

EXIT_OK = 0
EXIT_LINES_SKIPPED = 1
EXIT_NOT_WRITTEN = 2
EXIT_HISTORY_NOT_WRITTEN = 3

_MAX_LINE_WARNINGS = 10

_MERGE_DESCRIPTION = (
    "Fingerprint every event in a JSONL stream using PROFILE and merge the results "
    "into the fingerprint set SET: counts add up, aggregates continue, new "
    "fingerprints are appended. SET is created if it does not exist. Each run's own "
    "fingerprints are also kept in SET's history directory."
)

_MERGE_EPILOG = """\
example:
  # first run creates web.fingerprints.yaml; every later run merges into it
  fingerprint merge -p access_log.yaml -s web.fingerprints.yaml access_log.jsonl

  # read events from a pipe
  tail -n 1000 app.jsonl | fingerprint merge -p app.yaml -s app.fingerprints.yaml -

  # trial run: write the merged result elsewhere, leave the set untouched
  fingerprint merge -p app.yaml -s app.fingerprints.yaml -o /tmp/preview.yaml new.jsonl

The SET file is updated in place (atomically) unless --output is given.

history:
  Every run that updates SET also writes just that run's fingerprints, with a
  'run:' header (times, source, counts), to <SET without extension>.history/,
  e.g. web.fingerprints.history/2026-10-14T193005Z.yaml. 'fingerprint show'
  reads it. A run with --output writes no history.

exit status:
  0  set written, every line was used
  1  set written, but some input lines were skipped (see stderr)
  2  nothing written (bad arguments, profile, set file, or profile mismatch)
  3  set written, but its history file was not (takes precedence over 1)
"""


_CHECK_EPILOG = """\
Structure is checked against the profile JSON Schema shipped with the package
(also usable by editors: see the README); regexes, JSONPaths, ranges, duplicate
keys and aggregate functions are checked as well. Every problem is listed.

exit status:
  0  every profile is valid
  1  at least one profile has problems (listed on stdout)
"""


_SHOW_EPILOG = """\
example:
  fingerprint show web.fingerprints.yaml
  fingerprint show web.fingerprints.yaml | less -S    # long values: scroll sideways

ID is the start of the fingerprint ID; times are UTC; '-' means no value.
Each % column is the fingerprint's share of the set total: COUNT % of all
events, and one value and % column per SUM or COUNT aggregate (key.FN when
the aggregate has several functions).

exit status:
  0  table printed
  2  SET could not be read
"""


def _say(message: str) -> None:
    print(message, file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fingerprint", description="Fingerprint and sample JSONL event streams."
    )
    parser.add_argument("--version", action="version", version=f"fingerprint-sampler {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    merge = commands.add_parser(
        "merge",
        help="merge a JSONL event stream into a fingerprint set",
        description=_MERGE_DESCRIPTION,
        epilog=_MERGE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    merge.add_argument(
        "-p",
        "--profile",
        required=True,
        metavar="PROFILE",
        help="YAML profile: which fields identify a fingerprint, what to aggregate",
    )
    merge.add_argument(
        "-s",
        "--set",
        required=True,
        metavar="SET",
        dest="set_path",
        help="fingerprint set file to merge into (created if missing, updated in place)",
    )
    merge.add_argument(
        "events",
        nargs="?",
        default="-",
        metavar="EVENTS",
        help="JSONL file of events, one JSON object per line; '-' or omitted reads stdin",
    )
    merge.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        help="write the merged set here instead, leaving SET unchanged",
    )
    merge.add_argument(
        "--force-profile",
        action="store_true",
        help="merge even if SET was built with a different profile "
        "(its existing fingerprints are kept as they are)",
    )
    merge.set_defaults(func=_cmd_merge)

    check = commands.add_parser(
        "check",
        help="check profiles and list every problem",
        description="Check one or more profiles without reading any events.",
        epilog=_CHECK_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    check.add_argument("profiles", nargs="+", metavar="PROFILE", help="YAML profile to check")
    check.set_defaults(func=_cmd_check)

    show = commands.add_parser(
        "show",
        help="print a fingerprint set as a table",
        description="Print one row per fingerprint in SET, most frequent first: "
        "its count and share of all events, when it was first and last seen, "
        "its summed and counted aggregates with their shares, and its tokens.",
        epilog=_SHOW_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    show.add_argument("set_path", metavar="SET", help="fingerprint set file to show")
    show.set_defaults(func=_cmd_show)
    return parser


def _cmd_check(args: argparse.Namespace) -> int:
    status = EXIT_OK
    for path in args.profiles:
        try:
            load_profile(path)
        except ProfileError as exc:
            status = 1
            for problem in exc.problems:
                print(problem)
        else:
            print(f"{path}: OK")
    return status


def _time(value: Any) -> str:
    """A stored time as UTC `YYYY-MM-DD HH:MM:SS` ('-' if absent; as stored if not a time)."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if not isinstance(value, datetime):
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _table(rows: list[list[str]]) -> str:
    """Rows of cells as text, each column padded to its widest cell."""
    widths = [max(len(cell) for cell in column) for column in zip(*rows)]
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip() for row in rows
    )


def _lookup(values: dict, key: str, function: str | None) -> Any:
    """`values[key]`, or `values[key][function]` for a multi-function aggregate; None if absent."""
    value = values.get(key)
    if function is not None:
        value = value.get(function) if isinstance(value, dict) else None
    return value


def _cell(value: Any) -> str:
    return "-" if value is None else str(value)


def _percent(value: Any) -> str:
    return "-" if value is None else f"{value:.1f}"


def _shared_columns(records: Iterable[Fingerprint]) -> list[tuple[str, str | None]]:
    """(aggregate key, function or None) of every shared aggregate value, in first-seen order."""
    columns: dict[tuple[str, str | None], None] = {}
    for record in records:
        for key, share in record.share.get("aggregates", {}).items():
            for function in share if isinstance(share, dict) else [None]:
                columns[key, function] = None
    return list(columns)


def _show_row(
    fid: str, record: Fingerprint, shared: list[tuple[str, str | None]], keys: list[str]
) -> list[str]:
    """One `show` row: ID, count and share, times, each shared value and share, tokens."""
    meta, shares = record.meta, record.share.get("aggregates", {})
    values = []
    for key, function in shared:
        values.append(_cell(_lookup(record.aggregates, key, function)))
        values.append(_percent(_lookup(shares, key, function)))
    return [
        fid[:8],
        _cell(meta.get("count")),
        _percent(record.share.get("meta", {}).get("count")),
        _time(meta.get("first_seen")),
        _time(meta.get("last_seen")),
        *values,
        *(str(record.tokens.get(key, "-")) for key in keys),
    ]


def _show_table(records: list[tuple[str, Fingerprint]]) -> str:
    """The `show` table: a header, then one row per fingerprint, most frequent first."""
    records = sorted(records, key=lambda item: -item[1].meta.get("count", 0))  # ties: file order
    keys = sorted({key for _, record in records for key in record.tokens})
    shared = _shared_columns(record for _, record in records)
    names = [key if function is None else f"{key}.{function}" for key, function in shared]
    header = ["ID", "COUNT", "COUNT %", "FIRST SEEN", "LAST SEEN"]
    header += [column for name in names for column in (name, f"{name} %")] + keys
    return _table([header] + [_show_row(fid, record, shared, keys) for fid, record in records])


def _cmd_show(args: argparse.Namespace) -> int:
    fingerprints = FingerprintSet()
    try:
        fingerprints.load(args.set_path)
    except (FingerprintSetError, OSError) as exc:
        _say(f"fingerprint: cannot use set file: {exc}")
        return EXIT_NOT_WRITTEN
    records = [(fid, fingerprints.get(fid)) for fid in fingerprints]
    if not records:
        print(f"{args.set_path}: no fingerprints")
        return EXIT_OK
    print(_show_table(records))
    return EXIT_OK


def _fold_stream(
    lines: Iterable[str], profile: Profile, fingerprints: FingerprintSet, run: FingerprintSet
) -> dict:
    """Fingerprint each JSONL line into `fingerprints` and into `run` (this run only).

    Both get the same timestamp per event, so their times agree. Returns run statistics.
    """
    known_before = set(fingerprints)
    seen: set[str] = set()
    events = skipped_lines = 0

    def warn(lineno: int, reason: str) -> None:
        if skipped_lines <= _MAX_LINE_WARNINGS:
            _say(f"fingerprint: line {lineno}: {reason} - skipped")
        elif skipped_lines == _MAX_LINE_WARNINGS + 1:
            _say("fingerprint: further skipped lines are counted but not listed")

    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            skipped_lines += 1
            warn(lineno, f"invalid JSON ({exc.msg} at column {exc.colno})")
            continue
        if not isinstance(event, dict):
            skipped_lines += 1
            warn(lineno, f"expected a JSON object, got {type(event).__name__}")
            continue
        tokens, timestamp = profile.tokens(event), datetime.now(UTC).isoformat()
        run.upsert(tokens, event, timestamp)
        seen.add(fingerprints.upsert(tokens, event, timestamp))
        events += 1

    return {
        "events": events,
        "skipped_lines": skipped_lines,
        "new": len(seen - known_before),
        "updated": len(seen & known_before),
    }


class _NotWritten(Exception):
    """A merge step failed, so nothing is written. The message says why (possibly several lines)."""


def _load_profile(path: str) -> Profile:
    try:
        return load_profile(path)
    except ProfileError as exc:
        lines = [f"fingerprint: {problem}" for problem in exc.problems]
        lines.append(f"  nothing written; 'fingerprint check {path}' lists the same problems")
        raise _NotWritten("\n".join(lines)) from exc


def _open_set(args: argparse.Namespace, profile: Profile) -> FingerprintSet:
    fingerprints = FingerprintSet(profile.aggregates, profile.profile_id)
    if not os.path.exists(args.set_path):
        return fingerprints
    try:
        fingerprints.load(args.set_path, force=args.force_profile)
    except ProfileMismatchError as exc:
        raise _NotWritten(
            f"fingerprint: {exc}.\n"
            "  Fingerprints from different profiles are not comparable, so nothing was merged.\n"
            "  Use a separate --set file for this profile, or pass --force-profile to merge anyway."
        ) from exc
    except (FingerprintSetError, OSError) as exc:
        raise _NotWritten(f"fingerprint: cannot use set file: {exc}") from exc
    return fingerprints


def _open_events(args: argparse.Namespace) -> AbstractContextManager[IO[str]]:
    if args.events != "-":
        try:
            return open(args.events, encoding="utf-8", errors="replace")  # noqa: SIM115
        except OSError as exc:
            reason = exc.strerror or exc
            raise _NotWritten(
                f"fingerprint: cannot read events from {args.events}: {reason}"
            ) from exc
    if sys.stdin.isatty():
        raise _NotWritten(
            "fingerprint: no events to read. Name a JSONL file, or pipe events in:\n"
            f"  fingerprint merge -p {args.profile} -s {args.set_path} events.jsonl\n"
            f"  some-command | fingerprint merge -p {args.profile} -s {args.set_path} -"
        )
    return nullcontext(sys.stdin)


def _source(args: argparse.Namespace) -> str:
    return "stdin" if args.events == "-" else args.events


def _history_path(set_path: str, started: datetime) -> str:
    """A new file in `<set without extension>.history/`, named by UTC start time (STORY-FING-48).

    Creates the directory. A run starting in the same second as an earlier one gets _2, _3, ... (sorts after the first)
    """
    directory = os.path.splitext(set_path)[0] + ".history"
    os.makedirs(directory, exist_ok=True)
    stem = started.strftime("%Y-%m-%dT%H%M%SZ")
    path, n = os.path.join(directory, f"{stem}.yaml"), 2
    while os.path.exists(path):
        path, n = os.path.join(directory, f"{stem}_{n}.yaml"), n + 1
    return path


def _write_history(
    args: argparse.Namespace, run: FingerprintSet, stats: dict, started: datetime
) -> str:
    """Save this run's own set, with its `run:` header, to SET's history. Returns its path."""
    run.run = {
        "started": started.isoformat(),
        "finished": datetime.now(UTC).isoformat(),
        "source": _source(args),
        "events": stats["events"],
        "skipped_lines": stats["skipped_lines"],
        "set": args.set_path,
    }
    path = _history_path(args.set_path, started)
    run.save(path)
    return path


def _report(
    args: argparse.Namespace,
    stats: dict,
    fingerprints: FingerprintSet,
    profile: Profile,
    *,
    existed: bool,
) -> None:
    source = _source(args)
    destination = args.output or args.set_path
    verb = "updated" if existed and not args.output else "wrote"
    _say(f"fingerprint: {stats['events']} events read from {source}")
    _say(
        f"  fingerprints: {stats['new']} new, {stats['updated']} updated, "
        f"{len(fingerprints)} total in set"
    )
    _say(
        f"  skipped: {stats['skipped_lines']} malformed lines, "
        f"{fingerprints.skipped_values} unusable aggregate values"
    )
    _say(f"  {verb} {destination} (profile {profile.profile_id})")
    if args.output:
        _say(f"  {args.set_path} left unchanged")


def _cmd_merge(args: argparse.Namespace) -> int:
    started = datetime.now(UTC)
    destination = args.output or args.set_path
    existed = os.path.exists(args.set_path)
    try:
        profile = _load_profile(args.profile)
        fingerprints = _open_set(args, profile)
        run = FingerprintSet(profile.aggregates, profile.profile_id)
        with _open_events(args) as stream:
            stats = _fold_stream(stream, profile, fingerprints, run)
        try:
            fingerprints.save(destination)
        except OSError as exc:
            raise _NotWritten(
                f"fingerprint: cannot write {destination}: {exc.strerror or exc}"
            ) from exc
    except _NotWritten as exc:
        _say(str(exc))
        return EXIT_NOT_WRITTEN
    except KeyboardInterrupt:
        _say(f"fingerprint: interrupted - {destination} was not modified")
        return 130
    _report(args, stats, fingerprints, profile, existed=existed)
    status = EXIT_LINES_SKIPPED if stats["skipped_lines"] else EXIT_OK
    if args.output:
        return status
    try:
        _say(f"  history: {_write_history(args, run, stats, started)}")
    except OSError as exc:
        _say(
            f"fingerprint: {args.set_path} updated, but history not written: {exc.strerror or exc}"
        )
        return EXIT_HISTORY_NOT_WRITTEN
    return status


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
