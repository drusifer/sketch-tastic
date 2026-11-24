"""Lean dashboard payload and history drift builder for sketch-tastic.

Transforms a version-0 sketch (and optional `.history/` run files) in a single YAML read
into the JSON-serializable view-model consumed by the offline interactive HTML dashboard.
Client-side JS owns live filtered/re-weighted statistics so metrics are never computed twice.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sketchtastic._io import history_dir_for, is_number, sample_locator
from sketchtastic.aggregators import is_histogram_state
from sketchtastic.sketch import (
    SketchError,
    Skit,
    load_ranked_skits,
    load_sketch_with_header,
)

MAX_DRIFT_ITEMS = 20
AVG_KEYS = frozenset({"avg", "sum", "count"})
KNOWN_AGG_FUNCTIONS = frozenset({"SUM", "MIN", "MAX", "AVG", "COUNT", "FIRST", "LAST", "HISTOGRAM"})


def _to_epoch_ms(value: Any) -> int | None:
    """Convert a date, datetime, or ISO-8601 string into UTC epoch milliseconds."""
    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return int(moment.astimezone(UTC).timestamp() * 1000)
    if isinstance(value, date):
        return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp() * 1000)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    moment = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return int(moment.astimezone(UTC).timestamp() * 1000)


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return moment.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _json_safe(value: Any) -> Any:
    """Convert YAML-loaded values (including date/datetime) into plain JSON-safe primitives."""
    if isinstance(value, (datetime, date)):
        return _iso(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [_json_safe(v) for v in sorted(value, key=str)]
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def _is_avg_dict(value: Any) -> bool:
    return isinstance(value, dict) and AVG_KEYS.issubset(value)


def _is_multi_fn_dict(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and not _is_avg_dict(value)
        and not is_histogram_state(value)
        and set(value).issubset(KNOWN_AGG_FUNCTIONS)
    )


def _classify_scalar(value: Any) -> str | None:
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if is_number(value):
        return "numeric"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "samples"
    return None


def _resolve_kind(kinds: set[str]) -> str:
    for candidate in ("datetime", "date", "numeric", "text", "samples"):
        if candidate in kinds:
            return candidate
    return "empty"


def _safe_time_extremum(values: list[Any], *, pick_max: bool) -> str | None:
    if not values:
        return None
    keyed = [(_to_epoch_ms(v), v) for v in values]
    valid = [(ms, v) for ms, v in keyed if ms is not None]
    if not valid:
        return None
    chosen = (
        max(valid, key=lambda item: item[0]) if pick_max else min(valid, key=lambda item: item[0])
    )
    return _iso(chosen[1])


def _record_fn(functions: list[str], seen: set[str], name: str) -> None:
    if name not in seen:
        seen.add(name)
        functions.append(name)


def _time_bounds_from_pair(first_v: Any, last_v: Any) -> tuple[int, int] | None:
    if not (isinstance(first_v, (date, datetime)) or isinstance(last_v, (date, datetime))):
        return None
    lo_val = first_v if isinstance(first_v, (date, datetime)) else last_v
    hi_val = last_v if isinstance(last_v, (date, datetime)) else first_v
    lo_ms = _to_epoch_ms(lo_val)
    hi_ms = _to_epoch_ms(hi_val)
    if lo_ms is None or hi_ms is None:
        return None
    return min(lo_ms, hi_ms), max(lo_ms, hi_ms)


def _primary_metric_for_multi(raw: dict[str, Any]) -> str | None:
    if "AVG" in raw and _is_avg_dict(raw["AVG"]):
        return "AVG"
    if "SUM" in raw and is_number(raw["SUM"]):
        return "SUM"
    if "COUNT" in raw and is_number(raw["COUNT"]):
        return "COUNT"
    if is_number(raw.get("MAX")):
        return "MAX"
    return None


def _inspect_multi_entry(
    raw: dict[str, Any],
    functions: list[str],
    fn_seen: set[str],
    kinds: set[str],
    time_values: list[Any],
) -> tuple[str | None, tuple[int, int] | None]:
    for fn_name in raw:
        _record_fn(functions, fn_seen, fn_name)
    if any(
        fn in raw and (is_number(raw[fn]) or _is_avg_dict(raw[fn]) or is_histogram_state(raw[fn]))
        for fn in ("SUM", "COUNT", "AVG", "HISTOGRAM")
    ):
        kinds.add("numeric")
    mn, mx = raw.get("MIN"), raw.get("MAX")
    for candidate in (mn, mx):
        kind = _classify_scalar(candidate)
        if kind:
            kinds.add(kind)
        if isinstance(candidate, (date, datetime)):
            time_values.append(candidate)
    return _primary_metric_for_multi(raw), _time_bounds_from_pair(mn, mx)


def _inspect_single_entry(
    raw: Any,
    functions: list[str],
    fn_seen: set[str],
    kinds: set[str],
    time_values: list[Any],
) -> tuple[str | None, tuple[int, int] | None]:
    if _is_avg_dict(raw):
        _record_fn(functions, fn_seen, "AVG")
        kinds.add("numeric")
        return "AVG", None
    if is_histogram_state(raw):
        _record_fn(functions, fn_seen, "HISTOGRAM")
        kinds.add("numeric")
        return "HISTOGRAM", None
    _record_fn(functions, fn_seen, "VALUE")
    kind = _classify_scalar(raw)
    if kind:
        kinds.add(kind)
    if kind in ("datetime", "date"):
        time_values.append(raw)
        ms = _to_epoch_ms(raw)
        return None, (ms, ms) if ms is not None else None
    return ("VALUE" if kind == "numeric" else None), None


def _describe_aggregate(
    key: str, rows: list[tuple[str, Skit]]
) -> tuple[dict[str, Any], dict[str, Any] | None, list[tuple[str, int, int]]]:
    functions: list[str] = []
    fn_seen: set[str] = set()
    kinds: set[str] = set()
    time_values: list[Any] = []
    time_pairs: list[tuple[str, int, int]] = []
    metric_name = "VALUE"

    for sid, skit in rows:
        raw = skit.aggregates.get(key)
        if raw is None:
            continue
        if _is_multi_fn_dict(raw):
            metric, pair = _inspect_multi_entry(raw, functions, fn_seen, kinds, time_values)
        else:
            metric, pair = _inspect_single_entry(raw, functions, fn_seen, kinds, time_values)
        if metric is not None:
            metric_name = metric
        if pair is not None:
            time_pairs.append((sid, pair[0], pair[1]))

    kind = _resolve_kind(kinds)
    descriptor = {
        "key": key,
        "kind": kind,
        "functions": functions,
        "metric": metric_name,
    }
    axis = None
    if kind in ("datetime", "date") and time_pairs:
        axis = {
            "id": f"agg:{key}",
            "kind": kind,
            "label": key,
            "min_ms": min(lo for _, lo, _ in time_pairs),
            "max_ms": max(hi for _, _, hi in time_pairs),
            "min_iso": _safe_time_extremum(time_values, pick_max=False),
            "max_iso": _safe_time_extremum(time_values, pick_max=True),
        }
    return descriptor, axis, time_pairs


def _describe_aggregates(
    rows: list[tuple[str, Skit]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, list[int]]]]:
    """Build lightweight aggregate metadata, datetime axes, and per-skit time bounds."""
    if not rows:
        return [], [], {}
    agg_order = list(dict.fromkeys(k for _, skit in rows for k in skit.aggregates))
    descriptors: list[dict[str, Any]] = []
    time_axes: list[dict[str, Any]] = []
    skit_bounds: dict[str, dict[str, list[int]]] = {sid: {} for sid, _ in rows}

    for key in agg_order:
        descriptor, axis, time_pairs = _describe_aggregate(key, rows)
        descriptors.append(descriptor)
        if axis is not None:
            time_axes.append(axis)
            for sid, lo, hi in time_pairs:
                skit_bounds[sid][axis["id"]] = [lo, hi]
    return descriptors, time_axes, skit_bounds


def _extract_additive_weight(raw: Any) -> tuple[float | int | None, str | None]:
    """Return `(value, source)` if an aggregate entry is additive, else `(None, None)`."""
    if _is_multi_fn_dict(raw):
        return _extract_multi_additive_weight(raw)
    if _is_avg_dict(raw) and is_number(raw.get("sum")):
        return raw["sum"], "AVG.sum"
    if is_number(raw):
        return raw, "VALUE"
    return None, None


def _extract_multi_additive_weight(raw: dict[str, Any]) -> tuple[float | int | None, str | None]:
    if "SUM" in raw and is_number(raw["SUM"]):
        return raw["SUM"], "SUM"
    if "AVG" in raw and _is_avg_dict(raw["AVG"]) and is_number(raw["AVG"].get("sum")):
        return raw["AVG"]["sum"], "AVG.sum"
    if "COUNT" in raw and is_number(raw["COUNT"]):
        return raw["COUNT"], "COUNT"
    return None, None


def _evaluate_weighting_key(
    key: str, rows: list[tuple[str, Skit]]
) -> tuple[dict[str, Any], dict[str, float | int]] | None:
    per_skit: dict[str, float | int] = {}
    source: str | None = None
    total_w: float | int = 0
    active = 0
    for sid, skit in rows:
        raw = skit.aggregates.get(key)
        if raw is None:
            per_skit[sid] = 0
            continue
        val, src = _extract_additive_weight(raw)
        if val is None or not math.isfinite(val) or val < 0:
            return None
        source = source or src
        per_skit[sid] = val
        total_w += val
        active += int(val > 0)
    if source is None or total_w <= 0:
        return None
    meta = {
        "key": key,
        "source": source,
        "total": total_w,
        "active_skits": active,
        "total_skits": len(rows),
    }
    return meta, per_skit


def _discover_weightings(
    rows: list[tuple[str, Skit]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float | int]]]:
    """Auto-discover non-negative additive aggregates eligible as dashboard weights."""
    if not rows:
        return [], {}
    agg_order = list(dict.fromkeys(k for _, skit in rows for k in skit.aggregates))
    weightings: list[dict[str, Any]] = []
    skit_weights: dict[str, dict[str, float | int]] = {sid: {} for sid, _ in rows}
    for key in agg_order:
        evaluated = _evaluate_weighting_key(key, rows)
        if evaluated is None:
            continue
        meta, per_skit = evaluated
        weightings.append(meta)
        for sid, val in per_skit.items():
            skit_weights[sid][key] = val
    return weightings, skit_weights


def _resolve_default_weighting(default_weight: str | None, weightings: list[dict[str, Any]]) -> str:
    """Validate optional default weighting key and normalize to `'count'` or `'agg:<key>'`."""
    if default_weight is None or default_weight == "count":
        return "count"
    candidate = default_weight.removeprefix("agg:")
    valid_keys = [w["key"] for w in weightings]
    if candidate in valid_keys:
        return f"agg:{candidate}"
    options = ", ".join(["count", *valid_keys])
    raise ValueError(
        f"Unknown or ineligible weighting {default_weight!r}; available weightings: {options}"
    )


def _extract_run_skits(
    sketch_name: str, sketch: Any
) -> tuple[dict[str, tuple[int, dict[str, str]]], int]:
    skits_map: dict[str, tuple[int, dict[str, str]]] = {}
    total_events = 0
    for sid in sketch:
        skit = sketch.get(sid)
        if skit is None:
            continue
        cnt = skit.meta.get("count", 0)
        if type(cnt) is not int or cnt < 0:
            raise SketchError(f"Invalid count in {sketch_name}")
        skits_map[sid] = (cnt, dict(skit.tokens))
        total_events += cnt
    return skits_map, total_events


def _load_run_file(
    entry: Path,
) -> tuple[str, dict[str, Any], dict[str, tuple[int, dict[str, str]]]]:
    raw, sketch = load_sketch_with_header(entry)
    run_hdr = raw.get("run") if isinstance(raw.get("run"), dict) else {}
    run_id = str(run_hdr.get("id") or raw.get("last_run") or entry.stem)
    skits_map, total_events = _extract_run_skits(entry.name, sketch)
    events_val = run_hdr.get("events")
    skipped_val = run_hdr.get("skipped_lines", 0)
    info = {
        "id": run_id,
        "started": _json_safe(run_hdr.get("started")),
        "finished": _json_safe(run_hdr.get("finished")),
        "started_ms": _to_epoch_ms(run_hdr.get("started")),
        "finished_ms": _to_epoch_ms(run_hdr.get("finished")),
        "source": str(run_hdr["source"]) if run_hdr.get("source") is not None else None,
        "events": events_val if type(events_val) is int else total_events,
        "skipped_lines": skipped_val if type(skipped_val) is int else 0,
        "skit_count": len(skits_map),
        "observed_events": total_events,
    }
    return run_id, info, skits_map


def _drift_new_skits(
    new_ids: set[str], curr_skits: dict[str, tuple[int, dict[str, str]]], curr_total: int
) -> list[dict[str, Any]]:
    items = [
        {
            "id": sid,
            "count": curr_skits[sid][0],
            "weight_pct": round(100.0 * curr_skits[sid][0] / curr_total, 2) if curr_total else 0.0,
            "tokens": curr_skits[sid][1],
        }
        for sid in new_ids
    ]
    items.sort(key=lambda x: (-x["count"], x["id"]))
    return items[:MAX_DRIFT_ITEMS]


def _drift_gone_skits(
    gone_ids: set[str], prev_skits: dict[str, tuple[int, dict[str, str]]], prev_total: int
) -> list[dict[str, Any]]:
    items = [
        {
            "id": sid,
            "prev_count": prev_skits[sid][0],
            "prev_weight_pct": (
                round(100.0 * prev_skits[sid][0] / prev_total, 2) if prev_total else 0.0
            ),
            "tokens": prev_skits[sid][1],
        }
        for sid in gone_ids
    ]
    items.sort(key=lambda x: (-x["prev_count"], x["id"]))
    return items[:MAX_DRIFT_ITEMS]


def _drift_shifts(
    both_ids: set[str],
    prev_skits: dict[str, tuple[int, dict[str, str]]],
    curr_skits: dict[str, tuple[int, dict[str, str]]],
    totals: tuple[int, int],
) -> list[dict[str, Any]]:
    prev_total, curr_total = totals
    shifts = []
    for sid in both_ids:
        pc, toks = prev_skits[sid]
        cc, _ = curr_skits[sid]
        pp = (100.0 * pc / prev_total) if prev_total else 0.0
        cp = (100.0 * cc / curr_total) if curr_total else 0.0
        shifts.append(
            {
                "id": sid,
                "prev_count": pc,
                "curr_count": cc,
                "delta_count": cc - pc,
                "prev_pct": round(pp, 2),
                "curr_pct": round(cp, 2),
                "delta_pct": round(cp - pp, 2),
                "tokens": toks,
            }
        )
    shifts.sort(key=lambda x: (-abs(x["delta_pct"]), -abs(x["delta_count"]), x["id"]))
    return shifts[:MAX_DRIFT_ITEMS]


def _compute_run_drift(
    prev_info: dict[str, Any],
    prev_skits: dict[str, tuple[int, dict[str, str]]],
    curr_info: dict[str, Any],
    curr_skits: dict[str, tuple[int, dict[str, str]]],
) -> dict[str, Any]:
    prev_ids, curr_ids = set(prev_skits), set(curr_skits)
    new_ids = curr_ids - prev_ids
    gone_ids = prev_ids - curr_ids
    both_ids = prev_ids & curr_ids
    prev_total = prev_info["observed_events"]
    curr_total = curr_info["observed_events"]
    return {
        "from_run": prev_info["id"],
        "to_run": curr_info["id"],
        "new_count": len(new_ids),
        "disappeared_count": len(gone_ids),
        "persisted_count": len(both_ids),
        "new_skits": _drift_new_skits(new_ids, curr_skits, curr_total),
        "disappeared_skits": _drift_gone_skits(gone_ids, prev_skits, prev_total),
        "top_shifts": _drift_shifts(both_ids, prev_skits, curr_skits, (prev_total, curr_total)),
    }


def _resolve_history_dir(sketch_path: Path | str, history_dir: Path | str | None) -> Path | None:
    if history_dir is not None:
        directory = Path(history_dir)
        if not directory.is_dir():
            raise ValueError(f"History directory does not exist: {directory}")
        return directory
    directory = history_dir_for(sketch_path)
    return directory if directory.is_dir() else None


def _iter_history_yaml(directory: Path) -> list[Path]:
    return [
        entry
        for entry in sorted(directory.iterdir(), key=lambda p: p.name)
        if not entry.is_symlink() and entry.is_file() and entry.suffix.lower() in (".yaml", ".yml")
    ]


def _load_history(
    sketch_path: Path | str, history_dir: Path | str | None
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Load run files from explicit or auto-detected history directory."""
    directory = _resolve_history_dir(sketch_path, history_dir)
    if directory is None:
        return {"directory": None, "runs": [], "drift": [], "warnings": []}, {}

    warnings: list[str] = []
    loaded: list[tuple[str, dict[str, Any], dict[str, tuple[int, dict[str, str]]]]] = []
    for entry in _iter_history_yaml(directory):
        try:
            loaded.append(_load_run_file(entry))
        except (OSError, SketchError, ValueError, TypeError) as exc:
            warnings.append(f"Skipped history file {entry.name}: {exc}")

    loaded.sort(key=lambda item: item[0])
    runs = [info for _, info, _ in loaded]
    run_map = {run_id: info for run_id, info, _ in loaded}
    drift = [
        _compute_run_drift(prev_info, prev_skits, curr_info, curr_skits)
        for (_, prev_info, prev_skits), (_, curr_info, curr_skits) in zip(loaded, loaded[1:])
    ]
    return {
        "directory": str(directory),
        "runs": runs,
        "drift": drift,
        "warnings": warnings,
    }, run_map


def _build_seen_time_axis(
    rows: list[tuple[str, Skit]],
) -> tuple[dict[str, Any] | None, dict[str, list[int]]]:
    """Detect datetime/date `first_seen`/`last_seen` bounds (from profile `event_time`)."""
    bounds_by_sid: dict[str, list[int]] = {}
    candidates: list[Any] = []
    for sid, skit in rows:
        first_v, last_v = skit.meta.get("first_seen"), skit.meta.get("last_seen")
        pair = _time_bounds_from_pair(first_v, last_v)
        if pair is None:
            continue
        bounds_by_sid[sid] = [pair[0], pair[1]]
        candidates.extend(v for v in (first_v, last_v) if isinstance(v, (date, datetime)))
    if not bounds_by_sid:
        return None, {}
    kind = "datetime" if any(isinstance(v, datetime) for v in candidates) else "date"
    axis = {
        "id": "seen",
        "kind": kind,
        "label": "First / Last Seen (Event Time)",
        "min_ms": min(lo for lo, _ in bounds_by_sid.values()),
        "max_ms": max(hi for _, hi in bounds_by_sid.values()),
        "min_iso": _safe_time_extremum(candidates, pick_max=False),
        "max_iso": _safe_time_extremum(candidates, pick_max=True),
    }
    return axis, bounds_by_sid


def _build_runs_axis(
    rows: list[tuple[str, Skit]], run_map: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    run_ids: set[str] = set(run_map)
    for _, skit in rows:
        for key in ("first_seen", "last_seen"):
            val = skit.meta.get(key)
            if isinstance(val, str) and val:
                run_ids.add(val)
    if not run_ids:
        return None
    run_entries = [
        {
            "id": rid,
            "index": idx,
            "started": run_map.get(rid, {}).get("started"),
            "finished": run_map.get(rid, {}).get("finished"),
            "started_ms": run_map.get(rid, {}).get("started_ms"),
            "finished_ms": run_map.get(rid, {}).get("finished_ms"),
            "events": run_map.get(rid, {}).get("events"),
            "skit_count": run_map.get(rid, {}).get("skit_count"),
        }
        for idx, rid in enumerate(sorted(run_ids))
    ]
    return {"id": "runs", "kind": "runs", "label": "First / Last Seen Run", "runs": run_entries}


def _extract_sample_record(skit: Skit, slot: str) -> Any:
    entries = skit.meta.get(slot)
    if isinstance(entries, list) and entries and isinstance(entries[0], dict):
        return _json_safe(entries[0].get("record"))
    return None


def _serialize_skits(
    sketch_path: Path | str,
    rows: list[tuple[str, Skit]],
    total: int,
    skit_weights: dict[str, dict[str, float | int]],
    skit_bounds: dict[str, dict[str, list[int]]],
) -> list[dict[str, Any]]:
    skits_out: list[dict[str, Any]] = []
    cumulative = 0
    for sid, skit in rows:
        count = skit.meta["count"]
        cumulative += count
        first_rec = _extract_sample_record(skit, "first")
        last_rec = _extract_sample_record(skit, "last")
        skits_out.append(
            {
                "id": sid,
                "count": count,
                "weight_pct": round(100.0 * count / total, 4) if total else 0.0,
                "cum_pct": round(100.0 * cumulative / total, 4) if total else 0.0,
                "first_seen": _json_safe(skit.meta.get("first_seen")),
                "last_seen": _json_safe(skit.meta.get("last_seen")),
                "tokens": dict(skit.tokens),
                "aggregates": _json_safe(skit.aggregates),
                "weights": skit_weights.get(sid, {}),
                "time_bounds": skit_bounds.get(sid, {}),
                "first_record": first_rec,
                "last_record": None if last_rec == first_rec else last_rec,
                "sample_locator": sample_locator(sketch_path, sid),
            }
        )
    return skits_out


def _assemble_time_axes(
    rows: list[tuple[str, Skit]],
    agg_axes: list[dict[str, Any]],
    skit_bounds: dict[str, dict[str, list[int]]],
    run_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    time_axes = list(agg_axes)
    seen_axis, seen_bounds = _build_seen_time_axis(rows)
    if seen_axis is not None:
        time_axes.insert(0, seen_axis)
        for sid, pair in seen_bounds.items():
            skit_bounds[sid]["seen"] = pair
    runs_axis = _build_runs_axis(rows, run_map)
    if runs_axis is not None:
        time_axes.append(runs_axis)
    return time_axes


def analyze_sketch(
    sketch_path: Path | str,
    history_dir: Path | str | None = None,
    default_weight: str | None = None,
) -> dict[str, Any]:
    """Load a sketch once (plus optional history) into a lean JSON-safe dashboard payload."""
    raw_header, rows = load_ranked_skits(sketch_path)
    total = sum(skit.meta["count"] for _, skit in rows)
    singletons = sum(1 for _, skit in rows if skit.meta["count"] == 1)

    field_keys = list(dict.fromkeys(k for _, skit in rows for k in skit.tokens))
    agg_descriptors, agg_axes, skit_bounds = _describe_aggregates(rows)
    weightings, skit_weights = _discover_weightings(rows)
    resolved_weight = _resolve_default_weighting(default_weight, weightings)
    history, run_map = _load_history(sketch_path, history_dir)
    time_axes = _assemble_time_axes(rows, agg_axes, skit_bounds, run_map)
    skits_out = _serialize_skits(sketch_path, rows, total, skit_weights, skit_bounds)

    return {
        "meta": {
            "sketch_path": str(sketch_path),
            "sketch_name": Path(sketch_path).name,
            "profile_id": raw_header.get("profile_id"),
            "last_run": raw_header.get("last_run"),
            "total_observations": total,
            "total_skits": len(rows),
            "singleton_skits": singletons,
            "singleton_observations": singletons,
            "singleton_pct": round(100.0 * singletons / total, 2) if total else None,
            "default_weighting": resolved_weight,
        },
        "fields": [{"key": key} for key in field_keys],
        "aggregates": agg_descriptors,
        "weightings": weightings,
        "time_axes": time_axes,
        "history": history,
        "skits": skits_out,
    }
