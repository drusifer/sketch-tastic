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

from sketchtastic.aggregators import Aggregate
from sketchtastic.model import Field, Path, tokens
from sketchtastic.schema import schema_errors

_SECTIONS = {"fields": Field, "aggregates": Aggregate}


class ProfileError(ValueError):
    """A profile is missing, unreadable or invalid. `problems` lists every one, located."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("\n".join(problems))


def profile_id(fields: tuple[Field, ...] | list[Field]) -> str:
    """Stable ID of the identity-defining part of a profile (order-independent)."""
    lines = sorted(f.spec for f in fields)
    return hashlib.md5("\n".join(lines).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Profile:
    fields: tuple[Field, ...]
    aggregates: tuple[Aggregate, ...] = ()
    sequence: Path | None = None
    """Where each event's sequence number is (STORY-FING-49): drops events already merged."""

    @property
    def profile_id(self) -> str:
        """Depends on `fields` only: editing aggregates never invalidates an existing set."""
        return profile_id(self.fields)

    def tokens(self, event: Any) -> dict[str, str]:
        """The tokens this profile's fields make of `event`, by key."""
        return tokens(event, self.fields)


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


def _build(data: dict, section: str, source: str, problems: list[str]) -> list:
    """Build one section's entries, adding each failure (and duplicate keys) to `problems`."""
    entries = data.get(section) or []
    built = []
    for i, raw in enumerate(entries):
        try:
            built.append(_SECTIONS[section](**raw))
        except ValueError as exc:
            problems.append(f"{source}: {section}[{i}] (key {raw['key']!r}): {exc}")
    keys = [raw["key"] for raw in entries]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        problems.append(f"{source}: {section}: duplicate key(s): {', '.join(duplicates)}")
    return built


def check_profile(data: Any, source: str = "<profile>") -> tuple[Profile | None, list[str]]:
    """Check already-parsed profile data. Returns (profile or None, every problem found)."""
    problems = [
        f"{source}: {_location(data, path)}: {message}" for path, message in schema_errors(data)
    ]
    if problems:
        return None, problems

    built = {section: _build(data, section, source, problems) for section in _SECTIONS}
    sequence = None
    if "sequence" in data:
        try:
            sequence = Path(data["sequence"])
        except ValueError as exc:
            problems.append(f"{source}: sequence: {exc}")
    if problems:
        return None, problems
    return Profile(tuple(built["fields"]), tuple(built["aggregates"]), sequence), []


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
