"""The profile JSON Schema and the standard validator that applies it (STORY-FING-37)."""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_FILE = "profile.schema.json"


@cache
def profile_schema() -> dict[str, Any]:
    """The profile schema shipped with the package."""
    return json.loads(files("fingerprint_sampler").joinpath(SCHEMA_FILE).read_text("utf-8"))


@cache
def _validator(definition: str | None) -> Draft202012Validator:
    schema = profile_schema()
    if definition:
        schema = {"$defs": schema["$defs"], "$ref": f"#/$defs/{definition}"}
    return Draft202012Validator(schema)


def schema_errors(data: Any, definition: str | None = None) -> list[tuple[tuple, str]]:
    """Every way `data` breaks the schema (or one of its $defs), as (path, message), in path order."""
    errors = _validator(definition).iter_errors(data)
    found = {(tuple(error.absolute_path), error.message) for error in errors}
    return sorted(found, key=lambda e: ([(isinstance(p, str), p) for p in e[0]], e[1]))
