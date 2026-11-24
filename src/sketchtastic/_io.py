"""Shared internal I/O, formatting, and value primitives for sketch-tastic."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any


def is_number(value: Any) -> bool:
    """Return True for int/float values, excluding bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def safe_text(value: Any) -> str:
    """Escape terminal controls and non-ASCII characters without changing stored records."""
    return json.dumps(str(value), ensure_ascii=True)[1:-1]


def history_dir_for(sketch_path: Path | str) -> Path:
    """Return the companion `<sketch>.history` directory path for a sketch file."""
    return Path(os.path.splitext(str(sketch_path))[0] + ".history")


def sample_locator(sketch_path: Path | str, key: str) -> str:
    """Return a terminal-safe locator string for a skit's first retained record."""
    return f"{safe_text(sketch_path)}:skits[{safe_text(key)}].meta.first[0].record"


def atomic_replace_file(path: Path | str, prefix: str, write_fn: Callable[[IO[str]], None]) -> None:
    """Write via a same-directory temporary file and atomically replace `path`."""
    target = str(path)
    directory = os.path.dirname(os.path.abspath(target))
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=prefix, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            write_fn(stream)
        os.replace(tmp_path, target)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def publish_new_file(
    output: Path | str, prefix: str, filename: str, write_fn: Callable[[Path], None]
) -> None:
    """Stage `filename` in a sibling temp dir and hard-link it to a brand-new `output`."""
    out = Path(output)
    if out.exists() or out.is_symlink():
        raise FileExistsError(f"Output already exists: {out}")
    with tempfile.TemporaryDirectory(prefix=prefix, dir=out.parent) as staging:
        staged = Path(staging) / Path(filename).name
        write_fn(staged)
        os.link(staged, out)


def validate_output_target(output: Path | str, *, force: bool = False) -> Path:
    """Validate an atomic-publish destination before expensive work begins."""
    out = Path(output)
    if out.is_symlink():
        raise ValueError(f"Output must not be a symlink: {out}")
    if out.is_dir():
        raise IsADirectoryError(f"Output is a directory: {out}")
    if not force and out.exists():
        raise FileExistsError(f"Output already exists: {out} (pass --force to overwrite)")
    if not out.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {out.parent}")
    return out


def publish_file(
    output: Path | str,
    prefix: str,
    filename: str,
    write_fn: Callable[[Path], None],
    *,
    force: bool = False,
) -> None:
    """Atomically publish `filename` to `output`, refusing symlinks and directories."""
    out = validate_output_target(output, force=force)
    with tempfile.TemporaryDirectory(prefix=prefix, dir=out.parent) as staging:
        staged = Path(staging) / Path(filename).name
        write_fn(staged)
        if out.is_symlink():
            raise ValueError(f"Output must not be a symlink: {out}")
        if force:
            os.replace(staged, out)
        else:
            os.link(staged, out)
