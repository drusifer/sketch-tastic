"""Tests for the fingerprint set (stateful upsert warehouse)."""

import os
import tempfile
import unittest

import yaml

from sketchtastic.aggregators import Aggregate
from sketchtastic.sketch import (
    ProfileMismatchError,
    Sketch,
    SketchError,
    skit_id,
)

# Duration bounds plus the last three raw events: a typical telemetry-style aggregate set.
SAMPLE_AGGREGATES = (
    Aggregate("duration_ms", "$.duration_ms", ["MIN", "MAX"]),
    Aggregate("samples", "$", {"name": "LAST", "n": 3}),
)


class FingerprintIdTests(unittest.TestCase):
    def test_sorts_keys_before_hashing_serialization_drift_prevention(self):
        # AC1: alphabetical sort by key before flattening - insertion order must not matter.
        tokens_a = {"b_key": "1", "a_key": "2"}
        tokens_b = {"a_key": "2", "b_key": "1"}
        self.assertEqual(skit_id(tokens_a), skit_id(tokens_b))

    def test_returns_32_char_hex_md5(self):
        fid = skit_id({"a": "1"})
        self.assertEqual(len(fid), 32)
        int(fid, 16)  # raises ValueError if not valid hex

    def test_different_tokens_yield_different_ids(self):
        self.assertNotEqual(skit_id({"a": "1"}), skit_id({"a": "2"}))


class UpsertReconciliationTests(unittest.TestCase):
    def test_match_state_increments_occurrences_without_new_record(self):
        wh = Sketch()
        tokens = {"hook_syscall": "sys_connect"}

        for run in ("261014-0001", "261014-0002", "261015-0003"):
            wh.upsert(tokens, {"n": 1}, run=run)

        self.assertEqual(len(wh), 1)  # entry list count stays flat
        record = wh.get(skit_id(tokens))
        self.assertEqual(record.meta["count"], 3)
        self.assertEqual(record.meta["first_seen"], "261014-0001")  # runs, not times
        self.assertEqual(record.meta["last_seen"], "261015-0003")
        self.assertEqual(record.tokens, tokens)  # the set explains what the ID means

    def test_first_and_last_records_are_kept_in_their_envelopes(self):
        fingerprints = Sketch()
        for i in range(5):
            fingerprints.upsert({"k": "v"}, {"n": i}, run=f"t{i}")
        meta = fingerprints.get(skit_id({"k": "v"})).meta

        def envelopes(*ns):
            return [{"meta": {"run": f"t{i}"}, "record": {"n": i}} for i in ns]

        self.assertEqual(meta["first"], envelopes(0))  # one each keeps sets and run files small
        self.assertEqual(meta["last"], envelopes(4))

    def test_record_fields_named_like_built_ins_do_not_clash(self):
        fingerprints = Sketch(aggregates=[Aggregate("count", "$.count", "SUM")])
        fingerprints.upsert({"k": "v"}, {"count": 10, "meta": "x"}, run="t")
        record = fingerprints.get(skit_id({"k": "v"}))
        self.assertEqual(record.aggregates["count"], 10)
        self.assertEqual(record.meta["count"], 1)
        self.assertEqual(record.meta["first"][0]["record"], {"count": 10, "meta": "x"})

    def test_built_in_profile_does_not_count_toward_skipped_values(self):
        fingerprints = Sketch()
        fingerprints.upsert({"k": "v"}, {})
        self.assertEqual(fingerprints.skipped_values, 0)

    def test_drift_state_creates_new_record_block(self):
        wh = Sketch()
        wh.upsert({"a": "1"}, {}, run="t1")
        wh.upsert({"a": "2"}, {}, run="t1")

        self.assertEqual(len(wh), 2)

    def test_no_aggregators_keeps_only_built_in_counters(self):
        wh = Sketch()
        wh.upsert({"a": "1"}, {"duration_ms": 5.0}, run="t1")
        self.assertEqual(wh.get(skit_id({"a": "1"})).aggregates, {})
        self.assertEqual(wh.skipped_values, 0)


class AggregatedUpsertTests(unittest.TestCase):
    def test_min_max_aggregates_track_duration_bounds(self):
        # What the warehouse used to hardcode, now declared as MIN/MAX on $.duration_ms.
        wh = Sketch(aggregates=SAMPLE_AGGREGATES)
        tokens = {"a": "1"}
        for i, duration in enumerate((5.0, 1.0, 9.0)):
            wh.upsert(tokens, {"duration_ms": duration}, run=f"t{i}")

        duration = wh.get(skit_id(tokens)).aggregates["duration_ms"]
        self.assertEqual(duration, {"MIN": 1.0, "MAX": 9.0})

    def test_last_aggregate_keeps_last_three_raw_events(self):
        wh = Sketch(aggregates=SAMPLE_AGGREGATES)
        tokens = {"a": "1"}
        for i in range(5):
            wh.upsert(tokens, {"seq": i, "duration_ms": 1.0}, run=f"t{i}")

        samples = wh.get(skit_id(tokens)).aggregates["samples"]
        # oldest (seq 0, 1) rotated out; newest 3 retained in order
        self.assertEqual([s["seq"] for s in samples], [2, 3, 4])

    def test_aggregates_are_kept_per_fingerprint(self):
        wh = Sketch(aggregates=[Aggregate("size", "$.size", ["SUM", "AVG"])])
        wh.upsert({"kind": "a"}, {"size": 10}, run="t")
        wh.upsert({"kind": "a"}, {"size": 30}, run="t")
        wh.upsert({"kind": "b"}, {"size": 7}, run="t")

        a = wh.get(skit_id({"kind": "a"})).aggregates["size"]
        b = wh.get(skit_id({"kind": "b"})).aggregates["size"]
        self.assertEqual(a, {"SUM": 40, "AVG": {"avg": 20.0, "sum": 40, "count": 2}})
        self.assertEqual(b["SUM"], 7)

    def test_unusable_values_are_counted_not_fatal(self):
        wh = Sketch(aggregates=[Aggregate("size", "$.size", "SUM")])
        wh.upsert({"k": "1"}, {"size": "big"}, run="t")
        wh.upsert({"k": "1"}, {}, run="t")
        wh.upsert({"k": "1"}, {"size": 2}, run="t")

        record = wh.get(skit_id({"k": "1"}))
        self.assertEqual(record.meta["count"], 3)
        self.assertEqual(record.aggregates["size"], 2)
        self.assertEqual(wh.skipped_values, 1)  # "big"; the event without size is not a skip


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "fingerprints.yaml")

    def test_save_and_load_round_trip(self):
        wh = Sketch(aggregates=SAMPLE_AGGREGATES, profile_id="p1")
        tokens = {"a": "1"}
        wh.upsert(tokens, {"x": 1, "duration_ms": 1.0}, run="t1")
        wh.upsert(tokens, {"x": 2, "duration_ms": 2.0}, run="t2")
        wh.save(self.path)

        reloaded = Sketch(aggregates=SAMPLE_AGGREGATES, profile_id="p1")
        reloaded.load(self.path)

        self.assertEqual(reloaded.get(skit_id(tokens)), wh.get(skit_id(tokens)))

    def test_tricky_values_round_trip_exactly(self):
        record = {
            "looks_like": ["yes", "no", "on", "null", "~", "1e3", "0x10", "2026-10-14", "12:30"],
            "text": ["", " padded ", "a\nb\n", "tab\there", "héllo ✓ 🚀", ": #", "- x", "'\""],
            "long": "x" * 5000 + " y" * 500,
            "numbers": [0, -1, 2**70, 0.1, 1e300, -2.5e-8],
            "other": [True, False, None, {}, [], {"nested": [{"deep": "v"}]}],
        }
        wh = Sketch(aggregates=SAMPLE_AGGREGATES, profile_id="p1")
        wh.upsert({"a": "1"}, record, run="t1")
        wh.save(self.path)
        reloaded = Sketch(aggregates=SAMPLE_AGGREGATES, profile_id="p1")
        reloaded.load(self.path)
        self.assertEqual(reloaded.get(skit_id({"a": "1"})), wh.get(skit_id({"a": "1"})))

    def test_file_is_versioned_and_records_profile_id(self):
        wh = Sketch(profile_id="p1")
        wh.upsert({"a": "1"}, {}, run="t1")
        wh.save(self.path)

        with open(self.path) as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["version"], 0)
        self.assertEqual(data["profile_id"], "p1")
        self.assertEqual(list(data["skits"]), [skit_id({"a": "1"})])

    def test_file_reads_top_down_header_then_tokens_before_statistics(self):
        wh = Sketch(aggregates=SAMPLE_AGGREGATES, profile_id="p1")
        wh.upsert({"syscall": "sys_connect"}, {"duration_ms": 1.0}, run="t1")
        wh.save(self.path)

        with open(self.path) as f:
            text = f.read()
        order = [
            "version:",
            "profile_id:",
            "skits:",
            "tokens:",
            "aggregates:",
            "meta:",
        ]
        positions = [text.index(key) for key in order]
        self.assertEqual(positions, sorted(positions))

    def test_folding_across_a_save_load_boundary_equals_one_pass(self):
        aggs = [
            Aggregate("d", "$.d", ["SUM", "AVG", "MIN", "MAX"]),
            Aggregate("s", "$", {"name": "LAST", "n": 2}),
        ]
        events = [({"k": str(i % 2)}, {"d": i * 0.1, "i": i}) for i in range(9)]

        one_pass = Sketch(aggregates=aggs)
        for i, (tokens, event) in enumerate(events):
            one_pass.upsert(tokens, event, run=f"t{i}")

        first = Sketch(aggregates=aggs)
        for i, (tokens, event) in enumerate(events[:4]):
            first.upsert(tokens, event, run=f"t{i}")
        first.save(self.path)
        second = Sketch(aggregates=aggs)
        second.load(self.path)
        for i, (tokens, event) in enumerate(events[4:], start=4):
            second.upsert(tokens, event, run=f"t{i}")

        # Shares describe the set as last written, so compare both as written.
        second.save(self.path)
        one_pass.save(self.path + ".one")
        self.assertEqual(len(second), len(one_pass))
        for fid in one_pass:
            self.assertEqual(second.get(fid), one_pass.get(fid))

    def test_load_refuses_a_set_built_with_another_profile(self):
        Sketch(profile_id="old").save(self.path)
        wh = Sketch(profile_id="new")
        with self.assertRaises(ProfileMismatchError) as ctx:
            wh.load(self.path)
        self.assertEqual(
            (ctx.exception.set_profile_id, ctx.exception.current_profile_id), ("old", "new")
        )

    def test_load_with_force_adopts_a_mismatched_set(self):
        old = Sketch(profile_id="old")
        old.upsert({"a": "1"}, {}, run="t1")
        old.save(self.path)

        wh = Sketch(profile_id="new")
        wh.load(self.path, force=True)
        self.assertEqual(len(wh), 1)
        self.assertEqual(wh.profile_id, "new")

    def test_load_rejects_pre_aggregator_format_with_clear_error(self):
        with open(self.path, "w") as f:
            yaml.safe_dump({"abc": {"count": 1, "min_duration_ms": 1.0}}, f)
        with self.assertRaises(SketchError) as ctx:
            Sketch().load(self.path)
        self.assertIn("not a sketch", str(ctx.exception))

    def test_load_rejects_unknown_version_and_invalid_yaml(self):
        with open(self.path, "w") as f:
            yaml.safe_dump({"version": 99, "skits": {}}, f)
        with self.assertRaises(SketchError):
            Sketch().load(self.path)
        with open(self.path, "w") as f:
            f.write("fingerprints: [unclosed")
        with self.assertRaises(SketchError):
            Sketch().load(self.path)

    def test_failed_save_leaves_previous_file_intact_and_no_temp_files(self):
        wh = Sketch(profile_id="p1")
        wh.upsert({"a": "1"}, {}, run="t1")
        wh.save(self.path)
        with open(self.path) as f:
            before = f.read()

        wh.upsert({"a": "2"}, {"bad": object()}, run="t2")
        wh._records[skit_id({"a": "2"})].aggregates["x"] = {"LAST": [object()]}
        with self.assertRaises(yaml.YAMLError):
            wh.save(self.path)

        with open(self.path) as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(os.listdir(self._tmp.name), ["fingerprints.yaml"])


if __name__ == "__main__":
    unittest.main()


class ShareTests(unittest.TestCase):
    """Each fingerprint's share of every SUM and COUNT total, written on save (FING-46)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "fingerprints.yaml")

    def saved_shares(self, fingerprints):
        fingerprints.save(self.path)
        with open(self.path) as f:
            data = yaml.safe_load(f)
        return {rec["tokens"]["k"]: rec["share"] for rec in data["skits"].values()}

    def build(self, aggregates, events):
        fingerprints = Sketch(aggregates=aggregates)
        for kind, record in events:
            fingerprints.upsert({"k": kind}, record, run="2024-01-01T00:00:00Z")
        return fingerprints

    def test_shares_of_counts_and_sums_mirror_the_value_layout(self):
        fingerprints = self.build(
            [Aggregate("size", "$.size", ["SUM", "MAX"]), Aggregate("n", "$.size", "COUNT")],
            [("a", {"size": 10}), ("a", {"size": 30}), ("b", {"size": 60})],
        )
        shares = self.saved_shares(fingerprints)
        self.assertEqual(
            shares["a"],
            {"meta": {"count": 66.67}, "aggregates": {"size": {"SUM": 40.0}, "n": 66.67}},
        )
        self.assertEqual(
            shares["b"],
            {"meta": {"count": 33.33}, "aggregates": {"size": {"SUM": 60.0}, "n": 33.33}},
        )

    def test_zero_or_absent_total_has_no_share(self):
        fingerprints = self.build(
            [Aggregate("zero", "$.z", "SUM"), Aggregate("none", "$.missing", "SUM")],
            [("a", {"z": 0}), ("b", {"z": 0})],
        )
        self.assertEqual(self.saved_shares(fingerprints)["a"], {"meta": {"count": 50.0}})

    def test_shares_are_recomputed_after_a_merge_and_never_read_back(self):
        aggregates = [Aggregate("size", "$.size", "SUM")]
        self.build(aggregates, [("a", {"size": 10})]).save(self.path)

        merged = Sketch(aggregates=aggregates)
        merged.load(self.path)
        merged.upsert({"k": "b"}, {"size": 30}, run="2024-01-01T00:00:00Z")
        shares = self.saved_shares(merged)
        self.assertEqual(shares["a"]["aggregates"], {"size": 25.0})
        self.assertEqual(shares["b"]["aggregates"], {"size": 75.0})
        self.assertEqual(merged.get(skit_id({"k": "a"})).aggregates, {"size": 10})

    def test_share_is_written_after_the_values(self):
        fingerprints = self.build([], [("a", {})])
        fingerprints.save(self.path)
        with open(self.path) as f:
            text = f.read()
        self.assertLess(text.index("meta:"), text.index("share:"))


class RunHeaderTests(unittest.TestCase):
    """A run file is a set with a `run:` header (FING-48)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "run.yaml")

    def test_header_is_written_between_profile_id_and_fingerprints(self):
        fingerprints = Sketch(profile_id="p1")
        fingerprints.run = {"source": "stdin", "events": 1}
        fingerprints.upsert({"a": "1"}, {}, run="2024-01-01T00:00:00Z")
        fingerprints.save(self.path)
        with open(self.path) as f:
            text = f.read()
            data = yaml.safe_load(text)
        self.assertEqual(data["run"], {"source": "stdin", "events": 1})
        positions = [text.index(key) for key in ("profile_id:", "run:", "skits:")]
        self.assertEqual(positions, sorted(positions))

    def test_no_header_unless_set_and_load_ignores_it(self):
        plain = Sketch(profile_id="p1")
        plain.save(self.path)
        with open(self.path) as f:
            self.assertNotIn("run", yaml.safe_load(f))

        with_run = Sketch(profile_id="p1")
        with_run.run = {"events": 0}
        with_run.upsert({"a": "1"}, {}, run="2024-01-01T00:00:00Z")
        with_run.save(self.path)
        loaded = Sketch(profile_id="p1")
        loaded.load(self.path)
        self.assertEqual((len(loaded), loaded.run), (1, None))


class LastRunTests(unittest.TestCase):
    """The set remembers its latest run id, so the next run can number itself."""

    def test_last_run_is_saved_after_profile_id_and_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "set.yaml")
            fingerprints = Sketch(profile_id="p1")
            fingerprints.last_run = "261015-0003"
            fingerprints.save(path)
            with open(path) as f:
                text = f.read()
            self.assertLess(text.index("profile_id:"), text.index("last_run: 261015-0003"))
            self.assertLess(text.index("last_run:"), text.index("skits:"))
            loaded = Sketch(profile_id="p1")
            loaded.load(path)
            self.assertEqual(loaded.last_run, "261015-0003")

    def test_no_last_run_until_one_is_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "set.yaml")
            Sketch().save(path)
            with open(path) as f:
                self.assertNotIn("last_run", yaml.safe_load(f))


class SequenceMarkTests(unittest.TestCase):
    """The set keeps its duplicate-protection mark (FING-50)."""

    def test_mark_is_saved_after_last_run_and_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "set.yaml")
            fingerprints = Sketch()
            fingerprints.last_run = "261015-0001"
            fingerprints.sequence = {"path": "$.id", "max": 8}
            fingerprints.save(path)
            with open(path) as f:
                text = f.read()
            self.assertLess(text.index("last_run:"), text.index("sequence:"))
            self.assertLess(text.index("sequence:"), text.index("skits:"))
            loaded = Sketch()
            loaded.load(path)
            self.assertEqual(loaded.sequence, {"path": "$.id", "max": 8})

    def test_no_mark_unless_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "set.yaml")
            Sketch().save(path)
            with open(path) as f:
                self.assertNotIn("sequence", yaml.safe_load(f))


class VocabularyTests(unittest.TestCase):
    """STORY-SKT-02: sketches hold skits; ids are unchanged by the rename."""

    def test_skit_id_is_the_old_fingerprint_id(self):
        # README quickstart value from before the move (fingerprint-sampler 0.2.0)
        tokens = {"level": "INFO", "component": "db", "failed": "FALSE"}
        self.assertTrue(skit_id(tokens).startswith("b738d17a"))

    def test_library_names(self):
        import sketchtastic

        for name in ("Sketch", "Skit", "SketchError", "ProfileMismatchError", "skit_id"):
            self.assertIn(name, sketchtastic.__all__)
        for old in ("FingerprintSet", "Fingerprint", "fingerprint_id", "FingerprintSetError"):
            self.assertFalse(hasattr(sketchtastic, old))

    def test_file_lists_skits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.sketch.yaml")
            sketch = Sketch()
            sketch.upsert({"a": "1"}, {}, run="261015-0001")
            sketch.save(path)
            with open(path) as f:
                data = yaml.safe_load(f)
            self.assertIn("skits", data)
            self.assertNotIn("fingerprints", data)


class MergeTests(unittest.TestCase):
    """Fold a run into its own sketch, then merge it once (fold once, then merge)."""

    AGGREGATES = (
        Aggregate("n", "$.n", ["SUM", "COUNT", "MIN", "MAX", "AVG"]),
        Aggregate("word", "$.word", ["MIN", "MAX"]),
        Aggregate("first", "$.n", {"name": "FIRST", "n": 2}),
        Aggregate("last", "$.n", {"name": "LAST", "n": 2}),
    )
    EVENTS = [
        ({"k": "a"}, {"n": 4, "word": "pear"}),
        ({"k": "a"}, {"n": 1}),
        ({"k": "b"}, {"n": 7, "word": "fig"}),
        ({"k": "a"}, {"n": 9, "word": "apple"}),
        ({"k": "c"}, {"word": "kiwi"}),
        ({"k": "b"}, {"n": "x"}),
        ({"k": "a"}, {"n": 2}),
    ]

    def fold(self, events, run_id):
        sketch = Sketch(self.AGGREGATES, profile_id="p")
        for tokens, record in events:
            sketch.upsert(tokens, record, run=run_id)
        return sketch

    def test_merging_runs_equals_folding_every_event(self):
        for split in range(len(self.EVENTS) + 1):
            with self.subTest(split=split):
                expected = self.fold(self.EVENTS[:split], "r1")
                for tokens, record in self.EVENTS[split:]:
                    expected.upsert(tokens, record, run="r2")
                sketch = self.fold(self.EVENTS[:split], "r1")
                sketch.merge(self.fold(self.EVENTS[split:], "r2"))
                self.assertEqual(list(sketch), list(expected))
                for fid in expected:
                    self.assertEqual(sketch.get(fid), expected.get(fid))
                self.assertEqual(sketch.skipped_values, expected.skipped_values)

    def test_merge_into_an_empty_sketch_equals_the_run(self):
        run = self.fold(self.EVENTS, "r1")
        sketch = Sketch(self.AGGREGATES, profile_id="p")
        sketch.merge(run)
        self.assertEqual(list(sketch), list(run))
        for fid in run:
            self.assertEqual(sketch.get(fid), run.get(fid))

    def test_merged_skits_do_not_alias_the_run(self):
        run = self.fold(self.EVENTS[:1], "r1")
        sketch = Sketch(self.AGGREGATES, profile_id="p")
        sketch.merge(run)
        fid = skit_id({"k": "a"})
        run.get(fid).aggregates["last"].append(99)
        self.assertEqual(sketch.get(fid).aggregates["last"], [4])

    def test_aggregates_must_match(self):
        sketch = Sketch(self.AGGREGATES, profile_id="p")
        with self.assertRaises(SketchError):
            sketch.merge(Sketch(self.AGGREGATES[:1], profile_id="p"))
