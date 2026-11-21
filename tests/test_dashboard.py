"""Unit tests for the offline Chart.js HTML dashboard renderer (STORY-SKT-12, -13, -14)."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path

from sketchtastic.aggregators import Aggregate
from sketchtastic.analysis import analyze_sketch
from sketchtastic.dashboard import render_dashboard
from sketchtastic.profile import Field, Profile
from sketchtastic.sketch import Sketch


def _extract_app_script(html_text: str) -> str:
    match = re.search(r'<script id="skt-app-script">(.*?)</script>', html_text, flags=re.DOTALL)
    assert match is not None, "Missing skt-app-script block"
    return match.group(1)


class VendoredChartJsAssetTests(unittest.TestCase):
    def test_chartjs_bundle_matches_pinned_sha256_and_mit_license(self) -> None:
        assets = files("sketchtastic").joinpath("assets")
        bundle_bytes = assets.joinpath("chart.umd.min.js").read_bytes()
        expected_sha = assets.joinpath("CHARTJS_SHA256.txt").read_text("utf-8").strip()
        license_text = assets.joinpath("CHARTJS_LICENSE.txt").read_text("utf-8")

        self.assertEqual(hashlib.sha256(bundle_bytes).hexdigest(), expected_sha)
        self.assertIn("The MIT License", license_text)
        self.assertNotIn(b"</script", bundle_bytes.lower())


class DashboardRenderingTests(unittest.TestCase):
    def test_renders_self_contained_offline_html_with_strict_csp(self) -> None:
        profile = Profile(
            fields=(
                Field("kind", "$.kind"),
                Field("code", "$.code"),
                Field("ok", "$.ok", modifier="IS_PRESENT"),
            ),
            aggregates=(
                Aggregate("ms", "$.ms", ["SUM", "MIN", "MAX", "AVG"]),
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
            self.assertIn('"field_type":"boolean"', rendered)
            self.assertIn("Boolean", rendered)
            self.assertIn("Drop-One Field Ablation", rendered)
            self.assertIn('"ablation":', rendered)
            # Chart.js is inlined, no external resource loading tags
            self.assertIn("Chart.js", rendered)
            self.assertNotRegex(rendered, r'<script[^>]+src=["\']https?://')
            self.assertNotRegex(rendered, r'<link[^>]+href=["\']https?://')
            self.assertNotRegex(rendered, r'<img[^>]+src=["\']https?://')

            # Inline JS passes real Node syntax check when node is available
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

            # Raw breakout tag must NEVER appear anywhere in HTML
            self.assertNotIn("<img src=x onerror=alert(1)>", rendered)
            # Title HTML-escaped
            self.assertIn("&lt;/script&gt;&lt;img src=x onerror=alert(1)&gt;", rendered)
            # JSON script payload uses \u003c escaping
            data_match = re.search(
                r'<script id="skt-data" type="application/json">(.*?)</script>',
                rendered,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(data_match)
            assert data_match is not None
            self.assertNotIn("</script", data_match.group(1).lower())
            self.assertIn("\\u003c/script\\u003e", data_match.group(1))


if __name__ == "__main__":
    unittest.main()
