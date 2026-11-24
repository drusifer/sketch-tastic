"""The sketch: a stateful, mergeable inventory of skits.

Serializes tokenized events into a stable MD5 skit ID and reconciles
every observation against one bounded-size record per skit. Which
statistics and samples a record keeps is declared by the caller as a list of
aggregators, so the sketch works for any event stream, not just eBPF telemetry.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterator, Sequence

import yaml

from sketchtastic import _yaml
from sketchtastic._io import atomic_replace_file, is_number
from sketchtastic.aggregators import Aggregate
from sketchtastic.model import MISSING

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
    """MD5 of the token values in profile order (`tokens` as the profile makes them).

    The keys add nothing: the profile fixes them and their order, and the sketch's profile id
    covers both. The values are JSON-encoded so none can be mistaken for a separator.
    """
    values = json.dumps(list(tokens.values()), ensure_ascii=False, separators=(",", ":"))
    return hashlib.md5(values.encode("utf-8")).hexdigest()


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
    return tuple(Aggregate(**raw) for raw in _yaml.load(text)["aggregates"])


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

    def upsert(
        self,
        tokens: dict[str, str],
        record: Any,
        run: str | None = None,
        *,
        seen: Any = MISSING,
    ) -> str:
        """Fold one record into the sketch. Returns its skit_id.

        The profile's aggregates read the record. The built-in ones read an internal envelope
        whose `sample` is {"meta": {"run": run}, "record": record} and whose `meta.seen` defaults
        to `run` (or the caller-supplied `seen` value, such as an event UTC datetime from
        `profile.event_time`).

        The sketch keeps references, not copies: FIRST and LAST store `record` (or parts of
        it) as given, so the caller must not modify `record` afterwards.
        """
        sid = skit_id(tokens)
        skit = self._records.get(sid)
        if skit is None:
            skit = self._records[sid] = self._new_skit(tokens)
        seen_value = run if seen is MISSING else seen
        sample = {"meta": {"run": run}, "record": record}
        envelope = {"meta": {"run": run, "seen": seen_value}, "sample": sample}
        self.skipped_values += _fold(self._aggregates, skit.aggregates, record)
        _fold(builtin_aggregates(), skit.meta, envelope)
        return sid

    def merge(self, later: Sketch) -> None:
        """Fold `later` (a sketch of events that came after this one's) into this sketch.

        The result equals folding both streams' events one by one (each aggregate function
        merges its state), except that a MIN/MAX of a different kind from this sketch's keeps
        this sketch's value without counting `later`'s values as skipped. Merged skits are
        copies: `later` can change afterwards without changing this sketch.
        """
        if later._aggregates != self._aggregates:
            raise SketchError("cannot merge sketches with different aggregates")
        for sid, skit in later._records.items():
            copied = copy.deepcopy(skit)
            mine = self._records.get(sid)
            if mine is None:
                self._records[sid] = copied
                continue
            for aggregate in self._aggregates:
                aggregate.merge(mine.aggregates, copied.aggregates)
            for aggregate in builtin_aggregates():
                aggregate.merge(mine.meta, copied.meta)
        self.skipped_values += later.skipped_values

    def _new_skit(self, tokens: dict[str, str], stored: Skit | None = None) -> Skit:
        """A skit with every aggregate and built-in, in profile order: from `stored` (a loaded
        file) where it has them, else initial. Keys `stored` has beyond the profile follow."""
        skit = Skit(dict(tokens))
        for states, aggregates, old in (
            (skit.aggregates, self._aggregates, stored.aggregates if stored else {}),
            (skit.meta, builtin_aggregates(), stored.meta if stored else {}),
        ):
            for aggregate in aggregates:
                aggregate.init(states, old)
            states.update((key, value) for key, value in old.items() if key not in states)
        if stored:
            skit.share = stored.share
        return skit

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
            if is_number(value):
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
        data: dict[str, Any] = {"version": SKETCH_VERSION, "profile_id": self.profile_id}
        if self.last_run is not None:
            data["last_run"] = self.last_run
        if self.sequence is not None:
            data["sequence"] = self.sequence
        if self.run is not None:
            data["run"] = self.run
        data["skits"] = {sid: asdict(rec) for sid, rec in self._records.items()}
        # Insertion order, not alphabetical: header first, and each record leads with tokens.
        atomic_replace_file(path, ".sketch-", lambda stream: _yaml.dump(data, stream))

    def load_data(self, data: dict[str, Any], path: str, *, force: bool = False) -> None:
        """Populate this sketch from an already-parsed sketch mapping."""
        stored_profile = data.get("profile_id")
        if (
            not force
            and None not in (stored_profile, self.profile_id)
            and stored_profile != self.profile_id
        ):
            raise ProfileMismatchError(path, stored_profile, self.profile_id)
        self.last_run = data.get("last_run")
        self.sequence = data.get("sequence")
        skits_raw = data["skits"] or {}
        if not isinstance(skits_raw, dict):
            raise SketchError(f"{path} has a malformed 'skits' mapping")
        try:
            stored = {sid: Skit(**rec) for sid, rec in skits_raw.items()}
            self._records = {sid: self._new_skit(rec.tokens, rec) for sid, rec in stored.items()}
        except (AttributeError, TypeError, ValueError) as exc:
            raise SketchError(f"{path} has a malformed skit entry: {exc}") from exc

    def load(self, path: str, *, force: bool = False) -> None:
        """Replace the in-memory sketch with the one stored at `path`.

        Raises ProfileMismatchError if the file records a different profile
        than this sketch was created with, unless `force` is set (the file's
        skits are then adopted under the current profile).
        """
        self.load_data(read_sketch_file(path), path, force=force)


def read_sketch_file(path: Path | str) -> dict[str, Any]:
    """Read a sketch file once and check its header. An empty file is an empty sketch."""
    text_path = str(path)
    try:
        with open(text_path, encoding="utf-8") as f:
            data = _yaml.load(f)
    except yaml.YAMLError as exc:
        raise SketchError(f"{text_path} is not valid YAML: {exc}") from exc
    if data is None:
        return {"version": SKETCH_VERSION, "profile_id": None, "skits": {}}
    if not isinstance(data, dict) or "skits" not in data or "version" not in data:
        raise SketchError(f"{text_path} is not a sketch (expected top-level 'version' and 'skits')")
    if type(data["version"]) is not int or data["version"] != SKETCH_VERSION:
        raise SketchError(
            f"{text_path} is sketch version {data['version']}; "
            f"this tool reads version {SKETCH_VERSION}"
        )
    return data


def load_sketch_with_header(
    path: Path | str, *, profile_id: str | None = None
) -> tuple[dict[str, Any], Sketch]:
    """Parse a sketch file once and return `(raw_header, loaded_sketch)`."""
    text_path = str(path)
    raw = read_sketch_file(text_path)
    if profile_id is not None:
        stored = raw.get("profile_id")
        if stored != profile_id:
            raise ValueError(f"Baseline profile {stored!r} does not match profile {profile_id!r}")
    sketch = Sketch(profile_id=profile_id)
    sketch.load_data(raw, text_path)
    return raw, sketch


def _validate_skit(key: Any, skit: Skit) -> None:
    if not isinstance(key, str) or not isinstance(skit.tokens, dict):
        raise ValueError("Malformed skit identity")
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in skit.tokens.items()):
        raise ValueError(f"Malformed tokens for skit {key!r}")
    if key != skit_id(skit.tokens):
        raise ValueError(f"Skit ID {key!r} does not match its tokens")
    count = skit.meta.get("count")
    if type(count) is not int or count < 0:
        raise ValueError(f"Invalid count for skit {key!r}: expected nonnegative integer")


def load_ranked_skits(
    path: Path | str, profile_id: str | None = None
) -> tuple[dict[str, Any], list[tuple[str, Skit]]]:
    """Load a sketch once, validate every skit's identity/count, and rank by descending count."""
    try:
        raw, sketch = load_sketch_with_header(path, profile_id=profile_id)
        rows = [(key, sketch.get(key)) for key in sketch]
        for key, skit in rows:
            assert skit is not None
            _validate_skit(key, skit)
    except (AttributeError, KeyError, TypeError) as exc:
        raise SketchError(f"Malformed sketch: {path}") from exc
    ranked = sorted(rows, key=lambda item: (-item[1].meta["count"], item[0]))
    return raw, ranked
