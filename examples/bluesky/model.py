"""Image properties used by both the report and its regression-data profile.

Categories are deliberately finite: every branch has an explicit value. Original
values remain in the sample so a profile can later be refined without losing context.
"""

from collections import Counter
from collections.abc import Iterator
from typing import Any

DOMAINS = {
    "reply": ("original", "reply", "invalid"),
    "embed_kind": ("images", "gallery", "quote_images", "quote_gallery"),
    "attachment_count": ("1", "2", "3", "4", "5-10", "11+"),
    "mime": ("jpeg", "png", "webp", "gif", "other", "missing", "invalid"),
    "orientation": ("portrait", "square", "landscape", "missing", "invalid"),
    "alt": ("present", "empty", "missing", "invalid"),
}
MIME_TYPES = {f"image/{name}": name for name in ("jpeg", "png", "webp", "gif")}
POST = "app.bsky.feed.post"
IMAGE = "app.bsky.embed.images"
GALLERY = "app.bsky.embed.gallery"
QUOTE = "app.bsky.embed.recordWithMedia"


def orientation(image: dict[str, Any]) -> str:
    """Classify the supplied aspect-ratio hint, without fetching image bytes."""
    if "aspectRatio" not in image:
        return "missing"
    ratio = image["aspectRatio"]
    if not isinstance(ratio, dict):
        return "invalid"
    width, height = ratio.get("width"), ratio.get("height")
    if any(type(v) is not int or v <= 0 for v in (width, height)):
        return "invalid"
    if width == height:
        return "square"
    return "landscape" if width > height else "portrait"


def alt_state(image: dict[str, Any]) -> str:
    """Distinguish omitted, unusable, blank and meaningful alternative text."""
    if "alt" not in image:
        return "missing"
    alt = image["alt"]
    if not isinstance(alt, str):
        return "invalid"
    return "present" if alt.strip() else "empty"


def mime_class(blob: dict[str, Any]) -> str:
    """Map familiar image formats, retaining explicit other and error cases."""
    if "mimeType" not in blob:
        return "missing"
    mime = blob["mimeType"]
    if not isinstance(mime, str) or not mime.startswith("image/") or not mime[6:]:
        return "invalid"
    return MIME_TYPES.get(mime, "other")


def attachments(post: dict[str, Any], counts: Counter | None = None) -> tuple[str, list]:
    """Extract own image attachments, never dereferencing a quoted record."""
    counts = counts if counts is not None else Counter()
    embed = post.get("embed")
    if embed is None:
        return "", []
    if not isinstance(embed, dict):
        raise ValueError("embed must be an object")
    quoted = embed.get("$type") == QUOTE
    if quoted:
        embed = embed.get("media")
        if not isinstance(embed, dict):
            raise ValueError("recordWithMedia.media must be an object")
    kind = embed.get("$type")
    if kind not in (IMAGE, GALLERY):
        counts["excluded_embeds"] += 1
        return "", []
    key = "images" if kind == IMAGE else "items"
    items = embed.get(key)
    if not isinstance(items, list):
        raise ValueError(f"{kind}.{key} must be an array")
    selected = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{key}[{index}] must be an object")
        if kind == GALLERY and item.get("$type") != GALLERY + "#image":
            counts["excluded_gallery_items"] += 1
            continue
        if not isinstance(item.get("image"), dict):
            raise ValueError(f"{key}[{index}].image must be a blob object")
        selected.append((index, item))
    name = "images" if kind == IMAGE else "gallery"
    return ("quote_" if quoted else "") + name, selected


def image_rows(post: dict[str, Any], counts: Counter | None = None) -> list[dict[str, Any]]:
    """Normalize each image with its correlated metadata and original source post."""
    kind, images = attachments(post, counts)
    n = len(images)
    reply = (
        "original"
        if "reply" not in post
        else ("reply" if isinstance(post["reply"], dict) else "invalid")
    )
    count_class = str(n) if n <= 4 else "5-10" if n <= 10 else "11+"
    rows = []
    for index, image in images:
        blob = image["image"]
        row = {
            "reply": reply,
            "embed_kind": kind,
            "attachment_count": count_class,
            "mime": mime_class(blob),
            "orientation": orientation(image),
            "alt": alt_state(image),
            "image_index": index,
            "image_count": n,
            "source": post,
        }
        size = blob.get("size")
        if type(size) is int and size >= 0:
            row["bytes"] = size
        rows.append(row)
    return rows


def source_post(event: dict[str, Any], counts: Counter, seen: set) -> dict | None:
    """Accept bare posts and v1/v2 Jetstream create events; count exclusions."""
    if event.get("$type") == POST:
        return event
    payload = event.get("payload", event)
    if not isinstance(payload, dict):
        raise ValueError("event payload must be an object")
    commit = payload.get("commit", payload)
    if not isinstance(commit, dict):
        raise ValueError("event commit must be an object")
    if commit.get("collection") != POST:
        counts["ignored_events"] += 1
        return None
    if commit.get("operation") != "create":
        counts["ignored_operations"] += 1
        return None
    record = commit.get("record")
    if not isinstance(record, dict) or record.get("$type") != POST:
        raise ValueError("post create event must contain an app.bsky.feed.post record")
    did, rkey = payload.get("did"), commit.get("rkey")
    if not isinstance(did, str) or not isinstance(rkey, str) or not did or not rkey:
        raise ValueError("post create event requires did and rkey for duplicate protection")
    identity = (did, rkey)
    if identity in seen:
        counts["duplicates"] += 1
        return None
    seen.add(identity)
    return record


def rows_for_event(event: dict, counts: Counter, seen: set) -> Iterator[dict]:
    """Feed the sketch without losing source context or image correlations."""
    record = source_post(event, counts, seen)
    if record is None:
        return
    counts["posts"] += 1
    rows = image_rows(record, counts)
    if rows:
        counts["image_posts"] += 1
    for row in rows:
        # The exact event is useful for provenance; source remains the actual post.
        row["event"] = event
        yield row
