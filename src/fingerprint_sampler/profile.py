"""Fingerprint profiles (STORY-FING-24).

A profile is a YAML file saying how to fingerprint an event stream:
`fields` define a fingerprint's identity, `aggregates` are the statistics
and samples tracked per fingerprint. Everything is validated when the
profile is loaded, so a mistake surfaces before any event is read.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import yaml

from fingerprint_sampler.aggregators import AggregateEntry, make_entry
from fingerprint_sampler.tokenizer import MaskEntry, compile_path, validate_modifier

PROFILE_VERSION = 1

_TOP_LEVEL_KEYS = {"version", "fields", "aggregates"}
_FIELD_KEYS = {"key", "path", "modifier"}
_AGGREGATE_KEYS = {"key", "path", "fn"}


class ProfileError(ValueError):
    """A profile is missing, unreadable or invalid. The message names the offending entry."""


def profile_id(fields: tuple[MaskEntry, ...] | list[MaskEntry]) -> str:
    """Stable ID of the identity-defining part of a profile (order-independent)."""
    lines = sorted(f"{entry.key}|{entry.path}|{entry.modifier}" for entry in fields)
    return hashlib.md5("\n".join(lines).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Profile:
    fields: tuple[MaskEntry, ...]
    aggregates: tuple[AggregateEntry, ...] = ()

    @property
    def profile_id(self) -> str:
        """Depends on `fields` only: editing aggregates never invalidates an existing set."""
        return profile_id(self.fields)


def _entry_mapping(raw: Any, where: str, allowed: set[str], required: tuple[str, ...]) -> dict:
    if not isinstance(raw, dict):
        raise ProfileError(f"{where}: expected a mapping with {sorted(allowed)}, got {raw!r}")
    label = f"{where} (key {raw['key']!r})" if isinstance(raw.get("key"), str) else where
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ProfileError(f"{label}: unknown setting(s) {unknown}; allowed: {sorted(allowed)}")
    for name in required:
        value = raw.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ProfileError(f"{label}: '{name}' is required and must be a non-empty string")
    return raw


def _no_duplicates(keys: list[str], section: str, source: str) -> None:
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ProfileError(f"{source}: duplicate key(s) in {section}: {', '.join(duplicates)}")


def parse_profile(data: Any, source: str = "<profile>") -> Profile:
    """Validate already-parsed profile data and build a `Profile`."""
    if not isinstance(data, dict):
        raise ProfileError(f"{source}: expected a mapping with 'fields', got {type(data).__name__}")
    unknown = sorted(set(data) - _TOP_LEVEL_KEYS)
    if unknown:
        raise ProfileError(
            f"{source}: unknown top-level setting(s) {unknown}; allowed: {sorted(_TOP_LEVEL_KEYS)}"
        )
    version = data.get("version", PROFILE_VERSION)
    if version != PROFILE_VERSION:
        raise ProfileError(
            f"{source}: profile version {version!r} is not supported (expected {PROFILE_VERSION})"
        )

    raw_fields = data.get("fields")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise ProfileError(f"{source}: 'fields' must be a non-empty list")
    raw_aggregates = data.get("aggregates") or []
    if not isinstance(raw_aggregates, list):
        raise ProfileError(f"{source}: 'aggregates' must be a list")

    fields = []
    for i, raw in enumerate(raw_fields):
        where = f"{source}: fields[{i}]"
        entry = _entry_mapping(raw, where, _FIELD_KEYS, ("key", "path"))
        modifier = entry.get("modifier", "DEFAULT")
        try:
            compile_path(entry["path"])
            validate_modifier(modifier)
        except ValueError as exc:
            raise ProfileError(f"{where} (key {entry['key']!r}): {exc}") from exc
        fields.append(MaskEntry(key=entry["key"], path=entry["path"], modifier=modifier))
    _no_duplicates([f.key for f in fields], "fields", source)

    aggregates = []
    for i, raw in enumerate(raw_aggregates):
        where = f"{source}: aggregates[{i}]"
        entry = _entry_mapping(raw, where, _AGGREGATE_KEYS, ("key", "path"))
        if "fn" not in entry:
            raise ProfileError(
                f"{where} (key {entry['key']!r}): 'fn' is required, e.g. fn: [MIN, MAX]"
            )
        try:
            aggregates.append(make_entry(entry["key"], entry["path"], entry["fn"]))
        except ValueError as exc:
            raise ProfileError(f"{where} (key {entry['key']!r}): {exc}") from exc
    _no_duplicates([a.key for a in aggregates], "aggregates", source)

    return Profile(fields=tuple(fields), aggregates=tuple(aggregates))


def load_profile(path: str) -> Profile:
    """Load and validate a YAML profile file. Raises ProfileError with the file and entry named."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except OSError as exc:
        raise ProfileError(f"Cannot read profile {path}: {exc.strerror or exc}") from exc
    except yaml.YAMLError as exc:
        raise ProfileError(f"{path}: not valid YAML: {exc}") from exc
    return parse_profile(data, source=path)
