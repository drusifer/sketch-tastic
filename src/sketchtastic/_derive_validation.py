"""Validate retained aggregate states before a derivation can combine them."""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Sequence

from sketchtastic._io import is_number
from sketchtastic.aggregators import Aggregate, Aggregator, Histogram, log_bin_bounds


def _number(value: Any) -> bool:
    try:
        return is_number(value) and math.isfinite(value)
    except OverflowError:
        return False


def _count(value: Any) -> bool:
    return type(value) is int and value >= 0


def ordered_kind(value: Any) -> str:
    """The kinds MIN/MAX can combine without silently discarding another kind."""
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    return "text" if isinstance(value, str) else "number"


def _histogram_valid(value: Any, function: Histogram) -> bool:
    if not isinstance(value, dict) or not _count(value.get("count")):
        return False
    if function.buckets is not None:
        return _fixed_histogram_valid(value, function)
    bins = value.get("bins")
    return (
        value.get("mode") == "log"
        and set(value) == {"mode", "count", "bins"}
        and isinstance(bins, dict)
        and all(_bin_key(k) and _count(n) for k, n in bins.items())
        and sum(bins.values()) == value["count"]
    )


def _fixed_histogram_valid(value: dict, function: Histogram) -> bool:
    counts = value.get("counts")
    return (
        value.get("mode") == "fixed"
        and set(value) == {"mode", "count", "bounds", "counts"}
        and value.get("bounds") == list(function.buckets)
        and isinstance(counts, list)
        and len(counts) == len(function.buckets) + 1
        and all(_count(n) for n in counts)
        and sum(counts) == value["count"]
    )


def _bin_key(value: Any) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"0|[+-](?:0|-?[1-9][0-9]*)", value):
        return False
    try:
        return all(math.isfinite(bound) for bound in log_bin_bounds(value))
    except OverflowError, ValueError:
        return False


def _average_valid(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"sum", "count", "avg"}:
        return False
    if not _number(value["sum"]) or not _count(value["count"]):
        return False
    if value["count"] == 0:
        return value["avg"] is None and value["sum"] == 0
    return _number(value["avg"]) and math.isclose(
        value["avg"], value["sum"] / value["count"], rel_tol=1e-12, abs_tol=1e-12
    )


def _valid(value: Any, function: Aggregator) -> bool:
    valid = False
    match function.name:
        case "SUM":
            return _number(value)
        case "COUNT":
            return _count(value)
        case "MIN" | "MAX":
            return value is None or _number(value) or isinstance(value, (str, date))
        case "AVG":
            return _average_valid(value)
        case "FIRST" | "LAST":
            return isinstance(value, list) and len(value) <= function.n
        case "HISTOGRAM":
            valid = _histogram_valid(value, function)
    return valid


def validate_states(states: Any, specs: Sequence[Aggregate], location: str) -> None:
    """Do not allow Sketch.load_data's initialization to fabricate missing statistics."""
    if not isinstance(states, dict) or set(states) != {a.key for a in specs}:
        raise ValueError(f"{location}: incomplete or unexpected aggregate keys")
    for aggregate in specs:
        _validate_aggregate(states, aggregate, location)


def _validate_aggregate(states: dict, aggregate: Aggregate, location: str) -> None:
    stored = states[aggregate.key]
    if len(aggregate.fn) > 1 and (
        not isinstance(stored, dict) or set(stored) != {f.name for f in aggregate.fn}
    ):
        raise ValueError(f"{location}.{aggregate.key}: incomplete aggregate functions")
    for function in aggregate.fn:
        value = aggregate.value(states, function)
        if not _valid(value, function):
            raise ValueError(f"{location}.{aggregate.key}.{function.name}: invalid aggregate state")


def merge_states(before: dict, later: dict, specs: Sequence[Aggregate], location: str) -> None:
    """Merge retained statistics, refusing the mixed-kind MIN/MAX lossy fallback."""
    for aggregate in specs:
        for function in aggregate.fn:
            if function.name not in ("MIN", "MAX"):
                continue
            left, right = aggregate.value(before, function), aggregate.value(later, function)
            if left is not None and right is not None and ordered_kind(left) != ordered_kind(right):
                raise ValueError(f"{location}.{aggregate.key}: incompatible MIN/MAX kinds")
        aggregate.merge(before, later)
