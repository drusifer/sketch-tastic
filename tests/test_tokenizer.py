"""Tests: eBPF telemetry parser & modifier engine."""

import json
import unittest

from fingerprint_sampler.tokenizer import (
    MaskEntry,
    apply_modifier,
    compile_path,
    find_values,
    parse_jsonl,
    tokenize,
    validate_modifier,
)

SAMPLE_RECORD = {
    "time": "2026-07-12T09:44:10.005Z",
    "duration_ms": 1.84,
    "process_exec": {
        "process": {
            "pid": 14205,
            "binary": "/usr/bin/node",
        }
    },
    "process_kprobe": {
        "function_name": "sys_connect",
        "return_value": 0,
        "args": [
            {"sock_arg": {"dport": 6379, "daddr": "10.244.2.14"}},
        ],
    },
}


class FindValuesTests(unittest.TestCase):
    def test_resolves_nested_dot_path(self):
        self.assertEqual(
            find_values(SAMPLE_RECORD, "$.process_exec.process.binary"), ["/usr/bin/node"]
        )

    def test_resolves_array_index_path(self):
        self.assertEqual(
            find_values(SAMPLE_RECORD, "$.process_kprobe.args[0].sock_arg.dport"), [6379]
        )

    def test_missing_path_yields_no_matches(self):
        self.assertEqual(find_values(SAMPLE_RECORD, "$.process_exec.process.ppid"), [])

    def test_out_of_range_index_yields_no_matches(self):
        self.assertEqual(find_values(SAMPLE_RECORD, "$.process_kprobe.args[5].sock_arg.dport"), [])

    def test_explicit_json_null_is_a_match(self):
        record = {"process_kprobe": {"function_name": None}}
        self.assertEqual(find_values(record, "$.process_kprobe.function_name"), [None])

    def test_root_path_matches_whole_record(self):
        self.assertEqual(find_values(SAMPLE_RECORD, "$"), [SAMPLE_RECORD])


MULTI_ARG_RECORD = {
    "args": [
        {"type": "sock", "dport": 6379},
        {"type": "file", "name": "/etc/passwd"},
        {"type": "sock", "dport": 443},
        {"type": "sock", "dport": 80},
    ]
}


class FullJsonPathSyntaxTests(unittest.TestCase):
    """STORY-FING-23 AC2: syntax the hand-rolled resolver never supported."""

    def test_filter_expression_parenthesised(self):
        self.assertEqual(
            find_values(MULTI_ARG_RECORD, "$.args[?(@.type == 'sock')].dport"), [6379, 443, 80]
        )

    def test_filter_expression_with_comparison(self):
        self.assertEqual(find_values(MULTI_ARG_RECORD, "$.args[?@.dport > 100].dport"), [6379, 443])

    def test_slice(self):
        self.assertEqual(find_values(MULTI_ARG_RECORD, "$.args[0:2].type"), ["sock", "file"])

    def test_negative_index(self):
        self.assertEqual(find_values(MULTI_ARG_RECORD, "$.args[-1].dport"), [80])

    def test_union_of_names(self):
        self.assertEqual(
            find_values(MULTI_ARG_RECORD, "$.args[1]['type','name']"), ["file", "/etc/passwd"]
        )

    def test_recursive_descent(self):
        self.assertEqual(find_values(MULTI_ARG_RECORD, "$..dport"), [6379, 443, 80])

    def test_filter_feeds_tokenize(self):
        profile = [MaskEntry("sock_ports", "$.args[?(@.type == 'sock')].dport", "ANY(80, 443)")]
        # 6379 -> FALSE, 443 -> TRUE, 80 -> TRUE; deduplicated + sorted.
        self.assertEqual(tokenize(MULTI_ARG_RECORD, profile), {"sock_ports": "FALSE,TRUE"})


class InvalidPathTests(unittest.TestCase):
    """STORY-FING-23 AC5: bad paths fail at compile time, as ValueError."""

    def test_unterminated_bracket_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            compile_path("$.a[")
        self.assertIn("$.a[", str(ctx.exception))

    def test_empty_path_raises_value_error(self):
        with self.assertRaises(ValueError):
            compile_path("")

    def test_blank_path_raises_value_error(self):
        with self.assertRaises(ValueError):
            compile_path("   ")


class MatchCountSemanticsTests(unittest.TestCase):
    """STORY-FING-23 AC3: token shape depends on match count, not path spelling."""

    def test_single_match_from_wildcard_equals_scalar_token(self):
        record = {"args": [{"dport": 443}]}
        wildcard = tokenize(record, [MaskEntry("p", "$.args[*].dport", "DEFAULT")])
        indexed = tokenize(record, [MaskEntry("p", "$.args[0].dport", "DEFAULT")])
        self.assertEqual(wildcard, indexed)
        self.assertEqual(wildcard, {"p": "443"})

    def test_list_valued_single_match_is_not_expanded(self):
        record = {"tags": ["b", "a"]}
        self.assertEqual(
            tokenize(record, [MaskEntry("t", "$.tags", "DEFAULT")]), {"t": "['b', 'a']"}
        )

    def test_empty_wildcard_is_missing(self):
        record = {"args": []}
        self.assertEqual(
            tokenize(record, [MaskEntry("p", "$.args[*].dport", "IS_PRESENT")]), {"p": "FALSE"}
        )


class ApplyModifierTests(unittest.TestCase):
    def test_default_passes_literal_value(self):
        self.assertEqual(apply_modifier("sys_connect", "DEFAULT"), "sys_connect")

    def test_default_missing_yields_null(self):
        from fingerprint_sampler.tokenizer import _MISSING

        self.assertEqual(apply_modifier(_MISSING, "DEFAULT"), "NULL")

    def test_is_present_true_for_pid(self):
        # Verification Task: pid: 14205 + IS_PRESENT -> "TRUE"
        self.assertEqual(apply_modifier(14205, "IS_PRESENT"), "TRUE")

    def test_is_present_false_for_missing(self):
        from fingerprint_sampler.tokenizer import _MISSING

        self.assertEqual(apply_modifier(_MISSING, "IS_PRESENT"), "FALSE")

    def test_is_null_true_for_missing(self):
        from fingerprint_sampler.tokenizer import _MISSING

        self.assertEqual(apply_modifier(_MISSING, "IS_NULL"), "TRUE")

    def test_is_null_false_for_present_value(self):
        self.assertEqual(apply_modifier(14205, "IS_NULL"), "FALSE")

    def test_in_range_true_for_kernel_error(self):
        # Verification Task: return_value -110 vs IN_RANGE(-999, 0) -> "TRUE"
        self.assertEqual(apply_modifier(-110, "IN_RANGE(-999, 0)"), "TRUE")

    def test_in_range_false_outside_bounds(self):
        self.assertEqual(apply_modifier(5, "IN_RANGE(-999, 0)"), "FALSE")

    def test_in_range_false_for_missing(self):
        from fingerprint_sampler.tokenizer import _MISSING

        self.assertEqual(apply_modifier(_MISSING, "IN_RANGE(-999, 0)"), "FALSE")

    def test_any_true_for_whitelisted_port(self):
        self.assertEqual(apply_modifier(6379, "ANY(80, 443, 6379, 27017)"), "TRUE")

    def test_any_false_for_unlisted_port(self):
        self.assertEqual(apply_modifier(9999, "ANY(80, 443, 6379, 27017)"), "FALSE")

    def test_unknown_modifier_raises(self):
        with self.assertRaises(ValueError):
            apply_modifier("x", "BOGUS(*)")

    # AC4: "absent OR null" must both degrade gracefully - these exercise an
    # actual JSON `null` value, distinct from an absent/missing path.
    def test_default_explicit_null_yields_null(self):
        self.assertEqual(apply_modifier(None, "DEFAULT"), "NULL")

    def test_is_present_false_for_explicit_null(self):
        self.assertEqual(apply_modifier(None, "IS_PRESENT"), "FALSE")

    def test_is_null_true_for_explicit_null(self):
        self.assertEqual(apply_modifier(None, "IS_NULL"), "TRUE")

    def test_in_range_false_for_explicit_null(self):
        self.assertEqual(apply_modifier(None, "IN_RANGE(-999, 0)"), "FALSE")

    def test_any_false_for_explicit_null(self):
        self.assertEqual(apply_modifier(None, "ANY(80, 443)"), "FALSE")


class TokenizeTests(unittest.TestCase):
    def test_tokenizes_full_mask_profile_without_raising(self):
        mask_profile = [
            MaskEntry("application_binary", "$.process_exec.process.binary", "DEFAULT"),
            MaskEntry("hook_syscall", "$.process_kprobe.function_name", "DEFAULT"),
            MaskEntry("isolation_pid", "$.process_exec.process.pid", "IS_PRESENT"),
            MaskEntry(
                "network_dest_port",
                "$.process_kprobe.args[0].sock_arg.dport",
                "ANY(80, 443, 6379, 27017)",
            ),
            MaskEntry("kernel_return_state", "$.process_kprobe.return_value", "IN_RANGE(-999, 0)"),
            MaskEntry("missing_field", "$.does.not.exist", "DEFAULT"),
        ]

        tokens = tokenize(SAMPLE_RECORD, mask_profile)

        self.assertEqual(
            tokens,
            {
                "application_binary": "/usr/bin/node",
                "hook_syscall": "sys_connect",
                "isolation_pid": "TRUE",
                "network_dest_port": "TRUE",
                "kernel_return_state": "TRUE",
                "missing_field": "NULL",
            },
        )


class ParseJsonlTests(unittest.TestCase):
    def test_parses_multi_line_jsonl_stream(self):
        # AC1: "Must accept a valid JSONL input string mimicking standard eBPF engine outputs."
        jsonl_text = "\n".join(
            json.dumps(r) for r in [SAMPLE_RECORD, {**SAMPLE_RECORD, "duration_ms": 2.5}]
        )

        records = parse_jsonl(jsonl_text)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["process_kprobe"]["function_name"], "sys_connect")
        self.assertEqual(records[1]["duration_ms"], 2.5)

    def test_skips_blank_lines_in_stream(self):
        jsonl_text = f"{json.dumps(SAMPLE_RECORD)}\n\n"
        self.assertEqual(len(parse_jsonl(jsonl_text)), 1)

    def test_end_to_end_jsonl_to_tokens(self):
        mask_profile = [MaskEntry("hook_syscall", "$.process_kprobe.function_name", "DEFAULT")]
        records = parse_jsonl(json.dumps(SAMPLE_RECORD))

        tokens = tokenize(records[0], mask_profile)

        self.assertEqual(tokens, {"hook_syscall": "sys_connect"})


class WildcardAndRecursiveDescentTests(unittest.TestCase):
    def test_wildcard_array_resolution(self):
        record = {
            "process_kprobe": {
                "args": [
                    {"sock_arg": {"dport": 6379}},
                    {"sock_arg": {"dport": 443}},
                ]
            }
        }
        profile = [MaskEntry("ports", "$.process_kprobe.args[*].sock_arg.dport", "DEFAULT")]
        tokens = tokenize(record, profile)
        # Expected sorted and joined: "443,6379"
        self.assertEqual(tokens, {"ports": "443,6379"})

    def test_recursive_descent_resolution(self):
        record = {
            "process_kprobe": {
                "args": [
                    {"sock_arg": {"dport": 6379}},
                    {"sock_arg": {"dport": 443}},
                ],
                "nested": {"other_port": {"dport": 80}},
            }
        }
        profile = [MaskEntry("all_ports", "$.process_kprobe..dport", "DEFAULT")]
        tokens = tokenize(record, profile)
        # Expected sorted, deduplicated and joined: "443,6379,80" (sorted alphabetically: "443,6379,80" -> wait, str sort: '443', '6379', '80')
        # Let's verify str sort order: '443' < '6379' < '80' because '6' < '8'. Yes! "443,6379,80"
        self.assertEqual(tokens, {"all_ports": "443,6379,80"})

    def test_missing_wildcard_resolves_to_null_and_never_raises(self):
        record = {"process_kprobe": {}}
        profile = [MaskEntry("ports", "$.process_kprobe.args[*].sock_arg.dport", "DEFAULT")]
        tokens = tokenize(record, profile)
        self.assertEqual(tokens, {"ports": "NULL"})


if __name__ == "__main__":
    unittest.main()


class PatternModifierTests(unittest.TestCase):
    """GLOB, REGEX and REGSUB (FR-MOD-01)."""

    def test_glob_matches_whole_value(self):
        self.assertEqual(apply_modifier("/usr/bin/node", "GLOB(/usr/bin/*)"), "TRUE")
        self.assertEqual(apply_modifier("/opt/usr/bin/node", "GLOB(/usr/bin/*)"), "FALSE")

    def test_glob_is_case_sensitive(self):
        self.assertEqual(apply_modifier("/USR/bin/node", "GLOB(/usr/*)"), "FALSE")

    def test_glob_character_class_and_question_mark(self):
        self.assertEqual(apply_modifier("eth0", "GLOB(eth[0-3])"), "TRUE")
        self.assertEqual(apply_modifier("eth7", "GLOB(eth[0-3])"), "FALSE")
        self.assertEqual(apply_modifier("v1", "GLOB(v?)"), "TRUE")

    def test_glob_stringifies_numbers(self):
        self.assertEqual(apply_modifier(8080, "GLOB(80*)"), "TRUE")

    def test_regex_searches_anywhere_unless_anchored(self):
        self.assertEqual(apply_modifier("/api/v2/users", r"REGEX(/v\d+/)"), "TRUE")
        self.assertEqual(apply_modifier("/api/v2/users", r"REGEX(^/v\d+/)"), "FALSE")

    def test_regex_unquoted_pattern_may_contain_parentheses(self):
        self.assertEqual(apply_modifier("POST", "REGEX(^(GET|POST)$)"), "TRUE")
        self.assertEqual(apply_modifier("POSTED", "REGEX(^(GET|POST)$)"), "FALSE")

    def test_quoted_pattern_may_contain_commas_and_spaces(self):
        self.assertEqual(apply_modifier("aaa", "REGEX('^a{2,3}$')"), "TRUE")
        self.assertEqual(apply_modifier("a", 'REGEX("^a{2,3}$")'), "FALSE")
        self.assertEqual(apply_modifier("x y", "GLOB(' x y')"), "FALSE")
        self.assertEqual(apply_modifier(" x y", "GLOB(' x y')"), "TRUE")

    def test_doubled_quote_is_a_literal_quote(self):
        self.assertEqual(apply_modifier("it's", "GLOB('it''s')"), "TRUE")

    def test_regsub_replaces_every_match(self):
        self.assertEqual(
            apply_modifier("/users/123/orders/4567", r"REGSUB(\d+, N)"), "/users/N/orders/N"
        )

    def test_regsub_with_group_reference_and_quoted_arguments(self):
        self.assertEqual(
            apply_modifier("10.244.2.14", r"REGSUB('^(\d+\.\d+)\..*$', '\1.x.x')"), "10.244.x.x"
        )

    def test_regsub_empty_replacement_deletes(self):
        self.assertEqual(apply_modifier("abc-123", r"REGSUB('-\d+$', '')"), "abc")

    def test_regsub_without_a_match_passes_the_value_through(self):
        self.assertEqual(apply_modifier("GET", r"REGSUB(\d+, N)"), "GET")
        self.assertEqual(apply_modifier(42, r"REGSUB(x, y)"), "42")

    def test_missing_and_null_degrade_like_the_other_modifiers(self):
        from fingerprint_sampler.tokenizer import _MISSING

        for value in (_MISSING, None):
            self.assertEqual(apply_modifier(value, "GLOB(*)"), "FALSE")
            self.assertEqual(apply_modifier(value, "REGEX(.*)"), "FALSE")
            self.assertEqual(apply_modifier(value, "REGSUB(.*, x)"), "NULL")

    def test_several_matches_are_tokenized_individually(self):
        record = {"paths": ["/tmp/a1", "/tmp/b22", "/etc/passwd"]}
        self.assertEqual(
            tokenize(record, [MaskEntry("p", "$.paths[*]", "GLOB(/tmp/*)")]), {"p": "FALSE,TRUE"}
        )
        self.assertEqual(
            tokenize(record, [MaskEntry("p", "$.paths[*]", r"REGSUB(\d+, N)")]),
            {"p": "/etc/passwd,/tmp/aN,/tmp/bN"},
        )

    def test_quotes_work_for_existing_modifiers_too(self):
        self.assertEqual(apply_modifier("a,b", "ANY('a,b', c)"), "TRUE")
        self.assertEqual(apply_modifier("a", "ANY('a,b', c)"), "FALSE")


class ValidatePatternModifierTests(unittest.TestCase):
    def test_valid_expressions_pass(self):
        for modifier in (
            "GLOB(/usr/*)",
            "REGEX(^(GET|POST)$)",
            "REGEX('^a{2,3}$')",
            r"REGSUB(\d+, N)",
            r"REGSUB('(\d+)', '<\1>')",
            r"REGSUB('(?P<n>\d+)', '\g<n>')",
            r"REGSUB(\d+, '')",
        ):
            with self.subTest(modifier=modifier):
                validate_modifier(modifier)

    def test_invalid_expressions_say_what_is_wrong(self):
        cases = {
            "GLOB": "takes 1 argument",
            "GLOB()": "takes 1 argument",
            "GLOB(a, b)": "takes 1 argument",
            "REGEX(a{2,3})": "takes 1 argument",
            "REGEX(()": "not a valid regex",
            "REGEX([a-)": "not a valid regex",
            "REGSUB(a)": "takes 2 argument",
            "REGSUB([, x)": "not a valid regex",
            r"REGSUB(a, '\1')": "replacement is not valid",
            r"REGSUB(a, '\g<nope>')": "replacement is not valid",
            "REGEX('abc)": "missing closing '",
            "REGEX('a' b)": "after a quoted argument",
            "GLOB(/usr/*": "missing ')'",
        }
        for modifier, expected in cases.items():
            with self.subTest(modifier=modifier):
                with self.assertRaises(ValueError) as ctx:
                    validate_modifier(modifier)
                self.assertIn(expected, str(ctx.exception))
