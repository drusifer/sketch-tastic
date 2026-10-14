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
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from fingerprint_sampler.model import MISSING, Path, Rule, ValueType, typed_values

__all__ = [
    "Aggregate",
    "Aggregator",
    "Avg",
    "Count",
    "First",
    "Last",
    "Max",
    "Min",
    "Op",
    "Size",
    "Sum",
]


EMPTY = object()
"""The state of an aggregate function that has not seen a value yet."""

SKIP = object()
"""Returned by `Aggregator.accept` for a value the function cannot use."""


class Aggregator(Rule):
    """Folds one value into an aggregate function's state."""

    family = "aggregator"

    def accept(self, _state: Any, value: Any) -> Any:
        """The value to fold, or SKIP if this function cannot use it. Any value by default."""
        return value

    def fold(self, state: Any, value: Any) -> Any:
        """Return the new state after `value`; `state` is EMPTY before the first value."""
        raise NotImplementedError


class _Numeric(Aggregator):
    """Uses numbers and numeric strings only."""

    def accept(self, _state: Any, value: Any) -> Any:
        number = _as_number(value)
        return SKIP if number is None else number


def _kind(value: Any) -> str:
    if isinstance(value, datetime):
        return "datetime"
    return "date" if isinstance(value, date) else "text" if isinstance(value, str) else "number"


class _Ordered(Aggregator):
    """Uses numbers (and numeric strings), dates, datetimes or text; one kind, not a mix."""

    def accept(self, state: Any, value: Any) -> Any:
        number = _as_number(value)
        if number is not None:
            value = number
        elif not isinstance(value, (str, date)):
            return SKIP
        if state is not EMPTY and _kind(state) != _kind(value):
            return SKIP
        return value


@dataclass(frozen=True, kw_only=True)
class Sum(_Numeric):
    name = "SUM"

    def fold(self, state: Any, value: Any) -> Any:
        return value if state is EMPTY else state + value


@dataclass(frozen=True, kw_only=True)
class Min(_Ordered):
    name = "MIN"

    def fold(self, state: Any, value: Any) -> Any:
        return value if state is EMPTY else min(state, value)


@dataclass(frozen=True, kw_only=True)
class Max(_Ordered):
    name = "MAX"

    def fold(self, state: Any, value: Any) -> Any:
        return value if state is EMPTY else max(state, value)


@dataclass(frozen=True, kw_only=True)
class Avg(_Numeric):
    name = "AVG"

    def fold(self, state: Any, value: Any) -> Any:
        total, count = (0, 0) if state is EMPTY else (state["sum"], state["count"])
        total, count = total + value, count + 1
        return {"avg": total / count, "sum": total, "count": count}


@dataclass(frozen=True, kw_only=True)
class Count(Aggregator):
    name = "COUNT"

    def fold(self, state: Any, _value: Any) -> Any:
        return 1 if state is EMPTY else state + 1


@dataclass(frozen=True, kw_only=True)
class First(Aggregator):
    """The first `n` values."""

    name = "FIRST"
    n: int

    def fold(self, state: Any, value: Any) -> Any:
        samples = [] if state is EMPTY else state
        return samples if len(samples) >= self.n else [*samples, copy.deepcopy(value)]


@dataclass(frozen=True, kw_only=True)
class Last(Aggregator):
    """The latest `n` values."""

    name = "LAST"
    n: int

    def fold(self, state: Any, value: Any) -> Any:
        samples = [] if state is EMPTY else state
        return [*samples, copy.deepcopy(value)][-self.n :]


class Op(Rule):
    """What an aggregate folds in place of each selected value (STORY-FING-45)."""

    family = "op"

    def apply(self, value: Any) -> Any:
        raise NotImplementedError


@dataclass(frozen=True, kw_only=True)
class Size(Op):
    """Size in bytes: UTF-8 for text, the compact JSON encoding for anything else."""

    name = "SIZE"

    def apply(self, value: Any) -> int:
        text = (
            value
            if isinstance(value, str)
            else json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        )
        return len(text.encode("utf-8"))


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
    """Track `fn` over the values `path` selects (or what `op` makes of them), stored under `key`.

    `path` and `fn` may be given as text and a name, mapping or list of them; they are built
    and checked on creation (ValueError if wrong).
    """

    key: str
    path: Path
    fn: tuple[Aggregator, ...]
    type: ValueType | None = None
    op: Op | None = None

    def __post_init__(self) -> None:
        if self.type is not None:
            object.__setattr__(self, "type", ValueType.build(self.type))
        if self.op is not None:
            object.__setattr__(self, "op", Op.build(self.op))
        specs = self.fn if isinstance(self.fn, (list, tuple)) else [self.fn]
        functions = tuple(Aggregator.build(spec) for spec in specs)
        names = [f.name for f in functions]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"Aggregate function listed more than once: {', '.join(duplicates)}")
        object.__setattr__(self, "path", Path.of(self.path))
        object.__setattr__(self, "fn", functions)

    def update(self, states: dict, event: Any) -> int:
        """Fold one event into `states[self.key]`. Returns how many values were skipped.

        With one function the state is stored directly (`count: 12`); with several it is a
        map by function name (`{SUM: .., MAX: ..}`). A path that selects nothing is not a skip:
        one is counted per selected value that one of its functions could not use.
        """
        values = self.path.values(event)
        skipped = 0
        values = [self.op.apply(v) for v in values] if self.op else typed_values(values, self.type)
        for value in values:
            if value is MISSING:  # did not convert to the declared type
                skipped += 1
                continue
            unusable = False
            for function in self.fn:
                state = self._state(states, function)
                accepted = function.accept(state, value)
                if accepted is SKIP:
                    unusable = True
                else:
                    self._store(states, function, function.fold(state, accepted))
            skipped += unusable
        return skipped

    def _state(self, states: dict, function: Aggregator) -> Any:
        if len(self.fn) == 1:
            return states.get(self.key, EMPTY)
        return states.get(self.key, {}).get(function.name, EMPTY)

    def _store(self, states: dict, function: Aggregator, state: Any) -> None:
        if len(self.fn) == 1:
            states[self.key] = state
        else:
            states.setdefault(self.key, {})[function.name] = state
