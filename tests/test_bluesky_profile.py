"""Native profile fields classify unchanged original posts, including absent arrays."""

import copy
import unittest
from pathlib import Path

from sketchtastic import load_profile

PREFIXES = ("images", "gallery", "media_images", "media_gallery")


def sample(n=None, *, gallery=False, quote=False):
    embed = {"$type": "app.bsky.embed.gallery" if gallery else "app.bsky.embed.images"}
    if n is not None:
        items = [{"image": {"mimeType": "image/png"}} for _ in range(n)]
        if gallery:
            for item in items:
                item["$type"] = "app.bsky.embed.gallery#image"
        embed["items" if gallery else "images"] = items
    if quote:
        embed = {"$type": "app.bsky.embed.recordWithMedia", "media": embed}
    return {"$type": "app.bsky.feed.post", "embed": embed}


class PostProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = load_profile(
            str(Path(__file__).resolve().parents[1] / "examples/bluesky/profile.yaml")
        )

    def states(self, post, prefix):
        tokens = self.profile.tokens(post)
        return tuple(tokens[f"{prefix}_{suffix}"] for suffix in ("present", "any", "multiple"))

    def test_absent_zero_one_many_for_direct_gallery_and_quoted_media(self):
        for gallery in (False, True):
            for quote in (False, True):
                prefix = ("media_" if quote else "") + ("gallery" if gallery else "images")
                for n in (None, 0, 1, 2, 4, 11):
                    with self.subTest(gallery=gallery, quote=quote, n=n):
                        post = sample(n, gallery=gallery, quote=quote)
                        original = copy.deepcopy(post)
                        expected = (
                            "TRUE" if n is not None else "FALSE",
                            "TRUE" if n else "FALSE",
                            "TRUE" if n is not None and n > 1 else "FALSE",
                        )
                        self.assertEqual(self.states(post, prefix), expected)
                        for other in PREFIXES:
                            if other != prefix:
                                self.assertEqual(self.states(post, other), ("FALSE",) * 3)
                        self.assertEqual(post, original)

    def test_mixed_gallery_counts_only_typed_image_members(self):
        for quote in (False, True):
            post = sample(0, gallery=True, quote=quote)
            gallery = post["embed"]["media"] if quote else post["embed"]
            prefix = "media_gallery" if quote else "gallery"
            gallery["items"] = [
                {"$type": "app.bsky.embed.gallery#video", "image": {}},
                {"$type": "unknown", "image": {}},
            ]
            self.assertEqual(self.states(post, prefix), ("TRUE", "FALSE", "FALSE"))
            gallery["items"].append({"$type": "app.bsky.embed.gallery#image", "image": {}})
            self.assertEqual(self.states(post, prefix), ("TRUE", "TRUE", "FALSE"))
            gallery["items"].append({"$type": "app.bsky.embed.gallery#image", "image": {}})
            self.assertEqual(self.states(post, prefix), ("TRUE", "TRUE", "TRUE"))

    def test_no_embed_and_link_thumbnail_do_not_become_image_arrays(self):
        for post in (
            {"$type": "app.bsky.feed.post", "text": "no media"},
            {"embed": {"$type": "app.bsky.embed.external", "external": {"thumb": {}}}},
            {"embed": {"$type": "app.bsky.embed.record", "record": {"uri": "at://quote"}}},
        ):
            for prefix in PREFIXES:
                self.assertEqual(self.states(post, prefix), ("FALSE",) * 3)

    def test_presence_means_member_exists_not_schema_validity(self):
        post = sample()
        post["embed"]["images"] = None
        self.assertEqual(self.states(post, "images"), ("TRUE", "FALSE", "FALSE"))

    def test_unrecognized_outer_embed_does_not_count_media_images(self):
        for gallery in (False, True):
            post = sample(2, gallery=gallery, quote=True)
            post["embed"]["$type"] = "app.bsky.embed.external"
            prefix = "media_gallery" if gallery else "media_images"
            self.assertEqual(self.states(post, prefix), ("TRUE", "FALSE", "FALSE"))

    def test_arrays_are_sets_and_source_text_is_not_identity(self):
        a = {
            "text": "one",
            "langs": ["en", "fr", "en"],
            "facets": [{"features": [{"$type": "link"}, {"$type": "tag"}]}],
        }
        b = {
            "text": "another",
            "langs": ["fr", "en"],
            "facets": [{"features": [{"$type": "tag"}, {"$type": "link"}]}],
        }
        self.assertEqual(self.profile.tokens(a), self.profile.tokens(b))
        self.assertEqual(self.profile.tokens(a)["languages"], "en,fr")


if __name__ == "__main__":
    unittest.main()
