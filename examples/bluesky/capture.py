"""Capture a bounded public Jetstream window as reusable JSONL metadata.

No image bytes or credentials are fetched. Records are written and flushed to the output as
they arrive, so memory stays constant and a long capture is usable (and survives a crash) while
it runs. The adjacent `.meta.json` provenance file is written last, also when the capture
fails (`stop_reason: "error"`), so its presence means the JSONL will not grow any more.
"""

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_ENDPOINT = (
    "wss://jetstream.us-east.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents"
    "?collections=app.bsky.feed.post&kinds=commit"
)
MAX_FRAME_BYTES = 1_048_576
MAX_BACKOFF_SECONDS = 15.0


def connect(endpoint: str, **kwargs: Any) -> Any:
    """Load the optional dependency only when network capture is requested."""
    try:
        from websockets.sync.client import connect as websocket_connect
    except ImportError as exc:
        raise RuntimeError("Capture requires: bobp make bluesky-install") from exc
    return websocket_connect(endpoint, **kwargs)


def _validate(seconds: float, limit: int | None, endpoint: str) -> None:
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("--seconds must be finite and greater than zero")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0):
        raise ValueError("--limit must be an integer greater than zero")
    url = urlsplit(endpoint)
    if url.scheme != "wss" or not url.hostname or url.username or url.password:
        raise ValueError("--endpoint must be a wss:// URL without credentials")


def _extract_cursor(record: dict[str, Any]) -> int | None:
    """Extract Jetstream v1 (`time_us`) or v2 (`payload.seq`) cursor if present."""
    ts = record.get("time_us")
    if isinstance(ts, int) and not isinstance(ts, bool):
        return ts
    payload = record.get("payload")
    if isinstance(payload, dict):
        seq = payload.get("seq")
        if isinstance(seq, int) and not isinstance(seq, bool):
            return seq
    return None


def _with_cursor(endpoint: str, cursor: int | None) -> str:
    if cursor is None:
        return endpoint
    parts = urlsplit(endpoint)
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "cursor"]
    params.append(("cursor", str(cursor)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


def _is_transient_disconnect(exc: Exception) -> bool:
    if isinstance(exc, BrokenPipeError):
        return False
    if isinstance(exc, OSError):
        return True
    return type(exc).__module__.startswith("websockets")


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


def _stream_into(
    stream: Any,
    *,
    seconds: float,
    limit: int | None,
    endpoint: str,
    reconnect: bool,
    on_finish: Any = None,
) -> dict[str, Any]:
    """Read Jetstream frames into `stream` until `limit`, `seconds`, or pipe close.

    `on_finish(metadata)` runs exactly once when reading ends, including on failure
    (`stop_reason: "error"`, with the exception still propagating).
    """
    started = datetime.now(UTC).isoformat()
    deadline = time.monotonic() + seconds
    received = 0
    reconnects = 0
    cursor: int | None = None
    backoff = 0.5
    reason = "seconds"
    protocol = ["xrpc.v1.json"] if "/xrpc/" in urlsplit(endpoint).path else None

    failed = False
    try:
        while limit is None or received < limit:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            target = _with_cursor(endpoint, cursor)
            try:
                with connect(
                    target,
                    subprotocols=protocol,
                    open_timeout=min(remaining, 15),
                    close_timeout=2,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=MAX_FRAME_BYTES,
                    max_queue=512,
                ) as websocket:
                    while limit is None or received < limit:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        try:
                            frame = websocket.recv(timeout=remaining)
                        except TimeoutError:
                            break
                        record = _frame_record(frame)
                        backoff = 0.5
                        next_cursor = _extract_cursor(record)
                        if next_cursor is not None:
                            cursor = next_cursor
                        try:
                            stream.write(
                                json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n"
                            )
                            stream.flush()
                        except BrokenPipeError:
                            reason = "pipe_closed"
                            break
                        received += 1
                    if reason == "pipe_closed" or (limit is not None and received >= limit):
                        break
                    # Normal loop exit (deadline or recv TimeoutError)
                    break
            except Exception as exc:
                if not reconnect or not _is_transient_disconnect(exc):
                    raise
                reconnects += 1
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                wait = min(backoff, remaining)
                print(
                    f"Capture reconnecting ({reconnects}) after {type(exc).__name__}; "
                    f"resuming from cursor={cursor} in {wait:.1f}s...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)

    except BaseException:
        failed = True
        raise
    finally:
        if failed:
            reason = "error"
        elif reason != "pipe_closed" and limit is not None and received >= limit:
            reason = "limit"
        metadata: dict[str, Any] = {
            "endpoint": endpoint,
            "started": started,
            "finished": datetime.now(UTC).isoformat(),
            "seconds_limit": seconds,
            "record_limit": limit,
            "received": received,
            "reconnects": reconnects,
            "stop_reason": reason,
            "scope": "Public Jetstream observation window; not a complete network snapshot",
        }
        if cursor is not None:
            metadata["last_cursor"] = cursor
        if on_finish is not None:
            on_finish(metadata)
    return metadata


def capture(
    output: Path,
    *,
    seconds: float = 60,
    limit: int | None = None,
    endpoint: str = DEFAULT_ENDPOINT,
    reconnect: bool = False,
) -> dict[str, Any]:
    """Stream a time/count-bounded window into a new file, refusing to replace existing files.

    Each record is flushed as it arrives, so the file is readable during the capture and a
    failure keeps what was already captured. The `.meta.json` sidecar is written last, and
    also on failure (`stop_reason: "error"`); the time budget includes connection setup.
    """
    _validate(seconds, limit, endpoint)
    output = Path(output)
    metadata_path = output.with_suffix(output.suffix + ".meta.json")
    if metadata_path.exists() or metadata_path.is_symlink():
        raise FileExistsError("Capture output or .meta.json already exists; choose a new filename")
    output.parent.mkdir(parents=True, exist_ok=True)

    def write_sidecar(metadata: dict[str, Any]) -> None:
        with metadata_path.open("x", encoding="utf-8") as sidecar:
            sidecar.write(json.dumps(metadata, indent=2) + "\n")

    # Mode "x" is exclusive and never follows an existing symlink, so no overwrite race.
    with output.open("x", encoding="utf-8") as stream:
        return _stream_into(
            stream,
            seconds=seconds,
            limit=limit,
            endpoint=endpoint,
            reconnect=reconnect,
            on_finish=write_sidecar,
        )


def capture_stream(
    stream: Any,
    *,
    seconds: float = 60,
    limit: int | None = None,
    endpoint: str = DEFAULT_ENDPOINT,
    reconnect: bool = True,
) -> dict[str, Any]:
    """Stream validated JSONL frames directly to `stream`, reconnecting on drops by default."""
    _validate(seconds, limit, endpoint)
    return _stream_into(
        stream,
        seconds=seconds,
        limit=limit,
        endpoint=endpoint,
        reconnect=reconnect,
    )


def _kept(output: Path, to_stdout: bool) -> str:
    """Tell the user what a failed file capture left behind."""
    if to_stdout or not Path(output).exists():
        return ""
    return f"; partial capture kept: {ascii(str(output))}"


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
        "--limit",
        type=int,
        default=None,
        help="Maximum frames (default: unlimited; the time budget bounds the run)",
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Public WSS endpoint")
    parser.add_argument(
        "--no-reconnect",
        action="store_true",
        help="Fail immediately on disconnect instead of reconnecting from the last cursor",
    )
    args = parser.parse_args(argv)
    to_stdout = str(args.output) == "-"
    limit = args.limit
    reconnect = not args.no_reconnect
    try:
        if to_stdout:
            metadata = capture_stream(
                sys.stdout,
                seconds=args.seconds,
                limit=limit,
                endpoint=args.endpoint,
                reconnect=reconnect,
            )
        else:
            metadata = capture(
                args.output,
                seconds=args.seconds,
                limit=limit,
                endpoint=args.endpoint,
                reconnect=reconnect,
            )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Capture failed: {ascii(str(exc))}{_kept(args.output, to_stdout)}", file=sys.stderr)
        return 2
    except Exception as exc:
        # Optional websockets exception classes must not require the dependency for --help.
        print(
            f"Capture failed: {type(exc).__name__}: {ascii(str(exc))}"
            f"{_kept(args.output, to_stdout)}",
            file=sys.stderr,
        )
        return 2
    reason_map = {
        "limit": "frame limit",
        "pipe_closed": "downstream closed",
        "seconds": "time limit",
    }
    reason = reason_map.get(metadata["stop_reason"], metadata["stop_reason"])
    reconn = f", {metadata['reconnects']} reconnect(s)" if metadata["reconnects"] else ""
    if to_stdout:
        print(
            f"Captured {metadata['received']} frames{reconn}; stopped at {reason}.",
            file=sys.stderr,
        )
    else:
        print(f"Captured {metadata['received']} frames{reconn}; stopped at {reason}.")
        print(f"JSONL: {ascii(str(args.output))}")
        print(f"Provenance: {ascii(str(args.output) + '.meta.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
