"""JSONPath extraction and plug-and-play modifier engine (STORY-FING-01, -23).

Collapses high-cardinality eBPF telemetry fields (PIDs, timestamps, raw byte
counts) into stable, low-cardinality string tokens before hashing.
"""

from __future__ import annotations

import fnmatch
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import Any

import jsonpath

_MISSING = object()
"""Sentinel handed to modifiers when a path selects nothing."""


@dataclass(frozen=True)
class MaskEntry:
    """One extraction rule: pull `path` out of a record, tag it `key`, tokenize with `modifier`.

    `modifier` may be given as a Modifier, a bare name or a mapping; it is stored as a Modifier.
    """

    key: str
    path: str
    modifier: Modifier

    def __post_init__(self) -> None:
        object.__setattr__(self, "modifier", Modifier.of(self.modifier))


@lru_cache(maxsize=None)
def compile_path(path: str) -> jsonpath.JSONPath:
    """Compile a JSONPath expression (cached). Raises ValueError if it is empty or invalid."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError("JSONPath must be a non-empty string")
    try:
        return jsonpath.compile(path)
    except jsonpath.JSONPathError as exc:
        reason = str(exc).splitlines()[0]
        raise ValueError(f"Invalid JSONPath {path!r}: {reason}") from exc


def find_values(record: Any, path: str) -> list[Any]:
    """Return every value `path` selects from `record`, in document order ([] if none)."""
    return compile_path(path).findall(record)


def _absent(value: Any) -> bool:
    return value is _MISSING or value is None


def _mod_default(value: Any) -> str:
    return "NULL" if _absent(value) else str(value)


def _mod_is_present(value: Any) -> str:
    return "FALSE" if _absent(value) else "TRUE"


def _mod_is_null(value: Any) -> str:
    return "TRUE" if _absent(value) else "FALSE"


def _mod_in_range(value: Any, low: float, high: float) -> str:
    if _absent(value):
        return "FALSE"
    try:
        num = float(value)
    except TypeError, ValueError:
        return "FALSE"
    return "TRUE" if low <= num <= high else "FALSE"


def _mod_any(value: Any, values: tuple) -> str:
    if _absent(value):
        return "FALSE"
    return "TRUE" if str(value) in {str(v) for v in values} else "FALSE"


def _mod_glob(value: Any, pattern: str) -> str:
    if _absent(value):
        return "FALSE"
    return "TRUE" if fnmatch.fnmatchcase(str(value), pattern) else "FALSE"


def _mod_regex(value: Any, regex: re.Pattern) -> str:
    if _absent(value):
        return "FALSE"
    return "TRUE" if regex.search(str(value)) else "FALSE"


def _mod_regsub(value: Any, regex: re.Pattern, replace: str) -> str:
    if _absent(value):
        return "NULL"
    return regex.sub(replace, str(value))


# name -> (function, required arguments, optional arguments)
_MODIFIERS: dict[str, tuple[Callable[..., str], tuple[str, ...], tuple[str, ...]]] = {
    "DEFAULT": (_mod_default, (), ()),
    "IS_PRESENT": (_mod_is_present, (), ()),
    "IS_NULL": (_mod_is_null, (), ()),
    "IN_RANGE": (_mod_in_range, ("low", "high"), ()),
    "ANY": (_mod_any, ("values",), ()),
    "GLOB": (_mod_glob, ("pattern",), ()),
    "REGEX": (_mod_regex, ("pattern",), ("flags",)),
    "REGSUB": (_mod_regsub, ("pattern", "replace"), ("flags",)),
}

REGEX_FLAGS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE}
"""Letters allowed in a REGEX or REGSUB `flags` argument."""


def _mapping_hint(name: str) -> str:
    args = ", ".join(f"{arg}: ..." for arg in _MODIFIERS[name][1])
    return f"{{name: {name}, {args}}}"


@dataclass(frozen=True)
class Modifier:
    """A validated modifier: its name and its arguments, sorted by argument name.

    Build one with `Modifier.of(spec)`, where `spec` is a bare name such as
    "IS_PRESENT" or a mapping such as {"name": "REGEX", "pattern": "^GET"}.
    Calling it on a value returns that value's token.
    """

    name: str
    params: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def of(cls, spec: Modifier | str | Mapping[str, Any]) -> Modifier:
        """Validate `spec` and build a Modifier. Raises ValueError saying what is wrong."""
        if isinstance(spec, Modifier):
            return spec
        if isinstance(spec, str):
            return _modifier_from_name(spec)
        if not isinstance(spec, Mapping):
            raise ValueError(f"Modifier must be a name or a mapping with 'name', got {spec!r}")
        args = dict(spec)
        name = args.pop("name", None)
        if not isinstance(name, str) or name not in _MODIFIERS:
            raise ValueError(_unknown(name))
        _, required, optional = _MODIFIERS[name]
        missing = [arg for arg in required if arg not in args]
        if missing:
            raise ValueError(f"{name} needs {', '.join(map(repr, missing))}: {_mapping_hint(name)}")
        unknown = sorted(set(args) - set(required) - set(optional))
        if unknown:
            takes = ", ".join(required + optional) or "no arguments"
            raise ValueError(
                f"{name} does not take {', '.join(map(repr, unknown))} (it takes {takes})"
            )
        modifier = cls(name, tuple(sorted((k, _freeze(v)) for k, v in args.items())))
        modifier._check()
        return modifier

    @property
    def args(self) -> dict[str, Any]:
        return dict(self.params)

    @property
    def spec(self) -> str:
        """Canonical text of this modifier: the bare name, or sorted compact JSON."""
        if not self.params:
            return self.name
        data = {
            "name": self.name,
            **{k: list(v) if isinstance(v, tuple) else v for k, v in self.params},
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    @cached_property
    def _bound_args(self) -> tuple[Any, ...]:
        args = self.args
        if self.name in ("REGEX", "REGSUB"):
            regex = compile_regex(args["pattern"], args.get("flags", ""))
            return (regex, args["replace"]) if self.name == "REGSUB" else (regex,)
        return tuple(args[arg] for arg in _MODIFIERS[self.name][1])

    def __call__(self, value: Any) -> str:
        return _MODIFIERS[self.name][0](value, *self._bound_args)

    def _check(self) -> None:
        args = self.args
        if self.name == "IN_RANGE":
            for bound in ("low", "high"):
                if isinstance(args[bound], bool) or not isinstance(args[bound], (int, float)):
                    raise ValueError(f"IN_RANGE {bound} must be a number, got {args[bound]!r}")
            if args["low"] > args["high"]:
                raise ValueError(f"IN_RANGE low ({args['low']}) is above high ({args['high']})")
        elif self.name == "ANY":
            values = args["values"]
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"ANY values must be a non-empty list, got {values!r}")
        else:
            for arg in ("pattern", "replace", "flags"):
                if arg in args and not isinstance(args[arg], str):
                    raise ValueError(f"{self.name} {arg} must be a string, got {args[arg]!r}")
            if self.name in ("REGEX", "REGSUB"):
                regex = compile_regex(args["pattern"], args.get("flags", ""))
                if self.name == "REGSUB":
                    try:
                        regex.sub(args["replace"], "")
                    except (re.error, IndexError) as exc:
                        raise ValueError(f"REGSUB replace is not valid: {exc}") from None


def _freeze(value: Any) -> Any:
    return tuple(_freeze(v) for v in value) if isinstance(value, list) else value


def _unknown(name: Any) -> str:
    return f"Unknown modifier: {name!r} (known: {', '.join(_MODIFIERS)})"


@lru_cache(maxsize=None)
def _modifier_from_name(name: str) -> Modifier:
    if name not in _MODIFIERS:
        raise ValueError(_unknown(name))
    if _MODIFIERS[name][1]:
        raise ValueError(f"{name} needs arguments; use a mapping: {_mapping_hint(name)}")
    return Modifier(name)


@lru_cache(maxsize=None)
def compile_regex(pattern: str, flags: str = "") -> re.Pattern:
    """Compile a REGEX/REGSUB pattern with its flag letters. Raises ValueError if invalid."""
    bad = sorted(set(flags) - set(REGEX_FLAGS))
    if bad:
        raise ValueError(
            f"Unknown regex flag(s) {''.join(bad)!r}; use any of {''.join(REGEX_FLAGS)!r}"
        )
    try:
        return re.compile(pattern, sum((REGEX_FLAGS[f] for f in set(flags)), re.NOFLAG))
    except re.error as exc:
        raise ValueError(f"Invalid regex {pattern!r}: {exc}") from None


def validate_modifier(modifier: Modifier | str | Mapping[str, Any]) -> None:
    """Check a modifier up front. Raises ValueError saying what is wrong."""
    Modifier.of(modifier)


def apply_modifier(value: Any, modifier: Modifier | str | Mapping[str, Any]) -> str:
    """Tokenize one `value` with a modifier (a Modifier, a bare name, or a mapping)."""
    return Modifier.of(modifier)(value)


def tokenize_values(values: list[Any], modifier: Modifier | str | Mapping[str, Any]) -> str:
    """Collapse the values one path selected into a single stable token.

    No match is tokenized as missing, one match as that value. Several matches
    are tokenized individually, then deduplicated, sorted and comma-joined so
    array order can't cause fingerprint drift.
    """
    modifier = Modifier.of(modifier)
    if not values:
        return modifier(_MISSING)
    if len(values) == 1:
        return modifier(values[0])
    return ",".join(sorted({modifier(value) for value in values}))


def tokenize(record: dict, mask_profile: list[MaskEntry]) -> dict[str, str]:
    """Extract + tokenize every `MaskEntry` in `mask_profile` against `record`."""
    return {
        entry.key: tokenize_values(find_values(record, entry.path), entry.modifier)
        for entry in mask_profile
    }


def parse_jsonl(jsonl_text: str) -> list[dict]:
    """Parse a JSONL (newline-delimited JSON) string into a list of records.

    Blank lines are skipped so trailing newlines in a streamed eBPF probe
    output don't produce spurious entries.
    """
    return [json.loads(line) for line in jsonl_text.splitlines() if line.strip()]
