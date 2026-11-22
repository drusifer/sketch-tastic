"""Capture a bounded public Jetstream window as reusable JSONL metadata.

No image bytes or credentials are fetched. Network failures discard the partial capture;
the published JSONL filename is the commit marker for its adjacent provenance file.
"""

import argparse
import json
import math
import os
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_ENDPOINT = (
    "wss://jetstream.us-east.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents"
    "?collections=app.bsky.feed.post&kinds=commit"
)
MAX_FRAME_BYTES = 1_048_576


def connect(endpoint: str, **kwargs: Any) -> Any:
    """Load the optional dependency only when network capture is requested."""
    try:
        from websockets.sync.client import connect as websocket_connect
    except ImportError as exc:
        raise RuntimeError("Capture requires: bobp make bluesky-install") from exc
    return websocket_connect(endpoint, **kwargs)


def _validate(seconds: float, limit: int, endpoint: str) -> None:
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("--seconds must be finite and greater than zero")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("--limit must be an integer greater than zero")
    url = urlsplit(endpoint)
    if url.scheme != "wss" or not url.hostname or url.username or url.password:
        raise ValueError("--endpoint must be a wss:// URL without credentials")


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Non-JSON numeric constant: {value}")


def _frame_record(frame: str | bytes) -> dict[str, Any]:
    """Validate JSON without changing its object values; keep exactly one output line."""
    if isinstance(frame, bytes):
        frame = frame.decode("utf-8")
    if len(frame.encode("utf-8")) > MAX_FRAME_BYTES:
        raise ValueError("Jetstream frame exceeds the 1 MiB capture limit")
    value = json.loads(frame, parse_constant=_invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object from Jetstream")
    return value


def capture(
    output: Path,
    *,
    seconds: float = 60,
    limit: int = 100_000,
    endpoint: str = DEFAULT_ENDPOINT,
) -> dict[str, Any]:
    """Save a completed time/count-bounded window, refusing to replace existing files.

    The time budget includes connection establishment; close may take at most two extra seconds.
    The raw JSONL path is linked last, after provenance is ready, without an overwrite race.
    """
    _validate(seconds, limit, endpoint)
    output = Path(output)
    metadata_path = output.with_suffix(output.suffix + ".meta.json")
    if (
        output.exists()
        or output.is_symlink()
        or metadata_path.exists()
        or metadata_path.is_symlink()
    ):
        raise FileExistsError("Capture output or .meta.json already exists; choose a new filename")
    output.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat()
    deadline = time.monotonic() + seconds
    received = 0
    reason = "seconds"
    protocol = ["xrpc.v1.json"] if "/xrpc/" in urlsplit(endpoint).path else None
    with tempfile.TemporaryDirectory(prefix=".bluesky-capture-", dir=output.parent) as staging:
        raw = Path(staging) / "capture.jsonl"
        with raw.open("w", encoding="utf-8") as stream:
            with connect(
                endpoint,
                subprotocols=protocol,
                open_timeout=min(seconds, 10),
                close_timeout=2,
                max_size=MAX_FRAME_BYTES,
                max_queue=4,
            ) as websocket:
                while received < limit:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        frame = websocket.recv(timeout=remaining)
                    except TimeoutError:
                        break
                    record = _frame_record(frame)
                    stream.write(
                        json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n"
                    )
                    received += 1
                if received == limit:
                    reason = "limit"
        metadata = {
            "endpoint": endpoint,
            "started": started,
            "finished": datetime.now(UTC).isoformat(),
            "seconds_limit": seconds,
            "record_limit": limit,
            "received": received,
            "stop_reason": reason,
            "scope": "Public Jetstream observation window; not a complete network snapshot",
        }
        sidecar = Path(staging) / "metadata.json"
        sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        os.link(sidecar, metadata_path)
        try:
            os.link(raw, output)
        except BaseException:
            metadata_path.unlink()
            raise
    return metadata


def capture_stream(
    stream: Any,
    *,
    seconds: float = 60,
    limit: int = 100_000,
    endpoint: str = DEFAULT_ENDPOINT,
) -> dict[str, Any]:
    """Stream validated JSONL frames directly to `stream`, flushing each line as it arrives."""
    _validate(seconds, limit, endpoint)
    started = datetime.now(UTC).isoformat()
    deadline = time.monotonic() + seconds
    received = 0
    reason = "seconds"
    protocol = ["xrpc.v1.json"] if "/xrpc/" in urlsplit(endpoint).path else None
    with connect(
        endpoint,
        subprotocols=protocol,
        open_timeout=min(seconds, 10),
        close_timeout=2,
        max_size=MAX_FRAME_BYTES,
        max_queue=4,
    ) as websocket:
        while received < limit:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                frame = websocket.recv(timeout=remaining)
            except TimeoutError:
                break
            record = _frame_record(frame)
            try:
                stream.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
                stream.flush()
            except BrokenPipeError:
                reason = "pipe_closed"
                break
            received += 1
        if received == limit:
            reason = "limit"
    return {
        "endpoint": endpoint,
        "started": started,
        "finished": datetime.now(UTC).isoformat(),
        "seconds_limit": seconds,
        "record_limit": limit,
        "received": received,
        "stop_reason": reason,
        "scope": "Public Jetstream observation window; not a complete network snapshot",
    }


def main(argv: list[str] | None = None) -> int:
    """CLI for capturing metadata; exit nonzero without publishing partial data on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New JSONL file (never overwritten), or '-' to stream JSONL to stdout",
    )
    parser.add_argument(
        "--seconds", type=float, default=60, help="Time budget in seconds (default 60)"
    )
    parser.add_argument(
        "--limit", type=int, default=100_000, help="Maximum frames (default 100000)"
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Public WSS endpoint")
    args = parser.parse_args(argv)
    to_stdout = str(args.output) == "-"
    try:
        if to_stdout:
            metadata = capture_stream(
                sys.stdout, seconds=args.seconds, limit=args.limit, endpoint=args.endpoint
            )
        else:
            metadata = capture(
                args.output, seconds=args.seconds, limit=args.limit, endpoint=args.endpoint
            )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Capture failed: {ascii(str(exc))}", file=sys.stderr)
        return 2
    except Exception as exc:
        # Optional websockets exception classes must not require the dependency for --help.
        print(f"Capture failed: {type(exc).__name__}: {ascii(str(exc))}", file=sys.stderr)
        return 2
    reason_map = {
        "limit": "frame limit",
        "pipe_closed": "downstream closed",
        "seconds": "time limit",
    }
    reason = reason_map.get(metadata["stop_reason"], metadata["stop_reason"])
    if to_stdout:
        print(f"Captured {metadata['received']} frames; stopped at {reason}.", file=sys.stderr)
    else:
        print(f"Captured {metadata['received']} frames; stopped at {reason}.")
        print(f"JSONL: {ascii(str(args.output))}")
        print(f"Provenance: {ascii(str(args.output) + '.meta.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
