"""Unit tests for the lean dashboard payload builder and history drift loader (STORY-SKT-16)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from sketchtastic.aggregators import Aggregate
from sketchtastic.analysis import analyze_sketch
from sketchtastic.profile import Field, Profile
from sketchtastic.sketch import Sketch, SketchError, read_sketch_file


def _write_sketch(
    path: Path, profile: Profile, events: list[dict], run_id: str = "261120-0001"
) -> Sketch:
    sketch = Sketch(profile.aggregates, profile.profile_id)
    sketch.last_run = run_id
    for event in events:
        sketch.upsert(profile.tokens(event), event, run=run_id)
    sketch.save(str(path))
    return sketch


class AnalysisEmptyAndValidationTests(unittest.TestCase):
    def test_empty_sketch_produces_lean_empty_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "empty.sketch.yaml"
            Sketch(profile_id="empty-profile").save(str(sketch_path))

            result = analyze_sketch(sketch_path)

            self.assertEqual(result["meta"]["total_observations"], 0)
            self.assertEqual(result["meta"]["total_skits"], 0)
            self.assertEqual(result["meta"]["singleton_skits"], 0)
            self.assertIsNone(result["meta"]["singleton_pct"])
            self.assertEqual(result["meta"]["default_weighting"], "count")
            self.assertEqual(result["skits"], [])
            self.assertEqual(result["fields"], [])
            self.assertEqual(result["aggregates"], [])
            self.assertEqual(result["weightings"], [])
            self.assertEqual(result["time_axes"], [])
            self.assertEqual(result["history"]["runs"], [])
            # Lean payload omits client-recomputed blobs
            self.assertNotIn("ablation", result)
            self.assertNotIn("correlations", result)
            self.assertNotIn("concentration", result["meta"])

    def test_missing_and_malformed_sketch_raise_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                analyze_sketch(Path(tmp) / "missing.sketch.yaml")

            bad = Path(tmp) / "bad.sketch.yaml"
            bad.write_text("not: a sketch\n", encoding="utf-8")
            with self.assertRaises(SketchError):
                analyze_sketch(bad)

    def test_explicit_missing_history_dir_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "s.sketch.yaml"
            Sketch(profile_id="p").save(str(sketch_path))
            with self.assertRaises(ValueError):
                analyze_sketch(sketch_path, history_dir=Path(tmp) / "no-such-dir")

    def test_single_pass_yaml_read_for_sketch_and_history_files(self) -> None:
        profile = Profile(fields=(Field("kind", "$.kind"),))
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "single.sketch.yaml"
            hist_dir = Path(tmp) / "single.sketch.history"
            hist_dir.mkdir()
            _write_sketch(sketch_path, profile, [{"kind": "a"}], run_id="261123-0001")
            _write_sketch(
                hist_dir / "261123-0001.yaml", profile, [{"kind": "a"}], run_id="261123-0001"
            )

            with patch("sketchtastic.sketch.read_sketch_file", wraps=read_sketch_file) as spy:
                analyze_sketch(sketch_path)
            # Exactly 2 YAML reads: 1 for sketch + 1 for history run file (never double-parsed)
            self.assertEqual(spy.call_count, 2)


class AnalysisPayloadProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = Profile(
            fields=(
                Field("kind", "$.kind"),
                Field("status", "$.status"),
                Field("env", "$.env"),
            ),
            aggregates=(
                Aggregate("latency", "$.ms", ["SUM", "MIN", "MAX", "AVG"]),
                Aggregate("items", "$.items[*]", "COUNT"),
                Aggregate("occurred_at", "$.ts", ["MIN", "MAX"], type="DATETIME"),
            ),
        )

    def test_projects_ranked_skits_field_order_agg_descriptors_and_time_axes(self) -> None:
        events = [
            *[
                {
                    "kind": "a",
                    "status": 200,
                    "env": "prod",
                    "ms": 10,
                    "items": [1, 2],
                    "ts": "2026-11-20T10:00:00Z",
                }
                for _ in range(6)
            ],
            *[
                {
                    "kind": "b",
                    "status": 404,
                    "env": "prod",
                    "ms": 30,
                    "items": [1],
                    "ts": "2026-11-20T11:00:00Z",
                }
                for _ in range(3)
            ],
            {
                "kind": "c",
                "status": 500,
                "env": "prod",
                "ms": 100,
                "items": [],
                "ts": "2026-11-20T12:00:00Z",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "app.sketch.yaml"
            _write_sketch(sketch_path, self.profile, events)

            data = analyze_sketch(sketch_path)

            self.assertEqual(data["meta"]["total_observations"], 10)
            self.assertEqual(data["meta"]["total_skits"], 3)
            self.assertEqual(data["meta"]["singleton_skits"], 1)
            self.assertAlmostEqual(data["meta"]["singleton_pct"], 10.0)

            self.assertEqual([f["key"] for f in data["fields"]], ["kind", "status", "env"])
            self.assertEqual([s["tokens"]["kind"] for s in data["skits"]], ["a", "b", "c"])
            self.assertEqual([s["count"] for s in data["skits"]], [6, 3, 1])
            self.assertAlmostEqual(data["skits"][0]["weight_pct"], 60.0)
            self.assertAlmostEqual(data["skits"][1]["cum_pct"], 90.0)

            aggs = {a["key"]: a for a in data["aggregates"]}
            self.assertEqual(aggs["latency"]["kind"], "numeric")
            self.assertEqual(aggs["latency"]["metric"], "AVG")
            self.assertEqual(aggs["items"]["kind"], "numeric")
            self.assertEqual(aggs["items"]["metric"], "VALUE")
            self.assertEqual(aggs["occurred_at"]["kind"], "datetime")

            axis_ids = [axis["id"] for axis in data["time_axes"]]
            self.assertIn("agg:occurred_at", axis_ids)
            self.assertIn("runs", axis_ids)
            occ_axis = next(ax for ax in data["time_axes"] if ax["id"] == "agg:occurred_at")
            self.assertTrue(occ_axis["min_iso"].startswith("2026-11-20T10:00:00"))
            self.assertTrue(occ_axis["max_iso"].startswith("2026-11-20T12:00:00"))
            for skit in data["skits"]:
                bounds = skit["time_bounds"]["agg:occurred_at"]
                self.assertEqual(len(bounds), 2)
                self.assertLessEqual(bounds[0], bounds[1])

    def test_date_aggregate_and_sample_aggregate_metadata(self) -> None:
        profile = Profile(
            fields=(Field("missing", "$.absent"),),
            aggregates=(
                Aggregate("day", "$.d", ["MIN", "MAX"], type="DATE"),
                Aggregate("msgs", "$.m", {"name": "LAST", "n": 2}),
            ),
        )
        events = [{"d": "2026-11-19", "m": "hello"}, {"d": "2026-11-21", "m": "world"}]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "edge.sketch.yaml"
            _write_sketch(sketch_path, profile, events)
            data = analyze_sketch(sketch_path)

            aggs = {a["key"]: a for a in data["aggregates"]}
            self.assertEqual(aggs["day"]["kind"], "date")
            self.assertEqual(aggs["msgs"]["kind"], "samples")
            day_axis = next(ax for ax in data["time_axes"] if ax["id"] == "agg:day")
            self.assertEqual(day_axis["min_iso"], "2026-11-19")
            self.assertEqual(day_axis["max_iso"], "2026-11-21")

    def test_histogram_aggregates_preserved_on_skits_and_typed_numeric(self) -> None:
        profile = Profile(
            fields=(Field("kind", "$.kind"),),
            aggregates=(
                Aggregate("bytes", "$.bytes", ["SUM", "MIN", "MAX", "AVG", "HISTOGRAM"]),
                Aggregate("lat", "$.ms", {"name": "HISTOGRAM", "buckets": [10, 50, 100]}),
            ),
        )
        events = [
            *[{"kind": "a", "bytes": v, "ms": v} for v in (5, 8, 12, 20, 40)],
            *[{"kind": "b", "bytes": v, "ms": v} for v in (60, 80, 95, 150, 300)],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "hist.sketch.yaml"
            _write_sketch(sketch_path, profile, events)

            data = analyze_sketch(sketch_path)
            aggs = {a["key"]: a for a in data["aggregates"]}
            self.assertEqual(aggs["bytes"]["kind"], "numeric")
            self.assertIn("HISTOGRAM", aggs["bytes"]["functions"])
            self.assertEqual([w["key"] for w in data["weightings"]], ["bytes"])

            self.assertEqual(aggs["lat"]["kind"], "numeric")
            self.assertEqual(aggs["lat"]["functions"], ["HISTOGRAM"])
            # Per-skit serialized histogram states are passed through for live client merging
            for skit in data["skits"]:
                self.assertEqual(skit["aggregates"]["bytes"]["HISTOGRAM"]["mode"], "log")
                self.assertEqual(skit["aggregates"]["lat"]["mode"], "fixed")


class AnalysisHistoryAndWeightingTests(unittest.TestCase):
    def test_auto_detected_history_computes_runs_and_drift(self) -> None:
        profile = Profile(fields=(Field("kind", "$.kind"),))
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "stream.sketch.yaml"
            hist_dir = Path(tmp) / "stream.sketch.history"
            hist_dir.mkdir()

            run1 = Sketch(profile.aggregates, profile.profile_id)
            run1.last_run = "261120-0001"
            run1.run = {
                "id": "261120-0001",
                "started": datetime(2026, 11, 20, 10, 0, tzinfo=UTC).isoformat(),
                "finished": datetime(2026, 11, 20, 10, 5, tzinfo=UTC).isoformat(),
                "source": "r1.jsonl",
                "events": 5,
                "skipped_lines": 0,
                "sketch": str(sketch_path),
            }
            for e in [{"kind": "a"}] * 4 + [{"kind": "b"}]:
                run1.upsert(profile.tokens(e), e, run="261120-0001")
            run1.save(str(hist_dir / "261120-0001.yaml"))

            run2 = Sketch(profile.aggregates, profile.profile_id)
            run2.last_run = "261120-0002"
            run2.run = {
                "id": "261120-0002",
                "started": datetime(2026, 11, 20, 11, 0, tzinfo=UTC).isoformat(),
                "finished": datetime(2026, 11, 20, 11, 5, tzinfo=UTC).isoformat(),
                "source": "r2.jsonl",
                "events": 5,
                "skipped_lines": 0,
                "sketch": str(sketch_path),
            }
            for e in [{"kind": "a"}] + [{"kind": "c"}] * 4:
                run2.upsert(profile.tokens(e), e, run="261120-0002")
            run2.save(str(hist_dir / "261120-0002.yaml"))

            (hist_dir / "corrupt.yaml").write_text(":::bad:::\n", encoding="utf-8")
            (hist_dir / "non_dict_skits.yaml").write_text(
                "version: 0\nskits: [1, 2]\n", encoding="utf-8"
            )
            secret = Path(tmp) / "secret.txt"
            secret.write_text("TOP_SECRET_LINE\n", encoding="utf-8")
            (hist_dir / "link.yaml").symlink_to(secret)

            merged = Sketch(profile.aggregates, profile.profile_id)
            merged.last_run = "261120-0002"
            merged.merge(run1)
            merged.merge(run2)
            merged.save(str(sketch_path))

            data = analyze_sketch(sketch_path)

            self.assertEqual(len(data["history"]["runs"]), 2)
            self.assertEqual(
                [r["id"] for r in data["history"]["runs"]], ["261120-0001", "261120-0002"]
            )
            self.assertEqual(len(data["history"]["warnings"]), 2)
            self.assertFalse(any("TOP_SECRET_LINE" in w for w in data["history"]["warnings"]))
            self.assertEqual(len(data["history"]["drift"]), 1)

            drift = data["history"]["drift"][0]
            self.assertEqual(drift["from_run"], "261120-0001")
            self.assertEqual(drift["to_run"], "261120-0002")
            self.assertEqual(drift["new_count"], 1)
            self.assertEqual(drift["new_skits"][0]["tokens"]["kind"], "c")
            self.assertEqual(drift["disappeared_count"], 1)
            self.assertEqual(drift["disappeared_skits"][0]["tokens"]["kind"], "b")
            self.assertEqual(drift["persisted_count"], 1)
            self.assertEqual(drift["top_shifts"][0]["tokens"]["kind"], "a")
            self.assertAlmostEqual(drift["top_shifts"][0]["delta_pct"], -60.0)

            runs_axis = next(ax for ax in data["time_axes"] if ax["id"] == "runs")
            self.assertEqual(len(runs_axis["runs"]), 2)
            self.assertIsNotNone(runs_axis["runs"][0]["started_ms"])
            self.assertLess(runs_axis["runs"][0]["started_ms"], runs_axis["runs"][1]["started_ms"])

    def test_auto_discovers_non_negative_additive_weightings_and_filters_ineligible(self) -> None:
        profile = Profile(
            fields=(Field("kind", "$.kind"),),
            aggregates=(
                Aggregate("bytes", "$.bytes", ["SUM", "AVG", "MIN", "MAX"]),
                Aggregate("avg_only", "$.score", "AVG"),
                Aggregate("items", "$.items[*]", "COUNT"),
                Aggregate("bounds_only", "$.bytes", ["MIN", "MAX"]),
                Aggregate("profit", "$.profit", ["SUM", "MIN", "MAX"]),
                Aggregate("zeros", "$.zero", "SUM"),
                Aggregate("occurred_at", "$.ts", ["MIN", "MAX"], type="DATETIME"),
                Aggregate("samples", "$.note", {"name": "LAST", "n": 2}),
            ),
        )
        events = [
            {
                "kind": "heavy",
                "bytes": 500,
                "score": 10.5,
                "items": [1, 2, 3],
                "profit": -20,
                "zero": 0,
                "ts": "2026-11-21T10:00:00Z",
                "note": "a",
            },
            {
                "kind": "light",
                "bytes": 100,
                "score": 4.5,
                "items": [],
                "profit": 50,
                "zero": 0,
                "ts": "2026-11-21T11:00:00Z",
                "note": "b",
            },
            {
                "kind": "light",
                "score": 5.0,
                "items": [1],
                "profit": 10,
                "zero": 0,
                "ts": "2026-11-21T11:05:00Z",
                "note": "c",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "weights.sketch.yaml"
            _write_sketch(sketch_path, profile, events)

            data = analyze_sketch(sketch_path, default_weight="bytes")
            self.assertEqual(data["meta"]["default_weighting"], "agg:bytes")

            weightings = {w["key"]: w for w in data["weightings"]}
            self.assertEqual(set(weightings), {"bytes", "avg_only", "items"})
            self.assertEqual(weightings["bytes"]["source"], "SUM")
            self.assertEqual(weightings["bytes"]["total"], 600)
            self.assertEqual(weightings["bytes"]["active_skits"], 2)
            self.assertEqual(weightings["avg_only"]["source"], "AVG.sum")
            self.assertAlmostEqual(weightings["avg_only"]["total"], 20.0)
            self.assertEqual(weightings["items"]["total"], 4)

            by_kind = {s["tokens"]["kind"]: s for s in data["skits"]}
            self.assertEqual(by_kind["heavy"]["weights"]["bytes"], 500)
            self.assertEqual(by_kind["light"]["weights"]["bytes"], 100)
            self.assertAlmostEqual(by_kind["heavy"]["weights"]["avg_only"], 10.5)
            self.assertAlmostEqual(by_kind["light"]["weights"]["avg_only"], 9.5)
            self.assertEqual(by_kind["heavy"]["weights"]["items"], 3)
            self.assertEqual(by_kind["light"]["weights"]["items"], 1)

            for bad in ("bounds_only", "profit", "zeros", "occurred_at", "samples", "missing"):
                with self.assertRaises(ValueError):
                    analyze_sketch(sketch_path, default_weight=bad)


if __name__ == "__main__":
    unittest.main()
