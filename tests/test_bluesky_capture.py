"""Bounded capture contracts, without contacting the public network."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from examples.bluesky import capture


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "posts.jsonl"

    def socket(self, frames):
        connection = MagicMock()
        connection.recv.side_effect = frames
        connector = MagicMock()
        connector.return_value.__enter__.return_value = connection
        return connector, connection

    def test_count_limit_preserves_objects_and_provenance(self):
        frames = ['{\n"payload": {"text":"hi\\nthere"}\n}', b'{"kind":"commit"}']
        connector, connection = self.socket(frames)
        with patch.object(capture, "connect", connector):
            metadata = capture.capture(self.output, seconds=60, limit=2)
        self.assertEqual(metadata["received"], 2)
        self.assertEqual(metadata["stop_reason"], "limit")
        self.assertEqual(metadata["endpoint"], capture.DEFAULT_ENDPOINT)
        self.assertIn("started", metadata)
        self.assertIn("finished", metadata)
        self.assertEqual(
            [json.loads(line) for line in self.output.read_text().splitlines()],
            [json.loads(frame) for frame in frames],
        )
        self.assertEqual(
            json.loads(self.output.with_suffix(".jsonl.meta.json").read_text()), metadata
        )
        self.assertEqual(connection.recv.call_count, 2)
        self.assertEqual(connector.call_args.kwargs["max_size"], capture.MAX_FRAME_BYTES)
        self.assertEqual(connector.call_args.kwargs["subprotocols"], ["xrpc.v1.json"])

    def test_idle_timeout_finishes_without_waiting_for_a_record(self):
        connector, connection = self.socket([TimeoutError()])
        with patch.object(capture, "connect", connector):
            metadata = capture.capture(self.output, seconds=0.5)
        self.assertEqual(metadata["received"], 0)
        self.assertEqual(metadata["stop_reason"], "seconds")
        self.assertLessEqual(connection.recv.call_args.kwargs["timeout"], 0.5)
        self.assertEqual(self.output.read_text(), "")

    def test_deadline_checks_before_reading(self):
        connector, connection = self.socket([])
        with (
            patch.object(capture, "connect", connector),
            patch.object(capture.time, "monotonic", side_effect=[10, 12]),
        ):
            metadata = capture.capture(self.output, seconds=1)
        connection.recv.assert_not_called()
        self.assertEqual(metadata["stop_reason"], "seconds")

    def test_existing_data_or_sidecar_is_never_overwritten(self):
        for existing in [self.output, self.output.with_suffix(".jsonl.meta.json")]:
            with self.subTest(existing=existing):
                existing.write_text("keep me")
                with patch.object(capture, "connect") as connector:
                    with self.assertRaises(FileExistsError):
                        capture.capture(self.output)
                    connector.assert_not_called()
                self.assertEqual(existing.read_text(), "keep me")
                existing.unlink()

    def test_network_failure_keeps_partial_capture_and_records_error(self):
        connector, _ = self.socket(['{"kind":"commit"}', OSError("disconnected")])
        with patch.object(capture, "connect", connector):
            with self.assertRaisesRegex(OSError, "disconnected"):
                capture.capture(self.output)
        self.assertEqual(self.output.read_text(), '{"kind":"commit"}\n')
        sidecar = json.loads(self.output.with_suffix(".jsonl.meta.json").read_text())
        self.assertEqual(sidecar["stop_reason"], "error")
        self.assertEqual(sidecar["received"], 1)

    def test_invalid_frame_fails_and_records_error(self):
        for frame in ["no json", "[]", '{"value":NaN}', b"\xff"]:
            with self.subTest(frame=frame):
                connector, _ = self.socket([frame])
                with patch.object(capture, "connect", connector):
                    with self.assertRaises(ValueError):
                        capture.capture(self.output)
                self.assertEqual(self.output.read_text(), "")
                sidecar = self.output.with_suffix(".jsonl.meta.json")
                self.assertEqual(json.loads(sidecar.read_text())["stop_reason"], "error")
                self.output.unlink()
                sidecar.unlink()

    def test_limits_and_insecure_endpoint_rejected_before_network(self):
        for kwargs in [
            {"seconds": 0},
            {"seconds": float("nan")},
            {"limit": 0},
            {"limit": 1.5},
            {"endpoint": "ws://localhost/subscribe"},
            {"endpoint": "wss://user:secret@example.com/subscribe"},
        ]:
            with self.subTest(kwargs=kwargs), patch.object(capture, "connect") as connector:
                with self.assertRaises(ValueError):
                    capture.capture(self.output, **kwargs)
                connector.assert_not_called()

    def test_records_are_on_disk_while_capture_is_running(self):
        seen = []

        def frames():
            yield '{"n":1}'
            seen.append(self.output.read_text())
            seen.append(self.output.with_suffix(".jsonl.meta.json").exists())
            yield '{"n":2}'

        iterator = frames()
        connector, connection = self.socket([])
        connection.recv.side_effect = lambda timeout=None: next(iterator)
        with patch.object(capture, "connect", connector):
            capture.capture(self.output, limit=2)
        self.assertEqual(seen, ['{"n":1}\n', False])
        self.assertEqual(len(self.output.read_text().splitlines()), 2)

    def test_capture_to_stdout_streams_jsonl_and_handles_broken_pipe(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout

        frames = ['{"kind":"commit","n":1}', '{"kind":"commit","n":2}']
        connector, _ = self.socket(frames)
        out, err = io.StringIO(), io.StringIO()
        with (
            patch.object(capture, "connect", connector),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            code = capture.main(["--output", "-", "--limit", "2", "--seconds", "10"])
        self.assertEqual(code, 0, err.getvalue())
        self.assertEqual(
            [json.loads(line) for line in out.getvalue().splitlines()],
            [{"kind": "commit", "n": 1}, {"kind": "commit", "n": 2}],
        )
        self.assertIn("Captured 2 frames", err.getvalue())

    def test_capture_stream_reconnects_with_cursor_after_disconnect(self):
        import io

        conn1 = MagicMock()
        conn1.recv.side_effect = [
            '{"kind":"commit","time_us":100,"n":1}',
            '{"kind":"commit","time_us":200,"n":2}',
            OSError("connection dropped"),
        ]
        conn2 = MagicMock()
        conn2.recv.side_effect = [
            '{"kind":"commit","time_us":300,"n":3}',
            TimeoutError(),
        ]
        conns = iter([conn1, conn2])

        def fake_connect(endpoint, **kwargs):
            cm = MagicMock()
            cm.__enter__.return_value = next(conns)
            return cm

        connector = MagicMock(side_effect=fake_connect)
        out = io.StringIO()
        with (
            patch.object(capture, "connect", connector),
            patch.object(capture.time, "sleep") as sleep_mock,
        ):
            meta = capture.capture_stream(out, seconds=30, limit=None)

        self.assertEqual(meta["received"], 3)
        self.assertEqual(meta["reconnects"], 1)
        self.assertEqual(connector.call_count, 2)
        second_endpoint = connector.call_args_list[1].args[0]
        self.assertIn("cursor=200", second_endpoint)
        sleep_mock.assert_called_once()
        self.assertEqual(
            [json.loads(line)["n"] for line in out.getvalue().splitlines()],
            [1, 2, 3],
        )

    def test_capture_file_with_reconnect_survives_transient_drop(self):
        conn1 = MagicMock()
        conn1.recv.side_effect = [
            '{"$type":"message","payload":{"seq":4200},"n":1}',
            OSError("eof"),
        ]
        conn2 = MagicMock()
        conn2.recv.side_effect = ['{"$type":"message","payload":{"seq":4201},"n":2}']
        conns = iter([conn1, conn2])

        def fake_connect(endpoint, **kwargs):
            cm = MagicMock()
            cm.__enter__.return_value = next(conns)
            return cm

        connector = MagicMock(side_effect=fake_connect)
        with (
            patch.object(capture, "connect", connector),
            patch.object(capture.time, "sleep"),
        ):
            meta = capture.capture(self.output, seconds=30, limit=2, reconnect=True)

        self.assertEqual(meta["received"], 2)
        self.assertEqual(meta["reconnects"], 1)
        self.assertEqual(meta["stop_reason"], "limit")
        self.assertIn("cursor=4200", connector.call_args_list[1].args[0])
        self.assertEqual(len(self.output.read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
