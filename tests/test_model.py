"""Tests: paths, modifiers and fields (the domain model)."""

import unittest

import jsonpath

from sketchtastic.model import MISSING, AnyOf, Default, Field, Glob, Modifier, Path, tokens

MaskEntry = Field
tokenize = tokens
validate_modifier = Modifier.build
compile_path = Path


def find_values(record, path):
    return Path(path).values(record)


def apply_modifier(value, spec):
    return Modifier.build(spec).token(value)


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
        profile = [
            MaskEntry(
                "sock_ports",
                "$.args[?(@.type == 'sock')].dport",
                {"name": "ANY", "values": [80, 443]},
            )
        ]
        # 6379 -> FALSE, 443 -> TRUE, 80 -> TRUE; deduplicated + sorted.
        self.assertEqual(tokenize(MULTI_ARG_RECORD, profile), {"sock_ports": "FALSE,TRUE"})


class PlainPathTests(unittest.TestCase):
    """Plain paths ($, $.a.b) take a fast path that must select what python-jsonpath does
    (STORY-SKT-05 AC3)."""

    DOCUMENTS = [
        {},
        {"a": 1},
        {"a": None},
        {"a": {"b": 2}},
        {"a": {"b": None}},
        {"a": {"b": {"c": [1, {"d": 3}]}}},
        {"a": [1, 2]},
        {"a": [{"b": 1}, {"b": 2}]},
        {"a": "text"},
        {"a": {"b": "text"}},
        {"a": 0, "b": False},
        {"true": 1, "null": 2, "length": 3, "keys": 4, "_x9": 5, "A_b": {"c": 6}},
        [1, 2],
        [{"a": 1}],
        "text",
        None,
        7,
    ]
    PATHS = [
        "$",
        "$.a",
        "$.a.b",
        "$.a.b.c",
        "$.a.b.c.d",
        "$.b",
        "$.true",
        "$.null",
        "$.length",
        "$.keys",
        "$._x9",
        "$.A_b.c",
        "$.missing.b",
    ]

    def test_selects_what_python_jsonpath_selects(self):
        for path in self.PATHS:
            for document in self.DOCUMENTS:
                with self.subTest(path=path, document=document):
                    expected = jsonpath.compile(path).findall(document)
                    self.assertEqual(Path(path).values(document), expected)

    def test_selected_values_are_the_documents_own_objects(self):
        document = {"a": {"b": [1]}}
        self.assertIs(Path("$.a").values(document)[0], document["a"])
        self.assertIs(Path("$").values(document)[0], document)

    def test_other_paths_still_use_full_jsonpath(self):
        document = {"a": [{"b": 1}, {"b": 2}], "c d": 3}
        for path in ("$.a[*].b", "$.a[0].b", "$['c d']", "$..b", "$.a[?@.b > 1].b"):
            with self.subTest(path=path):
                self.assertEqual(Path(path).values(document), jsonpath.findall(path, document))


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

        self.assertEqual(apply_modifier(MISSING, "DEFAULT"), "NULL")

    def test_is_present_true_for_pid(self):
        # Verification Task: pid: 14205 + IS_PRESENT -> "TRUE"
        self.assertEqual(apply_modifier(14205, "IS_PRESENT"), "TRUE")

    def test_is_present_false_for_missing(self):

        self.assertEqual(apply_modifier(MISSING, "IS_PRESENT"), "FALSE")

    def test_is_null_false_for_missing(self):

        self.assertEqual(apply_modifier(MISSING, "IS_NULL"), "FALSE")

    def test_is_null_false_for_present_value(self):
        self.assertEqual(apply_modifier(14205, "IS_NULL"), "FALSE")

    def test_in_range_true_for_kernel_error(self):
        # Verification Task: return_value -110 vs IN_RANGE(-999, 0) -> "TRUE"
        self.assertEqual(apply_modifier(-110, {"name": "IN_RANGE", "low": -999, "high": 0}), "TRUE")

    def test_in_range_false_outside_bounds(self):
        self.assertEqual(apply_modifier(5, {"name": "IN_RANGE", "low": -999, "high": 0}), "FALSE")

    def test_in_range_false_for_missing(self):

        self.assertEqual(
            apply_modifier(MISSING, {"name": "IN_RANGE", "low": -999, "high": 0}), "FALSE"
        )

    def test_any_true_for_whitelisted_port(self):
        self.assertEqual(
            apply_modifier(6379, {"name": "ANY", "values": [80, 443, 6379, 27017]}), "TRUE"
        )

    def test_any_false_for_unlisted_port(self):
        self.assertEqual(
            apply_modifier(9999, {"name": "ANY", "values": [80, 443, 6379, 27017]}), "FALSE"
        )

    def test_unknown_modifier_raises(self):
        with self.assertRaises(ValueError):
            apply_modifier("x", "BOGUS(*)")

    # AC4: "absent OR null" must both degrade gracefully - these exercise an
    # actual JSON `null` value, distinct from an absent/missing path.
    def test_default_explicit_null_yields_null(self):
        self.assertEqual(apply_modifier(None, "DEFAULT"), "NULL")

    def test_is_present_true_for_explicit_null(self):
        self.assertEqual(apply_modifier(None, "IS_PRESENT"), "TRUE")

    def test_is_present_and_is_null_tell_missing_null_and_value_apart(self):
        record = {"a": None, "b": 1}
        fields = [
            MaskEntry(f"{key}_{name}", f"$.{key}", name)
            for key in ("a", "b", "c")
            for name in ("IS_PRESENT", "IS_NULL")
        ]
        self.assertEqual(
            tokenize(record, fields),
            {
                "a_IS_PRESENT": "TRUE",
                "a_IS_NULL": "TRUE",  # explicit null
                "b_IS_PRESENT": "TRUE",
                "b_IS_NULL": "FALSE",  # a value
                "c_IS_PRESENT": "FALSE",
                "c_IS_NULL": "FALSE",  # missing
            },
        )

    def test_is_null_true_for_explicit_null(self):
        self.assertEqual(apply_modifier(None, "IS_NULL"), "TRUE")

    def test_in_range_false_for_explicit_null(self):
        self.assertEqual(
            apply_modifier(None, {"name": "IN_RANGE", "low": -999, "high": 0}), "FALSE"
        )

    def test_any_false_for_explicit_null(self):
        self.assertEqual(apply_modifier(None, {"name": "ANY", "values": [80, 443]}), "FALSE")


class TokenizeTests(unittest.TestCase):
    def test_tokenizes_full_mask_profile_without_raising(self):
        mask_profile = [
            MaskEntry("application_binary", "$.process_exec.process.binary", "DEFAULT"),
            MaskEntry("hook_syscall", "$.process_kprobe.function_name", "DEFAULT"),
            MaskEntry("isolation_pid", "$.process_exec.process.pid", "IS_PRESENT"),
            MaskEntry(
                "network_dest_port",
                "$.process_kprobe.args[0].sock_arg.dport",
                {"name": "ANY", "values": [80, 443, 6379, 27017]},
            ),
            MaskEntry(
                "kernel_return_state",
                "$.process_kprobe.return_value",
                {"name": "IN_RANGE", "low": -999, "high": 0},
            ),
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
    """GLOB, REGEX and REGSUB (FR-MOD-01), written as mappings (STORY-FING-36)."""

    def test_glob_matches_whole_value(self):
        glob = {"name": "GLOB", "pattern": "/usr/bin/*"}
        self.assertEqual(apply_modifier("/usr/bin/node", glob), "TRUE")
        self.assertEqual(apply_modifier("/opt/usr/bin/node", glob), "FALSE")

    def test_glob_is_case_sensitive(self):
        self.assertEqual(apply_modifier("/USR/bin", {"name": "GLOB", "pattern": "/usr/*"}), "FALSE")

    def test_glob_character_class_and_question_mark(self):
        self.assertEqual(apply_modifier("eth0", {"name": "GLOB", "pattern": "eth[0-3]"}), "TRUE")
        self.assertEqual(apply_modifier("eth7", {"name": "GLOB", "pattern": "eth[0-3]"}), "FALSE")
        self.assertEqual(apply_modifier(8080, {"name": "GLOB", "pattern": "80*"}), "TRUE")

    def test_regex_searches_anywhere_unless_anchored(self):
        self.assertEqual(
            apply_modifier("/api/v2/x", {"name": "REGEX", "pattern": r"/v\d+/"}), "TRUE"
        )
        self.assertEqual(
            apply_modifier("/api/v2/x", {"name": "REGEX", "pattern": r"^/v\d+/"}), "FALSE"
        )

    def test_pattern_needs_no_quoting(self):
        self.assertEqual(apply_modifier("aaa", {"name": "REGEX", "pattern": "^a{2,3}$"}), "TRUE")
        self.assertEqual(
            apply_modifier("POST", {"name": "REGEX", "pattern": "^(GET|POST)$"}), "TRUE"
        )

    def test_regex_flags(self):
        regex = {"name": "REGEX", "pattern": "^hello", "flags": "i"}
        self.assertEqual(apply_modifier("HELLO world", regex), "TRUE")
        self.assertEqual(apply_modifier("HELLO world", {**regex, "flags": ""}), "FALSE")
        self.assertEqual(
            apply_modifier("a\nb", {"name": "REGEX", "pattern": "a.b", "flags": "s"}), "TRUE"
        )
        self.assertEqual(
            apply_modifier("x\nend", {"name": "REGEX", "pattern": "^end", "flags": "m"}), "TRUE"
        )

    def test_regsub_replaces_every_match(self):
        regsub = {"name": "REGSUB", "pattern": r"\d+", "replace": "N"}
        self.assertEqual(apply_modifier("/items/17", regsub), "/items/N")
        self.assertEqual(apply_modifier("/u/123/o/4567", regsub), "/u/N/o/N")

    def test_regsub_group_reference_empty_replacement_and_flags(self):
        subnet = {"name": "REGSUB", "pattern": r"^(\d+\.\d+)\..*$", "replace": r"\1.x.x"}
        self.assertEqual(apply_modifier("10.244.2.14", subnet), "10.244.x.x")
        strip = {"name": "REGSUB", "pattern": r"-\d+$", "replace": ""}
        self.assertEqual(apply_modifier("abc-123", strip), "abc")
        upper = {"name": "REGSUB", "pattern": "get", "replace": "R", "flags": "i"}
        self.assertEqual(apply_modifier("GET", upper), "R")

    def test_regsub_without_a_match_passes_the_value_through(self):
        regsub = {"name": "REGSUB", "pattern": r"\d+", "replace": "N"}
        self.assertEqual(apply_modifier("GET", regsub), "GET")

    def test_missing_and_null_degrade_like_the_other_modifiers(self):

        for value in (MISSING, None):
            self.assertEqual(apply_modifier(value, {"name": "GLOB", "pattern": "*"}), "FALSE")
            self.assertEqual(apply_modifier(value, {"name": "REGEX", "pattern": ".*"}), "FALSE")
            regsub = {"name": "REGSUB", "pattern": ".*", "replace": "x"}
            self.assertEqual(apply_modifier(value, regsub), "NULL")

    def test_several_matches_are_tokenized_individually(self):
        record = {"paths": ["/tmp/a1", "/tmp/b22", "/etc/passwd"]}
        glob = MaskEntry("p", "$.paths[*]", {"name": "GLOB", "pattern": "/tmp/*"})
        self.assertEqual(tokenize(record, [glob]), {"p": "FALSE,TRUE"})
        regsub = MaskEntry("p", "$.paths[*]", {"name": "REGSUB", "pattern": r"\d+", "replace": "N"})
        self.assertEqual(tokenize(record, [regsub]), {"p": "/etc/passwd,/tmp/aN,/tmp/bN"})


class ModifierObjectTests(unittest.TestCase):
    def test_mask_entry_normalises_its_modifier(self):
        entry = MaskEntry("k", "$.k", {"pattern": "a", "name": "GLOB"})
        self.assertEqual(entry.modifier, Glob(pattern="a"))
        self.assertEqual(MaskEntry("k", "$.k", "DEFAULT").modifier, Default())
        self.assertIsInstance(Modifier.build({"name": "ANY", "values": [1]}), AnyOf)

    def test_spec_is_bare_name_or_sorted_json(self):
        self.assertEqual(Modifier.build("IS_PRESENT").spec, "IS_PRESENT")
        self.assertEqual(Modifier.build({"name": "IS_PRESENT"}).spec, "IS_PRESENT")
        spec = Modifier.build({"values": [80, 443], "name": "ANY"}).spec
        self.assertEqual(spec, '{"name":"ANY","values":[80,443]}')

    def test_modifiers_are_hashable(self):
        self.assertEqual(len({Modifier.build({"name": "ANY", "values": [1]}) for _ in range(2)}), 1)


class ValidateModifierFormTests(unittest.TestCase):
    def test_valid_forms_pass(self):
        for modifier in (
            "DEFAULT",
            "IS_PRESENT",
            "IS_NULL",
            {"name": "IS_NULL"},
            {"name": "IN_RANGE", "low": 200, "high": 399.5},
            {"name": "ANY", "values": ["GET", 80]},
            {"name": "GLOB", "pattern": "/usr/*"},
            {"name": "REGEX", "pattern": "^(GET|POST)$", "flags": "imsx"},
            {"name": "REGSUB", "pattern": r"(?P<n>\d+)", "replace": r"<\g<n>>"},
            {"name": "REGSUB", "pattern": r"\d+", "replace": ""},
        ):
            with self.subTest(modifier=modifier):
                validate_modifier(modifier)

    def test_invalid_forms_say_what_is_wrong(self):
        cases = [
            ("IN_RANGE(200, 399)", "'IN_RANGE(200, 399)' is not one of"),
            ("GLOB", "GLOB needs arguments (pattern); write it as {name: GLOB, pattern: ...}"),
            ({"pattern": "a"}, "'name' is a required property"),
            ({"name": "REGX", "pattern": "a"}, "name: 'REGX' is not one of"),
            ({"name": "REGEX"}, "'pattern' is a required property"),
            ({"name": "REGSUB", "pattern": "a"}, "'replace' is a required property"),
            ({"name": "GLOB", "pattern": "a", "flags": "i"}, "('flags' was unexpected)"),
            ({"name": "DEFAULT", "x": 1}, "('x' was unexpected)"),
            ({"name": "REGEX", "pattern": "("}, "Invalid regex"),
            ({"name": "REGEX", "pattern": "a", "flags": "iq"}, "flags: 'iq' does not match"),
            ({"name": "REGEX", "pattern": 12}, "pattern: 12 is not of type 'string'"),
            ({"name": "REGSUB", "pattern": "a", "replace": r"\2"}, "REGSUB replace is not valid"),
            ({"name": "IN_RANGE", "low": "a", "high": 1}, "low: 'a' is not of type 'number'"),
            ({"name": "IN_RANGE", "low": True, "high": 1}, "low: True is not of type 'number'"),
            ({"name": "IN_RANGE", "low": 5, "high": 1}, "IN_RANGE low (5) is above high (1)"),
            ({"name": "ANY", "values": []}, "values: [] should be non-empty"),
            ({"name": "ANY", "values": 80}, "values: 80 is not of type 'array'"),
            (["GLOB"], "['GLOB'] is not of type 'object'"),
        ]
        for modifier, expected in cases:
            with self.subTest(modifier=modifier):
                with self.assertRaises(ValueError) as ctx:
                    validate_modifier(modifier)
                self.assertIn(expected, str(ctx.exception))
