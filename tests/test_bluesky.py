"""Original-post preparation contracts; identity belongs to the profile."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from examples.bluesky.demo import build
from sketchtastic import Sketch, load_profile


def post(text="hello", **extra):
    return {"$type": "app.bsky.feed.post", "text": text, **extra}


def event(record, key="a", operation="create", v2=False):
    commit = {
        "collection": "app.bsky.feed.post",
        "operation": operation,
        "rkey": key,
        "record": record,
    }
    if v2:
        return {
            "payload": {
                "$type": "network.bsky.jetstream.subscribeEvents#commit",
                "did": "did:plc:test",
                **commit,
            }
        }
    return {"kind": "commit", "did": "did:plc:test", "commit": commit}


class PostPreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile = self.root / "custom.yaml"
        self.profile.write_text(
            "# exact saved profile\nversion: 0\nfields:\n  - {key: langs, path: '$.langs[*]'}\n"
        )
        self.source = self.root / "input.jsonl"
        self.output = self.root / "result"

    def write(self, records):
        self.source.write_text("".join(json.dumps(r) + "\n" for r in records))

    def test_posts_are_unchanged_and_zero_image_posts_remain(self):
        plain = post(langs=["en"])
        images = post(langs=["fr"], embed={"images": [{"alt": "a"}, {"alt": "b"}]})
        self.write(
            [
                event(plain),
                event(plain),
                event(images, "b", v2=True),
                event(plain, "c", operation="update"),
                post(langs=["en"]),
            ]
        )
        summary = build(self.source, self.output, self.profile)
        self.assertEqual(summary["posts"], 3)
        self.assertEqual(summary["skits"], 2)
        self.assertEqual(summary["counts"]["duplicates"], 1)
        self.assertEqual(summary["counts"]["ignored_operations"], 1)
        self.assertEqual(
            summary["source_sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest()
        )
        self.assertEqual((self.output / "profile.yaml").read_bytes(), self.profile.read_bytes())
        reps = [
            json.loads(s) for s in (self.output / "representatives.jsonl").read_text().splitlines()
        ]
        self.assertEqual(reps, [plain, images])
        profile = load_profile(str(self.output / "profile.yaml"))
        sketch = Sketch(profile.aggregates, profile.profile_id)
        sketch.load(str(self.output / "posts.sketch.yaml"))
        reduced = Sketch(profile.aggregates, profile.profile_id)
        for record in reps:
            reduced.upsert(profile.tokens(record), record)
        self.assertEqual(set(sketch), set(reduced))
        samples = json.loads((self.output / "samples.json").read_text())
        for index, key in enumerate(sketch):
            self.assertEqual(samples[key]["representative_line"], index + 1)
            self.assertEqual(samples[key]["source_line"], [1, 3][index])
            self.assertEqual(samples[key]["source"], str(self.source))

    def test_native_array_tokens_and_custom_profile_define_kinds(self):
        self.write([post(langs=["fr", "en"]), post(langs=["en", "fr"]), post(langs=["de"])])
        summary = build(self.source, self.output, self.profile)
        self.assertEqual(summary["skits"], 2)
        self.assertEqual(summary["posts"], 3)

    def test_empty_input_and_capture_provenance(self):
        self.write([])
        capture = {"started": "then", "finished": "now", "received": 0}
        self.source.with_suffix(".jsonl.meta.json").write_text(json.dumps(capture))
        summary = build(self.source, self.output, self.profile)
        self.assertEqual((summary["posts"], summary["skits"]), (0, 0))
        self.assertEqual(summary["capture"], capture)
        self.assertEqual((self.output / "representatives.jsonl").read_text(), "")
        self.assertEqual(json.loads((self.output / "samples.json").read_text()), {})
