"""Derivation must equal folding the same population under a coarser profile."""

import copy
import tempfile
import unittest
from pathlib import Path

from sketchtastic.derive import derive_data
from sketchtastic.profile import parse_profile
from sketchtastic.sketch import Sketch, read_sketch_file, skit_id


def profile(fields, **extra):
    return parse_profile({"fields": fields, **extra})


def field(key, path=None, **extra):
    return {"key": key, "path": path or f"$.{key}", **extra}


class DeriveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def raw(self, spec, events):
        sketch = Sketch(spec.aggregates, spec.profile_id)
        for event in events:
            sketch.upsert(spec.tokens(event), event, "261124-0001")
        sketch.last_run = "261124-0001"
        path = self.root / "source.yaml"
        sketch.save(str(path))
        return read_sketch_file(path)

    def derive(self, raw, source, target):
        return derive_data(raw, source, target, source_name="source.yaml", output_name="v2.yaml")

    def test_drop_reorder_rename_and_merge_preserve_population_statistics(self):
        aggregates = [
            {
                "key": "size",
                "path": "$.size",
                "fn": ["SUM", "COUNT", "AVG", "MIN", "MAX", "HISTOGRAM"],
            }
        ]
        source = profile([field("kind"), field("region"), field("extra")], aggregates=aggregates)
        target = profile([field("location", "$.region"), field("kind")], aggregates=aggregates)
        events = [
            {"kind": "a", "region": "us", "extra": "x", "size": 2},
            {"kind": "a", "region": "us", "extra": "y", "size": 10},
            {"kind": "b", "region": "eu", "extra": "x", "size": 4},
        ]
        raw = self.raw(source, events)
        original = copy.deepcopy(raw)
        result = self.derive(raw, source, target)
        expected = self.raw(target, events)
        path = self.root / "derived.yaml"
        result.save(str(path))
        actual = read_sketch_file(path)
        self.assertEqual(len(result), 2)
        for sid, skit in expected["skits"].items():
            self.assertEqual(actual["skits"][sid]["aggregates"], skit["aggregates"])
            self.assertEqual(actual["skits"][sid]["meta"]["count"], skit["meta"]["count"])
            self.assertEqual(actual["skits"][sid]["share"], skit["share"])
        self.assertEqual(raw, original)
        self.assertEqual(actual["profile_id"], target.profile_id)
        self.assertEqual(actual["last_run"], "261124-0001")
        self.assertEqual(actual["derivation"]["source_profile_id"], source.profile_id)

    def test_presence_collapses_values_without_reading_retained_samples(self):
        source = profile([field("tags", "$.tags[*]")])
        target = profile([field("tags", "$.tags[*]", modifier="IS_PRESENT")])
        raw = self.raw(source, [{"tags": ["a", "b"]}, {"tags": ["c"]}, {"tags": [None, "d"]}])
        for skit in raw["skits"].values():
            skit["meta"]["first"] = []
            skit["meta"]["last"] = []
        result = self.derive(raw, source, target)
        self.assertEqual(len(result), 1)
        skit = result.get(next(iter(result)))
        self.assertEqual(skit.tokens, {"tags": "TRUE"})
        self.assertEqual(skit.meta["count"], 3)

    def test_missing_null_and_literal_null_derive_presence_exactly(self):
        source = profile([field("tag")])
        target = profile([field("tag", modifier="IS_PRESENT")])
        events = [{}, {"tag": None}, {"tag": "NULL"}]
        result = self.derive(self.raw(source, events), source, target)
        self.assertEqual(set(result), set(self.raw(target, events)["skits"]))
        self.assertEqual(len(result), 2)
        null_target = profile([field("tag", modifier="IS_NULL")])
        result = self.derive(self.raw(source, events), source, null_target)
        self.assertEqual(set(result), set(self.raw(null_target, events)["skits"]))

    def test_new_paths_refinements_type_and_aggregate_changes_are_rejected(self):
        source = profile([field("kind", modifier="IS_PRESENT")])
        raw = self.raw(source, [{"kind": "a"}])
        for target in (
            profile([field("kind")]),
            profile([field("new")]),
            profile([field("kind", modifier="IS_PRESENT", type="DATE")]),
            profile(
                [field("kind", modifier="IS_PRESENT")],
                aggregates=[{"key": "n", "path": "$", "fn": "COUNT"}],
            ),
            profile([field("kind", modifier="IS_PRESENT")], sequence="$.id"),
            profile([field("kind", modifier="IS_PRESENT")], event_time="$.time"),
        ):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.derive(raw, source, target)

    def test_typed_time_coarsening_matches_fresh_fold_including_null_and_multivalue(self):
        for modifier in ("DEFAULT", {"name": "TRUNC", "unit": "hour"}):
            source = profile([field("time", "$.times[*]", type="DATETIME", modifier=modifier)])
            target = profile(
                [
                    field(
                        "day",
                        "$.times[*]",
                        type="DATETIME",
                        modifier={"name": "TRUNC", "unit": "day"},
                    )
                ]
            )
            events = [
                {"times": ["2026-11-24T01:02:03Z", "2026-11-24T05:00:00Z"]},
                {},
                {"times": [None, "2026-11-24T07:00:00Z"]},
            ]
            result = self.derive(self.raw(source, events), source, target)
            expected = self.raw(target, events)
            self.assertEqual(set(result), set(expected["skits"]))
        finer = profile(
            [
                field(
                    "time",
                    "$.times[*]",
                    type="DATETIME",
                    modifier={"name": "TRUNC", "unit": "minute"},
                )
            ]
        )
        with self.assertRaises(ValueError):
            self.derive(self.raw(source, events), source, finer)

    def test_scalar_string_collapses_preserve_literal_commas_and_null_strings(self):
        source = profile([field("kind")])
        target = profile([field("kind", modifier={"name": "GLOB", "pattern": "a*"})])
        events = [
            {"kind": "abc"},
            {"kind": "ade"},
            {"kind": "b"},
            {},
            {"kind": "a,b"},
            {"kind": "NULL"},
            {"kind": None},
        ]
        result = self.derive(self.raw(source, events), source, target)
        self.assertEqual(set(result), set(self.raw(target, events)["skits"]))
        for value in (["a", "b"], [None], []):
            with self.assertRaisesRegex(ValueError, "array"):
                self.derive(self.raw(source, [{"kind": value}]), source, target)
        null_glob = profile([field("kind", modifier={"name": "GLOB", "pattern": "N*"})])
        result = self.derive(self.raw(source, events), source, null_glob)
        self.assertEqual(set(result), set(self.raw(null_glob, events)["skits"]))

    def test_all_supported_scalar_modifiers_match_folding_and_never_increase_skits(self):
        source = profile([field("value")])
        events = [
            {},
            {"value": None},
            {"value": "NULL"},
            {"value": "a,b"},
            {"value": "abc"},
            {"value": "abc"},
            {"value": 12},
        ]
        raw = self.raw(source, events)
        for modifier in (
            "IS_PRESENT",
            "IS_NULL",
            {"name": "ANY", "values": ["abc", 12]},
            {"name": "GLOB", "pattern": "a*"},
            {"name": "REGEX", "pattern": "a|12"},
            {"name": "REGSUB", "pattern": "a.*", "replace": "a"},
        ):
            target = profile([field("value", modifier=modifier)])
            with self.subTest(modifier=modifier):
                result = self.derive(raw, source, target)
                expected = self.raw(target, events)
                self.assertEqual(set(result), set(expected["skits"]))
                self.assertLessEqual(len(result), len(raw["skits"]))
                self.assertEqual(sum(result.get(sid).meta["count"] for sid in result), len(events))
                for sid in result:
                    self.assertEqual(
                        result.get(sid).meta["count"], expected["skits"][sid]["meta"]["count"]
                    )

    def test_missing_aggregate_state_and_profile_mismatch_never_become_zeroes(self):
        source = profile([field("kind")], aggregates=[{"key": "n", "path": "$", "fn": "COUNT"}])
        raw = self.raw(source, [{"kind": "a"}])
        del next(iter(raw["skits"].values()))["aggregates"]["n"]
        with self.assertRaisesRegex(ValueError, "aggregate"):
            self.derive(raw, source, source)
        raw = self.raw(source, [])
        raw["profile_id"] = "incorrect"
        with self.assertRaisesRegex(ValueError, "profile"):
            self.derive(raw, source, source)

    def test_identity_and_count_corruption_are_rejected(self):
        source = profile([field("kind")])
        for part in ("tokens", "count"):
            raw = self.raw(source, [{"kind": "a"}])
            skit = next(iter(raw["skits"].values()))
            if part == "tokens":
                skit["tokens"]["kind"] = "corrupted"
            else:
                skit["meta"]["count"] = -1
            with self.assertRaises(ValueError):
                self.derive(raw, source, source)

    def test_typed_presence_cannot_recover_invalid_values(self):
        source = profile([field("date", "$.dates[*]", type="DATE")])
        target = profile([field("date", "$.dates[*]", type="DATE", modifier="IS_PRESENT")])
        raw = self.raw(source, [{"dates": ["2026-11-24", "bad"]}])
        with self.assertRaises(ValueError):
            self.derive(raw, source, target)

    def test_collapsing_incompatible_extrema_is_rejected(self):
        aggregates = [{"key": "range", "path": "$.value", "fn": ["MIN", "MAX"]}]
        source = profile([field("kind"), field("other")], aggregates=aggregates)
        target = profile([field("kind")], aggregates=aggregates)
        raw = self.raw(
            source,
            [{"kind": "a", "other": 1, "value": 2}, {"kind": "a", "other": 2, "value": "abc"}],
        )
        with self.assertRaisesRegex(ValueError, "incompatible|kinds"):
            self.derive(raw, source, target)

    def test_missing_or_invalid_predicate_tokens_are_corrupt(self):
        source = profile([field("present", "$.x", modifier="IS_PRESENT")])
        for tokens in ({}, {"present": None}, {"present": []}, {"present": "yes"}):
            raw = self.raw(source, [{"x": 1}])
            skit = next(iter(raw["skits"].values()))
            skit["tokens"] = tokens
            raw["skits"] = {skit_id(tokens): skit}
            with self.subTest(tokens=tokens), self.assertRaisesRegex(ValueError, "predicate"):
                self.derive(raw, source, source)

    def test_invalid_histogram_bins_and_continuation_metadata_are_rejected(self):
        source = profile(
            [field("kind")],
            sequence="$.seq",
            aggregates=[{"key": "h", "path": "$.n", "fn": "HISTOGRAM"}],
        )
        raw = self.raw(source, [{"kind": "a", "seq": 1, "n": 3}])
        histogram = next(iter(raw["skits"].values()))["aggregates"]["h"]
        histogram["bins"] = {"garbage": 1}
        with self.assertRaisesRegex(ValueError, "aggregate"):
            self.derive(raw, source, source)
        for header in (
            {"sequence": {"path": "$.other", "max": 1}},
            {"sequence": {"path": "$.seq", "max": "bad"}},
            {"last_run": "bad"},
        ):
            raw = self.raw(source, [{"kind": "a", "seq": 1, "n": 3}])
            raw.update(header)
            with (
                self.subTest(header=header),
                self.assertRaisesRegex(ValueError, "sequence|last_run"),
            ):
                self.derive(raw, source, source)
