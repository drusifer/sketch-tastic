"""Derive publishes a new inventory and all available runs without modifying sources."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sketchtastic import _yaml
from sketchtastic._io import history_dir_for
from sketchtastic.cli import main
from sketchtastic.sketch import read_sketch_file


class DeriveCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old = self.root / "old-profile.yaml"
        self.new = self.root / "new-profile.yaml"
        common = "\nsequence: $.seq\naggregates:\n  - {key: size, path: $.size, fn: [SUM, AVG]}\n"
        self.old.write_text(
            "fields:\n  - {key: kind, path: $.kind}\n  - {key: extra, path: $.extra}\n" + common
        )
        self.new.write_text("fields:\n  - {key: kind, path: $.kind}\n" + common)
        self.source = self.root / "old.yaml"
        self.output = self.root / "v2.yaml"
        self.events = self.root / "events.jsonl"
        for seq in (1, 2):
            self.events.write_text(
                json.dumps({"seq": seq, "kind": "a", "extra": str(seq), "size": seq * 2}) + "\n"
            )
            self.assertEqual(
                self.command("merge", "-p", self.old, "-s", self.source, self.events)[0], 0
            )
        self.history = history_dir_for(self.source)
        self.before = {
            p: p.read_bytes() for p in [self.source, self.old, self.new, *self.history.iterdir()]
        }

    def command(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main([str(arg) for arg in args])
        return code, stdout.getvalue() + stderr.getvalue()

    def derive(self):
        return self.command(
            "derive", self.source, "--source-profile", self.old, "-p", self.new, "-o", self.output
        )

    def assert_sources_unchanged(self):
        for path, content in self.before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_history_provenance_counts_and_continued_merge(self):
        status, text = self.derive()
        self.assertEqual(status, 0, text)
        self.assertIn("2", text)
        self.assert_sources_unchanged()
        derived = read_sketch_file(self.output)
        self.assertEqual(len(derived["skits"]), 1)
        self.assertEqual(next(iter(derived["skits"].values()))["meta"]["count"], 2)
        self.assertEqual(derived["sequence"]["max"], 2)
        self.assertEqual(derived["last_run"], read_sketch_file(self.source)["last_run"])
        histories = sorted(history_dir_for(self.output).iterdir())
        self.assertEqual(
            [p.name for p in histories], sorted(p.name for p in self.history.iterdir())
        )
        for path in histories:
            raw = read_sketch_file(path)
            old = read_sketch_file(self.history / path.name)
            self.assertEqual(raw["run"]["id"], old["run"]["id"])
            self.assertEqual(raw["run"]["events"], old["run"]["events"])
            self.assertEqual(raw["run"]["sketch"], str(self.output))
            self.assertEqual(raw["profile_id"], derived["profile_id"])
        self.assertEqual(
            self.command("analyze", self.output, "-o", self.root / "report.html")[0], 0
        )
        # Replaying seq=2 is dropped; a new event still merges under the target profile.
        self.assertEqual(
            self.command("merge", "-p", self.new, "-s", self.output, self.events)[0], 0
        )
        raw = read_sketch_file(self.output)
        self.assertEqual(next(iter(raw["skits"].values()))["meta"]["count"], 2)
        self.assertIn("derivation", raw)
        self.events.write_text('{"seq":3,"kind":"a","size":8}\n')
        self.assertEqual(
            self.command("merge", "-p", self.new, "-s", self.output, self.events)[0], 0
        )
        self.assertEqual(
            next(iter(read_sketch_file(self.output)["skits"].values()))["meta"]["count"], 3
        )

    def test_bad_history_aborts_before_output_and_reports_filename(self):
        bad = sorted(self.history.iterdir())[-1]
        bad.write_text("bad history")
        status, text = self.derive()
        self.assertEqual(status, 2)
        self.assertIn(bad.name, text)
        self.assertFalse(self.output.exists())
        self.assertFalse(history_dir_for(self.output).exists())

    def test_unprovable_history_even_if_main_is_unambiguous_is_rejected(self):
        self.new.write_text(
            self.old.read_text().replace(
                "path: $.extra}", "path: $.extra, modifier: {name: GLOB, pattern: '*'}}"
            )
        )
        path = sorted(self.history.iterdir())[0]
        raw = read_sketch_file(path)
        from sketchtastic.sketch import skit_id

        skit = next(iter(raw["skits"].values()))
        skit["tokens"]["extra"] = ["a", "b"]
        raw["skits"] = {skit_id(skit["tokens"]): skit}
        with path.open("w") as stream:
            _yaml.dump(raw, stream)
        status, text = self.derive()
        self.assertEqual(status, 2, text)
        self.assertIn("array", text)
        self.assertFalse(self.output.exists())

    def test_existing_outputs_aliases_and_symlinks_are_refused(self):
        self.output.write_text("keep")
        status, text = self.derive()
        self.assertEqual(status, 2)
        self.assertNotIn("--force", text)
        self.assertEqual(self.output.read_text(), "keep")
        self.output.unlink()
        self.output.symlink_to(self.root / "missing")
        self.assertEqual(self.derive()[0], 2)
        self.output.unlink()
        history_dir_for(self.output).mkdir()
        self.assertEqual(self.derive()[0], 2)
        history_dir_for(self.output).rmdir()
        self.output = self.root / "old.yml"  # distinct file, same companion history
        self.assertEqual(self.derive()[0], 2)
        self.output = self.source
        self.assertEqual(self.derive()[0], 2)
        self.assert_sources_unchanged()

    def test_publish_failure_rolls_back_only_our_history_and_keeps_competing_output(self):
        real_link = os.link

        def race(src, dst, **kwargs):
            if Path(dst) == self.output:
                self.output.write_text("competing writer")
            return real_link(src, dst, **kwargs)

        with patch("os.link", race):
            status, text = self.derive()
        self.assertEqual(status, 2, text)
        self.assertEqual(self.output.read_text(), "competing writer")
        self.assertFalse(history_dir_for(self.output).exists())
        self.assert_sources_unchanged()

    def test_staging_failure_leaves_no_final_outputs(self):
        with patch("sketchtastic.sketch.Sketch.save", side_effect=OSError("disk full")):
            self.assertEqual(self.derive()[0], 2)
        self.assertFalse(self.output.exists())
        self.assertFalse(history_dir_for(self.output).exists())
        self.assert_sources_unchanged()

    def test_interruption_after_main_link_removes_only_our_published_pair(self):
        real_link = os.link

        def interrupted(src, dst, **kwargs):
            real_link(src, dst, **kwargs)
            if Path(dst) == self.output:
                raise KeyboardInterrupt

        with patch("os.link", interrupted):
            self.assertEqual(self.derive()[0], 130)
        self.assertFalse(self.output.exists())
        self.assertFalse(history_dir_for(self.output).exists())
        self.assert_sources_unchanged()

    def test_no_history_is_supported_and_does_not_invent_runs(self):
        for path in self.history.iterdir():
            path.unlink()
        self.history.rmdir()
        status, text = self.derive()
        self.assertEqual(status, 0, text)
        self.assertIn("0 history", text)
        self.assertFalse(history_dir_for(self.output).exists())

    def test_symlink_history_is_rejected_instead_of_silently_skipped(self):
        (self.history / "261124-9999.yaml").symlink_to(self.source)
        status, text = self.derive()
        self.assertEqual(status, 2, text)
        self.assertFalse(self.output.exists())
