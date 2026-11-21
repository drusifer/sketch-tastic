"""Pure statistical analysis and history drift engine for sketch-tastic sketches.

Transforms a version-0 sketch (and optional `.history/` run files) into a JSON-serializable
payload used by the interactive offline HTML dashboard.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sketchtastic.aggregators import as_number
from sketchtastic.reporting import _locator, _ranked
from sketchtastic.sketch import Sketch, SketchError, Skit, _read_set_file

CONCENTRATION_TARGETS = (50, 80, 90, 95, 99)
MAX_DRIFT_ITEMS = 20
MAX_OUTLIERS = 10


def _to_epoch_ms(value: Any) -> int | None:
    """Convert a date, datetime, or ISO-8601 string into UTC epoch milliseconds."""
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return int(dt.astimezone(UTC).timestamp() * 1000)
    if isinstance(value, date):
        dt = datetime(value.year, value.month, value.day, tzinfo=UTC)
        return int(dt.timestamp() * 1000)
    if isinstance(value, str):
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
    return None


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


def _analyze_fields(rows: list[tuple[str, Skit]], total: int) -> list[dict[str, Any]]:
    if not rows:
        return []
    n_skits = len(rows)
    field_order: list[str] = []
    seen_keys: set[str] = set()
    for _, skit in rows:
        for key in skit.tokens:
            if key not in seen_keys:
                seen_keys.add(key)
                field_order.append(key)

    summaries: list[dict[str, Any]] = []
    for key in field_order:
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

        cardinality = len(values)
        non_null = [(val, obs) for val, (obs, _) in by_val.items() if val != "NULL"]
        null_obs = by_val.get("NULL", [0, 0])[0]
        null_pct = round(100.0 * null_obs / total, 4) if total else None

        numeric_pairs: list[tuple[int | float, int]] = []
        is_numeric = bool(non_null)
        for val, obs in non_null:
            parsed = as_number(val)
            if parsed is None:
                is_numeric = False
                break
            numeric_pairs.append((parsed, obs))

        weighted_mean: float | None = None
        weighted_median: float | None = None
        if is_numeric:
            nums = [n for n, _ in numeric_pairs]
            min_val: Any = min(nums)
            max_val: Any = max(nums)
            num_weight = sum(obs for _, obs in numeric_pairs)
            if num_weight > 0:
                weighted_mean = sum(n * obs for n, obs in numeric_pairs) / num_weight
                weighted_median = _weighted_median([(float(n), obs) for n, obs in numeric_pairs])
        elif non_null:
            non_null_strs = [val for val, _ in non_null]
            min_val = min(non_null_strs)
            max_val = max(non_null_strs)
        else:
            min_val = "NULL" if by_val else None
            max_val = "NULL" if by_val else None

        mode = None
        if values:
            top = values[0]
            mode = {"value": top["value"], "count": top["count"], "weight_pct": top["weight_pct"]}

        summaries.append(
            {
                "key": key,
                "cardinality": cardinality,
                "non_null_cardinality": len(non_null),
                "is_constant": cardinality <= 1,
                "is_high_cardinality": cardinality > 20 and (cardinality / n_skits) >= 0.5,
                "is_numeric": is_numeric,
                "null_observations": null_obs,
                "null_pct": null_pct,
                "min": min_val,
                "max": max_val,
                "mode": mode,
                "weighted_mean": weighted_mean,
                "weighted_median": weighted_median,
                "values": values,
            }
        )
    return summaries


def _is_avg_dict(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "avg" in value
        and "sum" in value
        and "count" in value
        and len(value) == 3
    )


def _is_multi_fn_dict(value: Any) -> bool:
    if not isinstance(value, dict) or not value or _is_avg_dict(value):
        return False
    known = {"SUM", "MIN", "MAX", "AVG", "COUNT", "FIRST", "LAST"}
    return all(k in known for k in value)


def _classify_scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "numeric"
    if isinstance(value, list):
        return "samples"
    if isinstance(value, str):
        return "text"
    return None


def _tokens_preview(tokens: dict[str, str], limit: int = 4) -> str:
    items = [f"{k}={v}" for k, v in tokens.items() if v not in ("NULL", "FALSE")]
    if not items:
        items = [f"{k}={v}" for k, v in list(tokens.items())[:limit]]
    return ", ".join(items[:limit])


def _analyze_aggregates(
    rows: list[tuple[str, Skit]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, list[int]]]]:
    """Return (aggregate_summaries, datetime_axes, per_skit_time_bounds)."""
    if not rows:
        return [], [], {}

    agg_order: list[str] = []
    seen: set[str] = set()
    for _, skit in rows:
        for key in skit.aggregates:
            if key not in seen:
                seen.add(key)
                agg_order.append(key)

    summaries: list[dict[str, Any]] = []
    time_axes: list[dict[str, Any]] = []
    skit_bounds: dict[str, dict[str, list[int]]] = {fid: {} for fid, _ in rows}

    for key in agg_order:
        functions: list[str] = []
        fn_seen: set[str] = set()
        kinds: set[str] = set()

        sum_total: float | int = 0
        has_sum = False
        count_total: int = 0
        has_count = False
        avg_sum_total = 0.0
        avg_count_total = 0
        has_avg = False

        min_candidates: list[Any] = []
        max_candidates: list[Any] = []
        skit_metric_values: list[tuple[str, int, float, dict[str, str]]] = []
        skit_time_pairs: list[tuple[str, int, int]] = []
        metric_name = "VALUE"

        for fid, skit in rows:
            raw = skit.aggregates.get(key)
            if raw is None:
                continue

            if _is_multi_fn_dict(raw):
                for fn_name in raw:
                    if fn_name not in fn_seen:
                        fn_seen.add(fn_name)
                        functions.append(fn_name)

                if (
                    "SUM" in raw
                    and isinstance(raw["SUM"], (int, float))
                    and not isinstance(raw["SUM"], bool)
                ):
                    sum_total += raw["SUM"]
                    has_sum = True
                    kinds.add("numeric")
                if (
                    "COUNT" in raw
                    and isinstance(raw["COUNT"], (int, float))
                    and not isinstance(raw["COUNT"], bool)
                ):
                    count_total += int(raw["COUNT"])
                    has_count = True
                    kinds.add("numeric")
                if "AVG" in raw and _is_avg_dict(raw["AVG"]):
                    has_avg = True
                    kinds.add("numeric")
                    c = raw["AVG"].get("count") or 0
                    s = raw["AVG"].get("sum") or 0
                    if isinstance(c, (int, float)) and c > 0 and isinstance(s, (int, float)):
                        avg_count_total += int(c)
                        avg_sum_total += float(s)

                mn = raw.get("MIN")
                mx = raw.get("MAX")
                for candidate, bucket in ((mn, min_candidates), (mx, max_candidates)):
                    k = _classify_scalar(candidate)
                    if k:
                        kinds.add(k)
                        bucket.append(candidate)

                # Primary per-skit numeric metric: prefer AVG.avg (never falling back to SUM=0
                # when AVG has no values), else SUM, else COUNT, else MAX.
                primary: float | None = None
                if "AVG" in raw and _is_avg_dict(raw["AVG"]):
                    metric_name = "AVG"
                    if raw["AVG"].get("avg") is not None:
                        primary = float(raw["AVG"]["avg"])
                elif (
                    "SUM" in raw
                    and isinstance(raw["SUM"], (int, float))
                    and not isinstance(raw["SUM"], bool)
                ):
                    primary = float(raw["SUM"])
                    metric_name = "SUM"
                elif (
                    "COUNT" in raw
                    and isinstance(raw["COUNT"], (int, float))
                    and not isinstance(raw["COUNT"], bool)
                ):
                    primary = float(raw["COUNT"])
                    metric_name = "COUNT"
                elif isinstance(mx, (int, float)) and not isinstance(mx, bool):
                    primary = float(mx)
                    metric_name = "MAX"
                if primary is not None:
                    skit_metric_values.append((fid, skit.meta["count"], primary, skit.tokens))

                # Datetime/date bounds for range slider
                if isinstance(mn, (date, datetime)) or isinstance(mx, (date, datetime)):
                    lo = _to_epoch_ms(mn if mn is not None else mx)
                    hi = _to_epoch_ms(mx if mx is not None else mn)
                    if lo is not None and hi is not None:
                        skit_time_pairs.append((fid, min(lo, hi), max(lo, hi)))

            elif _is_avg_dict(raw):
                if "AVG" not in fn_seen:
                    fn_seen.add("AVG")
                    functions.append("AVG")
                has_avg = True
                kinds.add("numeric")
                c = raw.get("count") or 0
                s = raw.get("sum") or 0
                if isinstance(c, (int, float)) and c > 0 and isinstance(s, (int, float)):
                    avg_count_total += int(c)
                    avg_sum_total += float(s)
                if raw.get("avg") is not None:
                    metric_name = "AVG"
                    skit_metric_values.append(
                        (fid, skit.meta["count"], float(raw["avg"]), skit.tokens)
                    )
            else:
                if "VALUE" not in fn_seen:
                    fn_seen.add("VALUE")
                    functions.append("VALUE")
                k = _classify_scalar(raw)
                if k:
                    kinds.add(k)
                if k == "numeric":
                    sum_total += raw
                    has_sum = True
                    min_candidates.append(raw)
                    max_candidates.append(raw)
                    metric_name = "VALUE"
                    skit_metric_values.append((fid, skit.meta["count"], float(raw), skit.tokens))
                elif k in ("datetime", "date"):
                    min_candidates.append(raw)
                    max_candidates.append(raw)
                    ms = _to_epoch_ms(raw)
                    if ms is not None:
                        skit_time_pairs.append((fid, ms, ms))
                elif k == "text":
                    min_candidates.append(raw)
                    max_candidates.append(raw)

        if not kinds:
            kind = "empty"
        elif "datetime" in kinds:
            kind = "datetime"
        elif "date" in kinds:
            kind = "date"
        elif "numeric" in kinds:
            kind = "numeric"
        elif "samples" in kinds:
            kind = "samples"
        else:
            kind = "text"

        global_min: Any = None
        global_max: Any = None
        if min_candidates:
            try:
                global_min = _json_safe(min(min_candidates))
            except TypeError:
                global_min = _json_safe(min(str(v) for v in min_candidates))
        if max_candidates:
            try:
                global_max = _json_safe(max(max_candidates))
            except TypeError:
                global_max = _json_safe(max(str(v) for v in max_candidates))

        weighted_mean = (
            (avg_sum_total / avg_count_total) if (has_avg and avg_count_total > 0) else None
        )

        nums_only = [val for _, _, val, _ in skit_metric_values]
        skit_stats = {
            "metric": metric_name,
            "active_skits": len(nums_only),
            "min": min(nums_only) if nums_only else None,
            "max": max(nums_only) if nums_only else None,
            "mean": (sum(nums_only) / len(nums_only)) if nums_only else None,
            "median": _median(nums_only),
        }

        outliers = [
            {
                "id": fid,
                "count": cnt,
                "value": val,
                "tokens_preview": _tokens_preview(toks),
            }
            for fid, cnt, val, toks in sorted(
                skit_metric_values, key=lambda item: (-item[2], -item[1], item[0])
            )[:MAX_OUTLIERS]
        ]

        summaries.append(
            {
                "key": key,
                "kind": kind,
                "functions": functions,
                "global_sum": sum_total if has_sum else (avg_sum_total if has_avg else None),
                "global_count": count_total
                if has_count
                else (avg_count_total if has_avg else None),
                "global_min": global_min,
                "global_max": global_max,
                "weighted_mean": weighted_mean,
                "skit_stats": skit_stats,
                "outliers": outliers,
            }
        )

        if kind in ("datetime", "date") and skit_time_pairs:
            axis_id = f"agg:{key}"
            min_ms = min(lo for _, lo, _ in skit_time_pairs)
            max_ms = max(hi for _, _, hi in skit_time_pairs)
            for fid, lo, hi in skit_time_pairs:
                skit_bounds[fid][axis_id] = [lo, hi]
            time_axes.append(
                {
                    "id": axis_id,
                    "kind": kind,
                    "label": key,
                    "min_ms": min_ms,
                    "max_ms": max_ms,
                    "min_iso": global_min,
                    "max_iso": global_max,
                }
            )

    return summaries, time_axes, skit_bounds


def _default_history_dir(sketch_path: Path | str) -> Path:
    return Path(os.path.splitext(str(sketch_path))[0] + ".history")


def _load_history(
    sketch_path: Path | str, history_dir: Path | str | None
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Load run files from explicit or auto-detected history directory.

    Returns (history_payload, run_info_by_id).
    """
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
                "skipped_lines": int(run_hdr.get("skipped_lines", 0))
                if isinstance(run_hdr.get("skipped_lines"), int)
                else 0,
                "skit_count": len(skits_map),
                "observed_events": total_events,
            }
            loaded.append((run_id, info, skits_map))
        except (OSError, SketchError, ValueError, TypeError) as exc:
            warnings.append(f"Skipped history file {entry.name}: {exc}")

    loaded.sort(key=lambda item: item[0])
    runs = [info for _, info, _ in loaded]
    run_map = {run_id: info for run_id, info, _ in loaded}

    drift: list[dict[str, Any]] = []
    for (_, prev_info, prev_skits), (_, curr_info, curr_skits) in zip(loaded, loaded[1:]):
        prev_total = prev_info["observed_events"]
        curr_total = curr_info["observed_events"]
        prev_ids = set(prev_skits)
        curr_ids = set(curr_skits)
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
                    "prev_weight_pct": round(100.0 * prev_skits[fid][0] / prev_total, 2)
                    if prev_total
                    else 0.0,
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

        drift.append(
            {
                "from_run": prev_info["id"],
                "to_run": curr_info["id"],
                "new_count": len(new_ids),
                "disappeared_count": len(gone_ids),
                "persisted_count": len(both_ids),
                "new_skits": new_list[:MAX_DRIFT_ITEMS],
                "disappeared_skits": gone_list[:MAX_DRIFT_ITEMS],
                "top_shifts": shifts[:MAX_DRIFT_ITEMS],
            }
        )

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
    ordered = sorted(run_ids)
    run_entries = []
    for idx, rid in enumerate(ordered):
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
    return {
        "id": "runs",
        "kind": "runs",
        "label": "First / Last Seen Run",
        "runs": run_entries,
    }


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
