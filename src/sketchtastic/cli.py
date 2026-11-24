"""Command-line interface.

    sketch merge --profile P --sketch S [EVENTS|-]
    sketch check PROFILE [PROFILE ...]

Folds a stream of JSONL events into a sketch that grows across runs.
Knows nothing about where the events came from.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import re
import select
import sys
import time
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from datetime import UTC, date, datetime
from multiprocessing import Process, Queue
from queue import Empty
from typing import IO, Any, Callable, Iterable, Iterator

from sketchtastic import __version__
from sketchtastic._io import history_dir_for
from sketchtastic.aggregators import as_number
from sketchtastic.derive_cli import add_derive_command
from sketchtastic.model import Path
from sketchtastic.profile import Profile, ProfileError, load_profile
from sketchtastic.reporting import add_commands
from sketchtastic.sketch import (
    ProfileMismatchError,
    Sketch,
    SketchError,
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
  sketch merge -p access_log.yaml -s web.sketch.yaml access_log.jsonl

  # read events from a live pipe, stopping after 60 seconds or 1000 events
  tail -f app.jsonl | sketch merge -p app.yaml -s app.sketch.yaml --max-seconds 60 -
  tail -f app.jsonl | sketch merge -p app.yaml -s app.sketch.yaml --max-events 1000 -

  # trial run: write the merged result elsewhere, leave the sketch untouched
  sketch merge -p app.yaml -s app.sketch.yaml -o /tmp/preview.yaml new.jsonl

The SKETCH file is updated in place (atomically) unless --output is given.

streaming & limits:
  Reading from stdin ('-') or passing --max-events / --max-seconds folds events
  line-by-line as they arrive and writes the sketch as soon as EOF or either
  limit is reached.

parallel:
  -j N folds batches of 5000 lines in N worker processes (default: all cores)
  and merges their sketches. Everything is exact except FIRST/LAST samples
  (and each skit's first and last record): with N > 1 they come from matching
  events, not necessarily the very first or last ones.

history:
  Each run gets an id, YYMMDD-SEQ (UTC date, then a number that only goes up
  for this sketch), e.g. 261015-0003. Skits record the first and last run
  that saw them. Every run that updates SKETCH also writes just that run's
  skits, with a 'run:' header (id, times, source, counts), to
  <SKETCH without extension>.history/<run id>.yaml, e.g.
  web.sketch.history/261015-0003.yaml.
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


def _jobs(text: str) -> int:
    try:
        jobs = int(text)
    except ValueError:
        jobs = 0
    if jobs < 1:
        raise argparse.ArgumentTypeError(f"must be a whole number of at least 1, not {text!r}")
    return jobs


def _positive_seconds(text: str) -> float:
    try:
        seconds = float(text)
    except ValueError:
        seconds = 0.0
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError(f"must be a finite number greater than 0, not {text!r}")
    return seconds


def _say(message: str) -> None:
    print(message, file=sys.stderr)


def _prog() -> str:
    """The CLI command name (`sketch`, including when invoked via `python -m sketchtastic`)."""
    return "sketch"


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
        "-j",
        "--jobs",
        type=_jobs,
        default=os.process_cpu_count() or 1,
        metavar="N",
        help="worker processes (default: all cores, here %(default)s); 1 folds in-process",
    )
    merge.add_argument(
        "--max-events",
        type=_jobs,
        default=None,
        metavar="N",
        help="stop reading after N valid events have been folded, then save the sketch",
    )
    merge.add_argument(
        "--max-seconds",
        type=_positive_seconds,
        default=None,
        metavar="SECONDS",
        help="stop reading after SECONDS have elapsed, then save the sketch",
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

    add_commands(commands)
    add_derive_command(commands)
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

    def absorb(self, other: _Sequencer) -> None:
        """Add the counts of a sequencer that checked other events of this run (a worker's)."""
        self.dropped += other.dropped
        lows = [n for n in (self.low, other.low) if n is not None]
        highs = [n for n in (self.high, other.high) if n is not None]
        self.low, self.high = min(lows, default=None), max(highs, default=None)

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
            f"sketch: sequence path changed ({stored.get('path')} -> "
            f"{profile.sequence.text}); previous mark ignored"
        )
        mark = None
    return _Sequencer(profile.sequence, mark)


Folded = tuple[Sketch, dict, list[tuple[int, str]], "_Sequencer | None"]
"""What one fold returns: its run sketch, counts, its first warnings, its sequencer."""


def _iter_timed_fd(fd: int, deadline: float, timed_out: list[bool]) -> Iterator[bytes]:
    """Read complete lines from a non-seekable OS descriptor without exceeding `deadline`."""
    buf = bytearray()
    while True:
        while (nl := buf.find(b"\n")) != -1:
            if time.monotonic() >= deadline:
                timed_out[0] = True
                return
            yield bytes(buf[: nl + 1])
            del buf[: nl + 1]
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out[0] = True
            return
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            timed_out[0] = True
            return
        chunk = os.read(fd, 4096)
        if not chunk:
            if buf and time.monotonic() < deadline:
                yield bytes(buf)
            return
        buf.extend(chunk)


def _pipe_fd(stream: Any) -> int | None:
    """Return an OS fd for a non-seekable stream (like a pipe/stdin), else None."""
    try:
        if stream.seekable():
            return None
        return stream.fileno()
    except AttributeError, OSError, ValueError:
        return None


def _iter_stream_lines(
    stream: Any, deadline: float | None, timed_out: list[bool]
) -> Iterator[bytes | str]:
    """Yield lines immediately as they arrive, respecting an optional monotonic deadline."""
    if deadline is not None:
        fd = _pipe_fd(stream)
        if fd is not None:
            yield from _iter_timed_fd(fd, deadline, timed_out)
            return
    while True:
        if deadline is not None and time.monotonic() >= deadline:
            timed_out[0] = True
            return
        line = stream.readline()
        if not line:
            return
        yield line


@dataclass(frozen=True)
class _FoldOptions:
    """Execution mode and limits for `_fold_stream`."""

    jobs: int = 1
    streaming: bool = False
    max_events: int | None = None
    max_seconds: float | None = None


@dataclass(frozen=True)
class _WorkerConfig:
    """Immutable configuration handed to each parallel fold worker."""

    profile: Profile
    run_id: str
    sequence: Path | None
    mark: int | float | None


def _parse_event_line(raw_line: bytes | str) -> tuple[dict[str, Any] | None, str | None]:
    """Decode and parse one non-empty JSONL line into `(event_dict, skip_reason)`."""
    text = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
    try:
        event = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON ({exc.msg} at column {exc.colno})"
    if not isinstance(event, dict):
        return None, f"expected a JSON object, got {type(event).__name__}"
    return event, None


def _upsert_event(run: Sketch, profile: Profile, event: dict[str, Any], run_id: str) -> None:
    if profile.event_time is not None:
        event_time, unusable = profile.extract_event_time(event)
        run.skipped_values += int(unusable)
        run.upsert(profile.tokens(event), event, run_id, seen=event_time)
    else:
        run.upsert(profile.tokens(event), event, run_id)


def _check_sequence_or_raise(
    sequencer: _Sequencer | None, event: dict[str, Any], lineno: int
) -> Any:
    if sequencer is None:
        return 0
    sequence = sequencer.check(event)
    if sequence is None:  # duplicate detection must be exact, so the whole run fails
        raise _NotWritten(
            f"sketch: line {lineno}: no usable sequence at {sequencer.path.text} "
            "(missing, several values, or not a number)\n"
            "  nothing written: the profile declares a sequence, so every event needs one"
        )
    return sequence


def _record_warning(warnings: list[tuple[int, str]], lineno: int, reason: str) -> None:
    if len(warnings) <= _MAX_LINE_WARNINGS:
        warnings.append((lineno, reason))


def _fold_lines(
    numbered_lines: Iterable[tuple[int, bytes | str]],
    profile: Profile,
    run_id: str,
    sequencer: _Sequencer | None,
    *,
    max_events: int | None = None,
) -> Folded:
    """Fold `(line number, JSONL line)` pairs into a new run sketch, recording `run_id`.

    With a `sequencer`, events already merged are dropped, and an event without a usable
    sequence fails the run (_NotWritten). Keeps the first `_MAX_LINE_WARNINGS + 1` warnings.
    """
    run = Sketch(profile.aggregates, profile.profile_id)
    events = skipped_lines = 0
    stop_reason: str | None = None
    warnings: list[tuple[int, str]] = []

    for lineno, raw_line in numbered_lines:
        if not raw_line.strip():
            continue
        event, skip_reason = _parse_event_line(raw_line)
        if skip_reason is not None or event is None:
            skipped_lines += 1
            _record_warning(warnings, lineno, skip_reason or "invalid JSON")
            continue
        sequence = _check_sequence_or_raise(sequencer, event, lineno)
        events += 1
        if sequence is not DROP:
            _upsert_event(run, profile, event, run_id)
        if max_events is not None and events >= max_events:
            stop_reason = "max_events"
            break
    counts: dict[str, Any] = {"events": events, "skipped_lines": skipped_lines}
    if stop_reason is not None:
        counts["stop_reason"] = stop_reason
    return run, counts, warnings, sequencer


_BATCH_LINES = 5000
"""Lines per task for a worker; input of at most one batch folds in-process."""


def _fold_worker(tasks: Queue, results: Queue, config: _WorkerConfig) -> None:
    """A worker process: fold each (first line number, lines) task until a None, then put
    its fold on `results`."""
    sequencer = None if config.sequence is None else _Sequencer(config.sequence, config.mark)

    def lines() -> Iterator[tuple[int, bytes]]:
        while (task := tasks.get()) is not None:
            start, batch = task
            yield from enumerate(batch, start)

    try:
        results.put(_fold_lines(lines(), config.profile, config.run_id, sequencer))
    except Exception as exc:  # e.g. _NotWritten: report it, then drain so the parent never blocks
        results.put(exc)
        for _ in lines():
            pass


def _get(queue: Queue, stalled: Callable[[], bool]) -> Any:
    """`queue.get()`, failing the run instead of waiting forever if workers have died."""
    while True:
        try:
            return queue.get(timeout=1)
        except Empty:
            if stalled():
                raise _NotWritten(
                    "sketch: a worker process stopped unexpectedly; nothing written"
                ) from None


def _collect_worker_results(workers: list[Process], results: Queue) -> Iterator[Folded]:
    def all_dead() -> bool:
        return not any(worker.is_alive() for worker in workers)

    for _ in workers:
        part = _get(results, all_dead)
        if isinstance(part, Exception):
            raise part
        yield part
    for worker in workers:
        worker.join()


def _fold_parallel(
    numbered_lines: Iterable[tuple[int, bytes | str]],
    profile: Profile,
    run_id: str,
    sequencer: _Sequencer | None,
    jobs: int,
) -> Iterator[Folded]:
    """Fold lines in `jobs` worker processes, each into its own run sketch; yield each
    worker's fold as it arrives on the output queue.

    Lines go out in batches of `_BATCH_LINES`; the task queue holds at most 3 per worker, so
    the reader waits when the workers fall behind.
    """
    tasks, results = Queue(3 * jobs), Queue()
    config = _WorkerConfig(
        profile=profile,
        run_id=run_id,
        sequence=sequencer.path if sequencer else None,
        mark=sequencer.mark if sequencer else None,
    )
    workers = [
        Process(target=_fold_worker, args=(tasks, results, config), daemon=True)
        for _ in range(jobs)
    ]
    try:
        for worker in workers:
            worker.start()
        for batch in itertools.batched(numbered_lines, _BATCH_LINES):
            tasks.put((batch[0][0], [line for _, line in batch]))
        for _ in workers:
            tasks.put(None)
        yield from _collect_worker_results(workers, results)
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()


def _dispatch_fold(
    stream: Any,
    profile: Profile,
    run_id: str,
    sequencer: _Sequencer | None,
    options: _FoldOptions,
) -> tuple[Iterable[Folded], list[bool]]:
    timed_out = [False]
    if options.streaming or options.max_events is not None or options.max_seconds is not None:
        deadline = (
            time.monotonic() + options.max_seconds if options.max_seconds is not None else None
        )
        numbered = enumerate(_iter_stream_lines(stream, deadline, timed_out), start=1)
        return (
            [_fold_lines(numbered, profile, run_id, sequencer, max_events=options.max_events)],
            timed_out,
        )
    numbered = enumerate(stream, start=1)
    head = list(itertools.islice(numbered, _BATCH_LINES + 1))
    lines = itertools.chain(head, numbered)
    if options.jobs == 1 or len(head) <= _BATCH_LINES:
        return [_fold_lines(lines, profile, run_id, sequencer)], timed_out
    return _fold_parallel(lines, profile, run_id, sequencer, options.jobs), timed_out


def _merge_folded_parts(
    parts: Iterable[Folded],
    sequencer: _Sequencer | None,
    timed_out: list[bool],
) -> tuple[Sketch, dict[str, Any], list[tuple[int, str]]]:
    run: Sketch | None = None
    stats: dict[str, Any] = {"events": 0, "skipped_lines": 0}
    stop_reason: str | None = None
    warnings: list[tuple[int, str]] = []
    for part, counts, part_warnings, part_sequencer in parts:
        if run is None:
            run = part  # the first fold is the run; later ones merge into it
        else:
            run.merge(part)
        stats["events"] += counts["events"]
        stats["skipped_lines"] += counts["skipped_lines"]
        stop_reason = counts.get("stop_reason") or stop_reason
        warnings += part_warnings
        if sequencer and part_sequencer is not sequencer:
            sequencer.absorb(part_sequencer)
    if stop_reason is None and timed_out[0]:
        stop_reason = "max_seconds"
    if stop_reason is not None:
        stats["stop_reason"] = stop_reason
    assert run is not None  # every path yields at least one fold
    return run, stats, warnings


def _emit_line_warnings(warnings: list[tuple[int, str]], skipped_lines: int) -> None:
    for lineno, reason in sorted(warnings)[:_MAX_LINE_WARNINGS]:
        _say(f"sketch: line {lineno}: {reason} - skipped")
    if skipped_lines > _MAX_LINE_WARNINGS:
        _say("sketch: further skipped lines are counted but not listed")


def _fold_stream(
    stream: Any,
    profile: Profile,
    run_id: str,
    sequencer: _Sequencer | None,
    options: _FoldOptions | None = None,
) -> tuple[Sketch, dict[str, Any]]:
    """Fold a JSONL stream into this run's sketch, in-process or on worker processes.

    Streaming mode (stdin or when `--max-events`/`--max-seconds` is given) folds each line
    immediately as it arrives without buffering a full batch up front. Worker results are
    merged as they complete: counts, aggregates, run ids and the sequence range are exact;
    FIRST/LAST samples come from matching events, not necessarily the first or last.
    """
    opts = options or _FoldOptions()
    parts, timed_out = _dispatch_fold(stream, profile, run_id, sequencer, opts)
    run, stats, warnings = _merge_folded_parts(parts, sequencer, timed_out)
    _emit_line_warnings(warnings, stats["skipped_lines"])
    return run, {**stats, **(sequencer.stats() if sequencer else {})}


class _NotWritten(Exception):
    """A merge step failed, so nothing is written. The message says why (possibly several lines)."""


def _load_profile(path: str) -> Profile:
    try:
        return load_profile(path)
    except ProfileError as exc:
        lines = [f"sketch: {problem}" for problem in exc.problems]
        lines.append(f"  nothing written; 'sketch check {path}' lists the same problems")
        raise _NotWritten("\n".join(lines)) from exc


def _open_sketch(args: argparse.Namespace, profile: Profile) -> Sketch:
    sketch = Sketch(profile.aggregates, profile.profile_id)
    if not os.path.exists(args.sketch_path):
        return sketch
    try:
        sketch.load(args.sketch_path, force=args.force_profile)
    except ProfileMismatchError as exc:
        raise _NotWritten(
            f"sketch: {exc}.\n"
            "  Skits from different profiles are not comparable, so nothing was merged.\n"
            "  Use a separate --sketch file for this profile, or pass --force-profile to merge anyway."
        ) from exc
    except (SketchError, OSError) as exc:
        raise _NotWritten(f"sketch: cannot use sketch file: {exc}") from exc
    return sketch


def _open_events(args: argparse.Namespace) -> AbstractContextManager[IO[bytes] | IO[str]]:
    if args.events != "-":
        try:
            return open(args.events, "rb")  # noqa: SIM115 - decoded per line, errors replaced
        except OSError as exc:
            reason = exc.strerror or exc
            raise _NotWritten(f"sketch: cannot read events from {args.events}: {reason}") from exc
    if sys.stdin.isatty():
        raise _NotWritten(
            "sketch: no events to read. Name a JSONL file, or pipe events in:\n"
            f"  sketch merge -p {args.profile} -s {args.sketch_path} events.jsonl\n"
            f"  some-command | sketch merge -p {args.profile} -s {args.sketch_path} -"
        )
    return nullcontext(getattr(sys.stdin, "buffer", sys.stdin))


def _source(args: argparse.Namespace) -> str:
    return "stdin" if args.events == "-" else args.events


RUN_ID = re.compile(r"\d{6}-(\d{4,})")
"""A run id, `YYMMDD-SEQ`: the UTC date of the run and a per-sketch sequence number."""


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
    if stats.get("stop_reason"):
        run.run["stop_reason"] = stats["stop_reason"]
    directory = str(history_dir_for(args.sketch_path))
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
    _say(f"sketch: {stats['events']} events read from {source}")
    _say(f"  skits: {stats['new']} new, {stats['updated']} updated, {len(sketch)} total in sketch")
    _say(
        f"  skipped: {stats['skipped_lines']} malformed lines, "
        f"{sketch.skipped_values} unusable aggregate values"
    )
    if "dropped" in stats:
        mark = stats["mark"]
        since = "no earlier mark" if mark is None else f"sequence ≤ {mark}"
        _say(f"  dropped: {stats['dropped']} events already merged ({since})")
    if stats.get("stop_reason") == "max_events":
        _say(f"  stopped: reached --max-events {args.max_events}")
    elif stats.get("stop_reason") == "max_seconds":
        _say(f"  stopped: reached --max-seconds {args.max_seconds:g}")
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
        _say(f"sketch: {args.sketch_path} updated, but history not written: {exc.strerror or exc}")
        return EXIT_HISTORY_NOT_WRITTEN
    return EXIT_OK


def _cmd_merge(args: argparse.Namespace) -> int:
    started = datetime.now(UTC)
    destination = args.output or args.sketch_path
    existed = os.path.exists(args.sketch_path)
    try:
        profile = _load_profile(args.profile)
        sketch = _open_sketch(args, profile)
        run_id = _next_run_id(
            sketch.last_run, str(history_dir_for(args.sketch_path)), started.date()
        )
        sketch.last_run = run_id
        sequencer = _sequencer(profile, sketch)
        fold_opts = _FoldOptions(
            jobs=args.jobs,
            streaming=args.events == "-",
            max_events=args.max_events,
            max_seconds=args.max_seconds,
        )
        with _open_events(args) as stream:
            run, stats = _fold_stream(stream, profile, run_id, sequencer, fold_opts)
        known_before = set(sketch)
        sketch.merge(run)  # fold once, into the run; merge it once
        stats["new"] = len(set(run) - known_before)
        stats["updated"] = len(set(run) & known_before)
        if sequencer:
            sketch.sequence = sequencer.new_mark()
        try:
            sketch.save(destination)
        except OSError as exc:
            raise _NotWritten(f"sketch: cannot write {destination}: {exc.strerror or exc}") from exc
    except _NotWritten as exc:
        _say(str(exc))
        return EXIT_NOT_WRITTEN
    except KeyboardInterrupt:
        _say(f"sketch: interrupted - {destination} was not modified")
        return 130
    _report(args, stats, sketch, profile, existed=existed)
    status = EXIT_LINES_SKIPPED if stats["skipped_lines"] else EXIT_OK
    if args.output:
        return status
    return _record_history(args, run, run_id, stats, started) or status


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
