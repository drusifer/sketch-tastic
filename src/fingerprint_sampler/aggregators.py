"""Per-fingerprint aggregators (STORY-FING-25).

An aggregator folds the values one JSONPath selects, across every event that
hashes to the same fingerprint, into a small piece of state. That state is
plain data (numbers, lists, dicts) so it round-trips through the fingerprint
set file, and folding continues from stored state — which is what makes a set
built over many runs equal to one built in a single pass.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any, Iterable

from fingerprint_sampler.tokenizer import compile_path, find_values

NUMERIC_FNS = ("SUM", "AVG", "MIN", "MAX")
SUPPORTED = "SUM, AVG, MIN, MAX, LAST(n)"


@dataclass(frozen=True)
class AggregateEntry:
    """Track `fns` over the values `path` selects, stored under `key`.

    `fns` holds normalised labels such as "MIN" or "LAST(3)"; build entries
    with `make_entry` so they are validated.
    """

    key: str
    path: str
    fns: tuple[str, ...]


def parse_fn(spec: str) -> tuple[str, int | None, str]:
    """Parse one aggregator spec into (name, n, label). Raises ValueError if unsupported."""
    if not isinstance(spec, str):
        raise ValueError(f"Aggregator must be a string, got {spec!r}")
    name, paren, rest = spec.strip().partition("(")
    name = name.strip().upper()
    arg = rest.strip()
    if paren:
        if not arg.endswith(")"):
            raise ValueError(f"Malformed aggregator {spec!r}: missing ')'")
        arg = arg[:-1].strip()

    if name in NUMERIC_FNS:
        if arg:
            raise ValueError(f"Aggregator {name} takes no arguments, got {spec!r}")
        return name, None, name
    if name == "LAST":
        if not arg.isdigit() or int(arg) < 1:
            raise ValueError(f"LAST needs a positive sample count, e.g. LAST(3); got {spec!r}")
        n = int(arg)
        return name, n, f"LAST({n})"
    raise ValueError(f"Unknown aggregator {spec!r}; supported: {SUPPORTED}")


def make_entry(key: str, path: str, fns: str | Iterable[str]) -> AggregateEntry:
    """Build a validated `AggregateEntry` from one spec or a list of specs."""
    compile_path(path)
    specs = [fns] if isinstance(fns, str) else list(fns)
    if not specs:
        raise ValueError("At least one aggregator function is required")
    parsed = [parse_fn(spec) for spec in specs]
    names = [name for name, _, _ in parsed]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Aggregator listed more than once: {', '.join(duplicates)}")
    return AggregateEntry(key=key, path=path, fns=tuple(label for _, _, label in parsed))


def _as_number(value: Any) -> int | float | None:
    """Coerce to a finite number, or None if `value` isn't one (bools are not numbers)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number: int | float = value
    elif isinstance(value, str):
        try:
            number = int(value)
        except ValueError:
            try:
                number = float(value)
            except ValueError:
                return None
    else:
        return None
    return number if math.isfinite(number) else None


def _fold_number(state: dict, name: str, number: int | float) -> None:
    if name == "SUM":
        state["SUM"] = state.get("SUM", 0) + number
    elif name == "MIN":
        state["MIN"] = number if "MIN" not in state else min(state["MIN"], number)
    elif name == "MAX":
        state["MAX"] = number if "MAX" not in state else max(state["MAX"], number)
    elif name == "AVG":
        avg = state.setdefault("AVG", {"avg": 0, "sum": 0, "count": 0})
        avg["sum"] += number
        avg["count"] += 1
        avg["avg"] = avg["sum"] / avg["count"]


def update(state: dict, entry: AggregateEntry, record: Any) -> int:
    """Fold one event into `state` (the dict stored under `entry.key`).

    State is keyed by function name ("SUM", "AVG", "MIN", "MAX", "LAST"), so
    changing `n` in LAST(n) keeps the samples already collected.

    Returns how many values were skipped: one if the path selected nothing,
    otherwise one per selected value no numeric function could use.
    """
    values = find_values(record, entry.path)
    if not values:
        return 1

    parsed = [parse_fn(label) for label in entry.fns]
    numeric_names = [name for name, _, _ in parsed if name in NUMERIC_FNS]
    skipped = 0

    for value in values:
        if numeric_names:
            number = _as_number(value)
            if number is None:
                skipped += 1
            else:
                for name in numeric_names:
                    _fold_number(state, name, number)
        for name, n, _ in parsed:
            if name == "LAST":
                samples = state.setdefault("LAST", [])
                samples.append(copy.deepcopy(value))
                del samples[:-n]
    return skipped
