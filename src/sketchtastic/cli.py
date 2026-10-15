"""Command-line interface.

    sketchtastic merge --profile P --sketch S [EVENTS|-]
    sketchtastic check PROFILE [PROFILE ...]
    sketchtastic show [--sort KEY] SKETCH

Folds a stream of JSONL events into a sketch that grows across runs.
Knows nothing about where the events came from.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import AbstractContextManager, nullcontext
from datetime import UTC, date, datetime
from typing import IO, Any, Callable, Iterable, NamedTuple

from sketchtastic import __version__
from sketchtastic.aggregators import as_number
from sketchtastic.model import Path
from sketchtastic.profile import Profile, ProfileError, load_profile
from sketchtastic.sketch import (
    ProfileMismatchError,
    Sketch,
    SketchError,
    Skit,
)

EXIT_OK = 0
EXIT_LINES_SKIPPED = 1
EXIT_NOT_WRITTEN = 2
EXIT_HISTORY_NOT_WRITTEN = 3

_MAX_LINE_WARNINGS = 10

_MERGE_DESCRIPTION = (
    "Reduce every event in a JSONL stream to a skit using PROFILE and merge them "
    "into the sketch SKETCH: counts add up, aggregates continue, new skits are "
    "appended. SKETCH is created if it does not exist. Each run's own skits are "
    "also kept in SKETCH's history directory."
)

_MERGE_EPILOG = """\
example:
  # first run creates web.sketch.yaml; every later run merges into it
  sketchtastic merge -p access_log.yaml -s web.sketch.yaml access_log.jsonl

  # read events from a pipe
  tail -n 1000 app.jsonl | sketchtastic merge -p app.yaml -s app.sketch.yaml -

  # trial run: write the merged result elsewhere, leave the sketch untouched
  sketchtastic merge -p app.yaml -s app.sketch.yaml -o /tmp/preview.yaml new.jsonl

The SKETCH file is updated in place (atomically) unless --output is given.

history:
  Each run gets an id, YYMMDD-SEQ (UTC date, then a number that only goes up
  for this sketch), e.g. 261015-0003. Skits record the first and last run
  that saw them. Every run that updates SKETCH also writes just that run's
  skits, with a 'run:' header (id, times, source, counts), to
  <SKETCH without extension>.history/<run id>.yaml, e.g.
  web.sketch.history/261015-0003.yaml; 'sketchtastic show' reads it.
  A run with --output writes no history and uses up no run id.

duplicate protection:
  If the profile names a sequence (e.g. 'sequence: $.id', a number in each
  event that only grows), SKETCH keeps the highest one merged. Later runs drop
  events at or below it, so re-running over the same or overlapping input
  adds nothing twice; the summary says how many were dropped. An event without
  a usable sequence (missing, several values, not a number) is an error: the
  run fails and nothing is written (exit status 2).

exit status:
  0  sketch written, every line was used
  1  sketch written, but some input lines were skipped (see stderr)
  2  nothing written (bad arguments, profile, sketch file, profile mismatch, or an
     event without the sequence the profile declares)
  3  sketch written, but its history file was not (takes precedence over 1)
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
examples:
  sketchtastic show web.sketch.yaml
  sketchtastic show web.sketch.yaml | less -S    # long values: scroll sideways
  sketchtastic show --sort 'payload_bytes.SUM %' gh.sketch.yaml | tail

ID is the start of the skit ID; FIRST RUN and LAST RUN are the ids of
the first and last run that saw it (see 'sketchtastic merge --help'); '-' means
no value.
Each % column is the skit's share of the sketch total: COUNT % of all
events, and one value and % column per SUM or COUNT aggregate (key.FN when
the aggregate has several functions).
Rows are sorted by KEY, lowest first, so the largest are at the end; '-'
sorts first, numbers before text, and equal values keep file order.

exit status:
  0  table printed
  2  SKETCH could not be read, or KEY is not one of its columns
"""


def _say(message: str) -> None:
    print(message, file=sys.stderr)


def _prog() -> str:
    """The command as invoked (`sketchtastic` or `skt`); `sketchtastic` for `python -m`."""
    name = os.path.basename(sys.argv[0]) if sys.argv else ""
    return name if name in ("sketchtastic", "skt") else "sketchtastic"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=_prog(), description="Mergeable sketches of JSONL event streams."
    )
    parser.add_argument("--version", action="version", version=f"sketch-tastic {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    merge = commands.add_parser(
        "merge",
        help="merge a JSONL event stream into a sketch",
        description=_MERGE_DESCRIPTION,
        epilog=_MERGE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    merge.add_argument(
        "-p",
        "--profile",
        required=True,
        metavar="PROFILE",
        help="YAML profile: which fields identify a skit, what to aggregate",
    )
    merge.add_argument(
        "-s",
        "--sketch",
        required=True,
        metavar="SKETCH",
        dest="sketch_path",
        help="sketch file to merge into (created if missing, updated in place)",
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
        help="write the merged sketch here instead, leaving SKETCH unchanged",
    )
    merge.add_argument(
        "--force-profile",
        action="store_true",
        help="merge even if SKETCH was built with a different profile "
        "(its existing skits are kept as they are)",
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
        help="print a sketch as a table",
        description="Print one row per skit in SKETCH, least frequent first: "
        "its count and share of all events, the first and last run that saw it, "
        "its summed and counted aggregates with their shares, and its tokens.",
        epilog=_SHOW_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    show.add_argument(
        "--sort",
        metavar="KEY",
        default="COUNT",
        help="sort by the column with this header, in any case (default: COUNT)",
    )
    show.add_argument("sketch_path", metavar="SKETCH", help="sketch file to show")
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


def _shared_columns(records: Iterable[Skit]) -> list[tuple[str, str | None]]:
    """(aggregate key, function or None) of every shared aggregate value, in first-seen order."""
    columns: dict[tuple[str, str | None], None] = {}
    for record in records:
        for key, share in record.share.get("aggregates", {}).items():
            for function in share if isinstance(share, dict) else [None]:
                columns[key, function] = None
    return list(columns)


class _Column(NamedTuple):
    """One `show` column: its header, its raw value for a skit, and how that value prints."""

    header: str
    value: Callable[[str, Skit], Any]
    cell: Callable[[Any], str]


def _show_columns(records: list[tuple[str, Skit]]) -> list[_Column]:
    """ID, count and share, first/last run, each shared value and share, then each token key."""
    columns = [
        _Column("ID", lambda fid, record: fid, lambda fid: fid[:8]),
        _Column("COUNT", lambda fid, record: record.meta.get("count"), _cell),
        _Column(
            "COUNT %",
            lambda fid, record: record.share.get("meta", {}).get("count"),
            _percent,
        ),
        _Column("FIRST RUN", lambda fid, record: record.meta.get("first_seen"), _cell),
        _Column("LAST RUN", lambda fid, record: record.meta.get("last_seen"), _cell),
    ]
    for key, function in _shared_columns(record for _, record in records):
        name = key if function is None else f"{key}.{function}"
        columns.append(
            _Column(
                name,
                lambda fid, record, k=key, f=function: _lookup(record.aggregates, k, f),
                _cell,
            )
        )
        columns.append(
            _Column(
                f"{name} %",
                lambda fid, record, k=key, f=function: _lookup(
                    record.share.get("aggregates", {}), k, f
                ),
                _percent,
            )
        )
    for key in sorted({key for _, record in records for key in record.tokens}):
        columns.append(_Column(key, lambda fid, record, k=key: record.tokens.get(k), _cell))
    return columns


class _NoColumn(Exception):
    """`--sort` KEY names no column, or more than one; the message says which."""


def _find_column(columns: list[_Column], key: str, sketch_path: str) -> _Column:
    """The column headed KEY exactly, else the only one headed KEY in another case."""
    for column in columns:
        if column.header == key:
            return column
    matches = [column for column in columns if column.header.casefold() == key.casefold()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        headers = ", ".join(column.header for column in matches)
        raise _NoColumn(f"column {key!r} is ambiguous in {sketch_path}: {headers}")
    headers = ", ".join(column.header for column in columns)
    raise _NoColumn(f"no column {key!r} in {sketch_path}; columns: {headers}")


def _sort_key(value: Any) -> tuple:
    """Missing values first, then numbers by value, then everything else as text."""
    if value is None:
        return (0, 0)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (1, value)
    return (2, str(value))


def _show_table(records: list[tuple[str, Skit]], key: str, sketch_path: str) -> str:
    """The `show` table: a header, then one row per skit, sorted by column KEY, lowest first."""
    columns = _show_columns(records)
    column = _find_column(columns, key, sketch_path)
    records = sorted(records, key=lambda item: _sort_key(column.value(*item)))  # ties: file order
    rows = [
        [column.cell(column.value(fid, record)) for column in columns] for fid, record in records
    ]
    return _table([[column.header for column in columns]] + rows)


def _cmd_show(args: argparse.Namespace) -> int:
    sketch = Sketch()
    try:
        sketch.load(args.sketch_path)
    except (SketchError, OSError) as exc:
        _say(f"sketchtastic: cannot use sketch file: {exc}")
        return EXIT_NOT_WRITTEN
    records = [(fid, sketch.get(fid)) for fid in sketch]
    if not records:
        print(f"{args.sketch_path}: no skits")
        return EXIT_OK
    try:
        table = _show_table(records, args.sort, args.sketch_path)
    except _NoColumn as exc:
        _say(f"sketchtastic: {exc}")
        return EXIT_NOT_WRITTEN
    print(table)
    return EXIT_OK


DROP = object()
"""`_Sequencer.check` result for an event at or below the mark: already merged."""


class _Sequencer:
    """Duplicate protection (STORY-FING-50): drops events at or below the sketch's mark.

    The mark is the highest sequence merged before this run, so events slightly out of order
    within one run are all kept.
    """

    def __init__(self, path: Path, mark: int | float | None) -> None:
        self.path, self.mark = path, mark
        self.dropped = 0
        self.low: int | float | None = None
        self.high: int | float | None = None

    def check(self, event: Any) -> Any:
        """The event's sequence number to keep it, DROP if already merged, None if unusable
        (an error: the caller fails the run)."""
        values = self.path.values(event)
        number = as_number(values[0]) if len(values) == 1 else None
        if number is None:
            return None
        if self.mark is not None and number <= self.mark:
            self.dropped += 1
            return DROP
        self.low = number if self.low is None else min(self.low, number)
        self.high = number if self.high is None else max(self.high, number)
        return number

    def stats(self) -> dict:
        merged = None if self.high is None else {"min": self.low, "max": self.high}
        return {"dropped": self.dropped, "mark": self.mark, "sequence": merged}

    def new_mark(self) -> dict | None:
        """The sketch's mark after this run: {path, max}, or None if there is none."""
        highest = max((n for n in (self.mark, self.high) if n is not None), default=None)
        return None if highest is None else {"path": self.path.text, "max": highest}


def _sequencer(profile: Profile, sketch: Sketch) -> _Sequencer | None:
    """The run's duplicate protection, if the profile declares a sequence."""
    if profile.sequence is None:
        return None
    stored = sketch.sequence or {}
    mark = stored.get("max")
    if stored and stored.get("path") != profile.sequence.text:
        _say(
            f"sketchtastic: sequence path changed ({stored.get('path')} -> "
            f"{profile.sequence.text}); previous mark ignored"
        )
        mark = None
    return _Sequencer(profile.sequence, mark)


def _fold_stream(
    lines: Iterable[str],
    profile: Profile,
    run: Sketch,
    run_id: str,
    sequencer: _Sequencer | None = None,
) -> dict:
    """Fold each JSONL line into `run` (this run only), recording `run_id` as where it was seen.

    With a `sequencer`, events already merged are dropped, and an event without a usable
    sequence fails the run (_NotWritten). Returns run statistics.
    """
    events = skipped_lines = 0

    def warn(lineno: int, reason: str) -> None:
        if skipped_lines <= _MAX_LINE_WARNINGS:
            _say(f"sketchtastic: line {lineno}: {reason} - skipped")
        elif skipped_lines == _MAX_LINE_WARNINGS + 1:
            _say("sketchtastic: further skipped lines are counted but not listed")

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
        sequence = sequencer.check(event) if sequencer else 0
        if sequence is None:  # duplicate detection must be exact, so the whole run fails
            raise _NotWritten(
                f"sketchtastic: line {lineno}: no usable sequence at {sequencer.path.text} "
                "(missing, several values, or not a number)\n"
                "  nothing written: the profile declares a sequence, so every event needs one"
            )
        events += 1
        if sequence is DROP:
            continue
        run.upsert(profile.tokens(event), event, run_id)

    return {
        "events": events,
        "skipped_lines": skipped_lines,
        **(sequencer.stats() if sequencer else {}),
    }


class _NotWritten(Exception):
    """A merge step failed, so nothing is written. The message says why (possibly several lines)."""


def _load_profile(path: str) -> Profile:
    try:
        return load_profile(path)
    except ProfileError as exc:
        lines = [f"sketchtastic: {problem}" for problem in exc.problems]
        lines.append(f"  nothing written; 'sketchtastic check {path}' lists the same problems")
        raise _NotWritten("\n".join(lines)) from exc


def _open_sketch(args: argparse.Namespace, profile: Profile) -> Sketch:
    sketch = Sketch(profile.aggregates, profile.profile_id)
    if not os.path.exists(args.sketch_path):
        return sketch
    try:
        sketch.load(args.sketch_path, force=args.force_profile)
    except ProfileMismatchError as exc:
        raise _NotWritten(
            f"sketchtastic: {exc}.\n"
            "  Fingerprints from different profiles are not comparable, so nothing was merged.\n"
            "  Use a separate --sketch file for this profile, or pass --force-profile to merge anyway."
        ) from exc
    except (SketchError, OSError) as exc:
        raise _NotWritten(f"sketchtastic: cannot use sketch file: {exc}") from exc
    return sketch


def _open_events(args: argparse.Namespace) -> AbstractContextManager[IO[str]]:
    if args.events != "-":
        try:
            return open(args.events, encoding="utf-8", errors="replace")  # noqa: SIM115
        except OSError as exc:
            reason = exc.strerror or exc
            raise _NotWritten(
                f"sketchtastic: cannot read events from {args.events}: {reason}"
            ) from exc
    if sys.stdin.isatty():
        raise _NotWritten(
            "sketchtastic: no events to read. Name a JSONL file, or pipe events in:\n"
            f"  sketchtastic merge -p {args.profile} -s {args.sketch_path} events.jsonl\n"
            f"  some-command | sketchtastic merge -p {args.profile} -s {args.sketch_path} -"
        )
    return nullcontext(sys.stdin)


def _source(args: argparse.Namespace) -> str:
    return "stdin" if args.events == "-" else args.events


RUN_ID = re.compile(r"\d{6}-(\d{4,})")
"""A run id, `YYMMDD-SEQ`: the UTC date of the run and a per-sketch sequence number."""


def _history_dir(sketch_path: str) -> str:
    """`<sketch without its last extension>.history`, where each run's own sketch is kept."""
    return os.path.splitext(sketch_path)[0] + ".history"


def _next_run_id(last_run: str | None, history_dir: str, day: date) -> str:
    """`YYMMDD-SEQ` for a new run: SEQ is one past the highest in the sketch and its history.

    Counting the history too means a rebuilt sketch never reuses a number a run file holds.
    """
    ids = [last_run or ""]
    if os.path.isdir(history_dir):
        ids += [os.path.splitext(name)[0] for name in os.listdir(history_dir)]
    seqs = [int(match.group(1)) for match in map(RUN_ID.fullmatch, ids) if match]
    return f"{day:%y%m%d}-{max(seqs, default=0) + 1:04d}"


def _write_history(
    args: argparse.Namespace, run: Sketch, run_id: str, stats: dict, started: datetime
) -> str:
    """Save this run's own sketch, with its `run:` header, to SKETCH's history. Returns its path."""
    run.run = {
        "id": run_id,
        "started": started.isoformat(),
        "finished": datetime.now(UTC).isoformat(),
        "source": _source(args),
        "events": stats["events"],
        "skipped_lines": stats["skipped_lines"],
        "sketch": args.sketch_path,
    }
    if stats.get("sequence"):
        run.run["sequence"] = stats["sequence"]
    directory = _history_dir(args.sketch_path)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{run_id}.yaml")
    run.save(path)
    return path


def _report(
    args: argparse.Namespace,
    stats: dict,
    sketch: Sketch,
    profile: Profile,
    *,
    existed: bool,
) -> None:
    source = _source(args)
    destination = args.output or args.sketch_path
    verb = "updated" if existed and not args.output else "wrote"
    _say(f"sketchtastic: {stats['events']} events read from {source}")
    _say(f"  skits: {stats['new']} new, {stats['updated']} updated, {len(sketch)} total in sketch")
    _say(
        f"  skipped: {stats['skipped_lines']} malformed lines, "
        f"{sketch.skipped_values} unusable aggregate values"
    )
    if "dropped" in stats:
        mark = stats["mark"]
        since = "no earlier mark" if mark is None else f"sequence ≤ {mark}"
        _say(f"  dropped: {stats['dropped']} events already merged ({since})")
    _say(f"  {verb} {destination} (profile {profile.profile_id})")
    if args.output:
        _say(f"  {args.sketch_path} left unchanged")


def _record_history(
    args: argparse.Namespace, run: Sketch, run_id: str, stats: dict, started: datetime
) -> int:
    """Write the run file and say where. Returns EXIT_HISTORY_NOT_WRITTEN if it failed, else 0."""
    try:
        _say(f"  history: {_write_history(args, run, run_id, stats, started)}")
    except OSError as exc:
        _say(
            f"sketchtastic: {args.sketch_path} updated, but history not written: {exc.strerror or exc}"
        )
        return EXIT_HISTORY_NOT_WRITTEN
    return EXIT_OK


def _cmd_merge(args: argparse.Namespace) -> int:
    started = datetime.now(UTC)
    destination = args.output or args.sketch_path
    existed = os.path.exists(args.sketch_path)
    try:
        profile = _load_profile(args.profile)
        sketch = _open_sketch(args, profile)
        run_id = _next_run_id(sketch.last_run, _history_dir(args.sketch_path), started.date())
        sketch.last_run = run_id
        run = Sketch(profile.aggregates, profile.profile_id)
        sequencer = _sequencer(profile, sketch)
        with _open_events(args) as stream:
            stats = _fold_stream(stream, profile, run, run_id, sequencer)
        known_before = set(sketch)
        sketch.merge(run)  # fold once, into the run; merge it once
        stats["new"] = len(set(run) - known_before)
        stats["updated"] = len(set(run) & known_before)
        if sequencer:
            sketch.sequence = sequencer.new_mark()
        try:
            sketch.save(destination)
        except OSError as exc:
            raise _NotWritten(
                f"sketchtastic: cannot write {destination}: {exc.strerror or exc}"
            ) from exc
    except _NotWritten as exc:
        _say(str(exc))
        return EXIT_NOT_WRITTEN
    except KeyboardInterrupt:
        _say(f"sketchtastic: interrupted - {destination} was not modified")
        return 130
    _report(args, stats, sketch, profile, existed=existed)
    status = EXIT_LINES_SKIPPED if stats["skipped_lines"] else EXIT_OK
    if args.output:
        return status
    return _record_history(args, run, run_id, stats, started) or status


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
