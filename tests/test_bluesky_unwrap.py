"""Streaming unwrap contracts: one capture line in, at most one unchanged post out."""

import io
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from examples.bluesky import input as bluesky_input
from examples.bluesky.input import BoundedSeen
from examples.bluesky.unwrap import main, unwrap
from sketchtastic import cli


def post(text="hello", **extra):
    return {"$type": "app.bsky.feed.post", "text": text, **extra}


def event(record, key="a", operation="create", v2=False, did="did:plc:test"):
    commit = {"collection": "app.bsky.feed.post", "operation": operation, "rkey": key}
    if record is not None:
        commit["record"] = record
    if v2:
        return {"payload": {"$type": "jetstream#commit", "did": did, **commit}}
    return {"kind": "commit", "did": did, "commit": commit}


def lines(*objects):
    return io.BytesIO("".join(json.dumps(o) + "\n" for o in objects).encode())


class UnwrapTests(unittest.TestCase):
    def run_unwrap(self, source):
        out, counts = io.StringIO(), Counter()
        unwrap(source, out, counts)
        return [json.loads(line) for line in out.getvalue().splitlines()], counts

    def test_posts_pass_unchanged_and_non_creates_are_counted(self):
        plain = post(langs=["en"])
        images = post(langs=["fr"], embed={"images": [{"alt": "a"}, {"alt": "b"}]})
        records, counts = self.run_unwrap(
            lines(
                event(plain),
                event(plain),  # replay after reconnect
                event(images, "b", v2=True),
                event(None, "c", operation="delete"),
                {"commit": {"collection": "app.bsky.feed.like"}},
                post("bare"),
            )
        )
        self.assertEqual(records, [plain, images, post("bare")])
        self.assertEqual(counts["posts"], 3)
        self.assertEqual(counts["duplicates"], 1)
        self.assertEqual(counts["ignored_operations"], 1)
        self.assertEqual(counts["ignored_events"], 1)

    def test_each_post_is_flushed_before_the_next_line_is_read(self):
        seen_before_second_read = []

        class Sink(io.StringIO):
            def flush(self):
                seen_before_second_read.append(self.getvalue())

        source = lines(post("one"), post("two"))
        unwrap(source, Sink(), Counter())
        self.assertEqual(json.loads(seen_before_second_read[0])["text"], "one")

    def test_dedup_window_is_bounded(self):
        seen = BoundedSeen(maxlen=2)
        for item in ["a", "b", "c"]:
            seen.add(item)
        self.assertNotIn("a", seen)
        self.assertIn("b", seen)
        self.assertIn("c", seen)

    def test_malformed_line_names_its_number(self):
        for raw in (
            "{bad",
            "[]",
            '{"payload": []}',
            '{"commit": []}',
            '{"a": NaN}',
            '{"commit":{"collection":"app.bsky.feed.post","operation":"create","record":{}}}',
        ):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "line 2"):
                unwrap(io.BytesIO(("\n" + raw + "\n").encode()), io.StringIO(), Counter())

    def test_line_bound(self):
        with patch("examples.bluesky.unwrap.MAX_LINE_BYTES", 32):
            with self.assertRaisesRegex(ValueError, "line 1.*limit"):
                unwrap(io.BytesIO(b" " * 40), io.StringIO(), Counter())
        self.assertEqual(bluesky_input.MAX_LINE_BYTES, 4 * 1024 * 1024)

    def test_unicode_post_values_survive(self):
        record = post("\x1b[31m café")
        records, _ = self.run_unwrap(lines(event(record)))
        self.assertEqual(records, [record])

    def test_main_reports_bad_input_with_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "bad.jsonl"
            source.write_text("{bad\n")
            err = io.StringIO()
            with patch("sys.stderr", err), patch("sys.stdout", io.StringIO()):
                self.assertEqual(main([str(source)]), 2)
        self.assertIn("line 1", err.getvalue())

    def test_unwrapped_stream_folds_with_core_merge(self):
        profile = Path(__file__).resolve().parents[1] / "examples/bluesky/profile.yaml"
        out = io.StringIO()
        unwrap(lines(event(post("x")), event(post("x")), event(post("y"), "b")), out, Counter())
        with tempfile.TemporaryDirectory() as tmp:
            events = Path(tmp) / "posts.jsonl"
            events.write_text(out.getvalue())
            sketch = Path(tmp) / "posts.sketch.yaml"
            with patch("sys.stderr", io.StringIO()):
                code = cli.main(["merge", "-p", str(profile), "-s", str(sketch), str(events)])
            self.assertEqual(code, 0)
            self.assertIn("count: 2", sketch.read_text())


if __name__ == "__main__":
    unittest.main()
