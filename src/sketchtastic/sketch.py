"""The sketch: a stateful, mergeable inventory of skits.

Serializes tokenized events into a stable MD5 skit ID and reconciles
every observation against one bounded-size record per skit. Which
statistics and samples a record keeps is declared by the caller as a list of
aggregators, so the sketch works for any event stream, not just eBPF telemetry.
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

SKETCH_VERSION = 0
"""Format version of sketch files: 0 until 1.0, when the format becomes stable."""


class SketchError(ValueError):
    """A sketch file can't be used (unreadable, wrong format, wrong version)."""


class ProfileMismatchError(SketchError):
    """The sketch file was built with a different profile than the one now in use."""

    def __init__(self, path: str, set_profile_id: str, current_profile_id: str) -> None:
        self.set_profile_id = set_profile_id
        self.current_profile_id = current_profile_id
        super().__init__(
            f"{path} was built with profile {set_profile_id}, "
            f"but the current profile is {current_profile_id}"
        )


def skit_id(tokens: dict[str, str]) -> str:
    """Alphabetically sort tokens by key, flatten, and MD5-fold into a stable ID."""
    flattened = "|".join(f"{key}:{tokens[key]}" for key in sorted(tokens))
    return hashlib.md5(flattened.encode("utf-8")).hexdigest()


@dataclass
class Skit:
    tokens: dict[str, str]
    aggregates: dict[str, Any] = field(default_factory=dict)
    """What the profile asked for, keyed by its aggregate keys."""
    meta: dict[str, Any] = field(default_factory=dict)
    """The built-in metadata (`builtin.yaml`): count, first/last run seen in, first/last records."""
    share: dict[str, Any] = field(default_factory=dict)
    """Percent of the sketch total for each SUM and COUNT in `meta` and `aggregates`, laid out
    like them. Derived: rewritten on every save, never folded."""


SHARED_FUNCTIONS = ("SUM", "COUNT")
"""Functions whose values add up across skits, so a share of their total means something."""


@cache
def builtin_aggregates() -> tuple[Aggregate, ...]:
    """The aggregates every skit gets, from the `builtin.yaml` shipped with the package."""
    text = files("sketchtastic").joinpath("builtin.yaml").read_text("utf-8")
    return tuple(Aggregate(**raw) for raw in yaml.safe_load(text)["aggregates"])


def _fold(aggregates: Sequence[Aggregate], states: dict[str, Any], event: Any) -> int:
    """Fold `event` into each aggregate's state. Returns how many values were skipped."""
    return sum(aggregate.update(states, event) for aggregate in aggregates)


class Sketch:
    """The skits seen so far, with versioned YAML load/save."""

    def __init__(
        self,
        aggregates: Sequence[Aggregate] = (),
        profile_id: str | None = None,
    ) -> None:
        self._records: dict[str, Skit] = {}
        self._aggregates = tuple(aggregates)
        self.profile_id = profile_id
        self.skipped_values = 0
        """Running count of present values the profile's aggregates could not use."""
        self.last_run: str | None = None
        """Id of the latest run merged into this sketch (`YYMMDD-SEQ`); saved and loaded."""
        self.sequence: dict[str, Any] | None = None
        """Duplicate-protection mark (STORY-FING-50): {path, max}; saved and loaded."""
        self.run: dict[str, Any] | None = None
        """Header of a run file (STORY-FING-48): what one run read. Saved if set; never loaded."""

    def upsert(self, tokens: dict[str, str], record: Any, run: str | None = None) -> str:
        """Fold one record into the sketch. Returns its skit_id.

        The profile's aggregates read the record. The built-in ones read an envelope,
        {"meta": {"run": run}, "record": record}, so injected fields never clash with the
        record's own; `run` is the id of the run reading it.
        """
        fid = skit_id(tokens)
        skit = self._records.setdefault(fid, Skit(dict(tokens)))
        envelope = {"meta": {"run": run}, "record": record}
        self.skipped_values += _fold(self._aggregates, skit.aggregates, record)
        _fold(builtin_aggregates(), skit.meta, envelope)
        return fid

    def get(self, skit_id_: str) -> Skit | None:
        return self._records.get(skit_id_)

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, skit_id_: str) -> bool:
        return skit_id_ in self._records

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
        """Write the sketch to `path` atomically: a failed write leaves any existing file intact.

        Each record's `share` is recomputed first, so it describes the sketch as written.
        """
        self._compute_shares()
        data = {"version": SKETCH_VERSION, "profile_id": self.profile_id}
        if self.last_run is not None:
            data["last_run"] = self.last_run
        if self.sequence is not None:
            data["sequence"] = self.sequence
        if self.run is not None:
            data["run"] = self.run
        data["skits"] = {fid: asdict(rec) for fid, rec in self._records.items()}
        directory = os.path.dirname(os.path.abspath(path))
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".sketch-", suffix=".tmp")
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
        """Replace the in-memory sketch with the one stored at `path`.

        Raises ProfileMismatchError if the file records a different profile
        than this sketch was created with, unless `force` is set (the file's
        skits are then adopted under the current profile).
        """
        data = _read_set_file(path)
        stored = data.get("profile_id")
        if not force and None not in (stored, self.profile_id) and stored != self.profile_id:
            raise ProfileMismatchError(path, stored, self.profile_id)
        self.last_run = data.get("last_run")
        self.sequence = data.get("sequence")
        try:
            self._records = {fid: Skit(**rec) for fid, rec in (data["skits"] or {}).items()}
        except TypeError as exc:
            raise SketchError(f"{path} has a malformed skit entry: {exc}") from exc


def _read_set_file(path: str) -> dict:
    """Read a sketch file and check its header. An empty file is an empty sketch."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise SketchError(f"{path} is not valid YAML: {exc}") from exc
    if data is None:
        return {"version": SKETCH_VERSION, "profile_id": None, "skits": {}}
    if not isinstance(data, dict) or "skits" not in data or "version" not in data:
        raise SketchError(f"{path} is not a sketch (expected top-level 'version' and 'skits')")
    if data["version"] != SKETCH_VERSION:
        raise SketchError(
            f"{path} is sketch version {data['version']}; this tool reads version {SKETCH_VERSION}"
        )
    return data
