"""YAML reading and writing, through libyaml (included in PyYAML's wheels) everywhere.

Sketch files can be megabytes (FIRST/LAST keep whole events), and the pure-Python emitter was
the largest serial cost of a merge. One loader and one dumper keep every file consistent.
"""

from __future__ import annotations

from typing import IO, Any

import yaml

Dumper = getattr(yaml, "CSafeDumper", yaml.SafeDumper)
Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def load(stream: IO[str] | str) -> Any:
    """Safe-load one YAML document."""
    return yaml.load(stream, Loader=Loader)


def dump(data: Any, stream: IO[str]) -> None:
    """Safe-dump `data`, keeping key order."""
    yaml.dump(data, stream, Dumper=Dumper, sort_keys=False)
