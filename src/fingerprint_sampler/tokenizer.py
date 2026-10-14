"""JSONPath extraction and plug-and-play modifier engine (STORY-FING-01, -23).

Collapses high-cardinality eBPF telemetry fields (PIDs, timestamps, raw byte
counts) into stable, low-cardinality string tokens before hashing.
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable

import jsonpath

_MISSING = object()
"""Sentinel handed to modifiers when a path selects nothing."""


@dataclass(frozen=True)
class MaskEntry:
    """One extraction rule: pull `path` out of a record, tag it `key`, tokenize with `modifier`."""

    key: str
    path: str
    modifier: str


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


def _mod_default(value: Any) -> str:
    return "NULL" if value is _MISSING or value is None else str(value)


def _mod_is_present(value: Any) -> str:
    return "FALSE" if value is _MISSING or value is None else "TRUE"


def _mod_is_null(value: Any) -> str:
    return "TRUE" if value is _MISSING or value is None else "FALSE"


def _mod_in_range(value: Any, low: str, high: str) -> str:
    if value is _MISSING or value is None:
        return "FALSE"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "FALSE"
    return "TRUE" if float(low) <= num <= float(high) else "FALSE"


def _mod_any(value: Any, *options: str) -> str:
    if value is _MISSING or value is None:
        return "FALSE"
    return "TRUE" if str(value) in {str(o) for o in options} else "FALSE"


def _mod_glob(value: Any, pattern: str) -> str:
    if value is _MISSING or value is None:
        return "FALSE"
    return "TRUE" if fnmatch.fnmatchcase(str(value), pattern) else "FALSE"


def _mod_regex(value: Any, pattern: str) -> str:
    if value is _MISSING or value is None:
        return "FALSE"
    return "TRUE" if re.search(pattern, str(value)) else "FALSE"


def _mod_regsub(value: Any, pattern: str, replacement: str) -> str:
    if value is _MISSING or value is None:
        return "NULL"
    return re.sub(pattern, replacement, str(value))


_MODIFIERS: dict[str, Callable[..., str]] = {
    "DEFAULT": _mod_default,
    "IS_PRESENT": _mod_is_present,
    "IS_NULL": _mod_is_null,
    "IN_RANGE": _mod_in_range,
    "ANY": _mod_any,
    "GLOB": _mod_glob,
    "REGEX": _mod_regex,
    "REGSUB": _mod_regsub,
}


_ARG_COUNTS: dict[str, tuple[int, int | None]] = {
    "DEFAULT": (0, 0),
    "IS_PRESENT": (0, 0),
    "IS_NULL": (0, 0),
    "IN_RANGE": (2, 2),
    "ANY": (1, None),
    "GLOB": (1, 1),
    "REGEX": (1, 1),
    "REGSUB": (2, 2),
}

_QUOTES = ("'", '"')


def _split_args(text: str, modifier: str) -> list[str]:
    """Split the text between a modifier's parentheses into arguments.

    Arguments are comma-separated and stripped. An argument written in single
    or double quotes is taken verbatim, so it can hold commas, parentheses and
    surrounding spaces; a doubled quote inside it stands for one quote
    character. Backslashes are never special here, so regex escapes pass through.
    """
    if not text.strip():
        return []
    args: list[str] = []
    buf: list[str] = []
    quote = ""  # the open quote character, if inside a quoted argument
    quoted = False  # the current argument was written in quotes
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch != quote:
                buf.append(ch)
            elif text[i + 1 : i + 2] == quote:
                buf.append(ch)
                i += 1
            else:
                quote = ""
        elif ch == ",":
            args.append("".join(buf) if quoted else "".join(buf).strip())
            buf, quoted = [], False
        elif quoted:
            if not ch.isspace():
                raise ValueError(
                    f"Malformed modifier {modifier!r}: unexpected {ch!r} after a quoted argument"
                )
        elif ch in _QUOTES and not "".join(buf).strip():
            quote, quoted, buf = ch, True, []
        else:
            buf.append(ch)
        i += 1
    if quote:
        raise ValueError(f"Malformed modifier {modifier!r}: missing closing {quote}")
    args.append("".join(buf) if quoted else "".join(buf).strip())
    return args


@lru_cache(maxsize=None)
def _parse_modifier(modifier: str) -> tuple[str, tuple[str, ...]]:
    """Split a modifier expression into (name, args). Raises ValueError on unknown names."""
    name, _, rest = modifier.partition("(")
    name = name.strip()
    if name not in _MODIFIERS:
        raise ValueError(f"Unknown modifier: {name!r}")
    rest = rest.rstrip()
    if rest.endswith(")"):
        rest = rest[:-1]
    return name, tuple(_split_args(rest, modifier))


def validate_modifier(modifier: str) -> None:
    """Check a modifier expression up front. Raises ValueError saying what is wrong."""
    if not isinstance(modifier, str) or not modifier.strip():
        raise ValueError("Modifier must be a non-empty string")
    name, args = _parse_modifier(modifier)
    if "(" in modifier and not modifier.rstrip().endswith(")"):
        raise ValueError(f"Malformed modifier {modifier!r}: missing ')'")
    low, high = _ARG_COUNTS[name]
    if len(args) < low or (high is not None and len(args) > high):
        expected = f"{low}" if low == high else f"at least {low}"
        raise ValueError(
            f"Modifier {name} takes {expected} argument(s), got {len(args)}: {modifier!r}"
        )
    if name == "IN_RANGE":
        try:
            bounds = [float(a) for a in args]
        except ValueError:
            raise ValueError(f"IN_RANGE bounds must be numbers: {modifier!r}") from None
        if bounds[0] > bounds[1]:
            raise ValueError(f"IN_RANGE low bound exceeds high bound: {modifier!r}")
    if name in ("REGEX", "REGSUB"):
        try:
            pattern = re.compile(args[0])
        except re.error as exc:
            raise ValueError(f"{name} pattern is not a valid regex ({exc}): {modifier!r}") from None
        if name == "REGSUB":
            try:
                pattern.sub(args[1], "")
            except (re.error, IndexError) as exc:
                raise ValueError(f"REGSUB replacement is not valid ({exc}): {modifier!r}") from None


def apply_modifier(value: Any, modifier: str) -> str:
    """Apply a modifier expression (e.g. "IN_RANGE(-999, 0)") to one `value`."""
    name, args = _parse_modifier(modifier)
    return _MODIFIERS[name](value, *args)


def tokenize_values(values: list[Any], modifier: str) -> str:
    """Collapse the values one path selected into a single stable token.

    No match is tokenized as missing, one match as that value. Several matches
    are tokenized individually, then deduplicated, sorted and comma-joined so
    array order can't cause fingerprint drift.
    """
    if not values:
        return apply_modifier(_MISSING, modifier)
    if len(values) == 1:
        return apply_modifier(values[0], modifier)
    return ",".join(sorted({apply_modifier(value, modifier) for value in values}))


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
