"""Tests for the `fingerprint merge`, `check` and `show` CLI."""

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import UTC, date, datetime
from unittest import mock

import yaml

from sketchtastic.aggregators import Aggregate
from sketchtastic.cli import _history_dir, _next_run_id, main
from sketchtastic.profile import load_profile
from sketchtastic.sketch import Sketch, skit_id

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
        self.sketch_path = os.path.join(self.dir, "set.yaml")

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
            "merge", "-p", self.profile, "-s", self.sketch_path, events_path, *extra, **kwargs
        )

    def load_set(self, path=None):
        with open(path or self.sketch_path) as f:
            return yaml.safe_load(f)

    @staticmethod
    def without_timestamps(data):
        """Set contents minus run ids, for comparing sets built over different runs."""

        def strip(rec):
            meta = dict(rec["meta"])
            meta.pop("first_seen")
            meta.pop("last_seen")
            for key in ("first", "last"):
                meta[key] = [envelope["record"] for envelope in meta[key]]
            return {**rec, "meta": meta}

        return {fid: strip(rec) for fid, rec in data["skits"].items()}


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
        self.assertEqual(len(data["skits"]), 3)
        by_kind = {rec["tokens"]["kind"]: rec for rec in data["skits"].values()}
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
        by_kind = {rec["tokens"]["kind"]: (fid, rec) for fid, rec in merged["skits"].items()}
        fid_a, rec_a = by_kind["a"]
        self.assertEqual(rec_a["meta"]["count"], 3)  # 2 + 1: counts add
        self.assertEqual(rec_a["aggregates"]["size"]["SUM"], 40.5)  # aggregates merge
        self.assertEqual(rec_a["aggregates"]["recent"], [3, 4])  # LAST continues
        today = datetime.now(UTC).strftime("%y%m%d")
        self.assertEqual(first["last_run"], f"{today}-0001")
        self.assertEqual(merged["last_run"], f"{today}-0002")
        self.assertEqual(rec_a["meta"]["first_seen"], f"{today}-0001")  # the run, not a time
        self.assertEqual(rec_a["meta"]["last_seen"], f"{today}-0002")
        self.assertEqual(rec_a["meta"]["last"][0]["meta"], {"run": f"{today}-0002"})
        self.assertIn("c", by_kind)  # new fingerprint appended

    def _fingerprints_line(self, err):
        return next(line for line in err.splitlines() if "skits:" in line)

    def test_summary_reports_new_updated_total_and_skips(self):
        _, _, err1 = self.fingerprint(self.write_events("run1.jsonl", EVENTS[:3]))
        self.assertIn("3 events read", err1)
        self.assertIn("2 new, 0 updated, 2 total in sketch", self._fingerprints_line(err1))

        _, _, err2 = self.fingerprint(self.write_events("run2.jsonl", EVENTS[3:]))
        self.assertIn("1 new, 2 updated, 3 total in sketch", self._fingerprints_line(err2))
        self.assertIn("0 malformed lines, 0 unusable aggregate values", err2)  # no size: not a skip

    def test_present_but_unusable_value_is_counted(self):
        _, _, err = self.fingerprint(self.write_events("bad.jsonl", [{"kind": "a", "size": "big"}]))
        self.assertIn("0 malformed lines, 1 unusable aggregate values", err)

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
                sketch_path = os.path.join(self.dir, f"stdin{len(events_arg)}.yaml")
                code, _, err = self.run_cli(
                    "merge",
                    "-p",
                    self.profile,
                    "-s",
                    sketch_path,
                    *events_arg,
                    stdin=FakeStdin(text),
                )
                self.assertEqual(code, 0)
                self.assertIn("6 events read from stdin", err)
                self.assertEqual(len(self.load_set(sketch_path)["skits"]), 3)

    def test_output_flag_leaves_the_set_untouched(self):
        self.fingerprint(self.write_events("run1.jsonl", EVENTS[:3]))
        with open(self.sketch_path) as f:
            before = f.read()
        preview = os.path.join(self.dir, "preview.yaml")

        code, _, err = self.fingerprint(self.write_events("run2.jsonl", EVENTS[3:]), "-o", preview)

        self.assertEqual(code, 0)
        with open(self.sketch_path) as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(len(self.load_set(preview)["skits"]), 3)
        self.assertIn("left unchanged", err)


class NonTelemetryFixtureTests(CliTestCase):
    """AC8: the tool is not eBPF-specific — web access-log events, filter-expression field."""

    def test_access_log_fixture(self):
        code, _, err = self.run_cli(
            "merge", "-p", ACCESS_PROFILE, "-s", self.sketch_path, ACCESS_EVENTS
        )

        self.assertEqual(code, 0, err)
        records = list(self.load_set()["skits"].values())
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
        self.assertEqual(len(self.load_set()["skits"]), 1)  # the good lines still landed

    def test_many_bad_lines_do_not_flood_stderr(self):
        path = self.write("bad.jsonl", "nope\n" * 50)
        code, _, err = self.fingerprint(path)
        self.assertEqual(code, 1)
        self.assertEqual(err.count("invalid JSON"), 10)
        self.assertIn("further skipped lines are counted but not listed", err)
        self.assertIn("50 malformed lines", err)

    def test_terminal_stdin_explains_instead_of_hanging(self):
        code, _, err = self.run_cli(
            "merge", "-p", self.profile, "-s", self.sketch_path, stdin=FakeStdin(tty=True)
        )
        self.assertEqual(code, 2)
        self.assertIn("no events to read", err)
        self.assertFalse(os.path.exists(self.sketch_path))

    def test_invalid_profile_fails_before_reading_events(self):
        bad = self.write("bad.yaml", "fields:\n  - {key: k, path: '$.a[', modifier: DEFAULT}\n")
        code, _, err = self.run_cli(
            "merge", "-p", bad, "-s", self.sketch_path, self.write_events("e.jsonl", EVENTS)
        )
        self.assertEqual(code, 2)
        self.assertIn("'k'", err)
        self.assertIn("Invalid JSONPath", err)
        self.assertFalse(os.path.exists(self.sketch_path))

    def test_missing_profile_and_missing_events_file(self):
        code, _, err = self.run_cli(
            "merge", "-p", "/no/such.yaml", "-s", self.sketch_path, "x.jsonl"
        )
        self.assertEqual(code, 2)
        self.assertIn("/no/such.yaml", err)

        code, _, err = self.fingerprint(os.path.join(self.dir, "missing.jsonl"))
        self.assertEqual(code, 2)
        self.assertIn("missing.jsonl", err)
        self.assertFalse(os.path.exists(self.sketch_path))

    def test_unusable_set_file_is_refused_and_left_alone(self):
        with open(self.sketch_path, "w") as f:
            f.write("just: some other yaml\n")
        code, _, err = self.fingerprint(self.write_events("e.jsonl", EVENTS))
        self.assertEqual(code, 2)
        self.assertIn("not a sketch", err)
        with open(self.sketch_path) as f:
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
        code, _, err = self.run_cli("merge", "-s", self.sketch_path)
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
            "merge", "-p", bad, "-s", self.sketch_path, self.write_events("e.jsonl", EVENTS)
        )
        self.assertEqual(code, 2)
        self.assertIn(f"sketchtastic: {bad}: fields[0] (key 's') → modifier:", err)
        self.assertIn(f"check {bad}' lists the same problems", err)
        self.assertFalse(os.path.exists(self.sketch_path))


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
        code, _, _ = self.run_cli("merge", "-p", profile, "-s", self.sketch_path, events)
        self.assertEqual(code, 0)
        data = self.load_set()
        self.assertEqual(data["profile_id"], "f50d7a5f85ddf9f7f4c72370f454ae2e")
        self.assertEqual(len(data["skits"]), 3)
        db_ok = data["skits"]["b738d17a6a5f7265cb4cef73937afd4f"]
        self.assertEqual(db_ok["tokens"], {"level": "INFO", "component": "db", "failed": "FALSE"})
        self.assertEqual(db_ok["meta"]["count"], 2)
        self.assertEqual(db_ok["aggregates"]["example"], ["query ok", "query ok (cached)"])


class ProfileMismatchTests(CliTestCase):
    def setUp(self):
        super().setUp()
        self.fingerprint(self.write_events("run1.jsonl", EVENTS))
        with open(self.sketch_path) as f:
            self.before = f.read()
        self.other = self.write("other.yaml", OTHER_PROFILE)
        self.events = self.write_events("run2.jsonl", EVENTS)

    def test_merge_with_a_different_profile_is_refused(self):
        code, _, err = self.run_cli("merge", "-p", self.other, "-s", self.sketch_path, self.events)

        self.assertEqual(code, 2)
        self.assertIn(yaml.safe_load(self.before)["profile_id"], err)  # AC13: names both IDs...
        self.assertIn(load_profile(self.other).profile_id, err)
        self.assertIn("--force-profile", err)  # ...and the override flag
        with open(self.sketch_path) as f:
            self.assertEqual(f.read(), self.before)

    def test_force_profile_overrides(self):
        code, _, _ = self.run_cli(
            "merge", "-p", self.other, "-s", self.sketch_path, self.events, "--force-profile"
        )
        self.assertEqual(code, 0)
        data = self.load_set()
        self.assertNotEqual(data["profile_id"], yaml.safe_load(self.before)["profile_id"])
        self.assertEqual(len(data["skits"]), 4)  # 3 kept + 1 under the new profile

    def test_changing_only_aggregates_is_not_a_mismatch(self):
        tweaked = self.write("tweaked.yaml", PROFILE.replace("n: 2}", "n: 5}"))
        code, _, _ = self.run_cli("merge", "-p", tweaked, "-s", self.sketch_path, self.events)
        self.assertEqual(code, 0)


class AtomicWriteTests(CliTestCase):
    def test_failed_write_leaves_previous_set_intact(self):
        self.fingerprint(self.write_events("run1.jsonl", EVENTS[:3]))
        with open(self.sketch_path) as f:
            before = f.read()

        with mock.patch(
            "sketchtastic.sketch.os.replace",
            side_effect=OSError(28, "No space left on device"),
        ):
            code, _, err = self.fingerprint(self.write_events("run2.jsonl", EVENTS[3:]))

        self.assertEqual(code, 2)
        self.assertIn("cannot write", err)
        with open(self.sketch_path) as f:
            self.assertEqual(f.read(), before)
        leftovers = [n for n in os.listdir(self.dir) if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])


class EntryPointTests(unittest.TestCase):
    """The real `python -m sketchtastic` process, not just main()."""

    def run_module(self, *argv, **kwargs):
        return subprocess.run(
            [sys.executable, "-m", "sketchtastic", *argv],
            cwd=PACKAGE_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            **kwargs,
        )

    def test_help_has_worked_example_and_in_place_warning(self):
        result = self.run_module("merge", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage: sketchtastic merge", result.stdout)
        self.assertIn("example:", result.stdout)
        self.assertIn("updated in place", result.stdout)
        self.assertIn("--force-profile", result.stdout)
        self.assertIn("exit status:", result.stdout)

    def test_pipeline_end_to_end_via_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            sketch_path = os.path.join(tmp, "set.yaml")
            with open(ACCESS_EVENTS) as events:
                result = self.run_module(
                    "merge", "-p", ACCESS_PROFILE, "-s", sketch_path, "-", stdin=events
                )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertIn("8 events read from stdin", result.stderr)
            self.assertIn("4 new, 0 updated, 4 total in sketch", result.stderr)

    def test_help_names_the_command_it_was_run_as(self):
        for argv0, prog in (
            ("/usr/bin/skt", "skt"),
            ("/x/sketchtastic", "sketchtastic"),
            ("/x/__main__.py", "sketchtastic"),
        ):
            with self.subTest(argv0=argv0), mock.patch.object(sys, "argv", [argv0]):
                out = io.StringIO()
                with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
                    main(["--help"])
                self.assertTrue(out.getvalue().startswith(f"usage: {prog} "), out.getvalue())

    def test_sketch_flag_replaces_set(self):
        result = self.run_module("merge", "--help")
        self.assertIn("-s, --sketch SKETCH", result.stdout)
        self.assertNotIn("--set", result.stdout)

    def test_version_flag(self):
        result = self.run_module("--version")
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, r"^sketch-tastic \d+\.\d+\.\d+")


if __name__ == "__main__":
    unittest.main()


class ShowTests(CliTestCase):
    """`fingerprint show SET` (STORY-FING-42)."""

    def save_set(self, observations):
        """Build a set from (tokens, run id) pairs, in order, and save it."""
        fingerprints = Sketch()
        for tokens, run in observations:
            fingerprints.upsert(tokens, {}, run=run)
        fingerprints.save(self.sketch_path)

    def test_prints_one_row_per_skit_least_frequent_first(self):
        a, b, c = {"kind": "a"}, {"kind": "b", "route": "/x"}, {"kind": "c"}
        self.save_set(
            [
                (a, "261014-0001"),
                (b, "261014-0001"),
                (b, "261014-0002"),
                (c, "261015-0003"),
            ]
        )
        code, out, err = self.run_cli("show", self.sketch_path)
        self.assertEqual((code, err), (0, ""))
        ida, idb, idc = (skit_id(t)[:8] for t in (a, b, c))
        self.assertEqual(
            out.splitlines(),
            [
                "ID        COUNT  COUNT %  FIRST RUN    LAST RUN     kind  route",
                f"{ida}  1      25.0     261014-0001  261014-0001  a     -",
                f"{idc}  1      25.0     261015-0003  261015-0003  c     -",
                f"{idb}  2      50.0     261014-0001  261014-0002  b     /x",
            ],
        )

    def test_shared_aggregates_get_a_value_and_a_percent_column(self):
        fingerprints = Sketch(
            [Aggregate("size", "$.size", ["SUM", "MAX"]), Aggregate("n", "$.size", "COUNT")]
        )
        for kind, size in (("a", 10), ("a", 30), ("b", 60)):
            fingerprints.upsert({"k": kind}, {"size": size}, run="261014-0001")
        fingerprints.save(self.sketch_path)
        code, out, _ = self.run_cli("show", self.sketch_path)
        self.assertEqual(code, 0)
        rows = [re.split(r"\s{2,}", line) for line in out.splitlines()]
        run = "261014-0001"
        self.assertEqual(
            [row[1:] for row in rows],
            [
                [
                    "COUNT",
                    "COUNT %",
                    "FIRST RUN",
                    "LAST RUN",
                    "size.SUM",
                    "size.SUM %",
                    "n",
                    "n %",
                    "k",
                ],
                ["1", "33.3", run, run, "60", "60.0", "1", "33.3", "b"],
                ["2", "66.7", run, run, "40", "40.0", "2", "66.7", "a"],
            ],
        )

    def test_set_without_shares_shows_dashes(self):
        fid = skit_id({"k": "a"})
        self.write(
            "set.yaml",
            f"""
            version: 0
            profile_id: null
            skits:
              {fid}:
                tokens: {{k: a}}
                aggregates: {{size: 5}}
                meta: {{count: 1}}
            """,
        )
        code, out, _ = self.run_cli("show", self.sketch_path)
        self.assertEqual(code, 0)
        header, row = (re.split(r"\s{2,}", line) for line in out.splitlines())
        self.assertEqual(header, ["ID", "COUNT", "COUNT %", "FIRST RUN", "LAST RUN", "k"])
        self.assertEqual(row[1:3], ["1", "-"])

    def test_empty_set_says_so(self):
        Sketch().save(self.sketch_path)
        code, out, err = self.run_cli("show", self.sketch_path)
        self.assertEqual((code, out, err), (0, f"{self.sketch_path}: no skits\n", ""))

    def test_unusable_file_is_an_error_and_left_alone(self):
        not_a_set = self.write("not_a_set.yaml", "just: text\n")
        for path in (os.path.join(self.dir, "missing.yaml"), not_a_set):
            with self.subTest(path=path):
                code, out, err = self.run_cli("show", path)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.startswith("sketchtastic: cannot use sketch file: "), err)
                self.assertIn(os.path.basename(path), err)
        with open(not_a_set) as f:
            self.assertEqual(f.read(), "just: text\n")

    def test_help_describes_show_with_an_example(self):
        code, out, _ = self.run_cli("show", "--help")
        self.assertEqual(code, 0)
        self.assertIn("sketchtastic show web.sketch.yaml", out)
        self.assertIn("--sort KEY", out)
        self.assertIn("sketchtastic show --sort 'payload_bytes.SUM %' gh.sketch.yaml | tail", out)
        self.assertIn("KEY is not one of its columns", out)
        _, out, _ = self.run_cli("--help")
        self.assertIn("show", out)


class ShowSortTests(CliTestCase):
    """`show --sort KEY`: lowest first, default COUNT (STORY-SKT-03)."""

    def save_sizes(self, sizes):
        """One skit per (kind, size) with a SUM aggregate on size, saved in that order."""
        sketch = Sketch([Aggregate("size", "$.size", "SUM")])
        for kind, size in sizes:
            sketch.upsert({"kind": kind}, {"size": size}, run="261014-0001")
        sketch.save(self.sketch_path)

    def kinds(self, *args):
        """The `kind` column of `show` with ARGS, top to bottom; asserts success."""
        code, out, err = self.run_cli("show", *args, self.sketch_path)
        self.assertEqual((code, err), (0, ""))
        header, *rows = (re.split(r"\s{2,}", line) for line in out.splitlines())
        return [row[header.index("kind")] for row in rows]

    def test_sorts_by_an_aggregate_and_its_share_lowest_first(self):
        self.save_sizes([("a", 40), ("b", 60), ("c", 5)])
        for key in ("size", "size %", "SIZE %"):
            with self.subTest(key=key):
                self.assertEqual(self.kinds("--sort", key), ["c", "a", "b"])

    def test_sorts_by_every_fixed_column(self):
        a, b, c = {"kind": "a"}, {"kind": "b"}, {"kind": "c"}
        sketch = Sketch()
        for tokens, run in ((b, "261014-0002"), (c, "261014-0001"), (c, "261014-0003")):
            sketch.upsert(tokens, {}, run=run)
        sketch.upsert(a, {}, run="261014-0004")
        sketch.save(self.sketch_path)
        by_id = [t["kind"] for t in sorted((a, b, c), key=skit_id)]
        self.assertEqual(self.kinds("--sort", "id"), by_id)
        self.assertEqual(self.kinds("--sort", "count"), ["b", "a", "c"])
        self.assertEqual(self.kinds("--sort", "Count %"), ["b", "a", "c"])
        self.assertEqual(self.kinds("--sort", "first run"), ["c", "b", "a"])
        self.assertEqual(self.kinds("--sort", "LAST RUN"), ["b", "c", "a"])
        self.assertEqual(self.kinds("--sort", "kind"), ["a", "b", "c"])

    def test_default_is_count_with_ties_in_file_order(self):
        sketch = Sketch()
        for kind in ("x", "y", "y", "z"):
            sketch.upsert({"kind": kind}, {}, run="261014-0001")
        sketch.save(self.sketch_path)
        self.assertEqual(self.kinds(), ["x", "z", "y"])
        self.assertEqual(self.kinds(), self.kinds("--sort", "COUNT"))

    def test_missing_values_sort_first_and_numbers_before_text(self):
        sketch = Sketch()
        for tokens in ({"kind": "t", "v": "a"}, {"kind": "n10", "v": 10}, {"kind": "none"}):
            sketch.upsert(tokens, {}, run="261014-0001")
        sketch.upsert({"kind": "n9", "v": 9}, {}, run="261014-0001")
        sketch.save(self.sketch_path)
        self.assertEqual(self.kinds("--sort", "v"), ["none", "n9", "n10", "t"])

    def test_exact_header_wins_and_a_caseless_tie_is_ambiguous(self):
        sketch = Sketch()
        sketch.upsert({"kind": "a", "count": "2"}, {}, run="261014-0001")
        sketch.upsert({"kind": "b", "count": "1"}, {}, run="261014-0001")
        sketch.upsert({"kind": "b", "count": "1"}, {}, run="261014-0001")
        sketch.save(self.sketch_path)
        self.assertEqual(self.kinds("--sort", "count"), ["b", "a"])
        self.assertEqual(self.kinds("--sort", "COUNT"), ["a", "b"])
        code, out, err = self.run_cli("show", "--sort", "Count", self.sketch_path)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(
            err,
            f"sketchtastic: column 'Count' is ambiguous in {self.sketch_path}: COUNT, count\n",
        )

    def test_unknown_key_lists_the_columns(self):
        self.save_sizes([("a", 1)])
        code, out, err = self.run_cli("show", "--sort", "bytes", self.sketch_path)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(
            err,
            f"sketchtastic: no column 'bytes' in {self.sketch_path}; columns: "
            "ID, COUNT, COUNT %, FIRST RUN, LAST RUN, size, size %, kind\n",
        )

    def test_empty_sketch_says_so_with_any_key(self):
        Sketch().save(self.sketch_path)
        code, out, err = self.run_cli("show", "--sort", "nothing", self.sketch_path)
        self.assertEqual((code, out, err), (0, f"{self.sketch_path}: no skits\n", ""))


class HistoryTests(CliTestCase):
    """Each merge also writes the run's own fingerprints to <set>.history/ (FING-48)."""

    def history_dir(self):
        return os.path.join(self.dir, "set.history")

    def run_files(self):
        if not os.path.isdir(self.history_dir()):
            return []
        return sorted(os.listdir(self.history_dir()))

    def test_each_merge_writes_a_run_file_with_only_that_runs_data(self):
        self.fingerprint(self.write_events("one.jsonl", EVENTS[:3]))
        _, _, err = self.fingerprint(self.write_events("two.jsonl", EVENTS[3:]))
        files = self.run_files()
        self.assertEqual(len(files), 2)
        for name in files:
            self.assertRegex(name, r"^\d{6}-\d{4}\.yaml$")
        second = os.path.join(self.history_dir(), files[-1])
        self.assertIn(f"  history: {second}", err)

        run = self.load_set(second)
        self.assertEqual(run["version"], 0)
        self.assertEqual(run["profile_id"], self.load_set()["profile_id"])
        kinds = {rec["tokens"]["kind"]: rec for rec in run["skits"].values()}
        self.assertEqual(sorted(kinds), ["a", "b", "c"])  # events 4-6 only
        self.assertEqual(kinds["a"]["meta"]["count"], 1)  # the set has 3
        self.assertEqual(kinds["a"]["share"]["meta"]["count"], 33.33)

    def test_run_header_says_what_the_run_read(self):
        events = self.write("mixed.jsonl", json.dumps(EVENTS[0]) + "\nnot json\n")
        self.fingerprint(events)
        run = self.load_set(os.path.join(self.history_dir(), self.run_files()[0]))
        header = run["run"]
        self.assertEqual(list(run)[:3], ["version", "profile_id", "run"])
        self.assertEqual(
            {k: header[k] for k in ("source", "events", "skipped_lines", "sketch")},
            {"source": events, "events": 1, "skipped_lines": 1, "sketch": self.sketch_path},
        )
        self.assertLessEqual(header["started"], header["finished"])

    def test_stdin_source_and_empty_run(self):
        code, _, _ = self.fingerprint("-", stdin=FakeStdin(""))
        self.assertEqual(code, 0)
        run = self.load_set(os.path.join(self.history_dir(), self.run_files()[0]))
        self.assertEqual((run["run"]["source"], run["skits"]), ("stdin", {}))

    def test_run_file_is_readable_by_show(self):
        self.fingerprint(self.write_events("one.jsonl", EVENTS[:2]))
        code, out, _ = self.run_cli("show", os.path.join(self.history_dir(), self.run_files()[0]))
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 3)  # header + 2 fingerprints

    def test_trial_run_and_failed_run_write_no_history(self):
        events = self.write_events("one.jsonl", EVENTS)
        self.fingerprint(events, "-o", os.path.join(self.dir, "preview.yaml"))
        self.run_cli(
            "merge", "-p", self.write("bad.yaml", "fields: []"), "-s", self.sketch_path, events
        )
        self.assertEqual(self.run_files(), [])

    def test_unwritable_history_still_updates_the_set_and_exits_3(self):
        self.write("set.history", "a file, not a directory")
        events = self.write("mixed.jsonl", json.dumps(EVENTS[0]) + "\nnot json\n")
        code, _, err = self.fingerprint(events)
        self.assertEqual(code, 3)  # takes precedence over 1 (a line was skipped)
        self.assertIn(f"sketchtastic: {self.sketch_path} updated, but history not written: ", err)
        self.assertEqual(len(self.load_set()["skits"]), 1)

    def test_run_ids_number_on_from_the_set_and_its_history(self):
        today = date(2026, 10, 15)
        history = os.path.join(self.dir, "set.history")
        self.assertEqual(_next_run_id(None, history, today), "261015-0001")
        self.assertEqual(_next_run_id("261014-0005", history, today), "261015-0006")
        os.makedirs(history)
        for name in ("261014-0007.yaml", "notes.txt", "261014-0002.yaml"):
            self.write(os.path.join("set.history", name), "")
        # a rebuilt set must not reuse a number its history already holds
        self.assertEqual(_next_run_id("261014-0005", history, today), "261015-0008")
        self.assertEqual(_next_run_id(None, history, today), "261015-0008")

    def test_run_file_is_named_by_run_id_and_header_carries_it(self):
        self.fingerprint(self.write_events("one.jsonl", EVENTS[:2]))
        self.fingerprint(self.write_events("two.jsonl", EVENTS[2:]))
        today = datetime.now(UTC).strftime("%y%m%d")
        self.assertEqual(self.run_files(), [f"{today}-0001.yaml", f"{today}-0002.yaml"])
        run = self.load_set(os.path.join(self.history_dir(), f"{today}-0002.yaml"))
        self.assertEqual(run["run"]["id"], f"{today}-0002")

    def test_history_dir_drops_only_the_last_extension(self):
        self.assertEqual(
            _history_dir("data/app.fingerprints.yaml"), "data/app.fingerprints.history"
        )
        self.assertEqual(_history_dir("data/myset"), "data/myset.history")

    def test_trial_run_does_not_use_up_a_run_id(self):
        events = self.write_events("one.jsonl", EVENTS)
        self.fingerprint(events)
        self.fingerprint(events, "-o", os.path.join(self.dir, "preview.yaml"))
        self.fingerprint(events)
        today = datetime.now(UTC).strftime("%y%m%d")
        self.assertEqual(self.load_set()["last_run"], f"{today}-0002")


class SequenceTests(CliTestCase):
    """Events at or below the set's sequence mark are dropped (FING-50)."""

    def setUp(self):
        super().setUp()
        self.profile = self.write("seq.yaml", PROFILE + "sequence: $.id\n")

    def events(self, name, ids, kind="a"):
        return self.write_events(name, [{"id": i, "kind": kind, "size": 1} for i in ids])

    def total_count(self, data):
        return sum(rec["meta"]["count"] for rec in data["skits"].values())

    def test_first_run_records_the_highest_sequence(self):
        code, _, err = self.fingerprint(self.events("one.jsonl", [3, 1, 5, 2]))
        self.assertEqual(code, 0)
        self.assertEqual(self.load_set()["sequence"], {"path": "$.id", "max": 5})
        self.assertIn("  dropped: 0 events already merged (no earlier mark)", err)

    def test_events_at_or_below_the_mark_are_dropped(self):
        self.fingerprint(self.events("one.jsonl", [1, 2, 3, 4, 5]))
        code, _, err = self.fingerprint(self.events("two.jsonl", [3, 5, 6, 8]))
        self.assertEqual(code, 0)
        self.assertIn("4 events read", err)
        self.assertIn("  dropped: 2 events already merged (sequence ≤ 5)", err)
        merged = self.load_set()
        self.assertEqual((self.total_count(merged), merged["sequence"]["max"]), (7, 8))
        history = os.path.join(self.dir, "set.history")
        run = self.load_set(os.path.join(history, sorted(os.listdir(history))[-1]))
        self.assertEqual(self.total_count(run), 2)  # only 6 and 8
        self.assertEqual(run["run"]["sequence"], {"min": 6, "max": 8})

    def test_rerun_over_the_same_input_adds_nothing(self):
        events = self.events("one.jsonl", ["10", "11", "12"])  # numeric strings count
        self.fingerprint(events)
        before = self.load_set()
        code, _, err = self.fingerprint(events)
        self.assertEqual(code, 0)
        self.assertIn("  dropped: 3 events already merged (sequence ≤ 12)", err)
        after = self.load_set()
        self.assertEqual(self.total_count(after), self.total_count(before))
        history = os.path.join(self.dir, "set.history")
        run = self.load_set(os.path.join(history, sorted(os.listdir(history))[-1]))
        self.assertNotIn("sequence", run["run"])  # nothing merged in this run

    def test_event_without_a_usable_sequence_fails_the_whole_run(self):
        self.fingerprint(self.events("one.jsonl", [1, 2]))
        with open(self.sketch_path) as f:
            before = f.read()
        history = os.path.join(self.dir, "set.history")
        runs_before = os.listdir(history)
        for bad in ({"kind": "a"}, {"id": "abc", "kind": "a"}, {"id": True, "kind": "a"}):
            with self.subTest(bad=bad):
                lines = [{"id": 7, "kind": "a"}, bad, {"id": 8, "kind": "a"}]
                code, _, err = self.fingerprint(self.write_events("bad.jsonl", lines))
                self.assertEqual(code, 2)
                self.assertIn("sketchtastic: line 2: no usable sequence at $.id", err)
                self.assertIn("nothing written", err)
                with open(self.sketch_path) as f:
                    self.assertEqual(f.read(), before)  # set untouched, mark included
                self.assertEqual(os.listdir(history), runs_before)  # no run file

    def test_changed_sequence_path_ignores_the_old_mark(self):
        self.fingerprint(self.events("one.jsonl", [1, 2, 3]))
        data = self.load_set()
        data["sequence"]["path"] = "$.old"
        with open(self.sketch_path, "w") as f:
            yaml.safe_dump(data, f)
        _, _, err = self.fingerprint(self.events("two.jsonl", [2]))
        self.assertIn(
            "sketchtastic: sequence path changed ($.old -> $.id); previous mark ignored", err
        )
        self.assertEqual(self.load_set()["sequence"], {"path": "$.id", "max": 2})

    def test_profile_without_sequence_keeps_the_mark_and_drops_nothing(self):
        self.fingerprint(self.events("one.jsonl", [1, 2, 3]))
        plain = self.write("plain.yaml", PROFILE)
        _, _, err = self.run_cli(
            "merge", "-p", plain, "-s", self.sketch_path, self.events("two.jsonl", [1])
        )
        self.assertNotIn("dropped:", err)
        merged = self.load_set()
        self.assertEqual((self.total_count(merged), merged["sequence"]["max"]), (4, 3))
