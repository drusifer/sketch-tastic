"""Regression coverage of a baseline sketch and of each run in its history.

A regression corpus (JSONL of original records) is tokenized with the baseline's profile; a
baseline kind is *covered* when at least one regression record has the same skit ID. Coverage
is reported two ways: distinct kinds, and baseline observations in covered kinds. Both measure
sample representation only, never test execution, branch coverage or population completeness.

History awareness: every run file is a sketch of that run's events, so the same intersection
gives per-run coverage, cumulative coverage up to each run, and the kinds each run introduced
that the corpus does not cover yet. The result is part of the `analyze` dashboard payload.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sketchtastic.profile import Profile
from sketchtastic.sketch import Skit, skit_id

MAX_LINE_BYTES = 4 * 1024 * 1024
MAX_LISTED = 200
"""At most this many unknown regression kinds or new uncovered kinds per run are listed."""

RunSkits = dict[str, tuple[int, dict[str, Any]]]


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant {value}")


def read_objects(path: Path | str) -> Iterator[dict[str, Any]]:
    """Stream bounded, strict UTF-8 JSON object lines; a bad line aborts the comparison."""
    with open(path, "rb") as stream:
        line_number = 0
        while raw := stream.readline(MAX_LINE_BYTES + 1):
            line_number += 1
            try:
                if len(raw) > MAX_LINE_BYTES:
                    raise ValueError("exceeds 4 MiB line limit")
                if not raw.strip():
                    continue
                record = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
                if not isinstance(record, dict):
                    raise ValueError("expected a JSON object")
            except (ValueError, RecursionError) as exc:
                raise ValueError(f"{path}: line {line_number}: {exc}") from exc
            yield record


def regression_kinds(profile: Profile, path: Path | str) -> tuple[dict[str, dict[str, Any]], int]:
    """Kinds in the corpus: skit ID -> tokens and record count; plus the total record count."""
    kinds: dict[str, dict[str, Any]] = {}
    records = 0
    for record in read_objects(path):
        records += 1
        tokens = profile.tokens(record)
        entry = kinds.setdefault(skit_id(tokens), {"tokens": tokens, "records": 0})
        entry["records"] += 1
    return kinds, records


def _ratio(part: int, whole: int) -> float | None:
    return round(100.0 * part / whole, 2) if whole else None


def _tally(counts: dict[str, int], covered: set[str]) -> tuple[int, int, int, int]:
    """(kinds, covered kinds, events, covered events) for skit ID -> event count."""
    hits = [count for sid, count in counts.items() if sid in covered]
    return len(counts), len(hits), sum(counts.values()), sum(hits)


def _run_coverage(
    info: dict[str, Any],
    skits: RunSkits,
    covered: set[str],
    cumulative: dict[str, int],
) -> dict[str, Any]:
    """One run's own coverage, then fold it into `cumulative` (kind -> events so far)."""
    counts = {sid: count for sid, (count, _) in skits.items()}
    new = [sid for sid in counts if sid not in cumulative]
    new_uncovered = sorted(
        (sid for sid in new if sid not in covered), key=lambda sid: (-counts[sid], sid)
    )
    for sid, count in counts.items():
        cumulative[sid] = cumulative.get(sid, 0) + count
    kinds, covered_kinds, events, covered_events = _tally(counts, covered)
    cum_kinds, cum_covered_kinds, cum_events, cum_covered_events = _tally(cumulative, covered)
    return {
        "id": info["id"],
        "comparable": True,
        "kinds": kinds,
        "covered_kinds": covered_kinds,
        "kind_pct": _ratio(covered_kinds, kinds),
        "events": events,
        "covered_events": covered_events,
        "event_pct": _ratio(covered_events, events),
        "cum_kinds": cum_kinds,
        "cum_covered_kinds": cum_covered_kinds,
        "cum_kind_pct": _ratio(cum_covered_kinds, cum_kinds),
        "cum_event_pct": _ratio(cum_covered_events, cum_events),
        "new_kinds": len(new),
        "new_uncovered_count": len(new_uncovered),
        "new_uncovered": [
            {"id": sid, "count": counts[sid], "tokens": skits[sid][1]}
            for sid in new_uncovered[:MAX_LISTED]
        ],
    }


def coverage_payload(
    profile: Profile,
    regression_path: Path | str,
    rows: list[tuple[str, Skit]],
    runs: list[tuple[dict[str, Any], RunSkits]],
) -> dict[str, Any]:
    """Coverage of the baseline `rows` and of each history run, in run order."""
    kinds, records = regression_kinds(profile, regression_path)
    baseline = {sid for sid, _ in rows}
    covered = baseline.intersection(kinds)
    unknown = sorted(set(kinds) - baseline, key=lambda sid: (-kinds[sid]["records"], sid))
    cumulative: dict[str, int] = {}
    per_run = []
    for info, skits in runs:
        if info.get("profile_id") != profile.profile_id:
            per_run.append({"id": info["id"], "comparable": False})
            continue
        per_run.append(_run_coverage(info, skits, covered, cumulative))
    return {
        "regression": str(regression_path),
        "profile_id": profile.profile_id,
        "regression_records": records,
        "regression_kinds": len(kinds),
        "covered_ids": sorted(covered),
        "unknown_count": len(unknown),
        "unknown": [
            {"id": sid, "records": kinds[sid]["records"], "tokens": kinds[sid]["tokens"]}
            for sid in unknown[:MAX_LISTED]
        ],
        "runs": per_run,
    }
