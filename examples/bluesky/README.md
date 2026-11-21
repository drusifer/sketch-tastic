# Bluesky post kinds and regression data

One input row is one original post. The sketch profile defines what makes posts the same kind;
its retained records provide compact regression data for an application handling those kinds.
Reporting, sample export and frequency-weighted coverage are generic **sketch-tastic commands**.

## Profile-defined post features

The default profile includes embed type, quoted media type, reply presence, rich-text feature
types, English language presence (`is_english`, boolean via RFC 9535 `match()` + `IS_PRESENT`) and
content labels. For each of four containers—direct images, direct gallery,
quoted-post media images and quoted-post media gallery—it also uses three boolean fields:

| State | `*_present` | `*_any` | `*_multiple` |
|---|---|---|---|
| No array member | FALSE | FALSE | FALSE |
| Array present, zero image entries | TRUE | FALSE | FALSE |
| One image entry | TRUE | TRUE | FALSE |
| Multiple image entries | TRUE | TRUE | TRUE |

`IS_PRESENT` distinguishes a missing member from an empty array. It tests member existence,
not schema validity: an explicit `null` is present. Native JSONPath `count()` expressions count
image members; gallery counts include only entries typed `app.bsky.embed.gallery#image`, so a
video-only gallery has zero images. Quoted-media counts require `recordWithMedia` and the right
media type. Link thumbnails and references to another quoted post are not counted. All these
rules live in the profile; the original post is unchanged. Separate expressions avoid the
JSONPath parser's complexity limit. No general MAP/REDUCE feature or unnesting is needed.

These are 18 profile fields (six general fields and four groups of three bits), but the bits
are constrained by one another and the embed type; they do not imply 2^12 independent cases.
Edit the profile to reflect the distinctions your application actually makes.

### Per-kind aggregates

The profile also summarizes observations without adding identity fields:

- `images_count`, `gallery_count`, `media_images_count`, `media_gallery_count`: total recognized
  image members across the posts in the skit, using the same typed-container rules as identity.
- Corresponding `*_bytes`: SUM, MIN, MAX and AVG of declared blob sizes, **per image with a
  numeric size**, not per post. No image binary is downloaded; missing sizes are not zeroes.
- `text_bytes`: SUM, MIN, MAX and AVG of UTF-8 text size, per selected text value.
- `facet_features`: total feature entries, including repeated types. The identity token still
  uses only the distinct feature-type set.
- `posted_at`: earliest/latest `createdAt` in UTC; these are post timestamps, not capture times.
  The profile also sets top-level `event_time: $.createdAt`, so each skit's built-in
  `meta.first_seen` and `meta.last_seen` track UTC post creation times directly (powering the
  default *First / Last Seen (Event Time)* slider in `sketchtastic analyze`).

`meta.count` remains the built-in post count used for regression frequency weighting. `report`
prints aggregate values below each kind; `show` also exposes them as sortable columns. Rebuild
from the original capture to populate new aggregates for all observations; re-sketching only
representatives cannot recover population statistics. Aggregates do not change the profile ID.

## Capture and prepare

From the repository root:

```sh
bobp make bluesky-install
bobp make bluesky-capture ARGS="--seconds 600 --limit 100000 --output data/posts-capture.jsonl"
bobp make bluesky ARGS="prepare data/posts-capture.jsonl --output data/posts-demo"
```

Use fresh output paths. Capture saves raw public Jetstream frames plus endpoint/window provenance;
it needs no login and downloads no image binaries. Preparation only unwraps post-create envelopes,
deduplicates identified creates by DID/key, and feeds the **unchanged original post** to the sketch.
It also accepts bare post JSONL, counting those rows as supplied. Updates/deletions and other event
kinds are counted as exclusions. Posts without images remain in the baseline.

There is no image model, post-to-image expansion or computed feature row. JSONPath fields and
modifiers in [profile.yaml](profile.yaml) define all kind distinctions. Supply `prepare --profile
PATH` to choose another profile; the exact profile is saved with the resulting sketch.

## Inspect kinds and locate samples

```sh
bobp make -vvv run ARGS="report data/posts-demo/posts.sketch.yaml --limit 20"
bobp make -vvv run ARGS="report data/posts-demo/posts.sketch.yaml --limit 0"
bobp make -vvv run ARGS="analyze data/posts-demo/posts.sketch.yaml -o data/posts-demo/analysis.html --force"
```

The report ranks kinds by observed frequency, with full IDs, individual/cumulative percentages,
tokens and retained-sample locators. Each skit contains its original post in the built-in first
record. The demo also saves `samples.json`, mapping each full skit ID to the raw source filename
and line number and its line in `representatives.jsonl`. Inspect the corresponding original
capture line when the event envelope is useful. That provenance is not part of sketch identity.

## Assemble regression data

```sh
# All observed kinds, one retained original post each:
bobp make run ARGS="export data/posts-demo/posts.sketch.yaml --output data/regression-posts.jsonl"

# Or copy full IDs from report and repeat --id to select specific kinds:
bobp make run ARGS="export data/posts-demo/posts.sketch.yaml --output data/selected-posts.jsonl --id FULL_SKIT_ID"
```

Exports require a new path and preserve original post values. Preparation also writes
`representatives.jsonl` for all observed kinds and verifies that re-sketching those records
produces exactly the full baseline skit-ID set. Keep raw posts in your regression corpus;
coverage accepts original JSON objects, not capture envelopes or a hand-written list of IDs.

## Measure coverage

```sh
bobp make -vvv run ARGS="coverage data/posts-demo/posts.sketch.yaml -p data/posts-demo/profile.yaml data/regression-posts.jsonl"
```

The saved profile determines regression kind IDs. **Kind coverage** counts distinct baseline
kinds represented in the corpus. **Frequency-weighted coverage** sums the original baseline
counts of those kinds and divides by the baseline's total post count. Repeated samples of one
kind add nothing; unseen regression kinds are reported separately. Missing baseline kinds are
ranked by frequency, with full IDs you can export next. Percentages are N/A for an empty baseline.

This measures represented kinds, not whether tests ran or passed. Completeness is relative to
the selected profile and captured observations; it is not global Bluesky or code-path coverage.
A highly frequent kind can dominate weighted coverage while rare untested kinds remain visible.

## Files and scope

Preparation creates a standard `posts.sketch.yaml`, its exact `profile.yaml`, unchanged-post
`representatives.jsonl`, `samples.json` source locators and `summary.json` with input SHA-256,
counts, capture provenance and retained-ID validation. The core tools also work on sketches from
other applications without any Bluesky code. Generated files live under ignored `data/`;
`bobp make clean` removes them, so preserve captures elsewhere when needed.

Array JSONPath matches become sorted, deduplicated token sets within one post. They do not
explode rows or retain cross-field pairing between different array elements. Choose fields
according to the branches/mappings your application actually uses; do not add IDs, raw text or
other distinctions that the application does not need. Structural presence is not schema validation.

## Verify

```sh
bobp make test-bluesky
bobp make test ARGS=test_reporting
bobp make lint
```
