"""CLI registration for explicit, non-destructive sketch derivation."""

from __future__ import annotations

import argparse
import sys

from sketchtastic._io import safe_text
from sketchtastic.derive_io import derive_file


def _cmd_derive(args: argparse.Namespace) -> int:
    try:
        result = derive_file(args.source, args.source_profile, args.profile, args.output)
    except (OSError, ValueError) as exc:
        print(
            f"sketch: derive: {safe_text(exc)}; nothing published by this operation",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print("sketch: derivation interrupted", file=sys.stderr)
        return 130
    print(
        f"Derived {result.source_skits} -> {result.derived_skits} skits; "
        f"{result.observations} observations preserved; {result.history_runs} history runs.\n"
        f"Wrote {safe_text(args.output)}; source unchanged."
    )
    return 0


def add_derive_command(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "derive",
        help="derive a separately named sketch and history using a collapsing profile",
        description="Create a new sketch from retained tokens and statistics without replaying events.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:
  sketch derive old.yaml --source-profile old-profile.yaml -p new-profile.yaml -o v2.yaml

Supported changes: drop/reorder/rename fields, untyped values to IS_PRESENT,
scalar values to IS_NULL/ANY/GLOB/REGEX/REGSUB, and typed time coarsening.
Aggregate specifications, sequence and event_time must remain unchanged.
Unsupported refinements and ambiguous array transformations require original events.

Every available history run is transformed; missing history is not invented.
All files are validated and staged before publication. Output and its history
must not exist. Keep sources quiescent. Handled failures are cleaned up;
publication of two paths is not a crash-atomic filesystem transaction.
FIRST/LAST samples remain representative, not guaranteed chronological extrema.
Only the current structured-token format is supported; recapture legacy sketches.

Exit status: 0 created; 2 rejected or failed (no outputs from this operation);
130 interrupted.
""",
    )
    parser.add_argument("source", metavar="SOURCE", help="source sketch (left unchanged)")
    parser.add_argument(
        "--source-profile", required=True, help="original profile, including aggregates"
    )
    parser.add_argument(
        "-p", "--profile", required=True, help="target profile with collapsing changes"
    )
    parser.add_argument(
        "-o", "--output", required=True, help="new sketch filename/version; no overwrite"
    )
    parser.set_defaults(func=_cmd_derive)
