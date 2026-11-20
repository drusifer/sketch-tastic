"""Generic ranked samples and frequency-weighted regression coverage contracts."""

import contextlib
import datetime
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from sketchtastic import Sketch, load_profile
from sketchtastic.cli import main
from sketchtastic.reporting import coverage, export_samples, report


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile_path = self.root / "profile.yaml"
        self.profile_path.write_text("version: 0\nfields:\n  - {key: kind, path: $.kind}\n")
        self.profile = load_profile(str(self.profile_path))
        self.path = self.root / "baseline.yaml"
        self.sketch = Sketch(self.profile.aggregates, self.profile.profile_id)
        self.ids = {}
        for kind, count in [("common", 90), ("unusual", 9), ("rare", 1)]:
            for index in range(count):
                record = {"kind": kind, "sequence": index, "nested": {"original": ["\u00e9", None]}}
                self.ids[kind] = self.sketch.upsert(self.profile.tokens(record), record)
        self.sketch.save(str(self.path))

    def regression(self, records):
        path = self.root / "regression.jsonl"
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        return path

    def test_report_rank_full_ids_frequency_cumulative_and_sample_locator(self):
        text = report(self.path, limit=0)
        self.assertLess(text.index(self.ids["common"]), text.index(self.ids["unusual"]))
        self.assertLess(text.index(self.ids["unusual"]), text.index(self.ids["rare"]))
        self.assertIn("90.0%", text)
        self.assertIn("99.0%", text)
        self.assertIn("100.0%", text)
        self.assertIn("meta.first[0].record", text)
        self.assertIn("common", text)
        self.assertNotIn(self.ids["rare"], report(self.path, limit=2))

    def test_export_original_records_in_ranking_order_and_selected_ids(self):
        output = self.root / "samples.jsonl"
        ids = export_samples(self.path, output)
        self.assertEqual(ids, [self.ids[k] for k in ("common", "unusual", "rare")])
        rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(rows, [self.sketch.get(key).meta["first"][0]["record"] for key in ids])
        chosen = self.root / "chosen.jsonl"
        self.assertEqual(
            export_samples(
                self.path, chosen, [self.ids["rare"], self.ids["common"], self.ids["rare"]]
            ),
            [self.ids["common"], self.ids["rare"]],
        )
        self.assertEqual(len(chosen.read_text().splitlines()), 2)

    def test_export_invalid_id_or_existing_file_or_symlink_never_changes_output(self):
        output = self.root / "samples.jsonl"
        with self.assertRaisesRegex(ValueError, "Unknown"):
            export_samples(self.path, output, [self.ids["common"], "not-a-kind"])
        self.assertFalse(output.exists())
        output.write_text("keep")
        with self.assertRaises(FileExistsError):
            export_samples(self.path, output)
        self.assertEqual(output.read_text(), "keep")
        link = self.root / "dangling.jsonl"
        link.symlink_to(self.root / "missing")
        with self.assertRaises(FileExistsError):
            export_samples(self.path, link)
        self.assertTrue(link.is_symlink())

    def test_export_publish_race_does_not_clobber_competing_writer(self):
        import os

        output = self.root / "race.jsonl"
        real_link = os.link

        def competing(source, destination):
            Path(destination).write_text("other writer")
            real_link(source, destination)

        with patch("sketchtastic.reporting.os.link", competing):
            with self.assertRaises(FileExistsError):
                export_samples(self.path, output)
        self.assertEqual(output.read_text(), "other writer")

    def test_coverage_weights_unique_intersection_and_unknown_kinds(self):
        path = self.regression([{"kind": "common"}] * 7 + [{"kind": "new"}] * 2)
        text = coverage(self.path, self.profile_path, path, limit=0)
        self.assertIn("90 / 100", text)
        self.assertIn("90.0%", text)
        self.assertIn("1 / 3", text)
        self.assertIn("33.3%", text)
        self.assertIn("Unknown regression kinds: 1", text)
        self.assertIn(self.ids["unusual"], text)
        self.assertIn(self.ids["rare"], text)
        self.assertIn("not test execution or branch coverage", text)

    def test_empty_baseline_and_regression(self):
        empty = self.root / "empty.yaml"
        Sketch(profile_id=self.profile.profile_id).save(str(empty))
        text = coverage(empty, self.profile_path, self.regression([{"kind": "new"}]))
        self.assertIn("N/A (0 / 0)", text)
        self.assertIn("Unknown regression kinds: 1", text)
        self.assertIn("No kinds", report(empty))
        text = coverage(self.path, self.profile_path, self.regression([]))
        self.assertIn("0.0% (0 / 100)", text)

    def test_profile_mismatch_is_rejected(self):
        other = self.root / "other.yaml"
        other.write_text("fields:\n  - {key: changed, path: $.kind}\n")
        with self.assertRaisesRegex(ValueError, "profile"):
            coverage(self.path, other, self.regression([{"kind": "common"}]))

    def test_malformed_regression_fails_before_any_cli_output(self):
        for bad in ["[]", "{bad", '{"x":NaN}', '{"x":Infinity}']:
            with self.subTest(bad=bad):
                source = self.regression([{"kind": "common"}])
                with source.open("a") as stream:
                    stream.write(bad + "\n")
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    status = main(
                        ["coverage", str(self.path), "-p", str(self.profile_path), str(source)]
                    )
                self.assertEqual(status, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("line 2", stderr.getvalue())

    def test_report_escapes_arbitrary_token_text_and_cli_commands_work(self):
        sketch = Sketch(profile_id=self.profile.profile_id)
        row = {"kind": "\x1b[31m caf\u00e9\nnew"}
        sketch.upsert(self.profile.tokens(row), row)
        sketch.save(str(self.path))
        text = report(self.path)
        self.assertTrue(text.isascii())
        self.assertNotIn("\x1b", text)
        for args in [
            ["report", str(self.path), "--limit", "0"],
            ["export", str(self.path), "--output", str(self.root / "cli.jsonl")],
        ]:
            with self.subTest(args=args), contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(args), 0)
                self.assertTrue(stdout.getvalue().isascii())

    def test_coverage_bounds_lines_and_rejects_invalid_utf8(self):
        source = self.root / "invalid.jsonl"
        for content in [b"\xff\n", b'{"x":"' + b"x" * (4 * 1024 * 1024) + b'"}\n']:
            source.write_bytes(content)
            with self.assertRaisesRegex(ValueError, "line 1"):
                coverage(self.path, self.profile_path, source)

    def test_negative_limit_rejected(self):
        with self.assertRaisesRegex(ValueError, "limit"):
            report(self.path, limit=-1)

    def test_missing_profile_identity_cannot_claim_coverage(self):
        data = yaml.safe_load(self.path.read_text())
        data.pop("profile_id")
        self.path.write_text(yaml.safe_dump(data, sort_keys=False))
        with self.assertRaisesRegex(ValueError, "profile"):
            coverage(self.path, self.profile_path, self.regression([]))

    def test_invalid_counts_rejected_and_zero_weight_is_defined(self):
        original = yaml.safe_load(self.path.read_text())
        for value in [-1, True, 2.5, "90"]:
            with self.subTest(value=value):
                data = json.loads(json.dumps(original))
                data["skits"][self.ids["common"]]["meta"]["count"] = value
                self.path.write_text(yaml.safe_dump(data, sort_keys=False))
                with self.assertRaisesRegex(ValueError, "count"):
                    report(self.path)
        for skit in original["skits"].values():
            skit["meta"]["count"] = 0
        self.path.write_text(yaml.safe_dump(original, sort_keys=False))
        self.assertIn("N/A", report(self.path))
        self.assertIn("N/A (0 / 0)", coverage(self.path, self.profile_path, self.regression([])))

    def test_missing_retained_sample_aborts_export(self):
        data = yaml.safe_load(self.path.read_text())
        data["skits"][self.ids["rare"]]["meta"]["first"] = []
        self.path.write_text(yaml.safe_dump(data, sort_keys=False))
        output = self.root / "invalid-samples.jsonl"
        with self.assertRaisesRegex(ValueError, "no retained first record"):
            export_samples(self.path, output)
        self.assertFalse(output.exists())

    def test_report_includes_numeric_and_datetime_aggregates_safely(self):
        data = yaml.safe_load(self.path.read_text())
        data["skits"][self.ids["common"]]["aggregates"] = {
            "bytes": {"SUM": 400, "AVG": {"avg": 200, "sum": 400, "count": 2}},
            "posted_at": {"MIN": datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)},
            "unsafe\x1b": "value\x1b",
        }
        self.path.write_text(yaml.safe_dump(data, sort_keys=False))
        output = report(self.path, limit=1)
        self.assertIn('"SUM":400', output)
        self.assertIn('"avg":200', output)
        self.assertIn("2026-01-01", output)
        self.assertNotIn("\x1b", output)

    def test_non_json_retained_value_reports_error_without_publishing(self):
        data = yaml.safe_load(self.path.read_text())
        data["skits"][self.ids["common"]]["meta"]["first"][0]["record"]["invalid"] = datetime.date(
            2026, 1, 1
        )
        self.path.write_text(yaml.safe_dump(data, sort_keys=False))
        output = self.root / "invalid-date.jsonl"
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main(["export", str(self.path), "--output", str(output)])
        self.assertEqual(status, 2)
        self.assertIn("JSON", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")
        self.assertFalse(output.exists())
