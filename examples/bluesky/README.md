# Bluesky image counts

A local ASCII demo: capture public post records, count their image attachments by meaningful
properties, and use sketch-tastic to retain one real example for every observed combination.
No web app, login, image binary downloads, or frontend dependencies.

## Run it

From the repository root:

```sh
bobp make bluesky-install
bobp make bluesky-capture ARGS="--seconds 60 --limit 100000 --output data/bluesky.jsonl"
bobp make bluesky ARGS="prepare data/bluesky.jsonl --output data/bluesky-demo"
bobp make -vvv bluesky ARGS="report data/bluesky-demo --group-by orientation"
bobp make -vvv bluesky ARGS="report data/bluesky-demo --group-by mime --where reply=reply"
bobp make -vvv run ARGS="show data/bluesky-demo/images.sketch.yaml"
```

Use a **new filename/directory** for another capture or preparation; existing output is never
overwritten. `--seconds` and `--limit` bound capture (whichever comes first); the connection
attempt has a maximum 10-second timeout and closing may take two additional seconds. The
capture sidecar records endpoint and UTC window. Preparation records the raw file's SHA-256.
Increase the capture window to collect more variants. A bounded window is not a complete
network snapshot. `bobp make clean` removes generated `data/`, so preserve a capture elsewhere
if you need to keep it.

Already have data? `prepare` accepts raw post records or v1/v2 Jetstream frames, one JSON object
per line. Capture is optional. Preparation is offline and does not download referenced records.
Identified post creates are deduplicated by author DID and record key; bare records have no
identity and are counted as supplied. Updates/deletions are excluded and reported. This counts
attachments observed in creates, not unique blobs or images still present on Bluesky.

## What determines a skit?

Every grouping/filter property is in [profile.yaml](profile.yaml). [model.py](model.py)
explicitly maps source attributes into the finite categories used by the ASCII application:

| Property | Values / decision |
|---|---|
| `reply` | `original`, `reply`, `invalid`; reply object presence/type |
| `embed_kind` | `images`, `gallery`, `quote_images`, `quote_gallery`; embed union discriminator |
| `attachment_count` | `1`, `2`, `3`, `4`, `5-10`, `11+`; number of the post's own images |
| `mime` | `jpeg`, `png`, `webp`, `gif`, `other`, `missing`, `invalid`; image MIME mapping |
| `orientation` | `portrait`, `square`, `landscape`, `missing`, `invalid`; compare aspect-ratio hint width/height |
| `alt` | `present`, `empty`, `missing`, `invalid`; nonblank alt text, whitespace-only/empty, absent, wrong type |

These are **this demo's application decisions**, not a claim to enumerate all branches of
Bluesky. The upstream image grid separately handles 2, 3 and 4 images; its gallery schema
documents an authoring limit of 10 and a schema ceiling of 20. The demo therefore preserves
1–4 individually and partitions larger galleries at 10. JPEG/PNG/WebP/GIF are explicit mapping
cases; other image MIME types remain visible as `other`. Exact values remain in source samples.
The orientation is a metadata hint, not a measurement of downloaded pixels.

Source references:
- [Image schema](https://github.com/bluesky-social/bsky/blob/main/lexicons/app/bsky/embed/images.json)
- [Gallery schema](https://github.com/bluesky-social/bsky/blob/main/lexicons/app/bsky/embed/gallery.json)
- [Image grid implementation](https://github.com/bluesky-social/social-app/blob/main/src/components/images/ImageLayoutGrid.tsx)
- [Jetstream interface](https://bsky.network/docs/jetstream/)

Direct images and the post's own media alongside a quote are counted. Images belonging to the
referenced quoted post are not fetched or counted. Video and link-card thumbnails are excluded.
Unsupported gallery item types and embeds are reported. Malformed image structures fail with
their input line; invalid optional metadata instead produces an explicit category.

## Counts and representative data

Each image becomes one normalized row retaining its image index, exact post, and original
event. This preserves correlations: a portrait PNG and a landscape JPEG in one post are two
rows, not independent bags of formats and orientations.

The sketch uses the existing `Profile` and `Sketch` APIs. Counts in the ASCII bars sum
`meta.count` across matching skits; optional byte statistics are aggregates, not identity.
The report shows which enum values were and were not observed. It does **not** turn marginal
enum presence into a claim that all value combinations, branches, or program paths were covered.

Preparation creates:
- `images.sketch.yaml`: normal sketch-tastic file, inspectable with `skt show`.
- `profile.yaml`: the exact profile used for the capture.
- `summary.json`: provenance, exclusions, counts, enum definitions and validation result.
- `representatives.jsonl`: one retained normalized image row per skit, including original data.

Preparation re-sketches the retained rows and verifies that their skit IDs exactly equal the
full sketch's IDs. That demonstrates preservation of the **observed variants under this
profile**. Retained samples have different frequencies from the original population.

You can independently re-sketch these rows through the public CLI:

```sh
bobp make run ARGS="merge -p data/bluesky-demo/profile.yaml -s data/representatives.sketch.yaml data/bluesky-demo/representatives.jsonl"
bobp make -vvv run ARGS="show data/representatives.sketch.yaml"
```

Choose a fresh sketch path for that comparison; `merge` adds to an existing sketch. Raw source
posts remain accessible as `record.source` in sketch samples and `source` in representative rows.
Multiple retained images can belong to the same post.

## Verify

```sh
bobp make test-bluesky
bobp make lint
```

Tests cover duplicate capture events, direct/quoted/gallery image forms, enum boundaries,
attribute correlations, missing/invalid values, retained-ID equality and output protection.
