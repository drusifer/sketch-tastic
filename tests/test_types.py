"""Tests: value types (DATE, DATETIME) and the TRUNC modifier."""

import unittest
from datetime import date, datetime, timezone

from sketchtastic.aggregators import Aggregate
from sketchtastic.model import Field, ValueType
from sketchtastic.profile import ProfileError, parse_profile

UTC = timezone.utc


def convert(spec, value):
    return ValueType.build(spec).convert(value)


class DatetimeTests(unittest.TestCase):
    def test_iso_text_with_any_zone_becomes_utc(self):
        self.assertEqual(
            convert("DATETIME", "2024-01-01T17:00:00+02:00"), datetime(2024, 1, 1, 15, tzinfo=UTC)
        )
        self.assertEqual(
            convert("DATETIME", "2024-01-01T15:00:00Z"), datetime(2024, 1, 1, 15, tzinfo=UTC)
        )

    def test_text_without_a_zone_is_taken_as_utc(self):
        self.assertEqual(
            convert("DATETIME", "2024-01-01 15:00:00"), datetime(2024, 1, 1, 15, tzinfo=UTC)
        )

    def test_unparseable_values_become_none(self):
        for value in ("yesterday", None, True, 1704121200, [1], {"a": 1}):
            with self.subTest(value=value):
                self.assertIsNone(convert("DATETIME", value))


class DateTests(unittest.TestCase):
    def test_date_from_iso_date_or_datetime_text(self):
        self.assertEqual(convert("DATE", "2024-01-01"), date(2024, 1, 1))
        self.assertEqual(convert("DATE", "2024-01-01T23:30:00-02:00"), date(2024, 1, 2))
        self.assertIsNone(convert("DATE", "soon"))


class TypedAggregateTests(unittest.TestCase):
    def test_min_max_compare_real_times_across_zones(self):
        aggregate = Aggregate("t", "$.t", ["MIN", "MAX"], type="DATETIME")
        states = {}
        skipped = sum(
            aggregate.update(states, {"t": t})
            for t in ("2024-01-01T16:30:00+02:00", "2024-01-01T15:00:00Z", "bad")
        )
        self.assertEqual(
            states["t"],
            {
                "MIN": datetime(2024, 1, 1, 14, 30, tzinfo=UTC),
                "MAX": datetime(2024, 1, 1, 15, tzinfo=UTC),
            },
        )
        self.assertEqual(skipped, 1)


class TypedStatePersistenceTests(unittest.TestCase):
    def test_datetime_state_survives_save_and_load_and_keeps_folding(self):
        import os
        import tempfile

        from sketchtastic.fingerprint_set import FingerprintSet, fingerprint_id

        aggregate = Aggregate("t", "$.t", "MAX", type="DATETIME")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "set.yaml")
            first = FingerprintSet([aggregate])
            first.upsert({"k": "v"}, {"t": "2024-01-01T15:00:00Z"})
            first.save(path)
            second = FingerprintSet([aggregate])
            second.load(path)
            second.upsert({"k": "v"}, {"t": "2024-01-01T16:00:00+02:00"})
        state = second.get(fingerprint_id({"k": "v"})).aggregates["t"]
        self.assertEqual(state, datetime(2024, 1, 1, 15, tzinfo=UTC))


class TypedFieldTests(unittest.TestCase):
    def test_default_token_is_iso_utc(self):
        field = Field("t", "$.t", type="DATETIME")
        self.assertEqual(
            field.token({"t": "2024-01-01T17:00:00+02:00"}), "2024-01-01T15:00:00+00:00"
        )

    def test_unparseable_value_tokenizes_as_missing(self):
        self.assertEqual(Field("t", "$.t", type="DATETIME").token({"t": "nope"}), "NULL")

    def test_trunc_buckets_times(self):
        event = {"t": "2024-01-01T15:04:05Z"}
        for unit, token in [
            ("year", "2024"),
            ("month", "2024-01"),
            ("day", "2024-01-01"),
            ("hour", "2024-01-01T15"),
            ("minute", "2024-01-01T15:04"),
        ]:
            with self.subTest(unit=unit):
                field = Field("t", "$.t", {"name": "TRUNC", "unit": unit}, type="DATETIME")
                self.assertEqual(field.token(event), token)

    def test_trunc_needs_a_date_type(self):
        with self.assertRaises(ValueError) as ctx:
            Field("t", "$.t", {"name": "TRUNC", "unit": "day"})
        self.assertIn("TRUNC needs type DATE or DATETIME", str(ctx.exception))


class ProfileTypeTests(unittest.TestCase):
    def test_type_in_a_profile_and_its_errors(self):
        profile = parse_profile(
            {
                "fields": [{"key": "day", "path": "$.t", "type": "DATE"}],
                "aggregates": [{"key": "t", "path": "$.t", "type": "DATETIME", "fn": "MAX"}],
            }
        )
        self.assertEqual(profile.tokens({"t": "2024-01-01T15:00:00Z"}), {"day": "2024-01-01"})
        for bad in ("TIMESTAMP", {"name": "DATETIME", "format": "%Y"}):
            with self.subTest(type=bad), self.assertRaises(ProfileError) as ctx:
                parse_profile({"fields": [{"key": "d", "path": "$.t", "type": bad}]})
        self.assertIn("fields[0] (key 'd') → type", str(ctx.exception))

    def test_a_field_type_changes_the_profile_id_and_no_type_keeps_it(self):
        plain = parse_profile({"fields": [{"key": "t", "path": "$.t"}]}).profile_id
        typed = parse_profile({"fields": [{"key": "t", "path": "$.t", "type": "DATE"}]}).profile_id
        self.assertNotEqual(plain, typed)


if __name__ == "__main__":
    unittest.main()
