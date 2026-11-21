"""Pure statistical analysis and history drift engine for sketch-tastic sketches.

Transforms a version-0 sketch (and optional `.history/` run files) into a JSON-serializable
payload used by the interactive offline HTML dashboard.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sketchtastic.aggregators import as_number
from sketchtastic.reporting import _locator, _ranked
from sketchtastic.sketch import Sketch, SketchError, Skit, _read_set_file

CONCENTRATION_TARGETS = (50, 80, 90, 95, 99)
MAX_DRIFT_ITEMS = 20
MAX_OUTLIERS = 10
HIGH_CARDINALITY_MIN = 20
HIGH_CARDINALITY_RATIO = 0.5
AVG_KEYS = frozenset({"avg", "sum", "count"})
KNOWN_AGG_FUNCTIONS = frozenset({"SUM", "MIN", "MAX", "AVG", "COUNT", "FIRST", "LAST"})


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _to_epoch_ms(value: Any) -> int | None:
    """Convert a date, datetime, or ISO-8601 string into UTC epoch milliseconds."""
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return int(dt.astimezone(UTC).timestamp() * 1000)
    if isinstance(value, date):
        return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp() * 1000)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            d = date.fromisoformat(text)
        except ValueError:
            return None
        parsed = datetime(d.year, d.month, d.day, tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.astimezone(UTC).timestamp() * 1000)


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
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
    return value


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _weighted_median(pairs: list[tuple[float, int]]) -> float | None:
    """Exact observation-rank weighted median over positive integer counts."""
    filtered = sorted((val, w) for val, w in pairs if w > 0)
    total = sum(w for _, w in filtered)
    if total <= 0:
        return None
    low_rank = (total + 1) // 2
    high_rank = (total // 2) + 1 if total % 2 == 0 else low_rank
    low_val = high_val = None
    running = 0
    for val, w in filtered:
        running += w
        if low_val is None and running >= low_rank:
            low_val = val
        if high_val is None and running >= high_rank:
            high_val = val
            break
    assert low_val is not None and high_val is not None
    return (low_val + high_val) / 2.0


def _concentration(rows: list[tuple[str, Skit]], total: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    n_skits = len(rows)
    for target in CONCENTRATION_TARGETS:
        if total <= 0 or n_skits == 0:
            result.append(
                {
                    "target_pct": target,
                    "skits_needed": 0,
                    "skit_pct": None,
                    "achieved_pct": None,
                }
            )
            continue
        needed = 0
        cumulative = 0
        cutoff = total * (target / 100.0)
        for _, skit in rows:
            cumulative += skit.meta["count"]
            needed += 1
            if cumulative + 1e-12 >= cutoff:
                break
        result.append(
            {
                "target_pct": target,
                "skits_needed": needed,
                "skit_pct": round(100.0 * needed / n_skits, 2),
                "achieved_pct": round(100.0 * cumulative / total, 2),
            }
        )
    return result


def _parse_bool(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def _field_type_stats(
    non_null: list[tuple[str, int]], has_any: bool
) -> tuple[str, Any, Any, float | None, float | None, float | None]:
    """Classify a field as boolean, numeric, or enum and compute min/max and type stats."""
    bool_pairs: list[tuple[bool, str, int]] = []
    is_boolean = bool(non_null)
    for val, obs in non_null:
        parsed_bool = _parse_bool(val)
        if parsed_bool is None:
            is_boolean = False
            break
        bool_pairs.append((parsed_bool, val, obs))

    if is_boolean:
        ordered_bools = sorted(bool_pairs, key=lambda item: (item[0], item[1]))
        total_obs = sum(obs for _, _, obs in bool_pairs)
        true_obs = sum(obs for flag, _, obs in bool_pairs if flag)
        true_pct = round(100.0 * true_obs / total_obs, 4) if total_obs > 0 else None
        return "boolean", ordered_bools[0][1], ordered_bools[-1][1], None, None, true_pct

    numeric_pairs: list[tuple[int | float, int]] = []
    is_numeric = bool(non_null)
    for val, obs in non_null:
        parsed = as_number(val)
        if parsed is None:
            is_numeric = False
            break
        numeric_pairs.append((parsed, obs))

    if is_numeric:
        nums = [n for n, _ in numeric_pairs]
        num_weight = sum(obs for _, obs in numeric_pairs)
        mean = sum(n * obs for n, obs in numeric_pairs) / num_weight if num_weight > 0 else None
        med = _weighted_median([(float(n), obs) for n, obs in numeric_pairs])
        return "numeric", min(nums), max(nums), mean, med, None
    if non_null:
        strs = [val for val, _ in non_null]
        return "enum", min(strs), max(strs), None, None, None
    fallback = "NULL" if has_any else None
    return "enum", fallback, fallback, None, None, None


def _summarize_field(key: str, rows: list[tuple[str, Skit]], total: int) -> dict[str, Any]:
    n_skits = len(rows)
    by_val: dict[str, list[int]] = {}
    for _, skit in rows:
        val = skit.tokens.get(key, "NULL")
        entry = by_val.get(val)
        if entry is None:
            by_val[val] = [skit.meta["count"], 1]
        else:
            entry[0] += skit.meta["count"]
            entry[1] += 1

    ordered = sorted(by_val.items(), key=lambda item: (-item[1][0], item[0]))
    values = [
        {
            "value": val,
            "count": obs,
            "weight_pct": round(100.0 * obs / total, 4) if total else None,
            "skit_count": sc,
            "skit_pct": round(100.0 * sc / n_skits, 4) if n_skits else None,
        }
        for val, (obs, sc) in ordered
    ]
    non_null = [(val, obs) for val, (obs, _) in by_val.items() if val != "NULL"]
    null_obs = by_val.get("NULL", [0, 0])[0]
    field_type, min_val, max_val, w_mean, w_med, true_pct = _field_type_stats(
        non_null, bool(by_val)
    )
    cardinality = len(values)
    mode = (
        {
            "value": values[0]["value"],
            "count": values[0]["count"],
            "weight_pct": values[0]["weight_pct"],
        }
        if values
        else None
    )
    return {
        "key": key,
        "field_type": field_type,
        "cardinality": cardinality,
        "non_null_cardinality": len(non_null),
        "is_constant": cardinality <= 1,
        "is_high_cardinality": (
            cardinality > HIGH_CARDINALITY_MIN and (cardinality / n_skits) >= HIGH_CARDINALITY_RATIO
        ),
        "is_boolean": field_type == "boolean",
        "is_numeric": field_type == "numeric",
        "true_pct": true_pct,
        "null_observations": null_obs,
        "null_pct": round(100.0 * null_obs / total, 4) if total else None,
        "min": min_val,
        "max": max_val,
        "mode": mode,
        "weighted_mean": w_mean,
        "weighted_median": w_med,
        "values": values,
    }


def _analyze_fields(rows: list[tuple[str, Skit]], total: int) -> list[dict[str, Any]]:
    if not rows:
        return []
    field_order = list(dict.fromkeys(k for _, skit in rows for k in skit.tokens))
    return [_summarize_field(key, rows, total) for key in field_order]


def _is_avg_dict(value: Any) -> bool:
    return isinstance(value, dict) and value.keys() == AVG_KEYS


def _is_multi_fn_dict(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and not _is_avg_dict(value)
        and all(k in KNOWN_AGG_FUNCTIONS for k in value)
    )


def _classify_scalar(value: Any) -> str | None:
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if _is_number(value):
        return "numeric"
    if isinstance(value, list):
        return "samples"
    return "text" if isinstance(value, str) else None


def _tokens_preview(tokens: dict[str, str], limit: int = 4) -> str:
    items = [f"{k}={v}" for k, v in tokens.items() if v not in ("NULL", "FALSE")]
    if not items:
        items = [f"{k}={v}" for k, v in list(tokens.items())[:limit]]
    return ", ".join(items[:limit])


def _resolve_kind(kinds: set[str]) -> str:
    for preferred in ("datetime", "date", "numeric", "samples", "text"):
        if preferred in kinds:
            return preferred
    return "empty"


def _safe_extremum(values: list[Any], *, pick_max: bool) -> Any:
    if not values:
        return None
    fn = max if pick_max else min
    try:
        return _json_safe(fn(values))
    except TypeError:
        return _json_safe(fn(str(v) for v in values))


@dataclass
class _AggAccumulator:
    functions: list[str] = field(default_factory=list)
    fn_seen: set[str] = field(default_factory=set)
    kinds: set[str] = field(default_factory=set)
    sum_total: float | int = 0
    has_sum: bool = False
    count_total: int = 0
    has_count: bool = False
    avg_sum_total: float = 0.0
    avg_count_total: int = 0
    has_avg: bool = False
    min_candidates: list[Any] = field(default_factory=list)
    max_candidates: list[Any] = field(default_factory=list)
    skit_metrics: list[tuple[str, int, float, dict[str, str]]] = field(default_factory=list)
    skit_time_pairs: list[tuple[str, int, int]] = field(default_factory=list)
    metric_name: str = "VALUE"

    def record_fn(self, name: str) -> None:
        if name not in self.fn_seen:
            self.fn_seen.add(name)
            self.functions.append(name)

    def fold_avg(self, raw: dict[str, Any]) -> None:
        self.has_avg = True
        self.kinds.add("numeric")
        c = raw.get("count") or 0
        s = raw.get("sum") or 0
        if _is_number(c) and c > 0 and _is_number(s):
            self.avg_count_total += int(c)
            self.avg_sum_total += float(s)

    def fold_multi_fn(self, fid: str, skit: Skit, raw: dict[str, Any]) -> None:
        for fn_name in raw:
            self.record_fn(fn_name)
        if "SUM" in raw and _is_number(raw["SUM"]):
            self.sum_total += raw["SUM"]
            self.has_sum = True
            self.kinds.add("numeric")
        if "COUNT" in raw and _is_number(raw["COUNT"]):
            self.count_total += int(raw["COUNT"])
            self.has_count = True
            self.kinds.add("numeric")
        if "AVG" in raw and _is_avg_dict(raw["AVG"]):
            self.fold_avg(raw["AVG"])

        mn, mx = raw.get("MIN"), raw.get("MAX")
        for candidate, bucket in ((mn, self.min_candidates), (mx, self.max_candidates)):
            kind = _classify_scalar(candidate)
            if kind:
                self.kinds.add(kind)
                bucket.append(candidate)

        primary = self._multi_primary(raw, mx)
        if primary is not None:
            self.skit_metrics.append((fid, skit.meta["count"], primary, skit.tokens))

        if isinstance(mn, (date, datetime)) or isinstance(mx, (date, datetime)):
            lo = _to_epoch_ms(mn if mn is not None else mx)
            hi = _to_epoch_ms(mx if mx is not None else mn)
            if lo is not None and hi is not None:
                self.skit_time_pairs.append((fid, min(lo, hi), max(lo, hi)))

    def _multi_primary(self, raw: dict[str, Any], mx: Any) -> float | None:
        if "AVG" in raw and _is_avg_dict(raw["AVG"]):
            self.metric_name = "AVG"
            return float(raw["AVG"]["avg"]) if raw["AVG"].get("avg") is not None else None
        if "SUM" in raw and _is_number(raw["SUM"]):
            self.metric_name = "SUM"
            return float(raw["SUM"])
        if "COUNT" in raw and _is_number(raw["COUNT"]):
            self.metric_name = "COUNT"
            return float(raw["COUNT"])
        if _is_number(mx):
            self.metric_name = "MAX"
            return float(mx)
        return None

    def fold_scalar(self, fid: str, skit: Skit, raw: Any) -> None:
        self.record_fn("VALUE")
        kind = _classify_scalar(raw)
        if kind:
            self.kinds.add(kind)
        if kind == "numeric":
            self.sum_total += raw
            self.has_sum = True
            self.min_candidates.append(raw)
            self.max_candidates.append(raw)
            self.metric_name = "VALUE"
            self.skit_metrics.append((fid, skit.meta["count"], float(raw), skit.tokens))
        elif kind in ("datetime", "date"):
            self.min_candidates.append(raw)
            self.max_candidates.append(raw)
            ms = _to_epoch_ms(raw)
            if ms is not None:
                self.skit_time_pairs.append((fid, ms, ms))
        elif kind == "text":
            self.min_candidates.append(raw)
            self.max_candidates.append(raw)

    def fold(self, fid: str, skit: Skit, raw: Any) -> None:
        if _is_multi_fn_dict(raw):
            self.fold_multi_fn(fid, skit, raw)
        elif _is_avg_dict(raw):
            self.record_fn("AVG")
            self.fold_avg(raw)
            if raw.get("avg") is not None:
                self.metric_name = "AVG"
                self.skit_metrics.append((fid, skit.meta["count"], float(raw["avg"]), skit.tokens))
        else:
            self.fold_scalar(fid, skit, raw)


def _summarize_aggregate(
    key: str, rows: list[tuple[str, Skit]]
) -> tuple[dict[str, Any], dict[str, Any] | None, list[tuple[str, int, int]]]:
    acc = _AggAccumulator()
    for fid, skit in rows:
        raw = skit.aggregates.get(key)
        if raw is not None:
            acc.fold(fid, skit, raw)

    kind = _resolve_kind(acc.kinds)
    global_min = _safe_extremum(acc.min_candidates, pick_max=False)
    global_max = _safe_extremum(acc.max_candidates, pick_max=True)
    weighted_mean = (
        (acc.avg_sum_total / acc.avg_count_total)
        if (acc.has_avg and acc.avg_count_total > 0)
        else None
    )
    nums = [val for _, _, val, _ in acc.skit_metrics]
    outliers = [
        {"id": fid, "count": cnt, "value": val, "tokens_preview": _tokens_preview(toks)}
        for fid, cnt, val, toks in sorted(
            acc.skit_metrics, key=lambda item: (-item[2], -item[1], item[0])
        )[:MAX_OUTLIERS]
    ]
    summary = {
        "key": key,
        "kind": kind,
        "functions": acc.functions,
        "global_sum": acc.sum_total
        if acc.has_sum
        else (acc.avg_sum_total if acc.has_avg else None),
        "global_count": (
            acc.count_total if acc.has_count else (acc.avg_count_total if acc.has_avg else None)
        ),
        "global_min": global_min,
        "global_max": global_max,
        "weighted_mean": weighted_mean,
        "skit_stats": {
            "metric": acc.metric_name,
            "active_skits": len(nums),
            "min": min(nums) if nums else None,
            "max": max(nums) if nums else None,
            "mean": (sum(nums) / len(nums)) if nums else None,
            "median": _median(nums),
        },
        "outliers": outliers,
    }
    axis = None
    if kind in ("datetime", "date") and acc.skit_time_pairs:
        axis = {
            "id": f"agg:{key}",
            "kind": kind,
            "label": key,
            "min_ms": min(lo for _, lo, _ in acc.skit_time_pairs),
            "max_ms": max(hi for _, _, hi in acc.skit_time_pairs),
            "min_iso": global_min,
            "max_iso": global_max,
        }
    return summary, axis, acc.skit_time_pairs


def _analyze_aggregates(
    rows: list[tuple[str, Skit]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, list[int]]]]:
    """Return (aggregate_summaries, datetime_axes, per_skit_time_bounds)."""
    if not rows:
        return [], [], {}
    agg_order = list(dict.fromkeys(k for _, skit in rows for k in skit.aggregates))
    summaries: list[dict[str, Any]] = []
    time_axes: list[dict[str, Any]] = []
    skit_bounds: dict[str, dict[str, list[int]]] = {fid: {} for fid, _ in rows}

    for key in agg_order:
        summary, axis, time_pairs = _summarize_aggregate(key, rows)
        summaries.append(summary)
        if axis is not None:
            time_axes.append(axis)
            for fid, lo, hi in time_pairs:
                skit_bounds[fid][axis["id"]] = [lo, hi]
    return summaries, time_axes, skit_bounds


def _default_history_dir(sketch_path: Path | str) -> Path:
    return Path(os.path.splitext(str(sketch_path))[0] + ".history")


def _load_run_file(
    entry: Path,
) -> tuple[str, dict[str, Any], dict[str, tuple[int, dict[str, str]]]]:
    raw = _read_set_file(str(entry))
    sketch = Sketch()
    sketch.load(str(entry))
    run_hdr = raw.get("run") if isinstance(raw.get("run"), dict) else {}
    run_id = str(run_hdr.get("id") or raw.get("last_run") or entry.stem)
    skits_map: dict[str, tuple[int, dict[str, str]]] = {}
    total_events = 0
    for fid in sketch:
        skit = sketch.get(fid)
        if skit is None:
            continue
        cnt = skit.meta.get("count", 0)
        if type(cnt) is not int or cnt < 0:
            raise SketchError(f"Invalid count in {entry.name}")
        skits_map[fid] = (cnt, dict(skit.tokens))
        total_events += cnt
    info = {
        "id": run_id,
        "started": _json_safe(run_hdr.get("started")),
        "finished": _json_safe(run_hdr.get("finished")),
        "started_ms": _to_epoch_ms(run_hdr.get("started")),
        "finished_ms": _to_epoch_ms(run_hdr.get("finished")),
        "source": str(run_hdr["source"]) if run_hdr.get("source") is not None else None,
        "events": int(run_hdr["events"])
        if isinstance(run_hdr.get("events"), int)
        else total_events,
        "skipped_lines": (
            int(run_hdr.get("skipped_lines", 0))
            if isinstance(run_hdr.get("skipped_lines"), int)
            else 0
        ),
        "skit_count": len(skits_map),
        "observed_events": total_events,
    }
    return run_id, info, skits_map


def _compute_run_drift(
    prev_info: dict[str, Any],
    prev_skits: dict[str, tuple[int, dict[str, str]]],
    curr_info: dict[str, Any],
    curr_skits: dict[str, tuple[int, dict[str, str]]],
) -> dict[str, Any]:
    prev_total = prev_info["observed_events"]
    curr_total = curr_info["observed_events"]
    prev_ids, curr_ids = set(prev_skits), set(curr_skits)
    new_ids = curr_ids - prev_ids
    gone_ids = prev_ids - curr_ids
    both_ids = prev_ids & curr_ids

    new_list = sorted(
        (
            {
                "id": fid,
                "count": curr_skits[fid][0],
                "weight_pct": round(100.0 * curr_skits[fid][0] / curr_total, 2)
                if curr_total
                else 0.0,
                "tokens": curr_skits[fid][1],
            }
            for fid in new_ids
        ),
        key=lambda x: (-x["count"], x["id"]),
    )
    gone_list = sorted(
        (
            {
                "id": fid,
                "prev_count": prev_skits[fid][0],
                "prev_weight_pct": (
                    round(100.0 * prev_skits[fid][0] / prev_total, 2) if prev_total else 0.0
                ),
                "tokens": prev_skits[fid][1],
            }
            for fid in gone_ids
        ),
        key=lambda x: (-x["prev_count"], x["id"]),
    )
    shifts = []
    for fid in both_ids:
        pc, toks = prev_skits[fid]
        cc, _ = curr_skits[fid]
        pp = (100.0 * pc / prev_total) if prev_total else 0.0
        cp = (100.0 * cc / curr_total) if curr_total else 0.0
        shifts.append(
            {
                "id": fid,
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
    return {
        "from_run": prev_info["id"],
        "to_run": curr_info["id"],
        "new_count": len(new_ids),
        "disappeared_count": len(gone_ids),
        "persisted_count": len(both_ids),
        "new_skits": new_list[:MAX_DRIFT_ITEMS],
        "disappeared_skits": gone_list[:MAX_DRIFT_ITEMS],
        "top_shifts": shifts[:MAX_DRIFT_ITEMS],
    }


def _load_history(
    sketch_path: Path | str, history_dir: Path | str | None
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Load run files from explicit or auto-detected history directory."""
    explicit = history_dir is not None
    directory = Path(history_dir) if explicit else _default_history_dir(sketch_path)
    if explicit:
        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"History directory does not exist: {directory}")
    elif not directory.is_dir():
        return {"directory": None, "runs": [], "drift": [], "warnings": []}, {}

    warnings: list[str] = []
    loaded: list[tuple[str, dict[str, Any], dict[str, tuple[int, dict[str, str]]]]] = []
    for entry in sorted(directory.iterdir(), key=lambda p: p.name):
        if not entry.is_file() or entry.suffix.lower() not in (".yaml", ".yml"):
            continue
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


def _build_runs_axis(
    rows: list[tuple[str, Skit]], run_map: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    run_ids: set[str] = set(run_map.keys())
    for _, skit in rows:
        for key in ("first_seen", "last_seen"):
            val = skit.meta.get(key)
            if isinstance(val, str) and val:
                run_ids.add(val)
    if not run_ids:
        return None
    run_entries = []
    for idx, rid in enumerate(sorted(run_ids)):
        info = run_map.get(rid, {})
        run_entries.append(
            {
                "id": rid,
                "index": idx,
                "started": info.get("started"),
                "finished": info.get("finished"),
                "started_ms": info.get("started_ms"),
                "finished_ms": info.get("finished_ms"),
                "events": info.get("events"),
                "skit_count": info.get("skit_count"),
            }
        )
    return {"id": "runs", "kind": "runs", "label": "First / Last Seen Run", "runs": run_entries}


def _extract_sample_record(skit: Skit, slot: str) -> Any:
    entries = skit.meta.get(slot)
    if isinstance(entries, list) and entries and isinstance(entries[0], dict):
        return _json_safe(entries[0].get("record"))
    return None


def analyze_sketch(
    sketch_path: Path | str, history_dir: Path | str | None = None
) -> dict[str, Any]:
    """Load and analyze a sketch file (and optional history) into a JSON-safe dict."""
    raw_header = _read_set_file(str(sketch_path))
    rows = _ranked(sketch_path)
    total = sum(skit.meta["count"] for _, skit in rows)
    singletons = sum(1 for _, skit in rows if skit.meta["count"] == 1)

    field_summaries = _analyze_fields(rows, total)
    agg_summaries, time_axes, skit_bounds = _analyze_aggregates(rows)
    history, run_map = _load_history(sketch_path, history_dir)
    runs_axis = _build_runs_axis(rows, run_map)
    if runs_axis is not None:
        time_axes.append(runs_axis)

    skits_out: list[dict[str, Any]] = []
    cumulative = 0
    for fid, skit in rows:
        count = skit.meta["count"]
        cumulative += count
        first_rec = _extract_sample_record(skit, "first")
        last_rec = _extract_sample_record(skit, "last")
        if last_rec == first_rec:
            last_rec = None
        skits_out.append(
            {
                "id": fid,
                "count": count,
                "weight_pct": round(100.0 * count / total, 4) if total else 0.0,
                "cum_pct": round(100.0 * cumulative / total, 4) if total else 0.0,
                "first_seen": skit.meta.get("first_seen"),
                "last_seen": skit.meta.get("last_seen"),
                "tokens": dict(skit.tokens),
                "aggregates": _json_safe(skit.aggregates),
                "time_bounds": skit_bounds.get(fid, {}),
                "first_record": first_rec,
                "last_record": last_rec,
                "sample_locator": _locator(sketch_path, fid),
            }
        )

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
            "concentration": _concentration(rows, total),
        },
        "fields": field_summaries,
        "aggregates": agg_summaries,
        "time_axes": time_axes,
        "history": history,
        "skits": skits_out,
    }
