"""The profile JSON Schema and the standard validator that applies it (STORY-FING-37)."""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

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


@cache
def _required_arguments() -> dict[str, list[str]]:
    """Rule names whose mapping form requires arguments, with those arguments, from the schema."""
    required = {}
    for definition in profile_schema()["$defs"].values():
        for rule in definition.get("else", {}).get("allOf", []):
            if rule["then"].get("required"):
                required[rule["if"]["properties"]["name"]["const"]] = rule["then"]["required"]
    return required


def _message(error: ValidationError) -> str:
    """The validator's message, except for a rule named bare that needs arguments (STORY-FING-44)
    and a `not` whose subschema has a description (it says what is wrong better than the dump)."""
    if error.validator == "not" and "description" in error.validator_value:
        return error.validator_value["description"]
    bare_name = list(error.schema_path)[-2:] == ["then", "enum"] and isinstance(error.instance, str)
    args = _required_arguments().get(error.instance) if bare_name else None
    if not args:
        return error.message
    name = error.instance
    return (
        f"{name} needs arguments ({', '.join(args)}); write it as {{name: {name}, {args[0]}: ...}}"
    )


def schema_errors(data: Any, definition: str | None = None) -> list[tuple[tuple, str]]:
    """Every way `data` breaks the schema (or one of its $defs), as (path, message), in path order."""
    errors = _validator(definition).iter_errors(data)
    found = {(tuple(error.absolute_path), _message(error)) for error in errors}
    return sorted(found, key=lambda e: ([(isinstance(p, str), p) for p in e[0]], e[1]))
