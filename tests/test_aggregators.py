"""Tests: mergeable per-fingerprint aggregators."""

import unittest

from fingerprint_sampler.aggregators import AggregateEntry, make_entry, parse_fn, update


def fold(entry, records, state=None):
    state = {} if state is None else state
    skipped = sum(update(state, entry, record) for record in records)
    return state, skipped


class ParseFnTests(unittest.TestCase):
    def test_plain_functions_normalise_to_upper_case_labels(self):
        self.assertEqual(parse_fn(" avg "), ("AVG", None, "AVG"))
        self.assertEqual(parse_fn("SUM()"), ("SUM", None, "SUM"))

    def test_last_requires_positive_integer(self):
        self.assertEqual(parse_fn("last( 3 )"), ("LAST", 3, "LAST(3)"))
        for bad in ("LAST", "LAST()", "LAST(0)", "LAST(-1)", "LAST(x)", "LAST(1.5)"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_fn(bad)

    def test_unknown_function_raises_and_lists_supported(self):
        with self.assertRaises(ValueError) as ctx:
            parse_fn("MEDIAN")
        self.assertIn("MEDIAN", str(ctx.exception))
        self.assertIn("LAST(n)", str(ctx.exception))

    def test_numeric_functions_reject_arguments(self):
        with self.assertRaises(ValueError):
            parse_fn("SUM(3)")


class MakeEntryTests(unittest.TestCase):
    def test_accepts_single_spec_or_list(self):
        self.assertEqual(make_entry("d", "$.d", "min").fns, ("MIN",))
        self.assertEqual(make_entry("d", "$.d", ["MIN", "max"]).fns, ("MIN", "MAX"))

    def test_rejects_invalid_path_empty_fns_and_duplicates(self):
        with self.assertRaises(ValueError):
            make_entry("d", "$.d[", "MIN")
        with self.assertRaises(ValueError):
            make_entry("d", "$.d", [])
        with self.assertRaises(ValueError):
            make_entry("d", "$.d", ["MIN", "min"])
        with self.assertRaises(ValueError):
            make_entry("d", "$.d", ["LAST(2)", "LAST(3)"])


class NumericAggregatorTests(unittest.TestCase):
    RECORDS = [{"d": 5}, {"d": 1.5}, {"d": 9}]

    def test_sum_min_max_avg(self):
        entry = make_entry("d", "$.d", ["SUM", "MIN", "MAX", "AVG"])
        state, skipped = fold(entry, self.RECORDS)
        self.assertEqual(skipped, 0)
        self.assertEqual(state["SUM"], 15.5)
        self.assertEqual(state["MIN"], 1.5)
        self.assertEqual(state["MAX"], 9)
        self.assertEqual(state["AVG"], {"avg": 15.5 / 3, "sum": 15.5, "count": 3})

    def test_integer_inputs_keep_integer_sum(self):
        state, _ = fold(make_entry("d", "$.d", "SUM"), [{"d": 2}, {"d": 3}])
        self.assertEqual(state["SUM"], 5)
        self.assertIsInstance(state["SUM"], int)

    def test_numeric_strings_are_accepted(self):
        state, skipped = fold(make_entry("d", "$.d", ["SUM", "MAX"]), [{"d": "2.5"}, {"d": "4"}])
        self.assertEqual((state["SUM"], state["MAX"], skipped), (6.5, 4, 0))

    def test_non_numeric_null_bool_and_nan_are_skipped_and_counted(self):
        entry = make_entry("d", "$.d", ["SUM", "AVG"])
        records = [{"d": 1}, {"d": "abc"}, {"d": None}, {"d": True}, {"d": [1]}, {"d": "nan"}]
        state, skipped = fold(entry, records)
        self.assertEqual(state["SUM"], 1)
        self.assertEqual(state["AVG"]["count"], 1)
        self.assertEqual(skipped, 5)

    def test_event_without_a_match_counts_as_one_skip_and_leaves_state_alone(self):
        entry = make_entry("d", "$.d", ["MIN", "LAST(2)"])
        state, skipped = fold(entry, [{"other": 1}])
        self.assertEqual(state, {})
        self.assertEqual(skipped, 1)

    def test_all_matches_in_one_event_feed_the_aggregator(self):
        entry = make_entry("sizes", "$.args[*].size", ["SUM", "MAX", "AVG"])
        state, _ = fold(entry, [{"args": [{"size": 1}, {"size": 2}, {"size": 6}]}])
        self.assertEqual(state["SUM"], 9)
        self.assertEqual(state["MAX"], 6)
        self.assertEqual(state["AVG"]["count"], 3)


class LastAggregatorTests(unittest.TestCase):
    def test_keeps_newest_n_in_arrival_order(self):
        entry = make_entry("s", "$", "LAST(3)")
        state, _ = fold(entry, [{"seq": i} for i in range(5)])
        self.assertEqual([s["seq"] for s in state["LAST"]], [2, 3, 4])

    def test_stores_any_json_value_including_null_and_strings(self):
        entry = make_entry("s", "$.v", "LAST(5)")
        state, skipped = fold(entry, [{"v": "a"}, {"v": None}, {"v": {"x": 1}}])
        self.assertEqual(state["LAST"], ["a", None, {"x": 1}])
        self.assertEqual(skipped, 0)

    def test_stored_samples_do_not_alias_the_input_record(self):
        record = {"seq": 1}
        state, _ = fold(make_entry("s", "$", "LAST(2)"), [record])
        record["seq"] = 99
        self.assertEqual(state["LAST"], [{"seq": 1}])


class MergeabilityTests(unittest.TestCase):
    """AC3: folding across several runs equals folding in one run."""

    def test_split_fold_equals_single_fold(self):
        entry = make_entry("d", "$.d", ["SUM", "AVG", "MIN", "MAX", "LAST(3)"])
        records = [{"d": v} for v in (0.1, 0.2, 0.3, 7, "x", 0.4, 2, 0.7)]
        single, single_skipped = fold(entry, records)
        for cut in range(len(records) + 1):
            with self.subTest(cut=cut):
                first, s1 = fold(entry, records[:cut])
                merged, s2 = fold(entry, records[cut:], state=first)
                self.assertEqual(merged, single)
                self.assertEqual(s1 + s2, single_skipped)

    def test_changing_last_n_carries_stored_samples_forward(self):
        state, _ = fold(make_entry("s", "$.v", "LAST(5)"), [{"v": i} for i in range(5)])
        fold(make_entry("s", "$.v", "LAST(2)"), [{"v": 5}], state=state)
        self.assertEqual(state["LAST"], [4, 5])


class AggregateEntryTests(unittest.TestCase):
    def test_entry_is_hashable_value_object(self):
        self.assertEqual(make_entry("d", "$.d", "MIN"), AggregateEntry("d", "$.d", ("MIN",)))


if __name__ == "__main__":
    unittest.main()
