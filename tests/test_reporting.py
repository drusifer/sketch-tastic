"""Original representative sample export contracts."""

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
from sketchtastic.reporting import export_samples


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

        with patch("os.link", competing):
            with self.assertRaises(FileExistsError):
                export_samples(self.path, output)
        self.assertEqual(output.read_text(), "other writer")

    def test_export_cli_output_is_ascii(self):
        sketch = Sketch(profile_id=self.profile.profile_id)
        row = {"kind": "\x1b[31m caf\u00e9\nnew"}
        sketch.upsert(self.profile.tokens(row), row)
        sketch.save(str(self.path))
        for args in [
            ["export", str(self.path), "--output", str(self.root / "cli.jsonl")],
        ]:
            with self.subTest(args=args), contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(args), 0)
                self.assertTrue(stdout.getvalue().isascii())

    def test_missing_retained_sample_aborts_export(self):
        data = yaml.safe_load(self.path.read_text())
        data["skits"][self.ids["rare"]]["meta"]["first"] = []
        self.path.write_text(yaml.safe_dump(data, sort_keys=False))
        output = self.root / "invalid-samples.jsonl"
        with self.assertRaisesRegex(ValueError, "no retained first record"):
            export_samples(self.path, output)
        self.assertFalse(output.exists())

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
