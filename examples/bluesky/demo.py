"""Prepare and print a Bluesky image sketch using the existing sketch-tastic API."""

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from sketchtastic import Sketch, load_profile

from .model import DOMAINS, rows_for_event

PROFILE = Path(__file__).with_name("profile.yaml")
MAX_LINE_BYTES = 4 * 1024 * 1024
SCOPE = "Image attachments in accepted post creates; not a global inventory."


def safe_text(value: Any) -> str:
    """Escape untrusted control characters and Unicode for portable ASCII output."""
    return json.dumps(str(value), ensure_ascii=True)[1:-1]


def reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON number {value}")


def build(source: Path, output: Path) -> dict:
    """Fold JSONL, verify retained variants, then publish a fresh artifact directory."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}; choose a new directory")
    profile = load_profile(str(PROFILE))
    if [field.key for field in profile.fields] != list(DOMAINS):
        raise ValueError("Profile fields must match report dimensions in order")
    sketch = Sketch(profile.aggregates, profile.profile_id)
    counts, seen = Counter(), set()
    source_hash = hashlib.sha256()
    with source.open("rb") as stream:
        line_number = 0
        while line := stream.readline(MAX_LINE_BYTES + 1):
            line_number += 1
            if len(line) > MAX_LINE_BYTES:
                raise ValueError(f"{source}: line {line_number}: exceeds 4 MiB line limit")
            source_hash.update(line)
            if not line.strip():
                continue
            try:
                event = json.loads(line, parse_constant=reject_constant)
                if not isinstance(event, dict):
                    raise ValueError("expected a JSON object")
                counts["records"] += 1
                for row in rows_for_event(event, counts, seen):
                    sketch.upsert(profile.tokens(row), row)
                    counts["images"] += 1
            except (ValueError, TypeError, UnicodeError) as exc:
                raise ValueError(f"{source}: line {line_number}: {exc}") from exc
    representatives = [sketch.get(key).meta["first"][0]["record"] for key in sketch]
    reduced = Sketch(profile.aggregates, profile.profile_id)
    for row in representatives:
        reduced.upsert(profile.tokens(row), row)
    if set(reduced) != set(sketch):
        raise ValueError("Retained representatives do not reproduce the full skit-ID set")
    summary = {
        "source": str(source),
        "source_sha256": source_hash.hexdigest(),
        "profile_id": profile.profile_id,
        "counts": dict(counts),
        "images": counts["images"],
        "skits": len(sketch),
        "representatives_verified": True,
        "domains": DOMAINS,
        "scope": SCOPE,
    }
    sidecar = source.with_suffix(source.suffix + ".meta.json")
    if sidecar.exists():
        summary["capture"] = json.loads(sidecar.read_text(encoding="utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".bluesky-", dir=output.parent) as staging:
        stage = Path(staging) / "result"
        stage.mkdir()
        sketch.save(str(stage / "images.sketch.yaml"))
        (stage / "profile.yaml").write_text(PROFILE.read_text(), encoding="utf-8")
        (stage / "representatives.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in representatives),
            encoding="utf-8",
        )
        (stage / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        # Reserve without replacing any path, including a dangling symlink or a
        # concurrent creator's empty directory. Rename replaces only our reservation.
        output.mkdir()
        try:
            os.rename(stage, output)
        except OSError:
            output.rmdir()
            raise
    return summary


def report(directory: Path, group_by: str = "orientation", where: list[str] = ()) -> str:
    """Render population-weighted ASCII bars and observed enum values from a sketch."""
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    profile = load_profile(str(directory / "profile.yaml"))
    domains = summary["domains"]
    if domains != {key: list(values) for key, values in DOMAINS.items()}:
        raise ValueError("Saved enum domains do not match this demo version")
    if set(domains) != {field.key for field in profile.fields}:
        raise ValueError("Saved profile and report dimensions disagree")
    if group_by not in domains:
        raise ValueError(f"Unknown group {group_by!r}; choose {', '.join(domains)}")
    filters = []
    for expression in where:
        field, sep, value = expression.partition("=")
        if not sep or field not in domains or value not in domains[field]:
            raise ValueError(f"Unknown filter {expression!r}; use FIELD=VALUE from the enum list")
        filters.append((field, value))
    sketch = Sketch(profile.aggregates, profile.profile_id)
    sketch.load(str(directory / "images.sketch.yaml"))
    matches = [
        sketch.get(key)
        for key in sketch
        if all(sketch.get(key).tokens.get(field) == value for field, value in filters)
    ]
    histogram = Counter()
    for skit in matches:
        histogram[skit.tokens[group_by]] += skit.meta["count"]
    total = sum(histogram.values())
    lines = [
        "BLUESKY IMAGE COUNTS",
        "=" * 72,
        f"Source: {safe_text(summary['source'])}",
        SCOPE,
        f"Posts: {summary['counts'].get('posts', 0):,} accepted in full capture",
        f"Images: {total:,} matched / {summary['images']:,} total",
        f"Skits: {len(matches):,} matched / {len(sketch):,} total",
        f"Representative rows: {summary['skits']:,}; observed skit IDs preserved: "
        + ("yes" if summary["representatives_verified"] else "NO"),
        f"Filters: {', '.join(where) or '(none)'}",
        "",
        f"Images by {group_by}",
        "-" * 72,
    ]
    if capture := summary.get("capture"):
        lines.insert(
            3,
            "Capture: "
            + safe_text(capture.get("started", "unknown"))
            + " to "
            + safe_text(capture.get("finished", "unknown")),
        )
    maximum = max(histogram.values(), default=0)
    if not total:
        lines.append("No matching images.")
    for value in domains[group_by]:
        count = histogram[value]
        bar = "#" * max(1, round(32 * count / maximum)) if count else ""
        share = 100 * count / total if total else 0
        lines.append(f"{value:16} {count:9,} {share:6.1f}%  {bar}")
    lines.extend(["", "ENUM VALUES (matching data)", "-" * 72])
    for field, values in domains.items():
        present = {skit.tokens[field] for skit in matches}
        absent = [v for v in values if v not in present]
        lines.append(f"{field}: {', '.join(v for v in values if v in present) or '(none)'}")
        lines.append(f"  not observed: {', '.join(absent) or '(none)'}")
    lines.extend(
        [
            "",
            "Enum observations are not branch coverage; combinations may be unreachable.",
            "Representative rows retain variants, not original population frequencies.",
            "Excluded/ignored: "
            + ", ".join(
                f"{safe_text(key)}={value:,}"
                for key, value in sorted(summary["counts"].items())
                if key not in {"records", "posts", "image_posts", "images"}
            ),
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Expose offline preparation and plain-text reporting."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Sketch raw post JSONL into a NEW directory")
    prepare.add_argument("input", type=Path)
    prepare.add_argument("--output", type=Path, required=True)
    show = commands.add_parser("report", help="Print ASCII counts and observed enum variants")
    show.add_argument("directory", type=Path)
    show.add_argument("--group-by", default="orientation", choices=list(DOMAINS))
    show.add_argument("--where", action="append", default=[], metavar="FIELD=VALUE")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            summary = build(args.input, args.output)
            print(f"Prepared {summary['images']:,} images -> {summary['skits']:,} skits")
            print(f"Artifacts: {safe_text(args.output)}")
        else:
            print(report(args.directory, args.group_by, args.where))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"bluesky: {safe_text(exc)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
