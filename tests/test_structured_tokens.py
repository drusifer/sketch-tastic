"""Structured tokens retain missing/null/set distinctions without legacy guessing."""

import tempfile
import unittest
from pathlib import Path

from sketchtastic.model import Field, tokens
from sketchtastic.sketch import Sketch, SketchError, load_ranked_skits, skit_id


class StructuredTokenTests(unittest.TestCase):
    def test_missing_null_literal_null_and_empty_array_are_distinct(self):
        fields = [Field("tags", "$.tags")]
        expected = [{}, {"tags": None}, {"tags": "NULL"}, {"tags": []}]
        actual = [
            tokens(event, fields) for event in ({}, {"tags": None}, {"tags": "NULL"}, {"tags": []})
        ]
        self.assertEqual(actual, expected)
        self.assertEqual(len({skit_id(value) for value in actual}), 4)

    def test_direct_arrays_preserve_members_and_canonicalize_order_and_duplicates(self):
        fields = [Field("tags", "$.tags")]
        a = tokens({"tags": ["xyz", None, "xyz", "NULL", "a,b"]}, fields)
        b = tokens({"tags": ["a,b", "NULL", None, "xyz"]}, fields)
        self.assertEqual(a, b)
        self.assertIsInstance(a["tags"], list)
        self.assertEqual(len(a["tags"]), 4)
        self.assertIn(None, a["tags"])
        self.assertIn("NULL", a["tags"])
        self.assertIn("a,b", a["tags"])
        self.assertNotEqual(skit_id(a), skit_id({"tags": "NULL,a,b,xyz"}))

    def test_multimatch_sets_are_arrays_and_duplicate_singletons_stay_scalar(self):
        fields = [Field("tags", "$.tags[*]")]
        self.assertEqual(tokens({"tags": ["a", "a"]}, fields), {"tags": "a"})
        self.assertEqual(tokens({"tags": ["a", None]}, fields), {"tags": ["a", None]})
        self.assertEqual(tokens({"tags": []}, fields), {})

    def test_presence_and_nullness_still_emit_for_missing_and_explicit_null(self):
        fields = [Field("present", "$.tags", "IS_PRESENT"), Field("null", "$.tags", "IS_NULL")]
        for record, present, null in (
            ({}, "FALSE", "FALSE"),
            ({"tags": None}, "TRUE", "TRUE"),
            ({"tags": []}, "TRUE", "FALSE"),
        ):
            self.assertEqual(tokens(record, fields), {"present": present, "null": null})

    def test_value_modifiers_keep_missing_and_null_distinct(self):
        for extra in (
            {},
            {"modifier": {"name": "REGSUB", "pattern": "x", "replace": "y"}},
            {"modifier": {"name": "TRUNC", "unit": "day"}, "type": "DATE"},
        ):
            with self.subTest(extra=extra):
                fields = [Field("value", "$.value", **extra)]
                self.assertEqual(tokens({}, fields), {})
                self.assertEqual(tokens({"value": None}, fields), {"value": None})

    def test_invalid_typed_matches_are_omitted_without_conflating_explicit_null(self):
        fields = [Field("times", "$.times[*]", type="DATE")]
        self.assertEqual(tokens({"times": ["bad"]}, fields), {})
        self.assertEqual(tokens({"times": ["bad", None]}, fields), {"times": None})
        self.assertEqual(tokens({"times": ["bad", "2026-11-24"]}, fields), {"times": "2026-11-24"})

    def test_omitted_keys_do_not_hash_like_another_present_field(self):
        self.assertNotEqual(skit_id({"a": "x"}), skit_id({"b": "x"}))
        self.assertNotEqual(skit_id({}), skit_id({"a": None}))

    def test_stored_token_arrays_do_not_alias_input(self):
        values = {"tags": ["a", None]}
        sketch = Sketch()
        key = sketch.upsert(values, {})
        values["tags"].append("later")
        self.assertEqual(sketch.get(key).tokens, {"tags": ["a", None]})

    def test_nested_arrays_are_canonical_structures(self):
        fields = [Field("tags", "$.tags")]
        self.assertEqual(tokens({"tags": [["b", "a"], ["a", "b"]]}, fields), {"tags": [["a", "b"]]})

    def test_new_format_and_derivation_metadata_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sketch.yaml"
            sketch = Sketch()
            sketch.derivation = {"source": "original.yaml"}
            sketch.upsert({"tags": ["a", None]}, {"tags": ["a", None]})
            sketch.upsert({}, {})
            sketch.save(str(path))
            header, rows = load_ranked_skits(path)
            self.assertEqual(header["version"], 1)
            self.assertEqual(len(rows), 2)
            loaded = Sketch()
            loaded.load(str(path))
            self.assertEqual(loaded.derivation, sketch.derivation)
            loaded.save(str(path))
            self.assertIn("derivation:", path.read_text())

    def test_legacy_version_refused_with_recapture_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.yaml"
            path.write_text("version: 0\nskits: {}\n")
            with self.assertRaisesRegex(SketchError, "recapture|rebuild"):
                Sketch().load(str(path))

    def test_regular_load_refuses_noncanonical_tokens_and_mismatched_identity(self):
        for token, identity in (
            (["b", "a"], None),
            (["a", "a"], None),
            ({"bad": 1}, None),
            ("a", "invalid-id"),
        ):
            with self.subTest(token=token, identity=identity):
                values = {"tags": token}
                raw = {
                    "version": 1,
                    "skits": {
                        identity or skit_id(values): {
                            "tokens": values,
                            "meta": {"count": 1},
                        }
                    },
                }
                with self.assertRaises(SketchError):
                    Sketch().load_data(raw, "malformed.yaml")


if __name__ == "__main__":
    unittest.main()
