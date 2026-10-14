"""Tests for the fingerprint set (stateful upsert warehouse)."""

import os
import tempfile
import unittest
from datetime import datetime, timezone

import yaml

from fingerprint_sampler.aggregators import Aggregate
from fingerprint_sampler.fingerprint_set import (
    FingerprintSet,
    FingerprintSetError,
    ProfileMismatchError,
    fingerprint_id,
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
        self.assertEqual(fingerprint_id(tokens_a), fingerprint_id(tokens_b))

    def test_returns_32_char_hex_md5(self):
        fid = fingerprint_id({"a": "1"})
        self.assertEqual(len(fid), 32)
        int(fid, 16)  # raises ValueError if not valid hex

    def test_different_tokens_yield_different_ids(self):
        self.assertNotEqual(fingerprint_id({"a": "1"}), fingerprint_id({"a": "2"}))


class UpsertReconciliationTests(unittest.TestCase):
    def test_match_state_increments_occurrences_without_new_record(self):
        wh = FingerprintSet()
        tokens = {"hook_syscall": "sys_connect"}

        for second in (1, 2, 3):
            wh.upsert(tokens, {"n": second}, timestamp=f"2024-01-01T15:00:0{second}+00:00")

        self.assertEqual(len(wh), 1)  # entry list count stays flat
        record = wh.get(fingerprint_id(tokens))
        self.assertEqual(record.meta["count"], 3)
        self.assertEqual(
            record.meta["first_seen"], datetime(2024, 1, 1, 15, 0, 1, tzinfo=timezone.utc)
        )
        self.assertEqual(
            record.meta["last_seen"], datetime(2024, 1, 1, 15, 0, 3, tzinfo=timezone.utc)
        )
        self.assertEqual(record.tokens, tokens)  # the set explains what the ID means

    def test_first_and_last_records_are_kept_in_their_envelopes(self):
        fingerprints = FingerprintSet()
        for i in range(5):
            fingerprints.upsert({"k": "v"}, {"n": i}, timestamp=f"t{i}")
        meta = fingerprints.get(fingerprint_id({"k": "v"})).meta

        def envelopes(*ns):
            return [{"meta": {"seen": f"t{i}"}, "record": {"n": i}} for i in ns]

        self.assertEqual(meta["first"], envelopes(0, 1, 2))
        self.assertEqual(meta["last"], envelopes(2, 3, 4))

    def test_record_fields_named_like_built_ins_do_not_clash(self):
        fingerprints = FingerprintSet(aggregates=[Aggregate("count", "$.count", "SUM")])
        fingerprints.upsert({"k": "v"}, {"count": 10, "meta": "x"}, timestamp="t")
        record = fingerprints.get(fingerprint_id({"k": "v"}))
        self.assertEqual(record.aggregates["count"], 10)
        self.assertEqual(record.meta["count"], 1)
        self.assertEqual(record.meta["first"][0]["record"], {"count": 10, "meta": "x"})

    def test_samples_are_copies_and_saved_without_yaml_aliases(self):
        event = {"n": 1}
        fingerprints = FingerprintSet()
        fingerprints.upsert({"k": "v"}, event, timestamp="t")
        event["n"] = 99
        meta = fingerprints.get(fingerprint_id({"k": "v"})).meta
        self.assertEqual(meta["first"][0]["record"], {"n": 1})
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "set.yaml")
            fingerprints.save(path)
            with open(path) as f:
                self.assertNotIn("&id", f.read())

    def test_built_in_profile_does_not_count_toward_skipped_values(self):
        fingerprints = FingerprintSet()
        fingerprints.upsert({"k": "v"}, {})
        self.assertEqual(fingerprints.skipped_values, 0)

    def test_drift_state_creates_new_record_block(self):
        wh = FingerprintSet()
        wh.upsert({"a": "1"}, {}, timestamp="t1")
        wh.upsert({"a": "2"}, {}, timestamp="t1")

        self.assertEqual(len(wh), 2)

    def test_no_aggregators_keeps_only_built_in_counters(self):
        wh = FingerprintSet()
        wh.upsert({"a": "1"}, {"duration_ms": 5.0}, timestamp="t1")
        self.assertEqual(wh.get(fingerprint_id({"a": "1"})).aggregates, {})
        self.assertEqual(wh.skipped_values, 0)


class AggregatedUpsertTests(unittest.TestCase):
    def test_min_max_aggregates_track_duration_bounds(self):
        # What the warehouse used to hardcode, now declared as MIN/MAX on $.duration_ms.
        wh = FingerprintSet(aggregates=SAMPLE_AGGREGATES)
        tokens = {"a": "1"}
        for i, duration in enumerate((5.0, 1.0, 9.0)):
            wh.upsert(tokens, {"duration_ms": duration}, timestamp=f"t{i}")

        duration = wh.get(fingerprint_id(tokens)).aggregates["duration_ms"]
        self.assertEqual(duration, {"MIN": 1.0, "MAX": 9.0})

    def test_last_aggregate_keeps_last_three_raw_events(self):
        wh = FingerprintSet(aggregates=SAMPLE_AGGREGATES)
        tokens = {"a": "1"}
        for i in range(5):
            wh.upsert(tokens, {"seq": i, "duration_ms": 1.0}, timestamp=f"t{i}")

        samples = wh.get(fingerprint_id(tokens)).aggregates["samples"]
        # oldest (seq 0, 1) rotated out; newest 3 retained in order
        self.assertEqual([s["seq"] for s in samples], [2, 3, 4])

    def test_aggregates_are_kept_per_fingerprint(self):
        wh = FingerprintSet(aggregates=[Aggregate("size", "$.size", ["SUM", "AVG"])])
        wh.upsert({"kind": "a"}, {"size": 10}, timestamp="t")
        wh.upsert({"kind": "a"}, {"size": 30}, timestamp="t")
        wh.upsert({"kind": "b"}, {"size": 7}, timestamp="t")

        a = wh.get(fingerprint_id({"kind": "a"})).aggregates["size"]
        b = wh.get(fingerprint_id({"kind": "b"})).aggregates["size"]
        self.assertEqual(a, {"SUM": 40, "AVG": {"avg": 20.0, "sum": 40, "count": 2}})
        self.assertEqual(b["SUM"], 7)

    def test_unusable_values_are_counted_not_fatal(self):
        wh = FingerprintSet(aggregates=[Aggregate("size", "$.size", "SUM")])
        wh.upsert({"k": "1"}, {"size": "big"}, timestamp="t")
        wh.upsert({"k": "1"}, {}, timestamp="t")
        wh.upsert({"k": "1"}, {"size": 2}, timestamp="t")

        record = wh.get(fingerprint_id({"k": "1"}))
        self.assertEqual(record.meta["count"], 3)
        self.assertEqual(record.aggregates["size"], 2)
        self.assertEqual(wh.skipped_values, 1)  # "big"; the event without size is not a skip


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "fingerprints.yaml")

    def test_save_and_load_round_trip(self):
        wh = FingerprintSet(aggregates=SAMPLE_AGGREGATES, profile_id="p1")
        tokens = {"a": "1"}
        wh.upsert(tokens, {"x": 1, "duration_ms": 1.0}, timestamp="t1")
        wh.upsert(tokens, {"x": 2, "duration_ms": 2.0}, timestamp="t2")
        wh.save(self.path)

        reloaded = FingerprintSet(aggregates=SAMPLE_AGGREGATES, profile_id="p1")
        reloaded.load(self.path)

        self.assertEqual(reloaded.get(fingerprint_id(tokens)), wh.get(fingerprint_id(tokens)))

    def test_file_is_versioned_and_records_profile_id(self):
        wh = FingerprintSet(profile_id="p1")
        wh.upsert({"a": "1"}, {}, timestamp="t1")
        wh.save(self.path)

        with open(self.path) as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["version"], 0)
        self.assertEqual(data["profile_id"], "p1")
        self.assertEqual(list(data["fingerprints"]), [fingerprint_id({"a": "1"})])

    def test_file_reads_top_down_header_then_tokens_before_statistics(self):
        wh = FingerprintSet(aggregates=SAMPLE_AGGREGATES, profile_id="p1")
        wh.upsert({"syscall": "sys_connect"}, {"duration_ms": 1.0}, timestamp="t1")
        wh.save(self.path)

        with open(self.path) as f:
            text = f.read()
        order = [
            "version:",
            "profile_id:",
            "fingerprints:",
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

        one_pass = FingerprintSet(aggregates=aggs)
        for i, (tokens, event) in enumerate(events):
            one_pass.upsert(tokens, event, timestamp=f"t{i}")

        first = FingerprintSet(aggregates=aggs)
        for i, (tokens, event) in enumerate(events[:4]):
            first.upsert(tokens, event, timestamp=f"t{i}")
        first.save(self.path)
        second = FingerprintSet(aggregates=aggs)
        second.load(self.path)
        for i, (tokens, event) in enumerate(events[4:], start=4):
            second.upsert(tokens, event, timestamp=f"t{i}")

        self.assertEqual(len(second), len(one_pass))
        for fid in one_pass:
            self.assertEqual(second.get(fid), one_pass.get(fid))

    def test_load_refuses_a_set_built_with_another_profile(self):
        FingerprintSet(profile_id="old").save(self.path)
        wh = FingerprintSet(profile_id="new")
        with self.assertRaises(ProfileMismatchError) as ctx:
            wh.load(self.path)
        self.assertEqual(
            (ctx.exception.set_profile_id, ctx.exception.current_profile_id), ("old", "new")
        )

    def test_load_with_force_adopts_a_mismatched_set(self):
        old = FingerprintSet(profile_id="old")
        old.upsert({"a": "1"}, {}, timestamp="t1")
        old.save(self.path)

        wh = FingerprintSet(profile_id="new")
        wh.load(self.path, force=True)
        self.assertEqual(len(wh), 1)
        self.assertEqual(wh.profile_id, "new")

    def test_load_rejects_pre_aggregator_format_with_clear_error(self):
        with open(self.path, "w") as f:
            yaml.safe_dump({"abc": {"count": 1, "min_duration_ms": 1.0}}, f)
        with self.assertRaises(FingerprintSetError) as ctx:
            FingerprintSet().load(self.path)
        self.assertIn("not a fingerprint set", str(ctx.exception))

    def test_load_rejects_unknown_version_and_invalid_yaml(self):
        with open(self.path, "w") as f:
            yaml.safe_dump({"version": 99, "fingerprints": {}}, f)
        with self.assertRaises(FingerprintSetError):
            FingerprintSet().load(self.path)
        with open(self.path, "w") as f:
            f.write("fingerprints: [unclosed")
        with self.assertRaises(FingerprintSetError):
            FingerprintSet().load(self.path)

    def test_failed_save_leaves_previous_file_intact_and_no_temp_files(self):
        wh = FingerprintSet(profile_id="p1")
        wh.upsert({"a": "1"}, {}, timestamp="t1")
        wh.save(self.path)
        with open(self.path) as f:
            before = f.read()

        wh.upsert({"a": "2"}, {"bad": object()}, timestamp="t2")
        wh._records[fingerprint_id({"a": "2"})].aggregates["x"] = {"LAST": [object()]}
        with self.assertRaises(yaml.YAMLError):
            wh.save(self.path)

        with open(self.path) as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(os.listdir(self._tmp.name), ["fingerprints.yaml"])


if __name__ == "__main__":
    unittest.main()
