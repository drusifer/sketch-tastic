"""Command-line interface.

    fingerprint merge --profile P --set S [EVENTS|-]
    fingerprint check PROFILE [PROFILE ...]

Folds a stream of JSONL events into a fingerprint set that grows across runs.
Knows nothing about where the events came from.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import AbstractContextManager, nullcontext
from typing import IO, Iterable

from fingerprint_sampler import __version__
from fingerprint_sampler.fingerprint_set import (
    FingerprintSet,
    FingerprintSetError,
    ProfileMismatchError,
)
from fingerprint_sampler.profile import Profile, ProfileError, load_profile

EXIT_OK = 0
EXIT_LINES_SKIPPED = 1
EXIT_NOT_WRITTEN = 2

_MAX_LINE_WARNINGS = 10

_MERGE_DESCRIPTION = (
    "Fingerprint every event in a JSONL stream using PROFILE and merge the results "
    "into the fingerprint set SET: counts add up, aggregates continue, new "
    "fingerprints are appended. SET is created if it does not exist."
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

exit status:
  0  set written, every line was used
  1  set written, but some input lines were skipped (see stderr)
  2  nothing written (bad arguments, profile, set file, or profile mismatch)
"""


_CHECK_EPILOG = """\
Structure is checked against the profile JSON Schema shipped with the package
(also usable by editors: see the README); regexes, JSONPaths, ranges, duplicate
keys and aggregate functions are checked as well. Every problem is listed.

exit status:
  0  every profile is valid
  1  at least one profile has problems (listed on stdout)
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


def _fold_stream(lines: Iterable[str], profile: Profile, fingerprints: FingerprintSet) -> dict:
    """Fingerprint each JSONL line into `fingerprints`. Returns run statistics."""
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
        seen.add(fingerprints.upsert(profile.tokens(event), event))
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


def _report(
    args: argparse.Namespace,
    stats: dict,
    fingerprints: FingerprintSet,
    profile: Profile,
    *,
    existed: bool,
) -> None:
    source = "stdin" if args.events == "-" else args.events
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
    destination = args.output or args.set_path
    existed = os.path.exists(args.set_path)
    try:
        profile = _load_profile(args.profile)
        fingerprints = _open_set(args, profile)
        with _open_events(args) as stream:
            stats = _fold_stream(stream, profile, fingerprints)
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
    return EXIT_LINES_SKIPPED if stats["skipped_lines"] else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
