"""Per-skit aggregate functions (STORY-FING-25, -39).

An aggregate folds the values one JSONPath selects, across every event that
hashes to the same skit, into a small piece of state. That state is
plain data (numbers, lists, dicts) so it round-trips through the sketch
file, and folding continues from stored state — which is what makes a sketch
built over many runs equal to one built in a single pass. State is keyed by
function name, so changing LAST's `n` keeps the samples already collected.
"""

from __future__ import annotations

import bisect
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sketchtastic._io import is_number
from sketchtastic.model import MISSING, Path, Rule, ValueType, typed_values

__all__ = [
    "Aggregate",
    "Aggregator",
    "Avg",
    "Count",
    "First",
    "Histogram",
    "Last",
    "Max",
    "Min",
    "Op",
    "Size",
    "Sum",
    "histogram_bins",
    "histogram_quantiles",
    "is_histogram_state",
    "merge_histogram_states",
]

HISTOGRAM_MANTISSAS = (1.0, 1.5, 2.0, 3.0, 5.0, 7.0)
_LOG_BASE = 10.0


SKIP = object()
"""Returned by `Aggregator.accept` for a value the function cannot use."""


class Aggregator(Rule):
    """Folds one value into an aggregate function's state."""

    family = "aggregator"

    def initial(self) -> Any:
        """The state before any value: 0 or empty where that means "nothing yet", else None."""
        return None

    def accept(self, _state: Any, value: Any) -> Any:
        """The value to fold, or SKIP if this function cannot use it. Any value by default."""
        return value

    def fold(self, state: Any, value: Any) -> Any:
        """Return the new state after `value`; `state` is `initial()` before the first value."""
        raise NotImplementedError

    def merge(self, state: Any, later: Any) -> Any:
        """The state after folding everything `state` saw, then everything `later` saw.

        Either may be `initial()`. Folding a stream in parts and merging equals folding it whole.
        """
        raise NotImplementedError


class _Numeric(Aggregator):
    """Uses numbers and numeric strings only."""

    def accept(self, _state: Any, value: Any) -> Any:
        number = as_number(value)
        return SKIP if number is None else number


def _kind(value: Any) -> str:
    if isinstance(value, datetime):
        return "datetime"
    return "date" if isinstance(value, date) else "text" if isinstance(value, str) else "number"


class _Ordered(Aggregator):
    """Uses numbers (and numeric strings), dates, datetimes or text; one kind, not a mix."""

    def accept(self, state: Any, value: Any) -> Any:
        number = as_number(value)
        if number is not None:
            value = number
        elif not isinstance(value, (str, date)):
            return SKIP
        if state is not None and _kind(state) != _kind(value):
            return SKIP
        return value

    def merge(self, state: Any, later: Any) -> Any:
        if state is None or later is None:
            return later if state is None else state
        if _kind(state) != _kind(later):  # one kind, not a mix: the first kind seen stays
            return state
        return self.fold(state, later)


@dataclass(frozen=True, kw_only=True)
class Sum(_Numeric):
    name = "SUM"

    def initial(self) -> Any:
        return 0

    def fold(self, state: Any, value: Any) -> Any:
        return state + value

    def merge(self, state: Any, later: Any) -> Any:
        return state + later


@dataclass(frozen=True, kw_only=True)
class Min(_Ordered):
    name = "MIN"

    def fold(self, state: Any, value: Any) -> Any:
        return value if state is None else min(state, value)


@dataclass(frozen=True, kw_only=True)
class Max(_Ordered):
    name = "MAX"

    def fold(self, state: Any, value: Any) -> Any:
        return value if state is None else max(state, value)


@dataclass(frozen=True, kw_only=True)
class Avg(_Numeric):
    name = "AVG"

    def initial(self) -> Any:
        return {"avg": None, "sum": 0, "count": 0}

    def fold(self, state: Any, value: Any) -> Any:
        total, count = state["sum"] + value, state["count"] + 1
        return {"avg": total / count, "sum": total, "count": count}

    def merge(self, state: Any, later: Any) -> Any:
        total, count = state["sum"] + later["sum"], state["count"] + later["count"]
        return {"avg": total / count if count else None, "sum": total, "count": count}


@dataclass(frozen=True, kw_only=True)
class Count(Aggregator):
    name = "COUNT"

    def initial(self) -> Any:
        return 0

    def fold(self, state: Any, _value: Any) -> Any:
        return state + 1

    def merge(self, state: Any, later: Any) -> Any:
        return state + later


@dataclass(frozen=True, kw_only=True)
class First(Aggregator):
    """The first `n` values."""

    name = "FIRST"
    n: int

    def initial(self) -> Any:
        return []

    def fold(self, state: Any, value: Any) -> Any:
        return state if len(state) >= self.n else [*state, value]

    def merge(self, state: Any, later: Any) -> Any:
        return [*state, *later][: self.n]


@dataclass(frozen=True, kw_only=True)
class Last(Aggregator):
    """The latest `n` values."""

    name = "LAST"
    n: int

    def initial(self) -> Any:
        return []

    def fold(self, state: Any, value: Any) -> Any:
        return [*state, value][-self.n :]

    def merge(self, state: Any, later: Any) -> Any:
        return [*state, *later][-self.n :]


def _clean_bound(value: float) -> float:
    return float(f"{value:.6g}")


def _fmt_edge(value: float) -> str:
    if value == 0:
        return "0"
    mag = abs(value)
    sign = "-" if value < 0 else ""
    for scale, suffix in ((1e9, "G"), (1e6, "M"), (1e3, "k")):
        if mag >= scale:
            num = mag / scale
            return f"{sign}{num:g}{suffix}"
    return f"{value:g}"


def log_bin_key(value: int | float) -> str:
    """Map any finite number to a deterministic sparse log-decimal bin key (1, 1.5, 2, 3, 5, 7)."""
    if value == 0:
        return "0"
    sign = "+" if value > 0 else "-"
    mag = abs(float(value))
    exp = math.floor(math.log10(mag))
    mantissa = mag / (_LOG_BASE**exp)
    if mantissa >= _LOG_BASE:
        exp += 1
        mantissa = 1.0
    step = min(
        len(HISTOGRAM_MANTISSAS) - 1, max(0, bisect.bisect_right(HISTOGRAM_MANTISSAS, mantissa) - 1)
    )
    return f"{sign}{exp * len(HISTOGRAM_MANTISSAS) + step}"


def log_bin_bounds(key: str) -> tuple[float, float]:
    """Decode a log-decimal bin key back to its `(lo, hi)` interval."""
    if key == "0":
        return 0.0, 0.0
    sign = 1 if key[0] == "+" else -1
    idx = int(key[1:])
    n_steps = len(HISTOGRAM_MANTISSAS)
    exp, step = divmod(idx, n_steps)
    scale = _LOG_BASE**exp
    lo_mag = _clean_bound(HISTOGRAM_MANTISSAS[step] * scale)
    hi_mag = _clean_bound(
        (HISTOGRAM_MANTISSAS[step + 1] if step + 1 < n_steps else _LOG_BASE) * scale
    )
    return (lo_mag, hi_mag) if sign > 0 else (-hi_mag, -lo_mag)


def is_histogram_state(value: Any) -> bool:
    """Return True if `value` is a serialized `HISTOGRAM` state dict."""
    if not isinstance(value, dict):
        return False
    mode = value.get("mode")
    if mode == "log":
        return isinstance(value.get("bins"), dict) and isinstance(value.get("count"), int)
    if mode == "fixed":
        return (
            isinstance(value.get("bounds"), list)
            and isinstance(value.get("counts"), list)
            and isinstance(value.get("count"), int)
            and len(value["counts"]) == len(value["bounds"]) + 1
        )
    return False


def merge_histogram_states(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Associatively merge two serialized `HISTOGRAM` states."""
    if left.get("count", 0) == 0:
        return _copy_histogram_state(right)
    if right.get("count", 0) == 0:
        return _copy_histogram_state(left)
    mode = left.get("mode")
    if mode != right.get("mode"):
        raise ValueError(
            f"Cannot merge histograms of different modes: {mode!r} vs {right.get('mode')!r}"
        )
    if mode == "log":
        merged = dict(left["bins"])
        for key, cnt in right["bins"].items():
            merged[key] = merged.get(key, 0) + cnt
        return {"mode": "log", "count": left["count"] + right["count"], "bins": merged}
    if left["bounds"] != right["bounds"]:
        raise ValueError("Cannot merge fixed histograms with different bucket bounds")
    return {
        "mode": "fixed",
        "count": left["count"] + right["count"],
        "bounds": list(left["bounds"]),
        "counts": [a + b for a, b in zip(left["counts"], right["counts"])],
    }


def _copy_histogram_state(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("mode") == "log":
        return {"mode": "log", "count": state["count"], "bins": dict(state["bins"])}
    return {
        "mode": "fixed",
        "count": state["count"],
        "bounds": list(state["bounds"]),
        "counts": list(state["counts"]),
    }


def _log_histogram_bins(state: dict[str, Any], total: int) -> list[dict[str, Any]]:
    rows = sorted(
        (*log_bin_bounds(str(key)), int(cnt))
        for key, cnt in state.get("bins", {}).items()
        if cnt > 0
    )
    return [
        {
            "lo": lo,
            "hi": hi,
            "label": "0" if lo == 0 and hi == 0 else f"{_fmt_edge(lo)}–{_fmt_edge(hi)}",
            "count": cnt,
            "pct": round(100.0 * cnt / total, 2) if total else 0.0,
        }
        for lo, hi, cnt in rows
    ]


def _fixed_bin_label(lo: float | None, hi: float | None) -> str:
    if lo is None:
        return f"≤{_fmt_edge(hi)}" if hi is not None else ""
    if hi is None:
        return f">{_fmt_edge(lo)}"
    return f"{_fmt_edge(lo)}–{_fmt_edge(hi)}"


def _fixed_histogram_bins(state: dict[str, Any], total: int) -> list[dict[str, Any]]:
    bounds = state.get("bounds", [])
    counts = state.get("counts", [])
    out: list[dict[str, Any]] = []
    for idx, cnt in enumerate(counts):
        lo = None if idx == 0 else bounds[idx - 1]
        hi = None if idx == len(bounds) else bounds[idx]
        out.append(
            {
                "lo": lo,
                "hi": hi,
                "label": _fixed_bin_label(lo, hi),
                "count": int(cnt),
                "pct": round(100.0 * cnt / total, 2) if total else 0.0,
            }
        )
    return out


def histogram_bins(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand a serialized `HISTOGRAM` state into ordered bin descriptors."""
    total = state.get("count", 0)
    if state.get("mode") == "log":
        return _log_histogram_bins(state, total)
    return _fixed_histogram_bins(state, total)


def _interpolate_bin(bin_info: dict[str, Any], frac: float) -> float | None:
    lo, hi = bin_info["lo"], bin_info["hi"]
    if lo is not None and hi is not None:
        return lo + frac * (hi - lo)
    if lo is None and hi is not None:
        return (frac * hi) if hi >= 0 else float(hi)
    if lo is not None:
        return float(lo)
    return None


def _quantile_at_rank(bins: list[dict[str, Any]], rank: float) -> float | None:
    cum = 0
    for b in bins:
        cnt = b["count"]
        if cnt <= 0:
            continue
        if cum + cnt >= rank:
            frac = max(0.0, min(1.0, (rank - cum) / cnt))
            est = _interpolate_bin(b, frac)
            return round(est, 4) if est is not None else None
        cum += cnt
    return None


def histogram_quantiles(
    state: dict[str, Any], probs: tuple[float, ...] = (0.5, 0.9, 0.95, 0.99)
) -> dict[str, float | None]:
    """Estimate quantiles via linear interpolation within histogram bins."""
    labels = [f"p{int(round(p * 100))}" for p in probs]
    total = state.get("count", 0)
    if total <= 0:
        return dict.fromkeys(labels, None)
    bins = histogram_bins(state)
    return {name: _quantile_at_rank(bins, prob * total) for name, prob in zip(labels, probs)}


@dataclass(frozen=True, kw_only=True)
class Histogram(_Numeric):
    """Mergeable per-event numeric histogram (sparse log-decimal or explicit fixed buckets)."""

    name = "HISTOGRAM"
    buckets: tuple[int | float, ...] | None = None

    def check(self) -> None:
        if self.buckets is None:
            return
        if not self.buckets:
            raise ValueError("HISTOGRAM buckets must not be empty")
        prev: float | None = None
        for bound in self.buckets:
            if not is_number(bound) or not math.isfinite(bound):
                raise ValueError(f"HISTOGRAM bucket bound must be a finite number: {bound!r}")
            if prev is not None and bound <= prev:
                raise ValueError(
                    f"HISTOGRAM buckets must be strictly increasing ({prev!r} >= {bound!r})"
                )
            prev = bound

    def initial(self) -> Any:
        if self.buckets is None:
            return {"mode": "log", "count": 0, "bins": {}}
        return {
            "mode": "fixed",
            "count": 0,
            "bounds": list(self.buckets),
            "counts": [0] * (len(self.buckets) + 1),
        }

    def fold(self, state: Any, value: Any) -> Any:
        if state["mode"] == "log":
            bins = dict(state["bins"])
            key = log_bin_key(value)
            bins[key] = bins.get(key, 0) + 1
            return {"mode": "log", "count": state["count"] + 1, "bins": bins}
        bounds = state["bounds"]
        counts = list(state["counts"])
        counts[bisect.bisect_left(bounds, value)] += 1
        return {
            "mode": "fixed",
            "count": state["count"] + 1,
            "bounds": list(bounds),
            "counts": counts,
        }

    def merge(self, state: Any, later: Any) -> Any:
        return merge_histogram_states(state, later)


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


def as_number(value: Any) -> int | float | None:
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
        if self.key not in states:
            self.init(states)
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
                    self.store(states, function, function.fold(state, accepted))
            skipped += unusable
        return skipped

    def init(self, states: dict, stored: dict | None = None) -> None:
        """Add `states[self.key]`: each function's value from `stored` (a loaded file), else
        its initial state; several functions in the order the profile lists them."""
        stored = stored or {}
        if len(self.fn) == 1:
            states[self.key] = stored.get(self.key, self.fn[0].initial())
        else:
            old = stored.get(self.key)
            old = old if isinstance(old, dict) else {}
            states[self.key] = {f.name: old.get(f.name, f.initial()) for f in self.fn}

    def merge(self, states: dict, later: dict) -> None:
        """Merge `later[self.key]` (folded after `states`) into `states[self.key]`."""
        for function in self.fn:
            before, after = self._state(states, function), self._state(later, function)
            self.store(states, function, function.merge(before, after))

    def _state(self, states: dict, function: Aggregator) -> Any:
        if len(self.fn) == 1:
            return states[self.key]
        return states[self.key][function.name]

    def value(self, states: dict, function: Aggregator) -> Any:
        """`function`'s current value in `states` (its initial state before any value)."""
        return self._state(states, function)

    def store(self, states: dict, function: Aggregator, state: Any) -> None:
        """Put `function`'s value in `states`: directly for one function, by name for several."""
        if len(self.fn) == 1:
            states[self.key] = state
        else:
            states.setdefault(self.key, {})[function.name] = state
