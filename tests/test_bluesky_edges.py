"""Bounded input, no-clobber and safe terminal preparation contracts."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from examples.bluesky.demo import build, main


class PreparationBoundaries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile = self.root / "profile.yaml"
        self.profile.write_text("version: 0\nfields:\n  - {key: text, path: '$.text'}\n")
        self.source = self.root / "input.jsonl"
        self.output = self.root / "result"

    def test_malformed_input_never_publishes(self):
        for raw in (
            "{bad",
            "[]",
            '{"payload": []}',
            '{"commit": []}',
            '{"a": NaN}',
            '{"commit":{"collection":"app.bsky.feed.post","operation":"create","record":{}}}',
        ):
            with self.subTest(raw=raw):
                self.source.write_text("\n" + raw + "\n")
                with self.assertRaisesRegex(ValueError, "line 2"):
                    build(self.source, self.output, self.profile)
                self.assertFalse(self.output.exists())

    def test_line_bound(self):
        self.source.write_text(" " * 40)
        with patch("examples.bluesky.input.MAX_LINE_BYTES", 32):
            with self.assertRaisesRegex(ValueError, "line 1.*limit"):
                build(self.source, self.output, self.profile)
        self.assertFalse(self.output.exists())

    def test_existing_and_dangling_paths_are_never_clobbered(self):
        self.source.write_text("")
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            build(self.source, self.output, self.profile)
        self.output.rmdir()
        self.output.symlink_to(self.root / "missing")
        with self.assertRaises(FileExistsError):
            build(self.source, self.output, self.profile)
        self.assertTrue(self.output.is_symlink())

    def test_cli_preserves_unicode_post_but_escapes_output(self):
        record = {"$type": "app.bsky.feed.post", "text": "\x1b[31m caf\u00e9"}
        self.source.write_text(json.dumps(record) + "\n")
        self.output = self.root / "out\x1b\u00e9"
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(
                main(
                    [
                        "prepare",
                        str(self.source),
                        "--output",
                        str(self.output),
                        "--profile",
                        str(self.profile),
                    ]
                ),
                0,
            )
        self.assertTrue(stream.getvalue().isascii())
        self.assertNotIn("\x1b", stream.getvalue())
        self.assertEqual(json.loads((self.output / "representatives.jsonl").read_text()), record)
