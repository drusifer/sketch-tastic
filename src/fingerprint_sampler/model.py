"""The profile's building blocks: paths, rules, modifiers and fields (STORY-FING-39).

A `Rule` is one configurable behaviour chosen by name — a modifier, or an
aggregate function (see `aggregators`). Every rule is built the same way:
from a bare name or a mapping, checked against the profile JSON Schema, then
by its own `check()` for what a schema cannot express.
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import asdict, dataclass, field
from functools import cache, cached_property
from typing import Any, ClassVar, Self

import jsonpath

from fingerprint_sampler.schema import schema_errors

MISSING = object()
"""Handed to a modifier when a path selects nothing."""


@cache
def _compile_path(text: str) -> jsonpath.JSONPath:
    try:
        return jsonpath.compile(text)
    except jsonpath.JSONPathError as exc:
        raise ValueError(f"Invalid JSONPath {text!r}: {str(exc).splitlines()[0]}") from None


@dataclass(frozen=True)
class Path:
    """A JSONPath expression, compiled once. Raises ValueError if invalid."""

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("JSONPath must be a non-empty string")
        _compile_path(self.text)

    @classmethod
    def of(cls, path: Path | str) -> Path:
        return path if isinstance(path, Path) else cls(path)

    def values(self, event: Any) -> list[Any]:
        """Every value this path selects from `event`, in document order."""
        return _compile_path(self.text).findall(event)


def _freeze(value: Any) -> Any:
    return tuple(_freeze(v) for v in value) if isinstance(value, list) else value


def _thaw(value: Any) -> Any:
    return [_thaw(v) for v in value] if isinstance(value, tuple) else value


@dataclass(frozen=True, kw_only=True)
class Rule:
    """Base of every named, configurable behaviour.

    A family base sets `family` (its definition in the schema); each concrete
    rule sets `name` and declares its arguments as dataclass fields.
    """

    family: ClassVar[str]
    name: ClassVar[str]
    registry: ClassVar[dict[str, type[Rule]]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "family" in cls.__dict__:
            cls.registry = {}
        if "name" in cls.__dict__:
            cls.registry[cls.name] = cls

    @classmethod
    def build(cls, spec: Rule | str | dict[str, Any]) -> Self:
        """Build a rule from a bare name or a mapping. Raises ValueError saying what is wrong."""
        if isinstance(spec, cls):
            return spec
        problems = schema_errors(spec, cls.family)
        if problems:
            raise ValueError(
                "; ".join(f"{'.'.join(map(str, p))}: {m}" if p else m for p, m in problems)
            )
        args = {"name": spec} if isinstance(spec, str) else dict(spec)
        rule = cls.registry[args.pop("name")](**{k: _freeze(v) for k, v in args.items()})
        rule.check()
        return rule

    def check(self) -> None:
        """Raise ValueError for a problem the schema cannot express. Nothing to check by default."""

    @property
    def spec(self) -> str:
        """Canonical text: the bare name, or the arguments as sorted compact JSON."""
        args = {k: _thaw(v) for k, v in asdict(self).items()}
        if not args:
            return self.name
        return json.dumps({"name": self.name, **args}, sort_keys=True, separators=(",", ":"))


class Modifier(Rule):
    """Turns one selected value into a token. `absent` is the token for a missing or null value."""

    family = "modifier"
    absent: ClassVar[str] = "FALSE"

    def token(self, value: Any) -> str:
        return self.absent if value is MISSING or value is None else self.present(value)

    def present(self, value: Any) -> str:
        raise NotImplementedError


def _flag(condition: Any) -> str:
    return "TRUE" if condition else "FALSE"


@dataclass(frozen=True, kw_only=True)
class Default(Modifier):
    name = "DEFAULT"
    absent = "NULL"

    def present(self, value: Any) -> str:
        return str(value)


@dataclass(frozen=True, kw_only=True)
class IsPresent(Modifier):
    name = "IS_PRESENT"

    def present(self, value: Any) -> str:
        return "TRUE"


@dataclass(frozen=True, kw_only=True)
class IsNull(Modifier):
    name = "IS_NULL"
    absent = "TRUE"

    def present(self, value: Any) -> str:
        return "FALSE"


@dataclass(frozen=True, kw_only=True)
class InRange(Modifier):
    name = "IN_RANGE"
    low: float
    high: float

    def check(self) -> None:
        if self.low > self.high:
            raise ValueError(f"IN_RANGE low ({self.low}) is above high ({self.high})")

    def present(self, value: Any) -> str:
        try:
            return _flag(self.low <= float(value) <= self.high)
        except TypeError, ValueError:
            return "FALSE"


@dataclass(frozen=True, kw_only=True)
class AnyOf(Modifier):
    name = "ANY"
    values: tuple

    def present(self, value: Any) -> str:
        return _flag(str(value) in {str(v) for v in self.values})


@dataclass(frozen=True, kw_only=True)
class Glob(Modifier):
    name = "GLOB"
    pattern: str

    def present(self, value: Any) -> str:
        return _flag(fnmatch.fnmatchcase(str(value), self.pattern))


REGEX_FLAGS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE}
"""Letters allowed in a REGEX or REGSUB `flags` argument (the schema enforces them)."""


@dataclass(frozen=True, kw_only=True)
class Regex(Modifier):
    name = "REGEX"
    pattern: str
    flags: str = ""

    @cached_property
    def regex(self) -> re.Pattern:
        try:
            return re.compile(self.pattern, sum((REGEX_FLAGS[f] for f in set(self.flags)), 0))
        except re.error as exc:
            raise ValueError(f"Invalid regex {self.pattern!r}: {exc}") from None

    def check(self) -> None:
        self.regex  # noqa: B018 - compiling is the check

    def present(self, value: Any) -> str:
        return _flag(self.regex.search(str(value)))


@dataclass(frozen=True, kw_only=True)
class RegSub(Regex):
    name = "REGSUB"
    absent = "NULL"
    replace: str

    def check(self) -> None:
        try:
            self.regex.sub(self.replace, "")
        except (re.error, IndexError) as exc:
            raise ValueError(f"REGSUB replace is not valid: {exc}") from None

    def present(self, value: Any) -> str:
        return self.regex.sub(self.replace, str(value))


@dataclass(frozen=True)
class Field:
    """One part of a fingerprint's identity: the token `modifier` makes of what `path` selects.

    `path` and `modifier` may be given as text and a bare name or mapping; they are built and
    checked on creation (ValueError if wrong).
    """

    key: str
    path: Path
    modifier: Modifier = field(default="DEFAULT")

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path.of(self.path))
        object.__setattr__(self, "modifier", Modifier.build(self.modifier))

    def token(self, event: Any) -> str:
        """No match is tokenized as missing; several are tokenized, de-duplicated, sorted, joined."""
        values = self.path.values(event) or [MISSING]
        return ",".join(sorted({self.modifier.token(value) for value in values}))


def tokens(event: Any, fields: tuple[Field, ...] | list[Field]) -> dict[str, str]:
    """The tokens `fields` make of `event`, by key."""
    return {f.key: f.token(event) for f in fields}
