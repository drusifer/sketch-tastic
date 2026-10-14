"""Per-fingerprint aggregate functions (STORY-FING-25, -39).

An aggregate folds the values one JSONPath selects, across every event that
hashes to the same fingerprint, into a small piece of state. That state is
plain data (numbers, lists, dicts) so it round-trips through the fingerprint
set file, and folding continues from stored state — which is what makes a set
built over many runs equal to one built in a single pass. State is keyed by
function name, so changing LAST's `n` keeps the samples already collected.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any, ClassVar

from fingerprint_sampler.model import Path, Rule


class Aggregator(Rule):
    """Folds one value into the state of an aggregate. Numeric ones only see numbers."""

    family = "aggregator"
    numeric: ClassVar[bool] = True

    def update(self, state: dict, value: Any) -> None:
        raise NotImplementedError


@dataclass(frozen=True, kw_only=True)
class Sum(Aggregator):
    name = "SUM"

    def update(self, state: dict, value: Any) -> None:
        state["SUM"] = state.get("SUM", 0) + value


@dataclass(frozen=True, kw_only=True)
class Min(Aggregator):
    name = "MIN"

    def update(self, state: dict, value: Any) -> None:
        state["MIN"] = min(state.get("MIN", value), value)


@dataclass(frozen=True, kw_only=True)
class Max(Aggregator):
    name = "MAX"

    def update(self, state: dict, value: Any) -> None:
        state["MAX"] = max(state.get("MAX", value), value)


@dataclass(frozen=True, kw_only=True)
class Avg(Aggregator):
    name = "AVG"

    def update(self, state: dict, value: Any) -> None:
        avg = state.setdefault("AVG", {"avg": 0, "sum": 0, "count": 0})
        avg["sum"] += value
        avg["count"] += 1
        avg["avg"] = avg["sum"] / avg["count"]


@dataclass(frozen=True, kw_only=True)
class Last(Aggregator):
    name = "LAST"
    numeric = False
    n: int

    def update(self, state: dict, value: Any) -> None:
        samples = state.setdefault("LAST", [])
        samples.append(copy.deepcopy(value))
        del samples[: -self.n]


def _as_number(value: Any) -> int | float | None:
    """Coerce to a finite number, or None if `value` isn't one (bools are not numbers)."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                return None
    return value if math.isfinite(value) else None


@dataclass(frozen=True)
class Aggregate:
    """Track `fn` over the values `path` selects, stored under `key`.

    `path` and `fn` may be given as text and a name, mapping or list of them; they are built
    and checked on creation (ValueError if wrong).
    """

    key: str
    path: Path
    fn: tuple[Aggregator, ...]

    def __post_init__(self) -> None:
        specs = self.fn if isinstance(self.fn, (list, tuple)) else [self.fn]
        functions = tuple(Aggregator.build(spec) for spec in specs)
        names = [f.name for f in functions]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"Aggregate function listed more than once: {', '.join(duplicates)}")
        object.__setattr__(self, "path", Path.of(self.path))
        object.__setattr__(self, "fn", functions)

    def update(self, state: dict, event: Any) -> int:
        """Fold one event into `state`. Returns how many values were skipped.

        One is skipped if the path selected nothing; otherwise one per selected value that a
        numeric function could not use.
        """
        values = self.path.values(event)
        if not values:
            return 1
        skipped = 0
        for value in values:
            number = _as_number(value)
            for function in self.fn:
                if not function.numeric:
                    function.update(state, value)
                elif number is not None:
                    function.update(state, number)
            skipped += number is None and any(f.numeric for f in self.fn)
        return skipped
