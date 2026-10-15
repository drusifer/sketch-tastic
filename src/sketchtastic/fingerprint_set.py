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
from functools import cache
from importlib.resources import files
from typing import Any, Iterator, Sequence

import yaml

from sketchtastic.aggregators import Aggregate

SET_VERSION = 0
"""Format version of set files: 0 until 1.0, when the format becomes stable."""


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
    aggregates: dict[str, Any] = field(default_factory=dict)
    """What the profile asked for, keyed by its aggregate keys."""
    meta: dict[str, Any] = field(default_factory=dict)
    """The built-in metadata (`builtin.yaml`): count, first/last run seen in, first/last records."""
    share: dict[str, Any] = field(default_factory=dict)
    """Percent of the set total for each SUM and COUNT in `meta` and `aggregates`, laid out
    like them. Derived: rewritten on every save, never folded."""


SHARED_FUNCTIONS = ("SUM", "COUNT")
"""Functions whose values add up across fingerprints, so a share of their total means something."""


@cache
def builtin_aggregates() -> tuple[Aggregate, ...]:
    """The aggregates every fingerprint gets, from the `builtin.yaml` shipped with the package."""
    text = files("sketchtastic").joinpath("builtin.yaml").read_text("utf-8")
    return tuple(Aggregate(**raw) for raw in yaml.safe_load(text)["aggregates"])


def _fold(aggregates: Sequence[Aggregate], states: dict[str, Any], event: Any) -> int:
    """Fold `event` into each aggregate's state. Returns how many values were skipped."""
    return sum(aggregate.update(states, event) for aggregate in aggregates)


class FingerprintSet:
    """The fingerprints seen so far, with versioned YAML load/save."""

    def __init__(
        self,
        aggregates: Sequence[Aggregate] = (),
        profile_id: str | None = None,
    ) -> None:
        self._records: dict[str, Fingerprint] = {}
        self._aggregates = tuple(aggregates)
        self.profile_id = profile_id
        self.skipped_values = 0
        """Running count of present values the profile's aggregates could not use."""
        self.last_run: str | None = None
        """Id of the latest run merged into this set (`YYMMDD-SEQ`); saved and loaded."""
        self.sequence: dict[str, Any] | None = None
        """Duplicate-protection mark (STORY-FING-50): {path, max}; saved and loaded."""
        self.run: dict[str, Any] | None = None
        """Header of a run file (STORY-FING-48): what one run read. Saved if set; never loaded."""

    def upsert(self, tokens: dict[str, str], record: Any, run: str | None = None) -> str:
        """Fold one record into the set. Returns its fingerprint_id.

        The profile's aggregates read the record. The built-in ones read an envelope,
        {"meta": {"run": run}, "record": record}, so injected fields never clash with the
        record's own; `run` is the id of the run reading it.
        """
        fid = fingerprint_id(tokens)
        fingerprint = self._records.setdefault(fid, Fingerprint(dict(tokens)))
        envelope = {"meta": {"run": run}, "record": record}
        self.skipped_values += _fold(self._aggregates, fingerprint.aggregates, record)
        _fold(builtin_aggregates(), fingerprint.meta, envelope)
        return fid

    def get(self, fingerprint_id_: str) -> Fingerprint | None:
        return self._records.get(fingerprint_id_)

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, fingerprint_id_: str) -> bool:
        return fingerprint_id_ in self._records

    def __iter__(self) -> Iterator[str]:
        return iter(self._records)

    def _compute_shares(self) -> None:
        """Set every record's `share` from the current values (STORY-FING-46)."""
        for record in self._records.values():
            record.share = {}
        for section, aggregates in (
            ("meta", builtin_aggregates()),
            ("aggregates", self._aggregates),
        ):
            for aggregate in aggregates:
                for function in aggregate.fn:
                    if function.name in SHARED_FUNCTIONS:
                        self._share(section, aggregate, function)

    def _share(self, section: str, aggregate: Aggregate, function: Any) -> None:
        values = []
        for record in self._records.values():
            value = aggregate.value(getattr(record, section), function)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append((record, value))
        total = sum(value for _, value in values)
        if not total:
            return
        for record, value in values:
            target = record.share.setdefault(section, {})
            aggregate.store(target, function, round(100 * value / total, 2))

    def save(self, path: str) -> None:
        """Write the set to `path` atomically: a failed write leaves any existing file intact.

        Each record's `share` is recomputed first, so it describes the set as written.
        """
        self._compute_shares()
        data = {"version": SET_VERSION, "profile_id": self.profile_id}
        if self.last_run is not None:
            data["last_run"] = self.last_run
        if self.sequence is not None:
            data["sequence"] = self.sequence
        if self.run is not None:
            data["run"] = self.run
        data["fingerprints"] = {fid: asdict(rec) for fid, rec in self._records.items()}
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
        self.last_run = data.get("last_run")
        self.sequence = data.get("sequence")
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
