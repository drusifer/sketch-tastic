"""Tests for fingerprint profile files."""

import os
import tempfile
import textwrap
import unittest

import yaml

from fingerprint_sampler.aggregators import AggregateEntry
from fingerprint_sampler.profile import (
    Profile,
    ProfileError,
    load_profile,
    parse_profile,
    profile_id,
)
from fingerprint_sampler.tokenizer import MaskEntry, tokenize

EXAMPLE_PROFILES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples"
)

VALID = {
    "version": 1,
    "fields": [
        {"key": "syscall", "path": "$.fn", "modifier": "DEFAULT"},
        {
            "key": "port_ok",
            "path": "$.args[*].dport",
            "modifier": {"name": "ANY", "values": [80, 443]},
        },
    ],
    "aggregates": [
        {"key": "duration", "path": "$.ms", "fn": ["MIN", "max", "AVG"]},
        {"key": "samples", "path": "$", "fn": "LAST(3)"},
    ],
}


def variant(**changes):
    data = {k: (list(v) if isinstance(v, list) else v) for k, v in VALID.items()}
    data.update(changes)
    return data


class ParseProfileTests(unittest.TestCase):
    def test_builds_fields_and_aggregates(self):
        profile = parse_profile(VALID)
        self.assertEqual(
            profile.fields,
            (
                MaskEntry("syscall", "$.fn", "DEFAULT"),
                MaskEntry("port_ok", "$.args[*].dport", {"name": "ANY", "values": [80, 443]}),
            ),
        )
        self.assertEqual(
            profile.aggregates,
            (
                AggregateEntry("duration", "$.ms", ("MIN", "MAX", "AVG")),
                AggregateEntry("samples", "$", ("LAST(3)",)),
            ),
        )

    def test_fields_work_directly_with_the_existing_tokenize_api(self):
        profile = parse_profile(VALID)
        tokens = tokenize({"fn": "sys_connect", "args": [{"dport": 443}]}, list(profile.fields))
        self.assertEqual(tokens, {"syscall": "sys_connect", "port_ok": "TRUE"})

    def test_modifier_defaults_to_default_and_aggregates_are_optional(self):
        profile = parse_profile({"fields": [{"key": "k", "path": "$.k"}]})
        self.assertEqual(profile.fields, (MaskEntry("k", "$.k", "DEFAULT"),))
        self.assertEqual(profile.aggregates, ())


class ValidationTests(unittest.TestCase):
    def assert_invalid(self, data, *fragments):
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(data, source="p.yaml")
        message = str(ctx.exception)
        for fragment in ("p.yaml",) + fragments:
            self.assertIn(fragment, message)

    def test_missing_or_empty_fields(self):
        self.assert_invalid({"version": 1}, "'fields' must be a non-empty list")
        self.assert_invalid(variant(fields=[]), "'fields' must be a non-empty list")

    def test_not_a_mapping(self):
        self.assert_invalid(["nope"], "expected a mapping")

    def test_unknown_modifier_names_the_entry(self):
        fields = [{"key": "bin", "path": "$.b", "modifier": "BOGUS(*)"}]
        self.assert_invalid(variant(fields=fields), "fields[0]", "'bin'", "Unknown modifier")

    def test_invalid_regex_names_the_entry(self):
        fields = [{"key": "bin", "path": "$.b", "modifier": {"name": "REGEX", "pattern": "[a-"}}]
        self.assert_invalid(variant(fields=fields), "fields[0]", "'bin'", "Invalid regex")

    def test_bad_modifier_arguments(self):
        fields = [{"key": "rc", "path": "$.rc", "modifier": {"name": "IN_RANGE", "low": 0}}]
        self.assert_invalid(variant(fields=fields), "'rc'", "IN_RANGE needs 'high'")

    def test_bad_path_names_the_entry(self):
        fields = VALID["fields"] + [{"key": "broken", "path": "$.a[", "modifier": "DEFAULT"}]
        self.assert_invalid(variant(fields=fields), "fields[2]", "'broken'", "Invalid JSONPath")

    def test_unknown_aggregator_names_the_entry(self):
        aggregates = [{"key": "lat", "path": "$.ms", "fn": "MEDIAN"}]
        self.assert_invalid(variant(aggregates=aggregates), "aggregates[0]", "'lat'", "MEDIAN")

    def test_aggregate_without_fn(self):
        self.assert_invalid(
            variant(aggregates=[{"key": "lat", "path": "$.ms"}]), "'lat'", "'fn' is required"
        )

    def test_duplicate_keys(self):
        fields = [{"key": "a", "path": "$.a"}, {"key": "a", "path": "$.b"}]
        self.assert_invalid(variant(fields=fields), "duplicate key(s) in fields: a")
        aggregates = [
            {"key": "x", "path": "$.a", "fn": "SUM"},
            {"key": "x", "path": "$.b", "fn": "SUM"},
        ]
        self.assert_invalid(variant(aggregates=aggregates), "duplicate key(s) in aggregates: x")

    def test_misspelled_setting_is_caught_not_ignored(self):
        fields = [{"key": "a", "path": "$.a", "modifer": "IS_PRESENT"}]
        self.assert_invalid(variant(fields=fields), "'a'", "unknown setting(s) ['modifer']")
        self.assert_invalid(variant(agregates=[]), "unknown top-level setting(s) ['agregates']")

    def test_missing_key_or_path(self):
        self.assert_invalid(variant(fields=[{"path": "$.a"}]), "fields[0]", "'key' is required")
        self.assert_invalid(variant(fields=[{"key": "a"}]), "'a'", "'path' is required")

    def test_unsupported_version(self):
        self.assert_invalid(variant(version=2), "version 2")


class ValidateModifierTests(unittest.TestCase):
    def test_mapping_modifiers_load_from_yaml(self):
        data = yaml.safe_load(
            r"""
fields:
  - key: route
    path: $.path
    modifier: {name: REGSUB, pattern: '\d+', replace: N}
  - key: greeting
    path: $.text
    modifier:
      name: REGEX
      pattern: ^hello\s.*\sgoodbye\.$
      flags: i
"""
        )
        profile = parse_profile(data)
        tokens = tokenize(
            {"path": "/items/17", "text": "Hello there goodbye."}, list(profile.fields)
        )
        self.assertEqual(tokens, {"route": "/items/N", "greeting": "TRUE"})


class ProfileIdTests(unittest.TestCase):
    def test_is_32_char_hex_and_stable(self):
        pid = parse_profile(VALID).profile_id
        self.assertEqual(len(pid), 32)
        int(pid, 16)
        self.assertEqual(pid, parse_profile(VALID).profile_id)

    def test_independent_of_field_order(self):
        reordered = variant(fields=list(reversed(VALID["fields"])))
        self.assertEqual(parse_profile(reordered).profile_id, parse_profile(VALID).profile_id)

    def test_unaffected_by_aggregates(self):
        self.assertEqual(
            parse_profile(variant(aggregates=[])).profile_id, parse_profile(VALID).profile_id
        )

    def test_mapping_key_order_does_not_change_the_id(self):
        one = {"name": "REGSUB", "pattern": "a", "replace": "b"}
        two = {"replace": "b", "pattern": "a", "name": "REGSUB"}
        ids = {
            parse_profile({"fields": [{"key": "k", "path": "$.k", "modifier": m}]}).profile_id
            for m in (one, two)
        }
        self.assertEqual(len(ids), 1)

    def test_changes_when_identity_changes(self):
        base = parse_profile(VALID).profile_id
        changed_modifier = variant(
            fields=[
                VALID["fields"][0],
                {**VALID["fields"][1], "modifier": {"name": "ANY", "values": [80]}},
            ]
        )
        changed_path = variant(
            fields=[{**VALID["fields"][0], "path": "$.other"}, VALID["fields"][1]]
        )
        dropped_field = variant(fields=VALID["fields"][:1])
        for data in (changed_modifier, changed_path, dropped_field):
            self.assertNotEqual(parse_profile(data).profile_id, base)

    def test_matches_module_function_for_python_built_profiles(self):
        fields = (MaskEntry("syscall", "$.fn", "DEFAULT"),)
        self.assertEqual(Profile(fields=fields).profile_id, profile_id(fields))


class LoadProfileTests(unittest.TestCase):
    def write(self, text):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        self.addCleanup(os.unlink, tmp.name)
        tmp.write(textwrap.dedent(text))
        tmp.close()
        return tmp.name

    def test_loads_yaml_file(self):
        path = self.write(
            """
            version: 1
            fields:
              - {key: syscall, path: "$.fn"}
            aggregates:
              - {key: d, path: "$.ms", fn: [MIN, MAX]}
            """
        )
        profile = load_profile(path)
        self.assertEqual(profile.fields[0].key, "syscall")
        self.assertEqual(profile.aggregates[0].fns, ("MIN", "MAX"))

    def test_missing_file_and_invalid_yaml_raise_profile_error_naming_the_file(self):
        with self.assertRaises(ProfileError) as ctx:
            load_profile("/nonexistent/profile.yaml")
        self.assertIn("/nonexistent/profile.yaml", str(ctx.exception))

        path = self.write("fields: [unclosed")
        with self.assertRaises(ProfileError) as ctx:
            load_profile(path)
        self.assertIn(path, str(ctx.exception))

    def test_validation_error_from_file_names_file_and_entry(self):
        path = self.write(
            """
            fields:
              - {key: bad, path: "$.a[?(@.b ==]"}
            """
        )
        with self.assertRaises(ProfileError) as ctx:
            load_profile(path)
        self.assertIn(path, str(ctx.exception))
        self.assertIn("'bad'", str(ctx.exception))

    def test_every_shipped_example_profile_loads(self):
        names = sorted(n for n in os.listdir(EXAMPLE_PROFILES) if n.endswith(".yaml"))
        self.assertGreaterEqual(len(names), 1)
        for name in names:
            with self.subTest(profile=name):
                profile = load_profile(os.path.join(EXAMPLE_PROFILES, name))
                self.assertTrue(profile.fields)


if __name__ == "__main__":
    unittest.main()
