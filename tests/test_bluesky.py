"""Contracts for image counting and representative data preservation."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from examples.bluesky.demo import build, report
from examples.bluesky.model import DOMAINS, image_rows
from sketchtastic import Sketch, load_profile

PROFILE = Path(__file__).resolve().parents[1] / "examples/bluesky/profile.yaml"


def post(images=None, *, quote=False, gallery=False, reply=False):
    if images is None:
        images = [
            {
                "image": {"mimeType": "image/jpeg", "size": 100},
                "alt": "a cat",
                "aspectRatio": {"width": 4, "height": 3},
            }
        ]
    embed = {"$type": "app.bsky.embed.gallery" if gallery else "app.bsky.embed.images"}
    embed["items" if gallery else "images"] = images
    if gallery:
        for item in images:
            item["$type"] = "app.bsky.embed.gallery#image"
    if quote:
        embed = {
            "$type": "app.bsky.embed.recordWithMedia",
            "media": embed,
            "record": {"record": {"uri": "at://quoted/post"}},
        }
    result = {"$type": "app.bsky.feed.post", "text": "hello", "embed": embed}
    if reply:
        result["reply"] = {"parent": {"uri": "at://parent/post"}}
    return result


def event(record, key="one", operation="create"):
    return {
        "did": "did:plc:test",
        "kind": "commit",
        "time_us": 123,
        "commit": {
            "operation": operation,
            "collection": "app.bsky.feed.post",
            "rkey": key,
            "record": record,
        },
    }


class ImageModelTests(unittest.TestCase):
    def test_own_images_in_direct_quote_and_gallery(self):
        for quote, gallery, expected in [
            (False, False, "images"),
            (True, False, "quote_images"),
            (False, True, "gallery"),
            (True, True, "quote_gallery"),
        ]:
            rows = image_rows(post(quote=quote, gallery=gallery))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["embed_kind"], expected)
            self.assertEqual(rows[0]["orientation"], "landscape")

    def test_multiple_images_keep_correlated_properties(self):
        p = post(
            [
                {
                    "image": {"mimeType": "image/png"},
                    "alt": "",
                    "aspectRatio": {"width": 1, "height": 2},
                },
                {
                    "image": {"mimeType": "image/webp"},
                    "alt": "x",
                    "aspectRatio": {"width": 2, "height": 1},
                },
            ]
        )
        rows = image_rows(p)
        self.assertEqual(
            [(r["mime"], r["orientation"], r["alt"]) for r in rows],
            [("png", "portrait", "empty"), ("webp", "landscape", "present")],
        )
        self.assertTrue(all(r["attachment_count"] == "2" for r in rows))

    def test_missing_invalid_and_enum_partitions(self):
        images = [
            {"image": {}},
            {"image": {"mimeType": 1}, "alt": None, "aspectRatio": {"width": 0, "height": 2}},
            {
                "image": {"mimeType": "image/avif"},
                "alt": "  ",
                "aspectRatio": {"width": 1, "height": 1},
            },
        ]
        rows = image_rows(post(images))
        self.assertEqual(
            [(r["mime"], r["orientation"], r["alt"]) for r in rows],
            [
                ("missing", "missing", "missing"),
                ("invalid", "invalid", "invalid"),
                ("other", "square", "empty"),
            ],
        )
        for row in rows:
            for field, values in DOMAINS.items():
                self.assertIn(row[field], values)

    def test_no_images_from_quotes_video_or_link_thumbnails(self):
        for kind in ["record", "video", "external"]:
            p = {
                "$type": "app.bsky.feed.post",
                "embed": {"$type": f"app.bsky.embed.{kind}", "thumbnail": {}, "record": post()},
            }
            self.assertEqual(image_rows(p), [])

    def test_each_dimension_changes_identity_but_source_text_does_not(self):
        profile = load_profile(str(PROFILE))
        self.assertEqual({f.key for f in profile.fields}, set(DOMAINS))
        row = image_rows(post())[0]
        sketch = Sketch(profile.aggregates, profile.profile_id)
        first = sketch.upsert(profile.tokens(row), row)
        variant = copy.deepcopy(row)
        variant["source"]["text"] = "another post"
        self.assertEqual(first, sketch.upsert(profile.tokens(variant), variant))
        for field, values in DOMAINS.items():
            variant = copy.deepcopy(row)
            variant[field] = next(v for v in values if v != row[field])
            self.assertNotEqual(first, sketch.upsert(profile.tokens(variant), variant))


class DemoPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, records):
        path = self.root / "input.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in records))
        return path

    def test_population_counts_dedup_v1_v2_and_representatives(self):
        records = [
            event(post(), "a"),
            event(post(), "a"),
            event(post(), "b"),
            event(post(reply=True), "c"),
            event(post(), "d", "update"),
            {
                "payload": {
                    "$type": "network.bsky.jetstream.subscribeEvents#commit",
                    "did": "did:plc:test",
                    "collection": "app.bsky.feed.post",
                    "operation": "create",
                    "rkey": "e",
                    "record": post(),
                }
            },
        ]
        out = self.root / "out"
        summary = build(self.write(records), out)
        self.assertEqual(summary["images"], 4)
        self.assertEqual(summary["skits"], 2)
        self.assertEqual(summary["counts"]["duplicates"], 1)
        self.assertEqual(summary["counts"]["ignored_operations"], 1)
        self.assertTrue(summary["representatives_verified"])
        reps = [
            json.loads(line) for line in (out / "representatives.jsonl").read_text().splitlines()
        ]
        self.assertEqual(len(reps), 2)
        self.assertTrue(all("source" in r for r in reps))
        text = report(out, "reply", [])
        self.assertIn("original", text)
        self.assertIn("Images: 4", text)
        self.assertIn("Images: 1", report(out, "mime", ["reply=reply"]))
        self.assertIn("No matching images", report(out, "mime", ["mime=gif"]))
        with self.assertRaisesRegex(ValueError, "Unknown"):
            report(out, "nope", [])

    def test_malformed_input_does_not_publish_output(self):
        path = self.write([post()])
        with path.open("a") as stream:
            stream.write("{bad\n")
        out = self.root / "out"
        with self.assertRaisesRegex(ValueError, "line 2"):
            build(path, out)
        self.assertFalse(out.exists())

    def test_empty_and_existing_output(self):
        path = self.write([])
        out = self.root / "out"
        summary = build(path, out)
        self.assertEqual(summary["images"], 0)
        self.assertIn("No matching images", report(out, "mime", []))
        with self.assertRaises(FileExistsError):
            build(path, out)
