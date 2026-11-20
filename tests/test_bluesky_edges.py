"""Independent boundary acceptance tests for the ASCII image demo."""

import copy
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from examples.bluesky.demo import build, report
from examples.bluesky.model import image_rows


def attachment(mime="image/jpeg", width=4, height=3):
    return {
        "image": {"mimeType": mime, "size": 25},
        "alt": "photo",
        "aspectRatio": {"width": width, "height": height},
    }


def post(items):
    return {
        "$type": "app.bsky.feed.post",
        "text": "original",
        "embed": {"$type": "app.bsky.embed.images", "images": items},
    }


class ModelBoundaryTests(unittest.TestCase):
    def test_attachment_count_bin_boundaries_keep_exact_count_and_index(self):
        for count, category in [
            (1, "1"),
            (2, "2"),
            (3, "3"),
            (4, "4"),
            (5, "5-10"),
            (10, "5-10"),
            (11, "11+"),
            (20, "11+"),
        ]:
            with self.subTest(count=count):
                rows = image_rows(post([attachment() for _ in range(count)]))
                self.assertEqual(len(rows), count)
                self.assertEqual({r["attachment_count"] for r in rows}, {category})
                self.assertEqual({r["image_count"] for r in rows}, {count})
                self.assertEqual([r["image_index"] for r in rows], list(range(count)))
        self.assertEqual(image_rows(post([])), [])

    def test_gallery_exclusions_preserve_source_positions_and_count_only_images(self):
        first, last = attachment(), attachment("image/png")
        for item in (first, last):
            item["$type"] = "app.bsky.embed.gallery#image"
        record = {
            "$type": "app.bsky.feed.post",
            "embed": {
                "$type": "app.bsky.embed.gallery",
                "items": [first, {"$type": "app.bsky.embed.gallery#video", "image": {}}, last],
            },
        }
        original = copy.deepcopy(record)
        counts = Counter()
        rows = image_rows(record, counts)
        self.assertEqual([r["image_index"] for r in rows], [0, 2])
        self.assertEqual([r["attachment_count"] for r in rows], ["2", "2"])
        self.assertEqual(counts["excluded_gallery_items"], 1)
        self.assertEqual(record, original)
        self.assertTrue(all(r["source"] == original for r in rows))

    def test_dimension_invalid_values_are_not_coerced(self):
        for width, height in [(True, 1), (1, False), (1.0, 1), (-1, 1), (1, 0), (None, 1)]:
            with self.subTest(width=width, height=height):
                self.assertEqual(
                    image_rows(post([attachment(width=width, height=height)]))[0]["orientation"],
                    "invalid",
                )
        for mime, expected in [
            ("image/gif", "gif"),
            ("image/avif", "other"),
            ("video/mp4", "invalid"),
            ("image/", "invalid"),
            (False, "invalid"),
        ]:
            self.assertEqual(image_rows(post([attachment(mime)]))[0]["mime"], expected)
        record = post([{"image": {}, "alt": "\t\n "}])
        record["reply"] = None
        row = image_rows(record)[0]
        self.assertEqual(
            (row["reply"], row["mime"], row["orientation"], row["alt"]),
            ("invalid", "missing", "missing", "empty"),
        )


class PipelineBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def prepare(self, records, name="input.jsonl"):
        source = self.root / name
        source.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        output = self.root / "result"
        return build(source, output), output

    def test_and_filters_use_population_weights_and_matching_absence_sets(self):
        original = post([attachment()])
        reply = copy.deepcopy(original)
        reply["reply"] = {"parent": {"uri": "at://parent"}}
        portrait_reply = post([attachment("image/png", 1, 2)])
        portrait_reply["reply"] = reply["reply"]
        summary, output = self.prepare([original] * 5 + [reply] * 3 + [portrait_reply] * 2)
        self.assertEqual((summary["images"], summary["skits"]), (10, 3))
        text = report(output, "mime", ["reply=reply", "orientation=landscape"])
        self.assertIn("Images: 3 matched / 10 total", text)
        self.assertIn("Skits: 1 matched / 3 total", text)
        self.assertRegex(text, r"jpeg\s+3\s+100\.0%")
        self.assertRegex(text, r"png\s+0\s+0\.0%")
        self.assertIn("mime: jpeg\n  not observed: png, webp, gif, other, missing, invalid", text)
        self.assertIn("reply: reply\n  not observed: original, invalid", text)
        empty = report(output, "mime", ["reply=reply", "reply=original"])
        self.assertIn("Images: 0 matched / 10 total", empty)
        self.assertIn("No matching images.", empty)

    def test_original_event_and_unicode_retained_but_terminal_output_is_ascii(self):
        record = post([attachment()])
        record["text"] = "\x1b[31m caf\u00e9\ntext"
        event = {
            "did": "did:plc:test",
            "commit": {
                "collection": "app.bsky.feed.post",
                "operation": "create",
                "rkey": "key",
                "record": record,
            },
        }
        original = copy.deepcopy(event)
        _, output = self.prepare([event], "unsafe\x1b[31m\u00e9.jsonl")
        representatives = [
            json.loads(line) for line in (output / "representatives.jsonl").read_text().splitlines()
        ]
        self.assertEqual(representatives[0]["event"], original)
        self.assertEqual(representatives[0]["source"], original["commit"]["record"])
        self.assertEqual(event, original)
        rendered = report(output)
        self.assertTrue(rendered.isascii())
        self.assertNotIn("\x1b", rendered)
        self.assertIn(r"\u001b[31m\u00e9", rendered)

    def test_malformed_structures_and_non_json_numbers_publish_nothing(self):
        cases = [
            {"$type": "app.bsky.feed.post", "embed": []},
            post([{"image": None}]),
            post([None]),
            {"payload": []},
            {"commit": {"collection": "app.bsky.feed.post", "operation": "create", "record": {}}},
            ["not an object"],
        ]
        source = self.root / "input.jsonl"
        output = self.root / "result"
        for invalid in cases:
            with self.subTest(invalid=invalid):
                source.write_text(
                    json.dumps(post([attachment()])) + "\n" + json.dumps(invalid) + "\n"
                )
                with self.assertRaisesRegex(ValueError, "line 2"):
                    build(source, output)
                self.assertFalse(output.exists())
        source.write_text('{"value": NaN}\n')
        with self.assertRaisesRegex(ValueError, "non-JSON number"):
            build(source, output)
        self.assertFalse(output.exists())

    def test_saved_enum_spoof_is_rejected(self):
        _, output = self.prepare([post([attachment()])])
        path = output / "summary.json"
        summary = json.loads(path.read_text())
        summary["domains"]["mime"].append("\x1b[31m")
        path.write_text(json.dumps(summary))
        with self.assertRaisesRegex(ValueError, "enum domains"):
            report(output)

    def test_saved_profile_missing_report_dimension_is_rejected(self):
        _, output = self.prepare([post([attachment()])])
        path = output / "profile.yaml"
        path.write_text(path.read_text().replace("  - {key: alt, path: $.alt}\n", ""))
        with self.assertRaisesRegex(ValueError, "dimensions disagree"):
            report(output)
