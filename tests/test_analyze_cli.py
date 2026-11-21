"""CLI tests for `sketchtastic analyze` (STORY-SKT-12, STORY-SKT-14)."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from sketchtastic.aggregators import Aggregate
from sketchtastic.cli import main
from sketchtastic.profile import Field, Profile
from sketchtastic.sketch import Sketch


def _run_cli(*argv: str) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(list(argv))
    return code, stdout.getvalue(), stderr.getvalue()


class AnalyzeCliTests(unittest.TestCase):
    def _make_sketch(self, path: Path) -> None:
        profile = Profile(
            fields=(Field("level", "$.level"), Field("status", "$.status")),
            aggregates=(
                Aggregate("ms", "$.ms", ["SUM", "MIN", "MAX", "AVG"]),
                Aggregate("ts", "$.ts", ["MIN", "MAX"], type="DATETIME"),
            ),
        )
        sketch = Sketch(profile.aggregates, profile.profile_id)
        sketch.last_run = "261121-0001"
        for event in (
            {"level": "INFO", "status": 200, "ms": 10, "ts": "2026-11-21T09:00:00Z"},
            {"level": "INFO", "status": 200, "ms": 20, "ts": "2026-11-21T09:05:00Z"},
            {"level": "ERROR", "status": 500, "ms": 95, "ts": "2026-11-21T09:10:00Z"},
        ):
            sketch.upsert(profile.tokens(event), event, run="261121-0001")
        sketch.save(str(path))

    def test_analyze_writes_offline_dashboard_and_refuses_clobber_until_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "app.sketch.yaml"
            out_path = Path(tmp) / "report.html"
            self._make_sketch(sketch_path)

            code, out, err = _run_cli(
                "analyze", str(sketch_path), "-o", str(out_path), "--title", "My <Audit>"
            )
            self.assertEqual(code, 0, err)
            self.assertIn("3 observations", out)
            self.assertIn("2 skits", out)
            content = out_path.read_text("utf-8")
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("Chart.js", content)
            self.assertIn("My &lt;Audit&gt;", content)

            # Second run without --force fails with exit 2 and leaves file intact
            out_path.write_text("sentinel", encoding="utf-8")
            code, _, err = _run_cli("analyze", str(sketch_path), "-o", str(out_path))
            self.assertEqual(code, 2)
            self.assertIn("already exists", err)
            self.assertEqual(out_path.read_text("utf-8"), "sentinel")

            # With --force it atomically replaces the regular file
            code, _, err = _run_cli("analyze", str(sketch_path), "-o", str(out_path), "--force")
            self.assertEqual(code, 0, err)
            self.assertIn("<!DOCTYPE html>", out_path.read_text("utf-8"))

    def test_analyze_refuses_symlink_and_directory_even_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "app.sketch.yaml"
            self._make_sketch(sketch_path)
            target = Path(tmp) / "victim.txt"
            target.write_text("keep me", encoding="utf-8")
            link = Path(tmp) / "link.html"
            link.symlink_to(target)

            code, _, err = _run_cli("analyze", str(sketch_path), "-o", str(link), "--force")
            self.assertEqual(code, 2)
            self.assertIn("symlink", err)
            self.assertEqual(target.read_text("utf-8"), "keep me")

            sub = Path(tmp) / "subdir"
            sub.mkdir()
            code, _, err = _run_cli("analyze", str(sketch_path), "-o", str(sub), "--force")
            self.assertEqual(code, 2)
            self.assertIn("directory", err)

    def test_analyze_rejects_bad_sketch_and_missing_explicit_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.html"
            code, _, err = _run_cli("analyze", str(Path(tmp) / "missing.yaml"), "-o", str(out_path))
            self.assertEqual(code, 2)
            self.assertTrue(err.startswith("sketchtastic:"))
            self.assertFalse(out_path.exists())

            sketch_path = Path(tmp) / "app.sketch.yaml"
            self._make_sketch(sketch_path)
            code, _, err = _run_cli(
                "analyze",
                str(sketch_path),
                "-o",
                str(out_path),
                "--history",
                str(Path(tmp) / "missing-history"),
            )
            self.assertEqual(code, 2)
            self.assertIn("History directory", err)
            self.assertFalse(out_path.exists())

    def test_analyze_auto_detects_history_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = Path(tmp) / "app.sketch.yaml"
            hist_dir = Path(tmp) / "app.sketch.history"
            hist_dir.mkdir()
            self._make_sketch(sketch_path)
            self._make_sketch(hist_dir / "261121-0001.yaml")
            out_path = Path(tmp) / "dash.html"

            code, out, err = _run_cli("analyze", str(sketch_path), "-o", str(out_path))
            self.assertEqual(code, 0, err)
            self.assertIn("1 history runs", out)
            self.assertIn("261121-0001", out_path.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
