"""The fingerprint set: a stateful, mergeable inventory of fingerprints.

Serializes tokenized events into a stable MD5 fingerprint ID and reconciles
every observation against one bounded-size record per fingerprint. Which
statistics and samples a record keeps is declared by the caller as a list of
aggregators, so the set works for any event stream, not just eBPF telemetry.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Sequence

import yaml

from fingerprint_sampler.aggregators import Aggregate

SET_VERSION = 1


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
class FingerprintRecord:
    tokens: dict[str, str]
    total_occurrences: int
    first_seen: str
    last_seen: str
    aggregates: dict[str, dict] = field(default_factory=dict)


class Warehouse:
    """In-memory fingerprint set with versioned YAML load/save."""

    def __init__(
        self,
        aggregates: Sequence[Aggregate] = (),
        profile_id: str | None = None,
    ) -> None:
        self._records: dict[str, FingerprintRecord] = {}
        self._aggregates = tuple(aggregates)
        self.profile_id = profile_id
        self.skipped_values = 0
        """Running count of values the aggregates could not use (see `Aggregate.update`)."""

    def upsert(self, tokens: dict[str, str], record: Any, timestamp: str | None = None) -> str:
        """Fold one event into the set. Returns its fingerprint_id.

        Match: increments total_occurrences and updates last_seen — no new
        record block. Drift: creates a new record block. Either way every
        configured aggregator is folded over `record`.
        """
        fid = fingerprint_id(tokens)
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        existing = self._records.get(fid)

        if existing is None:
            existing = self._records[fid] = FingerprintRecord(
                tokens=dict(tokens), total_occurrences=1, first_seen=ts, last_seen=ts
            )
        else:
            existing.total_occurrences += 1
            existing.last_seen = ts

        for entry in self._aggregates:
            state = existing.aggregates.setdefault(entry.key, {})
            self.skipped_values += entry.update(state, record)
            if not state:
                del existing.aggregates[entry.key]

        return fid

    def get(self, fingerprint_id_: str) -> FingerprintRecord | None:
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

    def load(self, path: str, force: bool = False) -> None:
        """Replace the in-memory set with the one stored at `path`.

        Raises ProfileMismatchError if the file records a different profile
        than this warehouse was created with, unless `force` is set (the file's
        fingerprints are then adopted under the current profile).
        """
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise FingerprintSetError(f"{path} is not valid YAML: {exc}") from exc

        if data is None:
            data = {"version": SET_VERSION, "profile_id": None, "fingerprints": {}}
        if not isinstance(data, dict) or "fingerprints" not in data or "version" not in data:
            raise FingerprintSetError(
                f"{path} is not a fingerprint set (expected top-level 'version' and "
                f"'fingerprints'); sets written before the aggregator format are not supported"
            )
        if data["version"] != SET_VERSION:
            raise FingerprintSetError(
                f"{path} is fingerprint set version {data['version']}; "
                f"this tool reads version {SET_VERSION}"
            )

        stored_profile = data.get("profile_id")
        if (
            not force
            and stored_profile is not None
            and self.profile_id is not None
            and stored_profile != self.profile_id
        ):
            raise ProfileMismatchError(path, stored_profile, self.profile_id)

        try:
            self._records = {
                fid: FingerprintRecord(**rec) for fid, rec in (data["fingerprints"] or {}).items()
            }
        except TypeError as exc:
            raise FingerprintSetError(f"{path} has a malformed fingerprint entry: {exc}") from exc
