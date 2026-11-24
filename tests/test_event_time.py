"""TDD tests for optional profile `event_time` JSONPath config (historical ingestion)."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path

from sketchtastic.analysis import analyze_sketch
from sketchtastic.cli import main
from sketchtastic.dashboard import render_dashboard
from sketchtastic.profile import Profile, ProfileError, check_profile, parse_profile
from sketchtastic.sketch import Sketch


def _run_cli(*argv: str) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(list(argv))
    return code, stdout.getvalue(), stderr.getvalue()


class EventTimeProfileTests(unittest.TestCase):
    def test_profile_accepts_optional_event_time_jsonpath_without_changing_profile_id(self) -> None:
        base = parse_profile({"version": 0, "fields": [{"key": "kind", "path": "$.kind"}]})
        with_et = parse_profile(
            {
                "version": 0,
                "event_time": "$.created_at",
                "fields": [{"key": "kind", "path": "$.kind"}],
            }
        )
        self.assertIsNone(base.event_time)
        self.assertIsNotNone(with_et.event_time)
        assert with_et.event_time is not None
        self.assertEqual(with_et.event_time.text, "$.created_at")
        # Adding event_time never invalidates sketch identity
        self.assertEqual(base.profile_id, with_et.profile_id)

    def test_profile_rejects_invalid_or_empty_event_time(self) -> None:
        _, problems = check_profile(
            {"version": 0, "event_time": "   ", "fields": [{"key": "k", "path": "$.k"}]}
        )
        self.assertTrue(problems)

        with self.assertRaises(ProfileError) as ctx:
            parse_profile(
                {"version": 0, "event_time": "$[invalid", "fields": [{"key": "k", "path": "$.k"}]}
            )
        self.assertIn("event_time", str(ctx.exception))


class EventTimeMergeAndAnalysisTests(unittest.TestCase):
    def test_merge_uses_event_time_for_first_and_last_seen_across_historical_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "hist.yaml"
            profile_path.write_text(
                "version: 0\nevent_time: $.ts\nfields:\n  - {key: kind, path: $.kind}\n",
                encoding="utf-8",
            )
            events_path = Path(tmp) / "events.jsonl"
            # Intentionally out of chronological order, across timezones and date-only strings
            events = [
                {"kind": "login", "ts": "2023-06-15T12:00:00+02:00"},  # 10:00Z
                {"kind": "login", "ts": "2022-01-10T08:30:00Z"},  # earliest
                {"kind": "login", "ts": "2024-11-05T23:59:59Z"},  # latest
                {"kind": "signup", "ts": "2023-03-01"},  # date-only -> 00:00Z
                {"kind": "broken_ts", "ts": "not-a-timestamp"},  # unusable -> None, counted skipped
                {"kind": "missing_ts"},  # missing -> None, not skipped
            ]
            events_path.write_text(
                "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
            )
            sketch_path = Path(tmp) / "hist.sketch.yaml"

            # Profile check passes
            code, out, err = _run_cli("check", str(profile_path))
            self.assertEqual(code, 0, out + err)

            # Merge ingests historical timestamps into first_seen / last_seen
            code, _, err = _run_cli(
                "merge",
                "-j",
                "1",
                "-p",
                str(profile_path),
                "-s",
                str(sketch_path),
                str(events_path),
            )
            self.assertEqual(code, 0, err)
            self.assertIn("1 unusable aggregate values", err)

            sketch = Sketch()
            sketch.load(str(sketch_path))
            by_kind = {sketch.get(sid).tokens["kind"]: sketch.get(sid) for sid in sketch}

            login = by_kind["login"]
            self.assertEqual(login.meta["first_seen"], datetime(2022, 1, 10, 8, 30, tzinfo=UTC))
            self.assertEqual(login.meta["last_seen"], datetime(2024, 11, 5, 23, 59, 59, tzinfo=UTC))
            # Retained sample envelope still records merge run id (not altered)
            self.assertIn("run", login.meta["first"][0]["meta"])
            self.assertEqual(list(login.meta["first"][0]["meta"]), ["run"])

            signup = by_kind["signup"]
            self.assertEqual(signup.meta["first_seen"], datetime(2023, 3, 1, 0, 0, tzinfo=UTC))
            self.assertEqual(signup.meta["last_seen"], datetime(2023, 3, 1, 0, 0, tzinfo=UTC))

            self.assertIsNone(by_kind["broken_ts"].meta["first_seen"])
            self.assertIsNone(by_kind["missing_ts"].meta["first_seen"])

            # `analyze` detects event-time seen axis and renders valid offline dashboard
            analysis = analyze_sketch(sketch_path)
            self.assertTrue(analysis["time_axes"])
            self.assertEqual(analysis["time_axes"][0]["id"], "seen")
            self.assertEqual(analysis["time_axes"][0]["kind"], "datetime")
            self.assertTrue(analysis["time_axes"][0]["min_iso"].startswith("2022-01-10"))
            self.assertTrue(analysis["time_axes"][0]["max_iso"].startswith("2024-11-05"))

            login_row = next(s for s in analysis["skits"] if s["tokens"]["kind"] == "login")
            self.assertIn("seen", login_row["time_bounds"])
            self.assertLess(
                login_row["time_bounds"]["seen"][0], login_row["time_bounds"]["seen"][1]
            )

            html_doc = render_dashboard(analysis)
            self.assertIn("First / Last Seen (Event Time)", html_doc)

    def test_multi_run_merge_extends_historical_first_and_last_seen_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "hist.yaml"
            profile_path.write_text(
                "version: 0\nevent_time: $.ts\nfields:\n  - {key: kind, path: $.kind}\n",
                encoding="utf-8",
            )
            sketch_path = Path(tmp) / "hist.sketch.yaml"
            r1 = Path(tmp) / "r1.jsonl"
            r2 = Path(tmp) / "r2.jsonl"
            # Run 1 ingests 2024 data; Run 2 backfills older 2021 data!
            r1.write_text(
                json.dumps({"kind": "a", "ts": "2024-05-01T00:00:00Z"}) + "\n", encoding="utf-8"
            )
            r2.write_text(
                json.dumps({"kind": "a", "ts": "2021-02-01T00:00:00Z"}) + "\n", encoding="utf-8"
            )

            self.assertEqual(
                _run_cli(
                    "merge", "-j", "1", "-p", str(profile_path), "-s", str(sketch_path), str(r1)
                )[0],
                0,
            )
            self.assertEqual(
                _run_cli(
                    "merge", "-j", "1", "-p", str(profile_path), "-s", str(sketch_path), str(r2)
                )[0],
                0,
            )

            sketch = Sketch()
            sketch.load(str(sketch_path))
            skit = next(sketch.get(sid) for sid in sketch)
            self.assertEqual(skit.meta["first_seen"], datetime(2021, 2, 1, 0, 0, tzinfo=UTC))
            self.assertEqual(skit.meta["last_seen"], datetime(2024, 5, 1, 0, 0, tzinfo=UTC))

    def test_profile_without_event_time_preserves_run_id_behavior(self) -> None:
        profile = Profile(fields=())
        self.assertIsNone(profile.event_time)

    def test_multi_match_event_time_counted_as_unusable_and_parallel_merge_preserves_bounds(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "hist.yaml"
            profile_path.write_text(
                "version: 0\nevent_time: $.ts[*]\nfields:\n  - {key: kind, path: $.kind}\n",
                encoding="utf-8",
            )
            profile = parse_profile(
                {
                    "version": 0,
                    "event_time": "$.ts[*]",
                    "fields": [{"key": "kind", "path": "$.kind"}],
                }
            )
            val, unusable = profile.extract_event_time(
                {"kind": "a", "ts": ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"]}
            )
            self.assertIsNone(val)
            self.assertTrue(unusable)

            # Single-match nested array path works via parallel merge (-j 2)
            events_path = Path(tmp) / "events.jsonl"
            sketch_path = Path(tmp) / "p.sketch.yaml"
            events = [
                {"kind": "a", "ts": ["2024-06-01T00:00:00Z"]},
                {"kind": "a", "ts": ["2020-01-01T00:00:00Z"]},
                {"kind": "a", "ts": ["2025-12-31T23:59:59Z"]},
            ]
            events_path.write_text(
                "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
            )
            code, _, err = _run_cli(
                "merge",
                "-j",
                "2",
                "-p",
                str(profile_path),
                "-s",
                str(sketch_path),
                str(events_path),
            )
            self.assertEqual(code, 0, err)
            sketch = Sketch()
            sketch.load(str(sketch_path))
            skit = next(sketch.get(sid) for sid in sketch)
            self.assertEqual(skit.meta["first_seen"], datetime(2020, 1, 1, 0, 0, tzinfo=UTC))
            self.assertEqual(skit.meta["last_seen"], datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()
