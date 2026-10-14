"""Fingerprint profiles (STORY-FING-24, -37).

A profile is a YAML file saying how to fingerprint an event stream:
`fields` define a fingerprint's identity, `aggregates` are the statistics
and samples tracked per fingerprint.

Checking happens in two layers that report together. The shape is checked
against the published JSON Schema (`profile.schema.json`) by a standard
validator; only if the shape is right are the things a schema cannot express
checked: JSONPaths and regexes compile, ranges are ordered, keys are unique,
aggregate functions exist. Every problem is reported, not just the first.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import yaml

from fingerprint_sampler.aggregators import AggregateEntry, make_entry
from fingerprint_sampler.schema import schema_errors
from fingerprint_sampler.tokenizer import MaskEntry, compile_path

PROFILE_VERSION = 1


class ProfileError(ValueError):
    """A profile is missing, unreadable or invalid. `problems` lists every one, located."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("\n".join(problems))


def profile_id(fields: tuple[MaskEntry, ...] | list[MaskEntry]) -> str:
    """Stable ID of the identity-defining part of a profile (order-independent)."""
    lines = sorted(f"{entry.key}|{entry.path}|{entry.modifier.spec}" for entry in fields)
    return hashlib.md5("\n".join(lines).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Profile:
    fields: tuple[MaskEntry, ...]
    aggregates: tuple[AggregateEntry, ...] = ()

    @property
    def profile_id(self) -> str:
        """Depends on `fields` only: editing aggregates never invalidates an existing set."""
        return profile_id(self.fields)


def _location(data: Any, path: tuple) -> str:
    """Render a schema path like ('fields', 2, 'modifier') as "fields[2] (key 'route') → modifier"."""
    if not path:
        return "(top level)"
    text = str(path[0])
    rest = list(path[1:])
    if rest and isinstance(rest[0], int):
        index = rest.pop(0)
        text += f"[{index}]"
        try:
            key = data[path[0]][index].get("key")
        except AttributeError, IndexError, KeyError, TypeError:
            key = None
        if isinstance(key, str):
            text += f" (key {key!r})"
    if rest:
        text += " → " + ".".join(str(p) for p in rest)
    return text


def check_profile(data: Any, source: str = "<profile>") -> tuple[Profile | None, list[str]]:
    """Check already-parsed profile data. Returns (profile or None, every problem found)."""
    problems = [
        f"{source}: {_location(data, path)}: {message}" for path, message in schema_errors(data)
    ]
    if problems:
        return None, problems

    def entry_problem(section: str, index: int, key: str, exc: Exception) -> str:
        return f"{source}: {section}[{index}] (key {key!r}): {exc}"

    fields = []
    for i, raw in enumerate(data["fields"]):
        try:
            compile_path(raw["path"])
            fields.append(MaskEntry(raw["key"], raw["path"], raw.get("modifier", "DEFAULT")))
        except ValueError as exc:
            problems.append(entry_problem("fields", i, raw["key"], exc))

    aggregates = []
    for i, raw in enumerate(data.get("aggregates") or []):
        try:
            aggregates.append(make_entry(raw["key"], raw["path"], raw["fn"]))
        except ValueError as exc:
            problems.append(entry_problem("aggregates", i, raw["key"], exc))

    for section in ("fields", "aggregates"):
        keys = [raw["key"] for raw in data.get(section) or []]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            problems.append(f"{source}: {section}: duplicate key(s): {', '.join(duplicates)}")

    if problems:
        return None, problems
    return Profile(fields=tuple(fields), aggregates=tuple(aggregates)), []


def parse_profile(data: Any, source: str = "<profile>") -> Profile:
    """Check already-parsed profile data and build a `Profile`. Raises ProfileError."""
    profile, problems = check_profile(data, source)
    if problems:
        raise ProfileError(problems)
    return profile


def read_profile(path: str) -> Any:
    """Read a profile file's YAML. Raises ProfileError (with line and column for YAML errors)."""
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except OSError as exc:
        raise ProfileError([f"Cannot read profile {path}: {exc.strerror or exc}"]) from exc
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 1}, column {mark.column + 1}: " if mark else ""
        reason = getattr(exc, "problem", None) or str(exc)
        raise ProfileError([f"{path}: {where}not valid YAML: {reason}"]) from exc


def load_profile(path: str) -> Profile:
    """Load and check a YAML profile file. Raises ProfileError listing every problem."""
    return parse_profile(read_profile(path), source=path)
