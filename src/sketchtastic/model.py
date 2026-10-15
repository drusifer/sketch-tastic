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
from datetime import date, datetime, timezone
from functools import cache, cached_property
from typing import Any, ClassVar, Self

import jsonpath_rfc9535 as jsonpath

from sketchtastic.schema import schema_errors

__all__ = [
    "MISSING",
    "AnyOf",
    "DateType",
    "DatetimeType",
    "Default",
    "Field",
    "Glob",
    "InRange",
    "IsNull",
    "IsPresent",
    "Modifier",
    "Path",
    "RegSub",
    "Regex",
    "Rule",
    "Trunc",
    "ValueType",
    "tokens",
    "typed_values",
]

MISSING = object()
"""Handed to a modifier when a path selects nothing."""


@cache
def _compile_path(text: str) -> jsonpath.JSONPathQuery:
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
        return value.isoformat() if isinstance(value, date) else str(value)


@dataclass(frozen=True, kw_only=True)
class IsPresent(Modifier):
    """TRUE when the path finds the key, even if its value is null; FALSE when it is missing."""

    name = "IS_PRESENT"

    def token(self, value: Any) -> str:
        return _flag(value is not MISSING)


@dataclass(frozen=True, kw_only=True)
class IsNull(Modifier):
    """TRUE only for a key explicitly set to null; FALSE for a missing key or any other value."""

    name = "IS_NULL"

    def token(self, value: Any) -> str:
        return _flag(value is None)


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


_TRUNC_FORMATS = {
    "year": "%Y",
    "month": "%Y-%m",
    "day": "%Y-%m-%d",
    "hour": "%Y-%m-%dT%H",
    "minute": "%Y-%m-%dT%H:%M",
    "second": "%Y-%m-%dT%H:%M:%S",
}


@dataclass(frozen=True, kw_only=True)
class Trunc(Modifier):
    """A date or time cut down to `unit`, e.g. hour -> "2024-01-01T15". Needs a DATE/DATETIME type."""

    name = "TRUNC"
    absent = "NULL"
    unit: str

    def present(self, value: Any) -> str:
        return value.strftime(_TRUNC_FORMATS[self.unit]) if isinstance(value, date) else "NULL"


class ValueType(Rule):
    """What a path's values are. `convert` returns the typed value, or None if it isn't one."""

    family = "valuetype"

    def convert(self, value: Any) -> Any:
        raise NotImplementedError


def _utc(moment: datetime) -> datetime:
    return (
        moment.replace(tzinfo=timezone.utc)
        if moment.tzinfo is None
        else moment.astimezone(timezone.utc)
    )


@dataclass(frozen=True, kw_only=True)
class DatetimeType(ValueType):
    """An ISO-8601 datetime, compared in UTC (a time without a zone is taken as UTC)."""

    name = "DATETIME"

    def convert(self, value: Any) -> datetime | None:
        try:
            return _utc(datetime.fromisoformat(value)) if isinstance(value, str) else None
        except ValueError:
            return None


@dataclass(frozen=True, kw_only=True)
class DateType(ValueType):
    """An ISO-8601 date (or the UTC date of an ISO-8601 datetime)."""

    name = "DATE"

    def convert(self, value: Any) -> date | None:
        moment = DatetimeType().convert(value)
        return moment.date() if moment else None


def typed_values(values: list[Any], value_type: ValueType | None) -> list[Any]:
    """Convert values to `value_type`; one that won't convert becomes MISSING (null stays null)."""
    if value_type is None:
        return values
    converted = [(value, value_type.convert(value)) for value in values]
    return [MISSING if new is None and old is not None else new for old, new in converted]


@dataclass(frozen=True)
class Field:
    """One part of a skit's identity: the token `modifier` makes of what `path` selects.

    `path` and `modifier` may be given as text and a bare name or mapping; they are built and
    checked on creation (ValueError if wrong).
    """

    key: str
    path: Path
    modifier: Modifier = field(default="DEFAULT")
    type: ValueType | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path.of(self.path))
        object.__setattr__(self, "modifier", Modifier.build(self.modifier))
        if self.type is not None:
            object.__setattr__(self, "type", ValueType.build(self.type))
        if isinstance(self.modifier, Trunc) and not isinstance(self.type, (DateType, DatetimeType)):
            raise ValueError("TRUNC needs type DATE or DATETIME on the field")

    @property
    def spec(self) -> str:
        """This field's part of the profile id."""
        text = f"{self.key}|{self.path.text}|{self.modifier.spec}"
        return f"{text}|{self.type.spec}" if self.type else text

    def token(self, event: Any) -> str:
        """No match is tokenized as missing; several are tokenized, de-duplicated, sorted, joined."""
        values = typed_values(self.path.values(event), self.type) or [MISSING]
        return ",".join(sorted({self.modifier.token(value) for value in values}))


def tokens(event: Any, fields: tuple[Field, ...] | list[Field]) -> dict[str, str]:
    """The tokens `fields` make of `event`, by key."""
    return {f.key: f.token(event) for f in fields}
