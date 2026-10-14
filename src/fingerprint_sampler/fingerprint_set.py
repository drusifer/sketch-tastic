"""The fingerprint set: a stateful, mergeable inventory of fingerprints.

Serializes tokenized events into a stable MD5 fingerprint ID and reconciles
every observation against one bounded-size record per fingerprint. Which
statistics and samples a record keeps is declared by the caller as a list of
aggregators, so the set works for any event stream, not just eBPF telemetry.
"""

from __future__ import annotations

import copy
import hashlib
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Sequence

import yaml

from fingerprint_sampler.aggregators import Aggregate

SET_VERSION = 2


class FingerprintSetError(ValueError):
    """A fingerprint set file can't be used (unreadable, wrong format, wrong version)."""


class ProfileMismatchError(FingerprintSetError):
    """The set file was built with a different profile than the one now in use."""

    def __init__(self, path: str, set_profile_id: str, current_profile_id: str) -> None:
        self.set_profile_id = set_profile_id
        self.current_profile_id = current_profile_id
        super().__init__(
            f"{path} was built with profile {set_profile_id}, "
            f"but the current profile is {current_profile_id}"
        )


def fingerprint_id(tokens: dict[str, str]) -> str:
    """Alphabetically sort tokens by key, flatten, and MD5-fold into a stable ID."""
    flattened = "|".join(f"{key}:{tokens[key]}" for key in sorted(tokens))
    return hashlib.md5(flattened.encode("utf-8")).hexdigest()


@dataclass
class Fingerprint:
    tokens: dict[str, str]
    count: int
    first_seen: str
    last_seen: str
    aggregates: dict[str, dict] = field(default_factory=dict)
    first: list[dict] = field(default_factory=list)
    last: list[dict] = field(default_factory=list)


class FingerprintSet:
    """The fingerprints seen so far, with versioned YAML load/save."""

    def __init__(
        self,
        aggregates: Sequence[Aggregate] = (),
        profile_id: str | None = None,
        samples: int = 3,
    ) -> None:
        self._records: dict[str, Fingerprint] = {}
        self._aggregates = tuple(aggregates)
        self.profile_id = profile_id
        self.samples = samples
        self.skipped_values = 0
        """Running count of values the aggregates could not use (see `Aggregate.update`)."""

    def upsert(self, tokens: dict[str, str], record: Any, timestamp: str | None = None) -> str:
        """Fold one event into the set. Returns its fingerprint_id.

        Every fingerprint gets the built-in metadata: `count`, wall-clock `first_seen` /
        `last_seen`, and the first and last `samples` events with the time each was seen.
        The profile's aggregates are folded over `record` as well.
        """
        fid = fingerprint_id(tokens)
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        existing = self._records.get(fid)
        if existing is None:
            existing = self._records[fid] = Fingerprint(dict(tokens), 0, ts, ts)
        existing.count += 1
        existing.last_seen = ts
        if len(existing.first) < self.samples:
            existing.first.append({"seen": ts, "event": copy.deepcopy(record)})
        existing.last.append({"seen": ts, "event": copy.deepcopy(record)})
        del existing.last[: max(len(existing.last) - self.samples, 0)]

        for entry in self._aggregates:
            state = existing.aggregates.setdefault(entry.key, {})
            self.skipped_values += entry.update(state, record)
            if not state:
                del existing.aggregates[entry.key]

        return fid

    def get(self, fingerprint_id_: str) -> Fingerprint | None:
        return self._records.get(fingerprint_id_)

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, fingerprint_id_: str) -> bool:
        return fingerprint_id_ in self._records

    def __iter__(self) -> Iterator[str]:
        return iter(self._records)

    def save(self, path: str) -> None:
        """Write the set to `path` atomically: a failed write leaves any existing file intact."""
        data = {
            "version": SET_VERSION,
            "profile_id": self.profile_id,
            "fingerprints": {fid: asdict(rec) for fid, rec in self._records.items()},
        }
        directory = os.path.dirname(os.path.abspath(path))
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".fingerprints-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                # Insertion order, not alphabetical: header first, and each record
                # leads with the tokens that explain its ID.
                yaml.safe_dump(data, f, sort_keys=False)
            os.replace(tmp_path, path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def load(self, path: str, *, force: bool = False) -> None:
        """Replace the in-memory set with the one stored at `path`.

        Raises ProfileMismatchError if the file records a different profile
        than this set was created with, unless `force` is set (the file's
        fingerprints are then adopted under the current profile).
        """
        data = _read_set_file(path)
        stored = data.get("profile_id")
        if not force and None not in (stored, self.profile_id) and stored != self.profile_id:
            raise ProfileMismatchError(path, stored, self.profile_id)
        try:
            self._records = {
                fid: Fingerprint(**rec) for fid, rec in (data["fingerprints"] or {}).items()
            }
        except TypeError as exc:
            raise FingerprintSetError(f"{path} has a malformed fingerprint entry: {exc}") from exc


def _read_set_file(path: str) -> dict:
    """Read a set file and check its header. An empty file is an empty set."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise FingerprintSetError(f"{path} is not valid YAML: {exc}") from exc
    if data is None:
        return {"version": SET_VERSION, "profile_id": None, "fingerprints": {}}
    if not isinstance(data, dict) or "fingerprints" not in data or "version" not in data:
        raise FingerprintSetError(
            f"{path} is not a fingerprint set (expected top-level 'version' and 'fingerprints')"
        )
    if data["version"] != SET_VERSION:
        raise FingerprintSetError(
            f"{path} is fingerprint set version {data['version']}; this tool reads version {SET_VERSION}"
        )
    return data
