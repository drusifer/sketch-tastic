"""Tests: mergeable per-fingerprint aggregators."""

import unittest

from sketchtastic.aggregators import Aggregate


def fold(entry, records, state=None):
    """Fold records into one aggregate. Returns (its state, values skipped)."""
    states = {} if state is None else {entry.key: state}
    skipped = sum(entry.update(states, record) for record in records)
    return states.get(entry.key, {}), skipped


class BuildTests(unittest.TestCase):
    def test_accepts_one_function_or_a_list(self):
        self.assertEqual([f.name for f in Aggregate("d", "$.d", "MIN").fn], ["MIN"])
        functions = Aggregate("d", "$.d", ["MIN", {"name": "LAST", "n": 3}]).fn
        self.assertEqual([f.spec for f in functions], ["MIN", '{"n":3,"name":"LAST"}'])

    def test_rejects_with_a_reason(self):
        cases = [
            ("$.d[", "MIN", "Invalid JSONPath"),
            ("$.d", "LAST(3)", "is not one of ['SUM', 'MIN', 'MAX', 'AVG', 'COUNT']"),
            ("$.d", "min", "is not one of"),
            ("$.d", {"name": "LAST"}, "'n' is a required property"),
            ("$.d", "FIRST", "FIRST needs arguments (n); write it as {name: FIRST, n: ...}"),
            ("$.d", "LAST", "LAST needs arguments (n); write it as {name: LAST, n: ...}"),
            ("$.d", {"name": "LAST", "n": 0}, "n: 0 is less than the minimum of 1"),
            ("$.d", {"name": "MEDIAN"}, "name: 'MEDIAN' is not one of"),
            ("$.d", {"name": "SUM", "n": 2}, "('n' was unexpected)"),
            ("$.d", ["MIN", "MIN"], "listed more than once: MIN"),
            ("$.d", [{"name": "LAST", "n": 2}, {"name": "LAST", "n": 3}], "more than once: LAST"),
        ]
        for path, fn, expected in cases:
            with self.subTest(fn=fn), self.assertRaises(ValueError) as ctx:
                Aggregate("d", path, fn)
            self.assertIn(expected, str(ctx.exception))


class NumericAggregatorTests(unittest.TestCase):
    RECORDS = [{"d": 5}, {"d": 1.5}, {"d": 9}]

    def test_sum_min_max_avg(self):
        entry = Aggregate("d", "$.d", ["SUM", "MIN", "MAX", "AVG"])
        state, skipped = fold(entry, self.RECORDS)
        self.assertEqual(skipped, 0)
        self.assertEqual(state["SUM"], 15.5)
        self.assertEqual(state["MIN"], 1.5)
        self.assertEqual(state["MAX"], 9)
        self.assertEqual(state["AVG"], {"avg": 15.5 / 3, "sum": 15.5, "count": 3})

    def test_integer_inputs_keep_integer_sum(self):
        state, _ = fold(Aggregate("d", "$.d", "SUM"), [{"d": 2}, {"d": 3}])
        self.assertEqual(state, 5)  # one function: the value itself
        self.assertIsInstance(state, int)

    def test_numeric_strings_are_accepted(self):
        state, skipped = fold(Aggregate("d", "$.d", ["SUM", "MAX"]), [{"d": "2.5"}, {"d": "4"}])
        self.assertEqual((state["SUM"], state["MAX"], skipped), (6.5, 4, 0))

    def test_non_numeric_null_bool_and_nan_are_skipped_and_counted(self):
        entry = Aggregate("d", "$.d", ["SUM", "AVG"])
        records = [{"d": 1}, {"d": "abc"}, {"d": None}, {"d": True}, {"d": [1]}, {"d": "nan"}]
        state, skipped = fold(entry, records)
        self.assertEqual(state["SUM"], 1)
        self.assertEqual(state["AVG"]["count"], 1)
        self.assertEqual(skipped, 5)

    def test_event_without_a_match_is_not_a_skip_and_leaves_state_alone(self):
        entry = Aggregate("d", "$.d", ["MIN", {"name": "LAST", "n": 2}])
        state, skipped = fold(entry, [{"other": 1}])
        self.assertEqual(state, {})
        self.assertEqual(skipped, 0)

    def test_all_matches_in_one_event_feed_the_aggregator(self):
        entry = Aggregate("sizes", "$.args[*].size", ["SUM", "MAX", "AVG"])
        state, _ = fold(entry, [{"args": [{"size": 1}, {"size": 2}, {"size": 6}]}])
        self.assertEqual(state["SUM"], 9)
        self.assertEqual(state["MAX"], 6)
        self.assertEqual(state["AVG"]["count"], 3)


class LastAggregatorTests(unittest.TestCase):
    def test_keeps_newest_n_in_arrival_order(self):
        entry = Aggregate("s", "$", {"name": "LAST", "n": 3})
        state, _ = fold(entry, [{"seq": i} for i in range(5)])
        self.assertEqual([s["seq"] for s in state], [2, 3, 4])

    def test_stores_any_json_value_including_null_and_strings(self):
        entry = Aggregate("s", "$.v", {"name": "LAST", "n": 5})
        state, skipped = fold(entry, [{"v": "a"}, {"v": None}, {"v": {"x": 1}}])
        self.assertEqual(state, ["a", None, {"x": 1}])
        self.assertEqual(skipped, 0)


class CountAndFirstTests(unittest.TestCase):
    def test_count_counts_every_selected_value_of_any_type(self):
        state, skipped = fold(Aggregate("c", "$.v", "COUNT"), [{"v": "a"}, {"v": None}, {"v": 2}])
        self.assertEqual((state, skipped), (3, 0))

    def test_first_keeps_the_earliest_n(self):
        state, _ = fold(
            Aggregate("f", "$.v", {"name": "FIRST", "n": 2}), [{"v": i} for i in range(5)]
        )
        self.assertEqual(state, [0, 1])

    def test_first_keeps_an_explicit_null(self):
        state, _ = fold(Aggregate("f", "$.v", {"name": "FIRST", "n": 1}), [{"v": None}, {"v": 1}])
        self.assertEqual(state, [None])

    def test_several_functions_are_kept_by_name(self):
        state, _ = fold(Aggregate("t", "$.v", ["MIN", "MAX", "COUNT"]), [{"v": "b"}, {"v": "a"}])
        self.assertEqual(state, {"MIN": "a", "MAX": "b", "COUNT": 2})


class OrderedMinMaxTests(unittest.TestCase):
    def test_iso_timestamps_compare_as_text_whatever_the_arrival_order(self):
        times = ["2024-01-01T15:00:05Z", "2024-01-01T15:00:01Z", "2024-01-01T15:00:09Z"]
        state, skipped = fold(Aggregate("t", "$.t", ["MIN", "MAX"]), [{"t": t} for t in times])
        self.assertEqual(state, {"MIN": "2024-01-01T15:00:01Z", "MAX": "2024-01-01T15:00:09Z"})
        self.assertEqual(skipped, 0)

    def test_numeric_strings_still_compare_as_numbers(self):
        state, _ = fold(Aggregate("n", "$.n", "MAX"), [{"n": "9"}, {"n": "10"}])
        self.assertEqual(state, 10)

    def test_a_value_of_another_kind_is_skipped_and_counted(self):
        state, skipped = fold(Aggregate("m", "$.m", "MIN"), [{"m": 3}, {"m": "abc"}, {"m": None}])
        self.assertEqual((state, skipped), (3, 2))


class MergeabilityTests(unittest.TestCase):
    """AC3: folding across several runs equals folding in one run."""

    def test_split_fold_equals_single_fold(self):
        entry = Aggregate("d", "$.d", ["SUM", "AVG", "MIN", "MAX", {"name": "LAST", "n": 3}])
        records = [{"d": v} for v in (0.1, 0.2, 0.3, 7, "x", 0.4, 2, 0.7)]
        single, single_skipped = fold(entry, records)
        for cut in range(len(records) + 1):
            with self.subTest(cut=cut):
                first, s1 = fold(entry, records[:cut])
                merged, s2 = fold(entry, records[cut:], state=first)
                self.assertEqual(merged, single)
                self.assertEqual(s1 + s2, single_skipped)

    def test_changing_last_n_carries_stored_samples_forward(self):
        state, _ = fold(
            Aggregate("s", "$.v", {"name": "LAST", "n": 5}), [{"v": i} for i in range(5)]
        )
        state, _ = fold(Aggregate("s", "$.v", {"name": "LAST", "n": 2}), [{"v": 5}], state=state)
        self.assertEqual(state, [4, 5])


class AggregateValueTests(unittest.TestCase):
    def test_aggregate_is_a_comparable_value(self):
        self.assertEqual(Aggregate("d", "$.d", "MIN"), Aggregate("d", "$.d", ["MIN"]))


if __name__ == "__main__":
    unittest.main()


class SizeOpTests(unittest.TestCase):
    """`op: SIZE` measures each selected value in bytes before the functions see it (FING-45)."""

    def test_sum_avg_max_of_payload_bytes(self):
        entry = Aggregate("payload_bytes", "$.payload", ["SUM", "AVG", "MAX"], op="SIZE")
        state, skipped = fold(entry, [{"payload": "héllo"}, {"payload": {"a": 1}}])
        self.assertEqual((state["SUM"], state["MAX"], state["AVG"]["avg"]), (13, 7, 6.5))
        self.assertEqual(skipped, 0)

    def test_every_function_gets_the_size(self):
        entry = Aggregate("b", "$.v", {"name": "LAST", "n": 2}, op="SIZE")
        state, _ = fold(entry, [{"v": "a"}, {"v": [1, 2]}, {"v": True}])
        self.assertEqual(state, [5, 4])  # [1,2] and true

    def test_null_measures_4_and_absent_path_adds_nothing(self):
        entry = Aggregate("b", "$.v", "SUM", op="SIZE")
        state, skipped = fold(entry, [{"v": None}, {"other": "x"}])
        self.assertEqual((state, skipped), (4, 0))

    def test_unknown_op_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            Aggregate("b", "$.v", "SUM", op="BOGUS")
        self.assertIn("'BOGUS' is not one of ['SIZE']", str(ctx.exception))
