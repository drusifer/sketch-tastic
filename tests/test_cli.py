"""Tests for the `fingerprint merge` and `fingerprint check` CLI."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

import yaml

from fingerprint_sampler.cli import main
from fingerprint_sampler.profile import load_profile

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCESS_PROFILE = os.path.join(PACKAGE_ROOT, "examples", "access_log.yaml")
ACCESS_EVENTS = os.path.join(PACKAGE_ROOT, "examples", "access_log.jsonl")

PROFILE = """
version: 0
fields:
  - {key: kind, path: "$.kind"}
aggregates:
  - {key: size, path: "$.size", fn: [SUM, AVG, MIN, MAX]}
  - {key: recent, path: "$.id", fn: {name: LAST, n: 2}}
"""
OTHER_PROFILE = """
version: 0
fields:
  - {key: kind, path: "$.kind", modifier: IS_PRESENT}
"""


class FakeStdin(io.StringIO):
    def __init__(self, text="", tty=False):
        super().__init__(text)
        self._tty = tty

    def isatty(self):
        return self._tty


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        self.profile = self.write("profile.yaml", PROFILE)
        self.set_path = os.path.join(self.dir, "set.yaml")

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w") as f:
            f.write(textwrap.dedent(text))
        return path

    def write_events(self, name, events):
        return self.write(name, "".join(json.dumps(e) + "\n" for e in events))

    def run_cli(self, *argv, stdin=None):
        """Run the CLI in-process. Returns (exit_code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with mock.patch.object(sys, "stdin", stdin or FakeStdin(tty=True)):
                try:
                    code = main(list(argv))
                except SystemExit as exc:  # argparse usage errors / --help
                    code = exc.code
        return code, out.getvalue(), err.getvalue()

    def fingerprint(self, events_path, *extra, **kwargs):
        return self.run_cli(
            "merge", "-p", self.profile, "-s", self.set_path, events_path, *extra, **kwargs
        )

    def load_set(self, path=None):
        with open(path or self.set_path) as f:
            return yaml.safe_load(f)

    @staticmethod
    def without_timestamps(data):
        """Set contents minus wall-clock fields, for comparing sets built at different times."""

        def strip(rec):
            meta = dict(rec["meta"])
            meta.pop("first_seen")
            meta.pop("last_seen")
            for key in ("first", "last"):
                meta[key] = [envelope["record"] for envelope in meta[key]]
            return {**rec, "meta": meta}

        return {fid: strip(rec) for fid, rec in data["fingerprints"].items()}


EVENTS = [
    {"id": 1, "kind": "a", "size": 10},
    {"id": 2, "kind": "b", "size": 4},
    {"id": 3, "kind": "a", "size": 30},
    {"id": 4, "kind": "a", "size": 0.5},
    {"id": 5, "kind": "c"},
    {"id": 6, "kind": "b", "size": "6"},
]


class CreateAndMergeTests(CliTestCase):
    def test_first_run_creates_the_set(self):
        code, out, err = self.fingerprint(self.write_events("e.jsonl", EVENTS))

        self.assertEqual(code, 0)
        self.assertEqual(out, "")  # AC7: stdout stays clean
        data = self.load_set()
        self.assertEqual(data["version"], 0)
        self.assertEqual(len(data["fingerprints"]), 3)
        by_kind = {rec["tokens"]["kind"]: rec for rec in data["fingerprints"].values()}
        self.assertEqual(by_kind["a"]["meta"]["count"], 3)
        self.assertEqual(by_kind["a"]["aggregates"]["size"]["SUM"], 40.5)
        self.assertEqual(by_kind["a"]["aggregates"]["size"]["AVG"]["avg"], 13.5)  # AC12: readable
        self.assertEqual(by_kind["a"]["aggregates"]["recent"], [3, 4])
        self.assertNotIn("size", by_kind["c"]["aggregates"])

    def test_second_run_merges_into_existing_fingerprints(self):
        self.fingerprint(self.write_events("run1.jsonl", EVENTS[:3]))
        first = self.load_set()
        code, _, err = self.fingerprint(self.write_events("run2.jsonl", EVENTS[3:]))

        self.assertEqual(code, 0)
        merged = self.load_set()
        by_kind = {rec["tokens"]["kind"]: (fid, rec) for fid, rec in merged["fingerprints"].items()}
        fid_a, rec_a = by_kind["a"]
        self.assertEqual(rec_a["meta"]["count"], 3)  # 2 + 1: counts add
        self.assertEqual(rec_a["aggregates"]["size"]["SUM"], 40.5)  # aggregates merge
        self.assertEqual(rec_a["aggregates"]["recent"], [3, 4])  # LAST continues
        self.assertEqual(
            rec_a["meta"]["first_seen"], first["fingerprints"][fid_a]["meta"]["first_seen"]
        )
        self.assertIn("c", by_kind)  # new fingerprint appended

    def _fingerprints_line(self, err):
        return next(line for line in err.splitlines() if "fingerprints:" in line)

    def test_summary_reports_new_updated_total_and_skips(self):
        _, _, err1 = self.fingerprint(self.write_events("run1.jsonl", EVENTS[:3]))
        self.assertIn("3 events read", err1)
        self.assertIn("2 new, 0 updated, 2 total in set", self._fingerprints_line(err1))

        _, _, err2 = self.fingerprint(self.write_events("run2.jsonl", EVENTS[3:]))
        self.assertIn("1 new, 2 updated, 3 total in set", self._fingerprints_line(err2))
        self.assertIn("0 malformed lines, 1 aggregate values", err2)  # event 5 has no size

    def test_batch_and_split_runs_produce_equivalent_sets(self):
        # AC3: one batch == the same events split over several runs, at every split point.
        batch_set = os.path.join(self.dir, "batch.yaml")
        self.run_cli(
            "merge",
            "-p",
            self.profile,
            "-s",
            batch_set,
            self.write_events("all.jsonl", EVENTS),
        )
        expected = self.without_timestamps(self.load_set(batch_set))

        for cut in range(1, len(EVENTS)):
            with self.subTest(cut=cut):
                split_set = os.path.join(self.dir, f"split{cut}.yaml")
                for part, events in (("x", EVENTS[:cut]), ("y", EVENTS[cut:])):
                    path = self.write_events(f"{part}{cut}.jsonl", events)
                    self.run_cli("merge", "-p", self.profile, "-s", split_set, path)
                self.assertEqual(self.without_timestamps(self.load_set(split_set)), expected)

    def test_reads_events_from_stdin(self):
        text = "".join(json.dumps(e) + "\n" for e in EVENTS)
        for events_arg in (["-"], []):
            with self.subTest(events_arg=events_arg):
                set_path = os.path.join(self.dir, f"stdin{len(events_arg)}.yaml")
                code, _, err = self.run_cli(
                    "merge",
                    "-p",
                    self.profile,
                    "-s",
                    set_path,
                    *events_arg,
                    stdin=FakeStdin(text),
                )
                self.assertEqual(code, 0)
                self.assertIn("6 events read from stdin", err)
                self.assertEqual(len(self.load_set(set_path)["fingerprints"]), 3)

    def test_output_flag_leaves_the_set_untouched(self):
        self.fingerprint(self.write_events("run1.jsonl", EVENTS[:3]))
        with open(self.set_path) as f:
            before = f.read()
        preview = os.path.join(self.dir, "preview.yaml")

        code, _, err = self.fingerprint(self.write_events("run2.jsonl", EVENTS[3:]), "-o", preview)

        self.assertEqual(code, 0)
        with open(self.set_path) as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(len(self.load_set(preview)["fingerprints"]), 3)
        self.assertIn("left unchanged", err)


class NonTelemetryFixtureTests(CliTestCase):
    """AC8: the tool is not eBPF-specific — web access-log events, filter-expression field."""

    def test_access_log_fixture(self):
        code, _, err = self.run_cli(
            "merge", "-p", ACCESS_PROFILE, "-s", self.set_path, ACCESS_EVENTS
        )

        self.assertEqual(code, 0, err)
        records = list(self.load_set()["fingerprints"].values())
        by_shape = {
            (r["tokens"]["method"], r["tokens"]["route"], r["tokens"]["status_class"]): r
            for r in records
        }
        self.assertEqual(len(records), 4)

        ok_items = by_shape[("GET", "/items/{id}", "TRUE")]
        self.assertEqual(ok_items["meta"]["count"], 3)
        self.assertEqual(ok_items["aggregates"]["bytes_out"], 512 + 498 + 505)
        self.assertEqual(ok_items["aggregates"]["latency_ms"]["MIN"], 9.0)
        self.assertEqual(
            ok_items["aggregates"]["recent_paths"], ["/items/17", "/items/42", "/items/3"]
        )

        self.assertEqual(by_shape[("GET", "/items/{id}", "FALSE")]["meta"]["count"], 1)  # the 404

        orders = by_shape[("POST", "/orders", "TRUE")]
        self.assertEqual(
            orders["tokens"]["slow_upstreams"], "payments"
        )  # from the [?(@.ms > 500)] filter
        self.assertEqual(orders["aggregates"]["latency_ms"]["MAX"], 910.0)

        health = by_shape[("GET", "/health", "TRUE")]
        self.assertEqual(health["tokens"]["authenticated"], "FALSE")
        self.assertEqual(health["tokens"]["slow_upstreams"], "NULL")


class BadInputTests(CliTestCase):
    def test_malformed_lines_are_skipped_reported_and_reflected_in_exit_status(self):
        path = self.write(
            "mixed.jsonl",
            '{"id": 1, "kind": "a", "size": 1}\n'
            "{not json}\n"
            "\n"
            "[1, 2, 3]\n"
            '{"id": 2, "kind": "a", "size": 2}\n',
        )
        code, _, err = self.fingerprint(path)

        self.assertEqual(code, 1)
        self.assertIn("line 2: invalid JSON", err)
        self.assertIn("line 4: expected a JSON object, got list", err)
        self.assertIn("2 events read", err)
        self.assertIn("2 malformed lines", err)
        self.assertEqual(len(self.load_set()["fingerprints"]), 1)  # the good lines still landed

    def test_many_bad_lines_do_not_flood_stderr(self):
        path = self.write("bad.jsonl", "nope\n" * 50)
        code, _, err = self.fingerprint(path)
        self.assertEqual(code, 1)
        self.assertEqual(err.count("invalid JSON"), 10)
        self.assertIn("further skipped lines are counted but not listed", err)
        self.assertIn("50 malformed lines", err)

    def test_terminal_stdin_explains_instead_of_hanging(self):
        code, _, err = self.run_cli(
            "merge", "-p", self.profile, "-s", self.set_path, stdin=FakeStdin(tty=True)
        )
        self.assertEqual(code, 2)
        self.assertIn("no events to read", err)
        self.assertFalse(os.path.exists(self.set_path))

    def test_invalid_profile_fails_before_reading_events(self):
        bad = self.write("bad.yaml", "fields:\n  - {key: k, path: '$.a[', modifier: DEFAULT}\n")
        code, _, err = self.run_cli(
            "merge", "-p", bad, "-s", self.set_path, self.write_events("e.jsonl", EVENTS)
        )
        self.assertEqual(code, 2)
        self.assertIn("'k'", err)
        self.assertIn("Invalid JSONPath", err)
        self.assertFalse(os.path.exists(self.set_path))

    def test_missing_profile_and_missing_events_file(self):
        code, _, err = self.run_cli("merge", "-p", "/no/such.yaml", "-s", self.set_path, "x.jsonl")
        self.assertEqual(code, 2)
        self.assertIn("/no/such.yaml", err)

        code, _, err = self.fingerprint(os.path.join(self.dir, "missing.jsonl"))
        self.assertEqual(code, 2)
        self.assertIn("missing.jsonl", err)
        self.assertFalse(os.path.exists(self.set_path))

    def test_unusable_set_file_is_refused_and_left_alone(self):
        with open(self.set_path, "w") as f:
            f.write("just: some other yaml\n")
        code, _, err = self.fingerprint(self.write_events("e.jsonl", EVENTS))
        self.assertEqual(code, 2)
        self.assertIn("not a fingerprint set", err)
        with open(self.set_path) as f:
            self.assertEqual(f.read(), "just: some other yaml\n")

    def test_unwritable_destination(self):
        code, _, err = self.run_cli(
            "merge",
            "-p",
            self.profile,
            "-s",
            os.path.join(self.dir, "no-dir", "set.yaml"),
            self.write_events("e.jsonl", EVENTS),
        )
        self.assertEqual(code, 2)
        self.assertIn("cannot write", err)

    def test_missing_required_arguments_is_a_usage_error(self):
        code, _, err = self.run_cli("merge", "-s", self.set_path)
        self.assertEqual(code, 2)
        self.assertIn("--profile", err)


class CheckTests(CliTestCase):
    """STORY-FING-37: fingerprint check."""

    def test_valid_profiles_print_ok_and_exit_0(self):
        good = self.write("good.yaml", PROFILE)
        code, out, _ = self.run_cli("check", good, ACCESS_PROFILE)
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), [f"{good}: OK", f"{ACCESS_PROFILE}: OK"])

    def test_every_problem_is_listed_with_its_location_and_exit_1(self):
        bad = self.write(
            "bad.yaml",
            textwrap.dedent(
                """\
                fields:
                  - key: route
                    path: $.p
                    modifier: {name: REGSUB, pattern: '\\d+'}
                  - key: method
                    path: $.m
                    modifier: {name: REGEX, pattern: '(', flags: q}
                """
            ),
        )
        code, out, _ = self.run_cli("check", bad)
        self.assertEqual(code, 1)
        self.assertEqual(
            out.splitlines(),
            [
                f"{bad}: fields[0] (key 'route') → modifier: 'replace' is a required property",
                f"{bad}: fields[1] (key 'method') → modifier.flags: 'q' does not match '^[imsx]*$'",
            ],
        )

    def test_semantic_problems_use_the_same_format(self):
        bad = self.write(
            "bad.yaml", "fields:\n  - {key: m, path: $.m, modifier: {name: REGEX, pattern: '('}}\n"
        )
        code, out, _ = self.run_cli("check", bad)
        self.assertEqual(code, 1)
        self.assertIn(f"{bad}: fields[0] (key 'm'): Invalid regex '('", out)

    def test_yaml_syntax_error_gives_line_and_column(self):
        bad = self.write("bad.yaml", "fields:\n  - {key: a, path: $.a\n")
        code, out, _ = self.run_cli("check", bad)
        self.assertEqual(code, 1)
        self.assertRegex(out, rf"^{bad}: line \d+, column \d+: not valid YAML")

    def test_one_bad_profile_among_several(self):
        good = self.write("good.yaml", PROFILE)
        code, out, _ = self.run_cli("check", good, "/no/such.yaml")
        self.assertEqual(code, 1)
        self.assertIn(f"{good}: OK", out)
        self.assertIn("Cannot read profile /no/such.yaml", out)

    def test_merge_runs_the_same_check_and_writes_nothing(self):
        bad = self.write("bad.yaml", "fields:\n  - {key: s, path: $.s, modifier: GLOB}\n")
        code, _, err = self.run_cli(
            "merge", "-p", bad, "-s", self.set_path, self.write_events("e.jsonl", EVENTS)
        )
        self.assertEqual(code, 2)
        self.assertIn(f"fingerprint: {bad}: fields[0] (key 's') → modifier:", err)
        self.assertIn(f"check {bad}' lists the same problems", err)
        self.assertFalse(os.path.exists(self.set_path))


class GoldenFingerprintTests(CliTestCase):
    """STORY-FING-39 AC5: the README quickstart gives the ids it has always documented."""

    QUICKSTART_PROFILE = """
version: 0
fields:
  - {key: level,     path: "$.level"}
  - {key: component, path: "$.logger"}
  - {key: failed,    path: "$.error", modifier: IS_PRESENT}
aggregates:
  - {key: took_ms, path: "$.took_ms", fn: [MIN, MAX, AVG]}
  - {key: example, path: "$.msg",     fn: {name: LAST, n: 2}}
"""
    QUICKSTART_EVENTS = [
        {"level": "INFO", "logger": "db", "msg": "query ok", "took_ms": 3},
        {"level": "INFO", "logger": "db", "msg": "query ok (cached)", "took_ms": 1},
        {
            "level": "ERROR",
            "logger": "db",
            "msg": "query timed out",
            "error": "TimeoutError",
            "took_ms": 5000,
        },
        {"level": "INFO", "logger": "http", "msg": "GET /health", "took_ms": 0.4},
    ]

    def test_profile_id_and_fingerprint_ids_are_stable(self):
        profile = self.write("profile.yaml", self.QUICKSTART_PROFILE)
        events = self.write_events("events.jsonl", self.QUICKSTART_EVENTS)
        code, _, _ = self.run_cli("merge", "-p", profile, "-s", self.set_path, events)
        self.assertEqual(code, 0)
        data = self.load_set()
        self.assertEqual(data["profile_id"], "f50d7a5f85ddf9f7f4c72370f454ae2e")
        self.assertEqual(len(data["fingerprints"]), 3)
        db_ok = data["fingerprints"]["b738d17a6a5f7265cb4cef73937afd4f"]
        self.assertEqual(db_ok["tokens"], {"level": "INFO", "component": "db", "failed": "FALSE"})
        self.assertEqual(db_ok["meta"]["count"], 2)
        self.assertEqual(db_ok["aggregates"]["example"], ["query ok", "query ok (cached)"])


class ProfileMismatchTests(CliTestCase):
    def setUp(self):
        super().setUp()
        self.fingerprint(self.write_events("run1.jsonl", EVENTS))
        with open(self.set_path) as f:
            self.before = f.read()
        self.other = self.write("other.yaml", OTHER_PROFILE)
        self.events = self.write_events("run2.jsonl", EVENTS)

    def test_merge_with_a_different_profile_is_refused(self):
        code, _, err = self.run_cli("merge", "-p", self.other, "-s", self.set_path, self.events)

        self.assertEqual(code, 2)
        self.assertIn(yaml.safe_load(self.before)["profile_id"], err)  # AC13: names both IDs...
        self.assertIn(load_profile(self.other).profile_id, err)
        self.assertIn("--force-profile", err)  # ...and the override flag
        with open(self.set_path) as f:
            self.assertEqual(f.read(), self.before)

    def test_force_profile_overrides(self):
        code, _, _ = self.run_cli(
            "merge", "-p", self.other, "-s", self.set_path, self.events, "--force-profile"
        )
        self.assertEqual(code, 0)
        data = self.load_set()
        self.assertNotEqual(data["profile_id"], yaml.safe_load(self.before)["profile_id"])
        self.assertEqual(len(data["fingerprints"]), 4)  # 3 kept + 1 under the new profile

    def test_changing_only_aggregates_is_not_a_mismatch(self):
        tweaked = self.write("tweaked.yaml", PROFILE.replace("n: 2}", "n: 5}"))
        code, _, _ = self.run_cli("merge", "-p", tweaked, "-s", self.set_path, self.events)
        self.assertEqual(code, 0)


class AtomicWriteTests(CliTestCase):
    def test_failed_write_leaves_previous_set_intact(self):
        self.fingerprint(self.write_events("run1.jsonl", EVENTS[:3]))
        with open(self.set_path) as f:
            before = f.read()

        with mock.patch(
            "fingerprint_sampler.fingerprint_set.os.replace",
            side_effect=OSError(28, "No space left on device"),
        ):
            code, _, err = self.fingerprint(self.write_events("run2.jsonl", EVENTS[3:]))

        self.assertEqual(code, 2)
        self.assertIn("cannot write", err)
        with open(self.set_path) as f:
            self.assertEqual(f.read(), before)
        leftovers = [n for n in os.listdir(self.dir) if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])


class EntryPointTests(unittest.TestCase):
    """The real `python -m fingerprint_sampler` process, not just main()."""

    def run_module(self, *argv, **kwargs):
        return subprocess.run(
            [sys.executable, "-m", "fingerprint_sampler", *argv],
            cwd=PACKAGE_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            **kwargs,
        )

    def test_help_has_worked_example_and_in_place_warning(self):
        result = self.run_module("merge", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage: fingerprint merge", result.stdout)
        self.assertIn("example:", result.stdout)
        self.assertIn("updated in place", result.stdout)
        self.assertIn("--force-profile", result.stdout)
        self.assertIn("exit status:", result.stdout)

    def test_pipeline_end_to_end_via_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            set_path = os.path.join(tmp, "set.yaml")
            with open(ACCESS_EVENTS) as events:
                result = self.run_module(
                    "merge", "-p", ACCESS_PROFILE, "-s", set_path, "-", stdin=events
                )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertIn("8 events read from stdin", result.stderr)
            self.assertIn("4 new, 0 updated, 4 total in set", result.stderr)

    def test_version_flag(self):
        result = self.run_module("--version")
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, r"^fingerprint-sampler \d+\.\d+\.\d+")


if __name__ == "__main__":
    unittest.main()
