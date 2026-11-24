"""Derive a coarser sketch from retained states, never from representative samples."""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sketchtastic._derive_validation import merge_states, validate_states
from sketchtastic._io import is_number
from sketchtastic.model import MISSING, Field, canonical_set, is_token
from sketchtastic.profile import Profile
from sketchtastic.sketch import SKETCH_VERSION, Sketch, builtin_aggregates, skit_id

_STRING_RULES = {"ANY", "GLOB", "REGEX", "REGSUB", "IS_NULL"}
_TIME_UNITS = ("year", "month", "day", "hour", "minute", "second")
_TIME_SUFFIXES = ("-01-01", "-01", "", ":00:00", ":00", "")


@dataclass(frozen=True)
class FieldTransform:
    source: Field
    target: Field
    mode: str

    def apply(self, token: Any) -> Any:
        """One old field token deterministically produces one new field token."""
        if self.mode == "copy":
            return token
        if self.mode == "presence":
            return "FALSE" if token is MISSING else "TRUE"
        if self.mode == "string":
            if isinstance(token, list):
                raise ValueError(
                    f"field {self.target.key!r}: cannot prove transformation of an array; "
                    "a selected array and multiple scalar matches may have different meaning"
                )
            return self.target.modifier.token(token)
        if token is MISSING:
            return MISSING
        values = token if isinstance(token, list) else [token]
        transformed = canonical_set([self._time(value) for value in values])
        return transformed[0] if len(transformed) == 1 else transformed

    def _time(self, token: Any) -> str | None:
        if token is None:
            return None
        if not isinstance(token, str):
            raise ValueError(f"field {self.source.key!r}: invalid retained temporal token")
        if self.source.modifier.name == "DEFAULT":
            value = self.source.type.convert(token)
            if value is None or value.isoformat() != token:
                raise ValueError(f"field {self.source.key!r}: invalid retained temporal token")
        else:
            index = _TIME_UNITS.index(self.source.modifier.unit)
            try:
                value = datetime.fromisoformat(token + _TIME_SUFFIXES[index])
            except ValueError as exc:
                raise ValueError(f"field {self.source.key!r}: invalid truncated time") from exc
            if self.source.modifier.token(value) != token:
                raise ValueError(f"field {self.source.key!r}: noncanonical truncated time")
        return self.target.modifier.token(value)


def _mode(source: Field, target: Field) -> str | None:
    if source.path != target.path or source.type != target.type:
        return None
    old, new = source.modifier.name, target.modifier.name
    if source.modifier == target.modifier:
        return "copy"
    if source.type is None and old == "DEFAULT":
        modes = {name: "string" for name in _STRING_RULES}
        return {**modes, "IS_PRESENT": "presence"}.get(new)
    if source.type is not None and new == "TRUNC" and _coarsens_time(source, target):
        return "time"
    return None


def _coarsens_time(source: Field, target: Field) -> bool:
    if source.modifier.name == "DEFAULT":
        return True
    return source.modifier.name == "TRUNC" and _TIME_UNITS.index(
        target.modifier.unit
    ) <= _TIME_UNITS.index(source.modifier.unit)


def build_transforms(source: Profile, target: Profile) -> tuple[FieldTransform, ...]:
    """Prove supported profile changes before looking at or writing any sketch state."""
    for setting in ("aggregates", "sequence", "event_time"):
        if getattr(source, setting) != getattr(target, setting):
            raise ValueError(f"changed {setting}: derivation requires unchanged {setting}")
    transforms = []
    for field in target.fields:
        candidates = [(old, _mode(old, field)) for old in source.fields]
        supported = [(old, mode) for old, mode in candidates if mode is not None]
        supported.sort(key=lambda pair: (pair[1] != "copy", pair[0].key != field.key))
        if not supported:
            raise ValueError(
                f"field {field.key!r}: cannot prove a collapsing transform from retained fields; "
                "use original events or a compatible target profile"
            )
        old, mode = supported[0]
        transforms.append(FieldTransform(old, field, mode))
    return tuple(transforms)


def _validate_record(sid: str, record: dict, source: Profile) -> None:
    tokens = record.get("tokens")
    keys = [f.key for f in source.fields]
    if not isinstance(tokens, dict) or list(tokens) != [key for key in keys if key in tokens]:
        raise ValueError(f"skit {sid!r}: invalid source field keys/order")
    if any(not is_token(value) for value in tokens.values()):
        raise ValueError(f"skit {sid!r}: invalid structured token")
    _validate_predicates(tokens, source, sid)
    if sid != skit_id(tokens):
        raise ValueError(f"skit {sid!r}: ID does not match tokens")
    validate_states(record.get("aggregates"), source.aggregates, f"skit {sid}.aggregates")
    validate_states(record.get("meta"), builtin_aggregates(), f"skit {sid}.meta")


def _validate_predicates(tokens: dict, source: Profile, sid: str) -> None:
    for field in source.fields:
        if field.modifier.name in {"DEFAULT", "REGSUB", "TRUNC"}:
            continue
        token = tokens.get(field.key, MISSING)
        if token not in ("FALSE", "TRUE", ["FALSE", "TRUE"]):
            raise ValueError(f"skit {sid!r}: missing or invalid predicate token {field.key!r}")


def _rekey_records(raw: dict, source: Profile, transforms: tuple[FieldTransform, ...]) -> dict:
    records = {}
    for sid, record in raw.items():
        _validate_record(sid, record, source)
        tokens = {}
        for transform in transforms:
            token = transform.apply(record["tokens"].get(transform.source.key, MISSING))
            if token is not MISSING:
                tokens[transform.target.key] = copy.deepcopy(token)
        key = skit_id(tokens)
        copied = copy.deepcopy(record)
        copied["tokens"] = tokens
        copied["share"] = {}
        if key not in records:
            records[key] = copied
            continue
        mine = records[key]
        merge_states(mine["aggregates"], copied["aggregates"], source.aggregates, key)
        merge_states(mine["meta"], copied["meta"], builtin_aggregates(), key)
    return records


def derive_data(
    raw: dict,
    source: Profile,
    target: Profile,
    *,
    source_name: str,
    output_name: str,
) -> Sketch:
    """Collapse one validated inventory; history uses exactly this same transformation."""
    transforms = build_transforms(source, target)
    if raw.get("version") != SKETCH_VERSION or type(raw.get("version")) is not int:
        raise ValueError(
            f"{source_name}: expected sketch format {SKETCH_VERSION}; recapture required"
        )
    if raw.get("profile_id") != source.profile_id:
        raise ValueError(f"{source_name}: source profile does not match stored profile_id")
    if not isinstance(raw.get("skits"), dict):
        raise ValueError(f"{source_name}: invalid skits mapping")
    _validate_continuation(raw, source)
    try:
        records = _rekey_records(raw["skits"], source, transforms)
    except (AttributeError, KeyError, TypeError) as exc:
        raise ValueError(f"{source_name}: malformed retained state: {exc}") from exc
    header = {key: copy.deepcopy(raw[key]) for key in ("last_run", "sequence") if key in raw}
    header.update(version=SKETCH_VERSION, profile_id=target.profile_id, skits=records)
    header["derivation"] = {
        "source": source_name,
        "source_profile_id": source.profile_id,
        "target_profile_id": target.profile_id,
    }
    result = Sketch(target.aggregates, target.profile_id)
    result.load_data(header, source_name)
    result.derivation = header["derivation"]
    if "run" in raw:
        if not isinstance(raw["run"], dict):
            raise ValueError(f"{source_name}: invalid run header")
        result.run = {**copy.deepcopy(raw["run"]), "sketch": output_name}
    return result


def _validate_continuation(raw: dict, source: Profile) -> None:
    if "last_run" in raw and (
        not isinstance(raw["last_run"], str) or not re.fullmatch(r"\d{6}-\d{4,}", raw["last_run"])
    ):
        raise ValueError("invalid last_run; cannot preserve run continuation")
    if "sequence" not in raw:
        return
    _validate_sequence(raw["sequence"], source)


def _validate_sequence(mark: Any, source: Profile) -> None:
    if (
        not isinstance(mark, dict)
        or set(mark) != {"path", "max"}
        or source.sequence is None
        or mark["path"] != source.sequence.text
        or not is_number(mark["max"])
    ):
        raise ValueError("invalid sequence high-water mark for source profile")
    try:
        finite = math.isfinite(mark["max"])
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("invalid non-finite sequence high-water mark")
