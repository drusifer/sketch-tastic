"""Stream original Bluesky posts out of Jetstream JSONL, one line in, at most one line out.

Reads a capture file (or stdin as lines arrive) and writes each unchanged post-create record
to stdout, flushed per line, so it can sit between `capture --output -` and `sketch merge -`.
Updates, deletes and other collections are dropped; replayed creates are deduplicated in a
bounded window. Memory stays constant however long the stream runs. Counts go to stderr.
"""

import argparse
import json
import os
import sys
from collections import Counter
from typing import IO

from .input import MAX_LINE_BYTES, BoundedSeen, reject_constant, source_post


def unwrap(source: IO[bytes], sink: IO[str], counts: Counter) -> None:
    """Copy each post out of `source` into `sink`; raise ValueError naming a bad line."""
    seen = BoundedSeen()
    number = 0
    while line := source.readline(MAX_LINE_BYTES + 1):
        number += 1
        if len(line) > MAX_LINE_BYTES:
            raise ValueError(f"line {number}: exceeds {MAX_LINE_BYTES} byte line limit")
        if not line.strip():
            continue
        try:
            event = json.loads(line, parse_constant=reject_constant)
            if not isinstance(event, dict):
                raise ValueError("expected a JSON object")
            counts["records"] += 1
            record = source_post(event, counts, seen)
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            raise ValueError(f"line {number}: {exc}") from exc
        if record is not None:
            sink.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
            sink.flush()
            counts["posts"] += 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", nargs="?", default="-", help="Capture JSONL file; '-' or omitted reads stdin"
    )
    args = parser.parse_args(argv)
    counts: Counter = Counter()
    try:
        if args.input == "-":
            unwrap(sys.stdin.buffer, sys.stdout, counts)
        else:
            with open(args.input, "rb") as source:
                unwrap(source, sys.stdout, counts)
    except BrokenPipeError:
        # Downstream stopped reading (e.g. sketch merge --max-events); not an error here.
        # Point stdout at devnull so the interpreter's final flush cannot raise again.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.stderr.write("unwrap: downstream closed\n")
        return 0
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"unwrap: {json.dumps(str(exc), ensure_ascii=True)[1:-1]}\n")
        return 2
    finally:
        summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        sys.stderr.write(f"unwrap: {summary or 'no records'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
