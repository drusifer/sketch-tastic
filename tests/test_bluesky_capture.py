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

    def test_network_failure_discards_partial_capture(self):
        connector, _ = self.socket(['{"kind":"commit"}', OSError("disconnected")])
        with patch.object(capture, "connect", connector):
            with self.assertRaisesRegex(OSError, "disconnected"):
                capture.capture(self.output)
        self.assertEqual(list(self.output.parent.iterdir()), [])

    def test_invalid_frame_discards_partial_capture(self):
        for frame in ["no json", "[]", '{"value":NaN}', b"\xff"]:
            with self.subTest(frame=frame):
                connector, _ = self.socket([frame])
                with patch.object(capture, "connect", connector):
                    with self.assertRaises(ValueError):
                        capture.capture(self.output)
                self.assertEqual(list(self.output.parent.iterdir()), [])

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

    def test_publish_collision_does_not_replace_another_writers_file(self):
        connector, _ = self.socket(['{"kind":"commit"}'])
        real_link = capture.os.link

        def collide(source, target):
            if Path(target) == self.output:
                self.output.write_text("another writer")
            real_link(source, target)

        with patch.object(capture, "connect", connector), patch.object(capture.os, "link", collide):
            with self.assertRaises(FileExistsError):
                capture.capture(self.output, limit=1)
        self.assertEqual(self.output.read_text(), "another writer")
        self.assertFalse(self.output.with_suffix(".jsonl.meta.json").exists())


if __name__ == "__main__":
    unittest.main()
