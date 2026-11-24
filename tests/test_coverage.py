"""Regression coverage in the analyze dashboard: baseline kinds and every history run."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from sketchtastic import Sketch, load_profile
from sketchtastic.analysis import analyze_sketch
from sketchtastic.cli import main


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile_path = self.root / "profile.yaml"
        self.profile_path.write_text("version: 0\nfields:\n  - {key: kind, path: $.kind}\n")
        self.profile = load_profile(str(self.profile_path))
        self.path = self.root / "baseline.sketch.yaml"
        self.ids = {}

    def jsonl(self, name, records):
        path = self.root / name
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        return path

    def merge(self, records):
        """One `sketch merge` run, so the sketch gets a history file per call."""
        events = self.jsonl("events.jsonl", records)
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["merge", "-p", str(self.profile_path), "-s", str(self.path), str(events)])
        self.assertEqual(code, 0)

    def kind_id(self, kind):
        return Sketch().upsert(self.profile.tokens({"kind": kind}), {"kind": kind})

    def coverage(self, records):
        corpus = self.jsonl("regression.jsonl", records)
        return analyze_sketch(self.path, regression=(self.profile_path, corpus))

    def test_unique_intersection_weights_and_unknown_kinds(self):
        self.merge([{"kind": "common"}] * 90 + [{"kind": "unusual"}] * 9 + [{"kind": "rare"}])
        payload = self.coverage([{"kind": "common"}] * 7 + [{"kind": "new"}] * 2)
        cov = payload["coverage"]
        self.assertEqual(cov["covered_ids"], [self.kind_id("common")])
        self.assertEqual((cov["regression_records"], cov["regression_kinds"]), (9, 2))
        self.assertEqual(cov["unknown_count"], 1)
        self.assertEqual(cov["unknown"][0]["records"], 2)
        flags = {s["id"]: s["covered"] for s in payload["skits"]}
        self.assertEqual(sum(flags.values()), 1)
        self.assertTrue(flags[self.kind_id("common")])

    def test_without_regression_no_coverage_flags(self):
        self.merge([{"kind": "a"}])
        payload = analyze_sketch(self.path)
        self.assertIsNone(payload["coverage"])
        self.assertIsNone(payload["skits"][0]["covered"])

    def test_missing_and_null_tokens_are_different_kinds(self):
        self.merge([{}, {"kind": None}, {"kind": []}])
        cov = self.coverage([{"kind": None}])["coverage"]
        self.assertEqual(len(cov["covered_ids"]), 1)
        self.assertEqual(cov["unknown_count"], 0)

    def test_history_runs_get_own_and_cumulative_coverage(self):
        self.merge([{"kind": "a"}] * 3 + [{"kind": "b"}])
        self.merge([{"kind": "a"}] + [{"kind": "c"}] * 4)
        runs = self.coverage([{"kind": "a"}, {"kind": "b"}])["coverage"]["runs"]
        self.assertEqual(len(runs), 2)
        first, second = runs
        self.assertEqual((first["covered_kinds"], first["kinds"]), (2, 2))
        self.assertEqual(first["event_pct"], 100.0)
        self.assertEqual(first["new_uncovered_count"], 0)
        # Run 2 introduced kind c, which the corpus does not cover.
        self.assertEqual((second["covered_kinds"], second["kinds"]), (1, 2))
        self.assertEqual(second["event_pct"], 20.0)
        self.assertEqual((second["new_kinds"], second["new_uncovered_count"]), (1, 1))
        self.assertEqual(second["new_uncovered"][0]["id"], self.kind_id("c"))
        self.assertEqual(second["new_uncovered"][0]["count"], 4)
        # Cumulative over both runs: 5 of 9 events, 2 of 3 kinds.
        self.assertEqual(second["cum_event_pct"], round(100 * 5 / 9, 2))
        self.assertEqual((second["cum_covered_kinds"], second["cum_kinds"]), (2, 3))

    def test_history_run_with_other_profile_is_not_compared(self):
        self.merge([{"kind": "a"}])
        run_file = next((self.root / "baseline.sketch.history").iterdir())
        raw = yaml.safe_load(run_file.read_text())
        raw["profile_id"] = "0" * 32
        run_file.write_text(yaml.safe_dump(raw, sort_keys=False))
        runs = self.coverage([{"kind": "a"}])["coverage"]["runs"]
        self.assertEqual(runs, [{"id": runs[0]["id"], "comparable": False}])

    def test_empty_baseline_and_corpus(self):
        Sketch(profile_id=self.profile.profile_id).save(str(self.path))
        cov = self.coverage([{"kind": "new"}])["coverage"]
        self.assertEqual((cov["covered_ids"], cov["unknown_count"]), ([], 1))
        self.merge([{"kind": "a"}])
        self.assertEqual(self.coverage([])["coverage"]["covered_ids"], [])

    def test_profile_mismatch_and_missing_identity_are_rejected(self):
        self.merge([{"kind": "a"}])
        other = self.root / "other.yaml"
        other.write_text("fields:\n  - {key: changed, path: $.kind}\n")
        corpus = self.jsonl("regression.jsonl", [{"kind": "a"}])
        with self.assertRaisesRegex(ValueError, "profile"):
            analyze_sketch(self.path, regression=(other, corpus))
        data = yaml.safe_load(self.path.read_text())
        data.pop("profile_id")
        self.path.write_text(yaml.safe_dump(data, sort_keys=False))
        with self.assertRaisesRegex(ValueError, "profile"):
            analyze_sketch(self.path, regression=(self.profile_path, corpus))

    def test_bad_corpus_line_is_named(self):
        self.merge([{"kind": "a"}])
        source = self.root / "bad.jsonl"
        for content in [b"\xff\n", b"[]\n", b'{"x":NaN}\n', b'{"x":"' + b"x" * (4 << 20) + b'"}\n']:
            with self.subTest(content=content[:12]):
                source.write_bytes(content)
                with self.assertRaisesRegex(ValueError, "line 1"):
                    analyze_sketch(self.path, regression=(self.profile_path, source))

    def test_cli_writes_dashboard_with_coverage_and_rejects_half_options(self):
        self.merge([{"kind": "a"}, {"kind": "b"}])
        corpus = self.jsonl("regression.jsonl", [{"kind": "a"}])
        html = self.root / "dash.html"
        base = ["analyze", str(self.path), "-o", str(html)]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([*base, "--regression", str(corpus), "-p", str(self.profile_path)])
        self.assertEqual(code, 0)
        self.assertIn("1 of 2 kinds covered", out.getvalue())
        self.assertIn('"covered_ids"', html.read_text())
        html.unlink()
        for extra in (["--regression", str(corpus)], ["-p", str(self.profile_path)]):
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main([*base, *extra]), 2)
                self.assertIn("together", err.getvalue())
            self.assertFalse(html.exists())

    def test_malformed_corpus_writes_nothing(self):
        self.merge([{"kind": "a"}])
        corpus = self.jsonl("regression.jsonl", [{"kind": "a"}])
        with corpus.open("a") as stream:
            stream.write("{bad\n")
        html = self.root / "dash.html"
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(
                ["analyze", str(self.path), "-o", str(html), "--regression", str(corpus)]
                + ["-p", str(self.profile_path)]
            )
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("line 2", stderr.getvalue())
        self.assertFalse(html.exists())


if __name__ == "__main__":
    unittest.main()
