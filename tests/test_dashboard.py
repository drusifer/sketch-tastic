"""Unit tests for the offline Chart.js HTML dashboard renderer and JS stats engine (STORY-SKT-17)."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path

from sketchtastic.aggregators import Aggregate
from sketchtastic.analysis import analyze_sketch
from sketchtastic.dashboard import _JS_MODULES, render_dashboard
from sketchtastic.profile import Field, Profile
from sketchtastic.sketch import Sketch


def _extract_app_script(html_text: str) -> str:
    match = re.search(r'<script id="skt-app-script">(.*?)</script>', html_text, flags=re.DOTALL)
    assert match is not None, "Missing skt-app-script block"
    return match.group(1)


def _run_stats_js(
    expression: str, payload: dict | None = None, extra_modules: tuple[str, ...] = ()
) -> dict:
    """Execute a JS snippet against `assets/dashboard/stats.js` via Node and return parsed JSON."""
    stats_src = files("sketchtastic").joinpath("assets/dashboard/stats.js").read_text("utf-8")
    for module in extra_modules:
        stats_src += "\n" + files("sketchtastic").joinpath("assets/dashboard", module).read_text(
            "utf-8"
        )
    input_json = json.dumps(payload or {})
    runner = (
        f"const INPUT = {input_json};\n"
        f"{stats_src}\n"
        f"const RESULT = (() => {{ {expression} }})();\n"
        "process.stdout.write(JSON.stringify(RESULT));\n"
    )
    proc = subprocess.run(
        ["node", "-e", runner],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    return json.loads(proc.stdout)


class DashboardAssetsTests(unittest.TestCase):
    def test_chartjs_bundle_matches_pinned_sha256_and_mit_license(self) -> None:
        assets = files("sketchtastic").joinpath("assets")
        bundle_bytes = assets.joinpath("chart.umd.min.js").read_bytes()
        expected_sha = assets.joinpath("CHARTJS_SHA256.txt").read_text("utf-8").strip()
        license_text = assets.joinpath("CHARTJS_LICENSE.txt").read_text("utf-8")

        self.assertEqual(hashlib.sha256(bundle_bytes).hexdigest(), expected_sha)
        self.assertIn("The MIT License", license_text)
        self.assertNotIn(b"</script", bundle_bytes.lower())

    def test_modular_dashboard_assets_exist_and_contain_no_script_breakout(self) -> None:
        dash_dir = files("sketchtastic").joinpath("assets/dashboard")
        css_src = dash_dir.joinpath("styles.css").read_text("utf-8")
        self.assertTrue(css_src.strip())
        self.assertNotIn("</style", css_src.lower())
        self.assertIn("__APP_JS__", dash_dir.joinpath("template.html").read_text("utf-8"))
        seen_funcs: dict[str, str] = {}
        for module in _JS_MODULES:
            source = dash_dir.joinpath(module).read_text("utf-8")
            self.assertTrue(source.strip(), f"Empty JS module: {module}")
            self.assertNotIn("</script", source.lower(), f"Script breakout in {module}")
            for fn_name in re.findall(r"^function\s+(\w+)\s*\(", source, flags=re.MULTILINE):
                self.assertNotIn(
                    fn_name,
                    seen_funcs,
                    f"Duplicate top-level JS function {fn_name} in {module} and {seen_funcs.get(fn_name)}",
                )
                seen_funcs[fn_name] = module
        # stats.js must stay pure (zero DOM or global DATA references)
        stats_src = dash_dir.joinpath("stats.js").read_text("utf-8")
        self.assertNotIn("DATA.", stats_src)
        self.assertNotIn("document.", stats_src)


class DashboardRenderingTests(unittest.TestCase):
    def test_renders_self_contained_offline_html_with_strict_csp(self) -> None:
        profile = Profile(
            fields=(
                Field("kind", "$.kind"),
                Field("code", "$.code"),
                Field("ok", "$.ok", modifier="IS_PRESENT"),
            ),
            aggregates=(
                Aggregate("ms", "$.ms", ["SUM", "MIN", "MAX", "AVG", "HISTOGRAM"]),
                Aggregate("ts", "$.ts", ["MIN", "MAX"], type="DATETIME"),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "sample.sketch.yaml"
            sketch = Sketch(profile.aggregates, profile.profile_id)
            sketch.last_run = "261121-0001"
            for event in (
                {"kind": "ok", "code": 200, "ok": True, "ms": 12, "ts": "2026-11-21T10:00:00Z"},
                {"kind": "err", "code": 500, "ms": 80, "ts": "2026-11-21T12:00:00Z"},
            ):
                sketch.upsert(profile.tokens(event), event, run="261121-0001")
            sketch.save(str(sketch_path))

            payload = analyze_sketch(sketch_path)
            rendered = render_dashboard(payload, title="Sample Report")

            self.assertTrue(rendered.startswith("<!DOCTYPE html>"))
            self.assertIn("Content-Security-Policy", rendered)
            self.assertIn("default-src 'none'", rendered)
            self.assertIn("connect-src 'none'", rendered)
            self.assertIn("<title>Sample Report</title>", rendered)
            self.assertIn("Boolean", rendered)
            self.assertIn("Drop-One Field Ablation", rendered)
            self.assertIn("Correlated Value Clusters", rendered)
            self.assertIn("Alluvial / Sankey Flow", rendered)
            self.assertIn('"weightings":', rendered)
            self.assertIn('"default_weighting":"count"', rendered)
            self.assertIn('id="weight-select"', rendered)
            self.assertIn('id="copy-link-btn"', rendered)
            self.assertIn('id="agg-events"', rendered)
            self.assertIn('id="agg-quantiles"', rendered)
            self.assertIn('"HISTOGRAM"', rendered)
            # Lean payload omits unused server-side duplicates
            self.assertNotIn('"ablation":', rendered)
            self.assertNotIn('"correlations":', rendered)
            self.assertIn("syncUrlState", rendered)
            self.assertIn("hashchange", rendered)
            self.assertIn("Chart.js", rendered)
            self.assertNotRegex(rendered, r'<script[^>]+src=["\']https?://')
            self.assertNotRegex(rendered, r'<link[^>]+href=["\']https?://')
            self.assertNotRegex(rendered, r'<img[^>]+src=["\']https?://')

            if shutil.which("node"):
                app_js = _extract_app_script(rendered)
                with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as tmp_js:
                    tmp_js.write(app_js)
                    tmp_js.flush()
                    proc = subprocess.run(
                        ["node", "--check", tmp_js.name],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=False,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_empty_sketch_renders_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "empty.sketch.yaml"
            Sketch(profile_id="empty").save(str(sketch_path))
            payload = analyze_sketch(sketch_path)
            rendered = render_dashboard(payload)
            self.assertIn("empty.sketch.yaml", rendered)
            self.assertIn('"total_skits":0', rendered)

    def test_xss_and_prototype_pollution_payloads_are_safely_escaped(self) -> None:
        xss = "</script><img src=x onerror=alert(1)><!--"
        profile = Profile(
            fields=(
                Field("evil", "$.evil"),
                Field("__proto__", "$.proto_val"),
                Field("constructor", "$.ctor_val"),
            ),
            aggregates=(Aggregate("note", "$.note", ["MIN", "MAX"]),),
        )
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "xss.sketch.yaml"
            sketch = Sketch(profile.aggregates, profile.profile_id)
            event = {
                "evil": xss,
                "proto_val": "__proto__",
                "ctor_val": "toString",
                "note": xss,
                "raw": xss,
            }
            sketch.upsert(profile.tokens(event), event, run="261121-0001")
            sketch.save(str(sketch_path))

            payload = analyze_sketch(sketch_path)
            rendered = render_dashboard(payload, title=f"Title {xss}")

            self.assertNotIn("<img src=x onerror=alert(1)>", rendered)
            self.assertIn("&lt;/script&gt;&lt;img src=x onerror=alert(1)&gt;", rendered)
            data_match = re.search(
                r'<script id="skt-data" type="application/json">(.*?)</script>',
                rendered,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(data_match)
            assert data_match is not None
            self.assertNotIn("</script", data_match.group(1).lower())
            self.assertIn("\\u003c/script\\u003e", data_match.group(1))

    def test_placeholder_tokens_in_title_metadata_and_payload_are_not_expanded(self) -> None:
        sentinel = "__APP_JS__ __CHARTJS__ __DATA_JSON__ __CSS__"
        profile = Profile(fields=(Field("val", "$.val"),))
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "ph.sketch.yaml"
            sketch = Sketch(profile.aggregates, profile.profile_id)
            sketch.last_run = sentinel
            sketch.upsert(profile.tokens({"val": sentinel}), {"val": sentinel}, run=sentinel)
            sketch.save(str(sketch_path))

            payload = analyze_sketch(sketch_path)
            rendered = render_dashboard(payload, title=f"Report {sentinel}")

            self.assertIn(f"<title>Report {sentinel}</title>", rendered)
            data_match = re.search(
                r'<script id="skt-data" type="application/json">(.*?)</script>',
                rendered,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(data_match)
            assert data_match is not None
            parsed = json.loads(data_match.group(1))
            self.assertEqual(parsed["skits"][0]["tokens"]["val"], sentinel)
            self.assertEqual(parsed["meta"]["last_run"], sentinel)
            # App script marker appears only inside the single app script element
            self.assertEqual(rendered.count("function computeCorrelations("), 1)


@unittest.skipUnless(shutil.which("node"), "node is required for JS stats engine unit tests")
class DashboardStatsJsUnitTests(unittest.TestCase):
    def test_structured_tokens_distinguish_missing_null_literal_and_arrays(self) -> None:
        payload = {
            "skits": [
                {"id": "missing", "count": 2, "tokens": {}},
                {"id": "null", "count": 3, "tokens": {"tags": None}},
                {"id": "literal", "count": 5, "tokens": {"tags": "null"}},
                {"id": "empty", "count": 7, "tokens": {"tags": []}},
                {"id": "set-a", "count": 11, "tokens": {"tags": [None, "a"]}},
                {"id": "set-b", "count": 13, "tokens": {"tags": [None, "a"]}},
            ]
        }
        result = _run_stats_js(
            """
            const rows = INPUT.skits;
            return {
              keys: rows.map(s => tokenKey(s.tokens.tags)),
              labels: rows.map(s => tokenLabel(s.tokens.tags)),
              fields: computeFields(rows, ["tags"], 41, {isCount:true}),
              ablation: computeAblation(rows, ["tags"]),
              nullMatches: rows.map(s => matchesTokenFilter(s.tokens.tags, tokenKey(null))),
              emptyMatches: rows.map(s => matchesTokenFilter(s.tokens.tags, tokenKey([]))),
            };
            """,
            payload,
        )
        self.assertEqual(len(set(result["keys"])), 5)
        self.assertEqual(len(set(result["labels"])), 5)
        self.assertEqual(result["nullMatches"], [False, True, False, False, False, False])
        self.assertEqual(result["emptyMatches"], [False, False, False, True, False, False])
        self.assertEqual(result["ablation"][0]["cardinality"], 5)
        self.assertEqual(result["ablation"][0]["remaining_skits"], 1)

    def test_correlations_group_structured_values_by_content(self) -> None:
        payload = {
            "skits": [
                {"id": "a", "count": 5, "tokens": {"x": [None, "tag"], "y": "a"}},
                {"id": "b", "count": 5, "tokens": {"x": [None, "tag"], "y": "a"}},
                {"id": "c", "count": 5, "tokens": {"x": None, "y": "b"}},
                {"id": "d", "count": 5, "tokens": {"y": "c"}},
            ]
        }
        result = _run_stats_js(
            """
            const c = computeCorrelations(INPUT.skits, ["x", "y"], 20, {isCount:true});
            return {v: c.cramers.get("x").get("y"), u: c.theils.get("x").get("y")};
            """,
            payload,
        )
        self.assertAlmostEqual(result["v"], 1)
        self.assertAlmostEqual(result["u"], 1)

    def test_sankey_groups_equal_sets_and_preserves_null_and_missing(self) -> None:
        result = _run_stats_js(
            """
            const rows = [
              {tokens: {}, count: 1},
              {tokens: {x: null}, count: 2},
              {tokens: {x: []}, count: 3},
              {tokens: {x: [null, "a"]}, count: 4},
              {tokens: {x: [null, "a"]}, count: 5}
            ];
            return buildSankeyStages(["x"], rows, {isCount: true}).stageNodes[0];
            """,
            extra_modules=("sankey.js",),
        )
        self.assertEqual(len(result), 4)
        self.assertEqual(sorted(row["count"] for row in result), [1, 2, 3, 9])
        self.assertEqual(len({row["label"] for row in result}), 4)

    def test_medians_concentration_and_field_classification(self) -> None:
        profile = Profile(
            fields=(
                Field("kind", "$.kind"),
                Field("status", "$.status"),
                Field("present", "$.err", modifier="IS_PRESENT"),
                Field("env", "$.env"),
                Field("missing", "$.absent"),
            ),
            aggregates=(Aggregate("bytes", "$.bytes", ["SUM", "AVG"]),),
        )
        events = [
            *[{"kind": "a", "status": 200, "env": "prod", "bytes": 10} for _ in range(6)],
            *[
                {"kind": "b", "status": 404, "env": "prod", "err": "x", "bytes": 30}
                for _ in range(3)
            ],
            {"kind": "c", "status": 500, "env": "prod", "err": "y", "bytes": 500},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "stats.sketch.yaml"
            sketch = Sketch(profile.aggregates, profile.profile_id)
            for ev in events:
                sketch.upsert(profile.tokens(ev), ev, run="261123-0001")
            sketch.save(str(sketch_path))
            payload = analyze_sketch(sketch_path)

        out = _run_stats_js(
            """
            const wmCount = { isCount: true };
            const wmBytes = { isCount: false, key: "bytes" };
            const keys = INPUT.fields.map(f => f.key);
            const totalObs = INPUT.skits.reduce((s, x) => s + x.count, 0);
            const totalBytes = INPUT.skits.reduce((s, x) => s + skitWeight(x, wmBytes), 0);
            return {
              evenWeightedMed: weightedMedian([[10, 2], [30, 2]]),
              oddWeightedMed: weightedMedian([[10, 3], [30, 1]]),
              plainMedEven: plainMedian([10, 20, 30, 40]),
              plainMedOdd: plainMedian([10, 30, 100]),
              concCount: computeConcentration(INPUT.skits, totalObs, wmCount),
              concBytes: computeConcentration(INPUT.skits, totalBytes, wmBytes),
              fieldsCount: computeFields(INPUT.skits, keys, totalObs, wmCount),
              fieldsBytes: computeFields(INPUT.skits, keys, totalBytes, wmBytes),
            };
            """,
            payload,
        )

        self.assertAlmostEqual(out["evenWeightedMed"], 20.0)
        self.assertAlmostEqual(out["oddWeightedMed"], 10.0)
        self.assertAlmostEqual(out["plainMedEven"], 25.0)
        self.assertAlmostEqual(out["plainMedOdd"], 30.0)

        conc_count = {c["target_pct"]: c["skits_needed"] for c in out["concCount"]}
        self.assertEqual(conc_count, {50: 1, 80: 2, 90: 2, 95: 3, 99: 3})
        # Weighted by bytes (500 / 650 = 76.9% in singleton kind=c): top 1 covers >50%
        conc_bytes = {c["target_pct"]: c["skits_needed"] for c in out["concBytes"]}
        self.assertEqual(conc_bytes[50], 1)

        fields = {f["key"]: f for f in out["fieldsCount"]}
        self.assertEqual(fields["kind"]["field_type"], "enum")
        self.assertEqual(fields["status"]["field_type"], "numeric")
        self.assertAlmostEqual(fields["status"]["weighted_mean"], 291.2)
        self.assertAlmostEqual(fields["status"]["weighted_median"], 200.0)
        self.assertEqual(fields["present"]["field_type"], "boolean")
        self.assertAlmostEqual(fields["present"]["true_pct"], 40.0)
        self.assertEqual(fields["present"]["min"], "FALSE")
        self.assertEqual(fields["present"]["max"], "TRUE")
        self.assertTrue(fields["env"]["is_constant"])
        self.assertNotIn("missing", fields)  # no retained key means no observed dimension

        # Under bytes weighting, present=TRUE has (90 + 500) / 650 = 90.769%
        fields_b = {f["key"]: f for f in out["fieldsBytes"]}
        self.assertAlmostEqual(fields_b["present"]["true_pct"], 100 * 590 / 650, places=2)

    def test_ablation_correlations_and_histograms_in_js(self) -> None:
        profile = Profile(
            fields=(
                Field("embed", "$.embed"),
                Field("has_img", "$.img", modifier="IS_PRESENT"),
                Field("img_mirror", "$.img", modifier="IS_PRESENT"),
                Field("reply", "$.reply", modifier="IS_PRESENT"),
            ),
            aggregates=(
                Aggregate("bytes", "$.bytes", ["SUM", "MIN", "MAX", "AVG", "HISTOGRAM"]),
                Aggregate("lat", "$.ms", {"name": "HISTOGRAM", "buckets": [10, 50, 100]}),
            ),
        )
        events = [
            *[
                {"embed": "images", "img": 1, "bytes": 10 + i * 5, "ms": 5 + i * 4}
                for i in range(10)
            ],
            *[{"embed": "video", "bytes": 100 + i * 10, "ms": 60 + i * 5} for i in range(10)],
            *[{"embed": "none", "reply": 1, "bytes": 50, "ms": 150} for _ in range(10)],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "corr.sketch.yaml"
            sketch = Sketch(profile.aggregates, profile.profile_id)
            for ev in events:
                sketch.upsert(profile.tokens(ev), ev, run="261123-0001")
            sketch.save(str(sketch_path))
            payload = analyze_sketch(sketch_path)

        out = _run_stats_js(
            """
            const wm = { isCount: true };
            const keys = INPUT.fields.map(f => f.key);
            const total = INPUT.skits.reduce((s, x) => s + x.count, 0);
            const corr = computeCorrelations(INPUT.skits, keys, total, wm);
            const aggs = computeAggregates(INPUT.skits, INPUT.aggregates);
            const ablation = computeAblation(INPUT.skits, keys);
            return {
              cramers_hm: corr.cramers.get("has_img").get("img_mirror"),
              theils_e_to_h: corr.theils.get("embed").get("has_img"),
              theils_h_to_e: corr.theils.get("has_img").get("embed"),
              redundant_h: corr.redundant_with.get("has_img"),
              determined_h: corr.determined_by.get("has_img"),
              edges: corr.edges,
              clusters: findPositiveClusters(corr.edges),
              aggs,
              ablation,
            };
            """,
            payload,
        )

        self.assertAlmostEqual(out["cramers_hm"], 1.0, places=3)
        self.assertAlmostEqual(out["theils_e_to_h"], 1.0, places=3)
        self.assertLess(out["theils_h_to_e"], 0.7)
        self.assertIn("img_mirror", out["redundant_h"])
        self.assertIn("embed", out["determined_h"])

        edge_map = {(e["a"], e["b"]): e for e in out["edges"]}
        edge_map.update({(e["b"], e["a"]): e for e in out["edges"]})
        self.assertAlmostEqual(edge_map[("embed=images", "has_img=TRUE")]["phi"], 1.0, places=3)
        self.assertAlmostEqual(edge_map[("has_img=TRUE", "reply=TRUE")]["phi"], -0.5, places=3)
        self.assertTrue(out["clusters"])

        aggs = {a["key"]: a for a in out["aggs"]}
        self.assertEqual(aggs["bytes"]["histogram"]["mode"], "log")
        self.assertEqual(aggs["bytes"]["histogram"]["count"], 30)
        self.assertIsNotNone(aggs["bytes"]["histogram"]["quantiles"]["p50"])
        self.assertEqual(aggs["lat"]["histogram"]["mode"], "fixed")
        self.assertEqual(aggs["lat"]["histogram"]["count"], 30)
        self.assertEqual([b["count"] for b in aggs["lat"]["histogram"]["bins"]], [2, 8, 9, 11])
        self.assertEqual(len(out["ablation"]), 4)

    def test_ablation_in_js_identifies_singleton_and_cardinality_drivers(self) -> None:
        profile = Profile(
            fields=(
                Field("env", "$.env"),
                Field("kind", "$.kind"),
                Field("lang", "$.lang"),
            ),
        )
        events = [
            {"env": "prod", "kind": "post", "lang": "en"},
            {"env": "prod", "kind": "post", "lang": "en"},
            {"env": "prod", "kind": "post", "lang": "fr"},
            {"env": "prod", "kind": "post", "lang": "de"},
            {"env": "prod", "kind": "post", "lang": "ja"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "ablate.sketch.yaml"
            sketch = Sketch(profile.aggregates, profile.profile_id)
            for ev in events:
                sketch.upsert(profile.tokens(ev), ev, run="261123-0001")
            sketch.save(str(sketch_path))
            payload = analyze_sketch(sketch_path)

        out = _run_stats_js(
            "return computeAblation(INPUT.skits, INPUT.fields.map(f => f.key));",
            payload,
        )
        self.assertEqual(out[0]["key"], "lang")
        self.assertEqual(out[0]["cardinality"], 4)
        self.assertEqual(out[0]["singleton_only_values"], 3)
        self.assertEqual(out[0]["skits_collapsed"], 3)
        self.assertEqual(out[0]["singletons_removed"], 3)
        self.assertEqual(out[0]["remaining_skits"], 1)
        self.assertEqual(out[0]["remaining_singletons"], 0)


if __name__ == "__main__":
    unittest.main()
