"""Stage a derived sketch and all available history before no-clobber publication."""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sketchtastic._io import history_dir_for, validate_output_target
from sketchtastic.derive import build_transforms, derive_data
from sketchtastic.profile import Profile, load_profile
from sketchtastic.sketch import read_sketch_file


@dataclass(frozen=True)
class DeriveResult:
    source_skits: int
    derived_skits: int
    observations: int
    history_runs: int


def _destinations(source: Path, output: Path) -> tuple[Path, Path]:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}; choose a new sketch name")
    validate_output_target(output)
    old_history, new_history = history_dir_for(source), history_dir_for(output)
    if source.resolve() == output.resolve() or old_history.resolve() == new_history.resolve():
        raise ValueError("Choose a new sketch name with a distinct history directory")
    if output.resolve().is_relative_to(old_history.resolve()):
        raise ValueError("Output must not be inside source history")
    if source.resolve().is_relative_to(new_history.resolve()):
        raise ValueError("Output history must not contain the source sketch")
    _check_history_paths(old_history, new_history)
    return old_history, new_history


def _check_history_paths(old_history: Path, new_history: Path) -> None:
    if new_history.exists() or new_history.is_symlink():
        raise FileExistsError(f"Output history already exists: {new_history}")
    if old_history.is_symlink() or (old_history.exists() and not old_history.is_dir()):
        raise ValueError(f"Source history must be a regular directory: {old_history}")


def _history_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    result = []
    for entry in sorted(directory.iterdir()):
        if entry.is_symlink():
            raise ValueError(f"History symlinks are not supported: {entry}")
        if entry.suffix.lower() not in (".yaml", ".yml"):
            continue
        if not entry.is_file():
            raise ValueError(f"History entry must be a regular file: {entry}")
        result.append(entry)
    return result


def _stage_history(
    paths: list[Path], staging: Path, source: Profile, target: Profile, output: Path
) -> list[Path]:
    staged = []
    ids = set()
    for path in paths:
        raw = read_sketch_file(path)
        run = raw.get("run")
        if (
            not isinstance(run, dict)
            or not re.fullmatch(r"\d{6}-\d{4,}", path.stem)
            or run.get("id") != path.stem
            or path.stem in ids
        ):
            raise ValueError(f"{path}: invalid or duplicate history run ID")
        ids.add(path.stem)
        try:
            sketch = derive_data(
                raw, source, target, source_name=str(path), output_name=str(output)
            )
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc
        destination = staging / path.name
        sketch.save(str(destination))
        staged.append(destination)
    return staged


def _publish(staged: Path, output: Path, history: list[Path], history_dir: Path) -> None:
    """Publish main last; undo only our own links if a handled publication fails."""
    created_directory = False
    linked = []
    try:
        if history:
            history_dir.mkdir()  # exclusive: never adopt an existing directory
            created_directory = True
            for source in history:
                destination = history_dir / source.name
                os.link(source, destination)
                linked.append((source, destination))
        os.link(staged, output)  # exclusive even if a competitor created output after validation
    except BaseException:
        for source, destination in reversed(linked):
            with contextlib.suppress(OSError):
                if not destination.is_symlink() and source.samefile(destination):
                    destination.unlink()
        if created_directory:
            with contextlib.suppress(OSError):
                history_dir.rmdir()  # leave any files another writer created
        raise


def derive_file(
    source_path: Path | str,
    source_profile: Path | str,
    target_profile: Path | str,
    output_path: Path | str,
) -> DeriveResult:
    """Derive a fresh inventory/history pair; input files must be quiescent during this call."""
    source_path, output = Path(source_path), Path(output_path)
    if source_path.is_symlink() or not source_path.is_file():
        raise ValueError(f"Source sketch must be a regular file: {source_path}")
    old_history, new_history = _destinations(source_path, output)
    source, target = load_profile(str(source_profile)), load_profile(str(target_profile))
    build_transforms(source, target)
    raw = read_sketch_file(source_path)
    derived = derive_data(
        raw, source, target, source_name=str(source_path), output_name=str(output)
    )
    paths = _history_files(old_history)
    with tempfile.TemporaryDirectory(prefix=".derive-", dir=output.parent) as temp:
        staging = Path(temp)
        history_staging = staging / "history"
        history_staging.mkdir()
        histories = _stage_history(paths, history_staging, source, target, output)
        staged = staging / "sketch.yaml"
        derived.save(str(staged))
        _publish(staged, output, histories, new_history)
    return DeriveResult(
        len(raw["skits"]),
        len(derived),
        sum(record["meta"]["count"] for record in raw["skits"].values()),
        len(paths),
    )
