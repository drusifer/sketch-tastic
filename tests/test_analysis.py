"""Unit tests for sketch analysis data engine and history drift loader (STORY-SKT-13, -14)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from sketchtastic.aggregators import Aggregate
from sketchtastic.analysis import analyze_sketch
from sketchtastic.profile import Field, Profile
from sketchtastic.sketch import Sketch, SketchError


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
    def test_empty_sketch_produces_zero_counts_and_na_ratios(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "empty.sketch.yaml"
            Sketch(profile_id="empty-profile").save(str(sketch_path))

            result = analyze_sketch(sketch_path)

            self.assertEqual(result["meta"]["total_observations"], 0)
            self.assertEqual(result["meta"]["total_skits"], 0)
            self.assertEqual(result["meta"]["singleton_skits"], 0)
            self.assertIsNone(result["meta"]["singleton_pct"])
            self.assertEqual(result["skits"], [])
            self.assertEqual(result["fields"], [])
            self.assertEqual(result["aggregates"], [])
            self.assertEqual(result["history"]["runs"], [])
            for item in result["meta"]["concentration"]:
                self.assertEqual(item["skits_needed"], 0)
                self.assertIsNone(item["achieved_pct"])

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


class AnalysisStatsAndDistributionsTests(unittest.TestCase):
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

    def test_weighted_enum_distributions_min_max_and_numeric_mean_median(self) -> None:
        events = [
            # 6 observations of status=200 (kind=a)
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
            # 3 observations of status=404 (kind=b)
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
            # 1 observation of status=500 (kind=c) — singleton
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

            # Overview & concentration
            self.assertEqual(data["meta"]["total_observations"], 10)
            self.assertEqual(data["meta"]["total_skits"], 3)
            self.assertEqual(data["meta"]["singleton_skits"], 1)
            self.assertAlmostEqual(data["meta"]["singleton_pct"], 10.0)

            thresholds = {c["target_pct"]: c["skits_needed"] for c in data["meta"]["concentration"]}
            self.assertEqual(thresholds[50], 1)  # 60% covered by top 1
            self.assertEqual(thresholds[80], 2)  # 90% covered by top 2
            self.assertEqual(thresholds[90], 2)
            self.assertEqual(thresholds[95], 3)  # 100% covered by top 3
            self.assertEqual(thresholds[99], 3)

            fields = {f["key"]: f for f in data["fields"]}

            # Categorical field: kind
            kind = fields["kind"]
            self.assertFalse(kind["is_numeric"])
            self.assertFalse(kind["is_constant"])
            self.assertEqual(kind["min"], "a")
            self.assertEqual(kind["max"], "c")
            self.assertEqual(kind["mode"]["value"], "a")
            self.assertEqual(kind["mode"]["count"], 6)
            self.assertAlmostEqual(kind["mode"]["weight_pct"], 60.0)
            self.assertIsNone(kind["weighted_mean"])
            self.assertIsNone(kind["weighted_median"])
            self.assertEqual([v["value"] for v in kind["values"]], ["a", "b", "c"])
            self.assertAlmostEqual(kind["values"][0]["weight_pct"], 60.0)
            self.assertAlmostEqual(kind["values"][0]["skit_pct"], 100 / 3, places=2)

            # Numeric token field: status (6x200, 3x404, 1x500) -> mean=291.2, median=200
            status = fields["status"]
            self.assertTrue(status["is_numeric"])
            self.assertEqual(status["min"], 200)
            self.assertEqual(status["max"], 500)
            self.assertAlmostEqual(status["weighted_mean"], (6 * 200 + 3 * 404 + 500) / 10)
            self.assertAlmostEqual(status["weighted_median"], 200.0)

            # Constant field: env
            self.assertTrue(fields["env"]["is_constant"])
            self.assertEqual(fields["env"]["cardinality"], 1)

            # Aggregates: latency
            aggs = {a["key"]: a for a in data["aggregates"]}
            lat = aggs["latency"]
            self.assertEqual(lat["kind"], "numeric")
            self.assertEqual(lat["global_sum"], 250)  # 6*10 + 3*30 + 100
            self.assertEqual(lat["global_count"], 10)
            self.assertEqual(lat["global_min"], 10)
            self.assertEqual(lat["global_max"], 100)
            self.assertAlmostEqual(lat["weighted_mean"], 25.0)
            # Across-skit stats of per-skit AVG [10, 30, 100] -> mean=46.666..., median=30.0
            self.assertEqual(lat["skit_stats"]["active_skits"], 3)
            self.assertAlmostEqual(lat["skit_stats"]["min"], 10.0)
            self.assertAlmostEqual(lat["skit_stats"]["max"], 100.0)
            self.assertAlmostEqual(lat["skit_stats"]["median"], 30.0)
            self.assertAlmostEqual(lat["skit_stats"]["mean"], 140 / 3, places=4)

            # Single-fn COUNT aggregate: items (6*2=12, 3*1=3, 1*0=0) -> global_sum=15
            items = aggs["items"]
            self.assertEqual(items["kind"], "numeric")
            self.assertEqual(items["global_sum"], 15)
            self.assertEqual(items["skit_stats"]["median"], 3.0)

            # Datetime aggregate & axis detection
            occ = aggs["occurred_at"]
            self.assertEqual(occ["kind"], "datetime")
            self.assertTrue(occ["global_min"].startswith("2026-11-20T10:00:00"))
            self.assertTrue(occ["global_max"].startswith("2026-11-20T12:00:00"))

            axis_ids = [axis["id"] for axis in data["time_axes"]]
            self.assertIn("agg:occurred_at", axis_ids)
            self.assertIn("runs", axis_ids)
            # Every skit has numeric time_bounds for agg:occurred_at
            for skit in data["skits"]:
                bounds = skit["time_bounds"]["agg:occurred_at"]
                self.assertEqual(len(bounds), 2)
                self.assertLessEqual(bounds[0], bounds[1])

    def test_even_weighted_median_averages_middle_two_observations(self) -> None:
        profile = Profile(fields=(Field("val", "$.v"),))
        events = [{"v": 10}, {"v": 10}, {"v": 30}, {"v": 30}]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "even.sketch.yaml"
            _write_sketch(sketch_path, profile, events)
            data = analyze_sketch(sketch_path)
            val = data["fields"][0]
            self.assertTrue(val["is_numeric"])
            self.assertAlmostEqual(val["weighted_median"], 20.0)
            self.assertAlmostEqual(val["weighted_mean"], 20.0)

    def test_null_only_field_date_aggregate_and_sample_aggregate(self) -> None:
        profile = Profile(
            fields=(Field("missing", "$.absent"),),
            aggregates=(
                Aggregate("day", "$.d", ["MIN", "MAX"], type="DATE"),
                Aggregate("msgs", "$.m", {"name": "LAST", "n": 2}),
            ),
        )
        events = [
            {"d": "2026-11-19", "m": "hello"},
            {"d": "2026-11-21", "m": "world"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "edge.sketch.yaml"
            _write_sketch(sketch_path, profile, events)
            data = analyze_sketch(sketch_path)
            fld = data["fields"][0]
            self.assertFalse(fld["is_numeric"])
            self.assertEqual(fld["min"], "NULL")
            self.assertEqual(fld["max"], "NULL")
            self.assertEqual(fld["null_observations"], 2)
            aggs = {a["key"]: a for a in data["aggregates"]}
            self.assertEqual(aggs["day"]["kind"], "date")
            self.assertEqual(aggs["day"]["global_min"], "2026-11-19")
            self.assertEqual(aggs["day"]["global_max"], "2026-11-21")
            self.assertEqual(aggs["msgs"]["kind"], "samples")
            self.assertIn("agg:day", [ax["id"] for ax in data["time_axes"]])

    def test_sum_and_count_stay_separate_and_empty_avg_excluded_from_skit_stats(self) -> None:
        profile = Profile(
            fields=(Field("kind", "$.kind"),),
            aggregates=(Aggregate("bytes", "$.size", ["SUM", "COUNT", "AVG"]),),
        )
        events = [
            {"kind": "with_size", "size": 100},
            {"kind": "with_size", "size": 300},
            {"kind": "no_size"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "split.sketch.yaml"
            _write_sketch(sketch_path, profile, events)
            data = analyze_sketch(sketch_path)
            b = data["aggregates"][0]
            self.assertEqual(b["global_sum"], 400)
            self.assertEqual(b["global_count"], 2)
            self.assertAlmostEqual(b["weighted_mean"], 200.0)
            # Only the 1 skit with actual AVG values should be in active_skits (not no_size)
            self.assertEqual(b["skit_stats"]["active_skits"], 1)
            self.assertAlmostEqual(b["skit_stats"]["min"], 200.0)
            self.assertAlmostEqual(b["skit_stats"]["median"], 200.0)

    def test_boolean_fields_classified_distinct_from_enum_and_numeric(self) -> None:
        profile = Profile(
            fields=(
                Field("present", "$.err", modifier="IS_PRESENT"),
                Field("flag", "$.flag"),
                Field("const_false", "$.never", modifier="IS_PRESENT"),
                Field("mixed", "$.mixed"),
            ),
        )
        events = [
            {"err": "boom", "flag": True, "mixed": "TRUE"},
            {"flag": False, "mixed": "TRUE"},
            {"flag": False, "mixed": "maybe"},
            {"mixed": "maybe"},  # flag absent -> NULL
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "bools.sketch.yaml"
            _write_sketch(sketch_path, profile, events)
            data = analyze_sketch(sketch_path)
            fields = {f["key"]: f for f in data["fields"]}

            # IS_PRESENT -> TRUE/FALSE Boolean (1 TRUE, 3 FALSE -> 25% true)
            present = fields["present"]
            self.assertEqual(present["field_type"], "boolean")
            self.assertTrue(present["is_boolean"])
            self.assertFalse(present["is_numeric"])
            self.assertEqual(present["min"], "FALSE")
            self.assertEqual(present["max"], "TRUE")
            self.assertAlmostEqual(present["true_pct"], 25.0)
            self.assertIsNone(present["weighted_mean"])

            # DEFAULT JSON bool + NULL -> True/False Boolean (1 True, 2 False -> 33.3333% of non-NULL)
            flag = fields["flag"]
            self.assertEqual(flag["field_type"], "boolean")
            self.assertTrue(flag["is_boolean"])
            self.assertEqual(flag["min"], "False")
            self.assertEqual(flag["max"], "True")
            self.assertAlmostEqual(flag["true_pct"], 100.0 / 3, places=3)
            self.assertAlmostEqual(flag["null_pct"], 25.0)

            # Constant FALSE -> still Boolean
            cf = fields["const_false"]
            self.assertEqual(cf["field_type"], "boolean")
            self.assertTrue(cf["is_boolean"])
            self.assertTrue(cf["is_constant"])
            self.assertAlmostEqual(cf["true_pct"], 0.0)
            self.assertEqual(cf["min"], "FALSE")
            self.assertEqual(cf["max"], "FALSE")

            # Mixed TRUE + "maybe" -> Enum, not Boolean
            mixed = fields["mixed"]
            self.assertEqual(mixed["field_type"], "enum")
            self.assertFalse(mixed["is_boolean"])
            self.assertIsNone(mixed["true_pct"])

    def test_drop_one_ablation_identifies_singleton_and_cardinality_drivers(self) -> None:
        profile = Profile(
            fields=(
                Field("env", "$.env"),
                Field("kind", "$.kind"),
                Field("lang", "$.lang"),
            ),
        )
        # 4 skits total, 3 singletons driven entirely by `lang` on kind=post
        events = [
            {"env": "prod", "kind": "post", "lang": "en"},
            {"env": "prod", "kind": "post", "lang": "en"},
            {"env": "prod", "kind": "post", "lang": "fr"},
            {"env": "prod", "kind": "post", "lang": "de"},
            {"env": "prod", "kind": "post", "lang": "ja"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "ablate.sketch.yaml"
            _write_sketch(sketch_path, profile, events)
            data = analyze_sketch(sketch_path)

            self.assertIn("ablation", data)
            ablation = data["ablation"]
            # Ranked highest impact first: `lang` collapses 4 -> 1 skit and 3 -> 0 singletons
            self.assertEqual(ablation[0]["key"], "lang")
            self.assertEqual(ablation[0]["cardinality"], 4)
            self.assertEqual(ablation[0]["singleton_only_values"], 3)
            self.assertEqual(ablation[0]["skits_collapsed"], 3)
            self.assertAlmostEqual(ablation[0]["skits_collapsed_pct"], 75.0)
            self.assertEqual(ablation[0]["singletons_removed"], 3)
            self.assertAlmostEqual(ablation[0]["singletons_removed_pct"], 100.0)
            self.assertEqual(ablation[0]["remaining_skits"], 1)
            self.assertEqual(ablation[0]["remaining_singletons"], 0)

            by_key = {row["key"]: row for row in ablation}
            # Constant fields collapse 0 skits and 0 singletons
            self.assertEqual(by_key["env"]["skits_collapsed"], 0)
            self.assertEqual(by_key["env"]["singletons_removed"], 0)
            self.assertEqual(by_key["kind"]["skits_collapsed"], 0)

    def test_empty_sketch_has_empty_ablation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "empty.sketch.yaml"
            Sketch(profile_id="empty").save(str(sketch_path))
            data = analyze_sketch(sketch_path)
            self.assertEqual(data["ablation"], [])
            self.assertEqual(data["correlations"]["fields"], [])
            self.assertEqual(data["correlations"]["edges"], [])

    def test_correlations_cramers_v_asymmetric_theils_u_redundancy_and_phi_lift(self) -> None:
        profile = Profile(
            fields=(
                Field("embed", "$.embed"),
                Field("has_img", "$.img", modifier="IS_PRESENT"),
                Field("img_mirror", "$.img", modifier="IS_PRESENT"),
                Field("reply", "$.reply", modifier="IS_PRESENT"),
            ),
        )
        # embed determines has_img 100% (images -> TRUE, else FALSE), but not vice versa
        # has_img and img_mirror are 1:1 mutually locked (V=1, U=1 both ways)
        # reply strongly anti-correlates with images (negative phi)
        events = [
            *[{"embed": "images", "img": 1} for _ in range(10)],
            *[{"embed": "video"} for _ in range(10)],
            *[{"embed": "none", "reply": 1} for _ in range(10)],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "corr.sketch.yaml"
            _write_sketch(sketch_path, profile, events)
            data = analyze_sketch(sketch_path)

            corr = data["correlations"]
            # Mutual 1:1 lock between has_img and img_mirror
            self.assertAlmostEqual(corr["cramers"]["has_img"]["img_mirror"], 1.0, places=3)
            self.assertAlmostEqual(corr["theils"]["has_img"]["img_mirror"], 1.0, places=3)
            self.assertAlmostEqual(corr["theils"]["img_mirror"]["has_img"], 1.0, places=3)

            # One-way lock: embed completely determines has_img, not vice versa
            self.assertAlmostEqual(corr["theils"]["embed"]["has_img"], 1.0, places=3)
            self.assertLess(corr["theils"]["has_img"]["embed"], 0.7)

            # Redundancy diagnostics reported on fields
            fields = {f["key"]: f for f in data["fields"]}
            self.assertIn("img_mirror", fields["has_img"]["redundant_with"])
            self.assertIn("embed", fields["has_img"]["determined_by"])

            # Value-level edges capture positive lock and negative anti-correlation
            edge_map = {(e["a"], e["b"]): e for e in corr["edges"]}
            edge_map.update({(e["b"], e["a"]): e for e in corr["edges"]})
            pos_edge = edge_map[("embed=images", "has_img=TRUE")]
            self.assertAlmostEqual(pos_edge["phi"], 1.0, places=3)
            self.assertAlmostEqual(pos_edge["lift"], 3.0, places=2)
            self.assertEqual(pos_edge["n11"], 10)

            # reply=TRUE and embed=none co-occur 100% (phi=+1.0)
            rep_none = edge_map[("embed=none", "reply=TRUE")]
            self.assertAlmostEqual(rep_none["phi"], 1.0, places=3)

            # Zero co-occurrence anti-correlation: reply=TRUE and has_img=TRUE (phi=-0.5)
            neg_edge = edge_map[("has_img=TRUE", "reply=TRUE")]
            self.assertAlmostEqual(neg_edge["phi"], -0.5, places=3)
            self.assertEqual(neg_edge["n11"], 0)
            self.assertAlmostEqual(neg_edge["lift"], 0.0, places=3)


class AnalysisHistoryDriftTests(unittest.TestCase):
    def test_auto_detected_history_computes_runs_and_drift(self) -> None:
        profile = Profile(fields=(Field("kind", "$.kind"),))
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "stream.sketch.yaml"
            hist_dir = Path(tmp) / "stream.sketch.history"
            hist_dir.mkdir()

            # Run 1: 4x a, 1x b
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

            # Run 2: 1x a (drops), 4x c (new); b disappears
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

            # Corrupt extra file should warn without aborting auto-detected history
            (hist_dir / "corrupt.yaml").write_text(":::bad:::\n", encoding="utf-8")

            # Merged sketch
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
            self.assertEqual(len(data["history"]["warnings"]), 1)
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

            # Runs axis carries history timestamps
            runs_axis = next(ax for ax in data["time_axes"] if ax["id"] == "runs")
            self.assertEqual(len(runs_axis["runs"]), 2)
            self.assertIsNotNone(runs_axis["runs"][0]["started_ms"])
            self.assertLess(runs_axis["runs"][0]["started_ms"], runs_axis["runs"][1]["started_ms"])


if __name__ == "__main__":
    unittest.main()
