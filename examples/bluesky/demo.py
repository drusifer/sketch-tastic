"""Prepare an original-post Bluesky sketch for sketch-tastic's generic commands."""

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from sketchtastic import Sketch, load_profile

from .input import MAX_LINE_BYTES, posts, reject_constant

PROFILE = Path(__file__).with_name("profile.yaml")
SCOPE = "Unique accepted post creates in this input; not a global network inventory."


def safe_text(value: Any) -> str:
    """Escape untrusted control characters and Unicode for portable ASCII output."""
    return json.dumps(str(value), ensure_ascii=True)[1:-1]


def build(source: Path, output: Path, profile_path: Path = PROFILE) -> dict:
    """Sketch unchanged posts and publish a fresh directory of traceable samples."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}; choose a new directory")
    # Read once so the saved profile is exactly the one used for this preparation.
    profile_bytes = profile_path.read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".bluesky-", dir=output.parent) as staging:
        stage = Path(staging) / "result"
        stage.mkdir()
        saved_profile = stage / "profile.yaml"
        saved_profile.write_bytes(profile_bytes)
        profile = load_profile(str(saved_profile))
        sketch = Sketch(profile.aggregates, profile.profile_id)
        counts = Counter()
        digest = hashlib.sha256()
        samples = {}
        for number, record in posts(source, counts, digest):
            if profile.event_time is not None:
                event_time, unusable = profile.extract_event_time(record)
                sketch.skipped_values += int(unusable)
                key = sketch.upsert(profile.tokens(record), record, seen=event_time)
            else:
                key = sketch.upsert(profile.tokens(record), record)
            samples.setdefault(
                key,
                {
                    "source": str(source),
                    "source_line": number,
                    "representative_line": len(samples) + 1,
                },
            )
        representatives = [sketch.get(key).meta["first"][0]["record"] for key in sketch]
        reduced = Sketch(profile.aggregates, profile.profile_id)
        for record in representatives:
            reduced.upsert(profile.tokens(record), record)
        if set(reduced) != set(sketch):
            raise ValueError("Retained representatives do not reproduce the full skit-ID set")
        summary = {
            "source": str(source),
            "source_sha256": digest.hexdigest(),
            "profile_id": profile.profile_id,
            "counts": dict(counts),
            "posts": counts["posts"],
            "skits": len(sketch),
            "representatives_verified": True,
            "scope": SCOPE,
        }
        sidecar = source.with_suffix(source.suffix + ".meta.json")
        if sidecar.exists():
            with sidecar.open("rb") as stream:
                raw = stream.read(MAX_LINE_BYTES + 1)
            if len(raw) > MAX_LINE_BYTES:
                raise ValueError("Capture provenance exceeds size limit")
            capture = json.loads(raw, parse_constant=reject_constant)
            if not isinstance(capture, dict):
                raise ValueError("Capture provenance must be an object")
            summary["capture"] = capture
        sketch.save(str(stage / "posts.sketch.yaml"))
        (stage / "representatives.jsonl").write_text(
            "".join(json.dumps(record, ensure_ascii=True) + "\n" for record in representatives),
            encoding="utf-8",
        )
        for name, value in (("samples.json", samples), ("summary.json", summary)):
            (stage / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        # Reserve without replacing a concurrent creator, including an empty directory.
        output.mkdir()
        try:
            os.rename(stage, output)
        except OSError:
            output.rmdir()
            raise
    return summary


def main(argv: list[str] | None = None) -> int:
    """Expose offline preparation; reporting and coverage belong to the core CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Sketch original post JSONL into a NEW directory")
    prepare.add_argument("input", type=Path)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--profile", type=Path, default=PROFILE)
    args = parser.parse_args(argv)
    try:
        summary = build(args.input, args.output, args.profile)
        print(f"Prepared {summary['posts']:,} posts -> {summary['skits']:,} skits")
        print(f"Artifacts: {safe_text(args.output)}")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"bluesky: {safe_text(exc)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
