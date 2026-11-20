"""Unwrap post-create observations without changing the original post record."""

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

POST = "app.bsky.feed.post"
MAX_LINE_BYTES = 4 * 1024 * 1024


def reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON number {value}")


def source_post(event: dict, counts: Counter, seen: set) -> dict | None:
    """Accept bare posts and v1/v2 create envelopes, deduplicating identified creates."""
    if event.get("$type") == POST:
        return event
    payload = event.get("payload", event)
    if not isinstance(payload, dict):
        raise ValueError("event payload must be an object")
    commit = payload.get("commit", payload)
    if not isinstance(commit, dict):
        raise ValueError("event commit must be an object")
    if commit.get("collection") != POST:
        counts["ignored_events"] += 1
        return None
    if commit.get("operation") != "create":
        counts["ignored_operations"] += 1
        return None
    record = commit.get("record")
    if not isinstance(record, dict) or record.get("$type") != POST:
        raise ValueError("post create event must contain an app.bsky.feed.post record")
    did, rkey = payload.get("did"), commit.get("rkey")
    if not isinstance(did, str) or not did or not isinstance(rkey, str) or not rkey:
        raise ValueError("post create event requires did and rkey for duplicate protection")
    identity = (did, rkey)
    if identity in seen:
        counts["duplicates"] += 1
        return None
    seen.add(identity)
    return record


def posts(source: Path, counts: Counter, digest) -> Iterator[tuple[int, dict]]:
    """Yield source line and unchanged post; hash all source bytes including blanks."""
    seen = set()
    with source.open("rb") as stream:
        number = 0
        while line := stream.readline(MAX_LINE_BYTES + 1):
            number += 1
            if len(line) > MAX_LINE_BYTES:
                raise ValueError(
                    f"{source}: line {number}: exceeds {MAX_LINE_BYTES} byte line limit"
                )
            digest.update(line)
            if not line.strip():
                continue
            try:
                event = json.loads(line, parse_constant=reject_constant)
                if not isinstance(event, dict):
                    raise ValueError("expected a JSON object")
                counts["records"] += 1
                record = source_post(event, counts, seen)
            except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
                raise ValueError(f"{source}: line {number}: {exc}") from exc
            if record is not None:
                counts["posts"] += 1
                yield number, record
