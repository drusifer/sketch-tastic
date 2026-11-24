"""Unwrap post-create observations without changing the original post record."""

from collections import Counter, deque
from collections.abc import Hashable

POST = "app.bsky.feed.post"
MAX_LINE_BYTES = 4 * 1024 * 1024
MAX_DEDUP_IDS = 100_000


def reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON number {value}")


class BoundedSeen:
    """Constant-memory set of the most recent `(did, rkey)` identities.

    Duplicate creates come from Jetstream replaying events after a reconnect, so they arrive
    close together; remembering a bounded recent window catches them without growing with
    the stream.
    """

    def __init__(self, maxlen: int = MAX_DEDUP_IDS) -> None:
        self._maxlen = maxlen
        self._set: set[Hashable] = set()
        self._order: deque[Hashable] = deque()

    def __contains__(self, item: Hashable) -> bool:
        return item in self._set

    def add(self, item: Hashable) -> None:
        if item in self._set:
            return
        if len(self._order) >= self._maxlen:
            self._set.discard(self._order.popleft())
        self._set.add(item)
        self._order.append(item)


def source_post(event: dict, counts: Counter, seen: BoundedSeen) -> dict | None:
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
