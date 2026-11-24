# Bluesky post kinds and regression data

One input row is one original post. The sketch profile defines what makes posts the same kind;
its retained records provide compact regression data for an application handling those kinds.
The dashboard, sample export and frequency-weighted coverage are generic **sketch-tastic commands**.

## Profile-defined post features

The default profile includes embed type, quoted media type, reply presence, rich-text feature
types, multi-language presence (`is_multi_lang`, boolean via `$.langs[1]` + `IS_PRESENT`) and
content labels. Tags are a boolean (`tags`, via `$.tags[0]` + `IS_PRESENT`): absent or
empty arrays yield `FALSE`; arrays with a member yield `TRUE`, regardless of tag text.
For each of four containers—direct images, direct gallery,
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

These are 19 profile fields (seven general fields and four groups of three bits), but the bits
are constrained by one another and the embed type; they do not imply 2^12 independent cases.
Edit the profile to reflect the distinctions your application actually makes.

Adding the tags field changes the profile ID. Start a new sketch or rebuild from original
posts; existing sketches and history do not gain this field automatically.

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
  default *First / Last Seen (Event Time)* slider in `sketch analyze`).

`meta.count` remains the built-in post count used for regression frequency weighting. The
`analyze` dashboard shows aggregate values per kind. Rebuild
from the original capture to populate new aggregates for all observations; re-sketching only
representatives cannot recover population statistics. Aggregates do not change the profile ID.

## Capture and sketch: one streaming pipeline

```
capture (raw Jetstream frames) -> unwrap (original posts) -> sketch merge - (sketch + history)
```

Every stage reads a line and writes a line; nothing waits for the end and memory does not grow
with the stream. `capture` and `unwrap` are example modules, not part of the installed
package, so run them from a checkout of this repository, at its root:

```sh
pip install sketch-tastic 'websockets>=15,<17'
set -o pipefail   # so a failed capture or unwrap fails the whole pipeline

# Live: capture straight into a sketch for 30 minutes.
python -m examples.bluesky.capture --output - --seconds 1800 \
  | python -m examples.bluesky.unwrap \
  | sketch merge -p examples/bluesky/profile.yaml -s data/posts.sketch.yaml -

# Or keep the raw capture first (streamed to disk, readable while it runs) ...
python -m examples.bluesky.capture --seconds 1800 --output data/posts-capture.jsonl
# ... then sketch it (or re-sketch it later with another profile).
python -m examples.bluesky.unwrap data/posts-capture.jsonl \
  | sketch merge -p examples/bluesky/profile.yaml -s data/posts.sketch.yaml -
```

`capture` saves raw public Jetstream frames, flushing each one, and writes the `.meta.json`
provenance file last (also on failure, with `stop_reason: "error"`). It needs no login and
downloads no image binaries. `--limit` is optional; the time budget bounds the run.

`unwrap` (`examples/bluesky/unwrap.py`) is the only Bluesky-specific step. It writes each
unchanged post-create record to stdout, drops updates/deletes/other collections, and drops
creates replayed after a reconnect (dedup by DID/key over the 100,000 most recent creates). Bare
post JSONL passes through. Counts go to stderr. A malformed line stops it with exit 2 and the
line number; the sketch keeps what was merged before it.

There is no image model, post-to-image expansion or computed feature row. JSONPath fields and
modifiers in [profile.yaml](profile.yaml) define all kind distinctions.

## Inspect kinds

```sh
sketch analyze data/posts.sketch.yaml -o data/analysis.html --force
```

Open `data/analysis.html` in a browser. Its skit explorer ranks kinds by observed frequency, with
full IDs, shares, tokens and each kind's retained original post.

## Assemble regression data

```sh
# All observed kinds, one retained original post each:
sketch export data/posts.sketch.yaml --output data/regression-posts.jsonl

# Or copy full IDs from the dashboard and repeat --id to select specific kinds:
sketch export data/posts.sketch.yaml --output data/selected-posts.jsonl --id FULL_SKIT_ID
```

Exports require a new path and preserve original post values.

## Measure coverage

```sh
sketch analyze data/posts.sketch.yaml -o data/analysis.html --force \
  --regression data/regression-posts.jsonl -p examples/bluesky/profile.yaml
```

The dashboard's *Regression Coverage* card shows **kind coverage** (distinct baseline kinds the
corpus represents) and **frequency-weighted coverage** (baseline posts in those kinds / all
posts), following the current filters. Set the *Coverage* filter to *uncovered* and the skit
explorer ranks the kinds to export next. With run history, the card charts coverage per run and
cumulatively, and lists the kinds each run introduced that the corpus does not cover yet. That
is how a new capture shows up: merge it into the same sketch, re-run `analyze`, and read off
what the latest run added. Repeated samples of one kind add nothing.

This measures represented kinds, not whether tests ran or passed. Completeness is relative to
the selected profile and captured observations; it is not global Bluesky or code-path coverage.

## Scope

Array JSONPath matches become sorted, deduplicated token sets within one post. They do not
explode rows or retain cross-field pairing between different array elements. Choose fields
according to the branches your application actually uses. Structural presence is not schema
validation. The commands above write under `data/`, which git ignores; the repository's `clean` target
removes it, so preserve captures elsewhere when needed.

## Verify

For contributors, the project's test gates (see [docs/SDLC.md](../../docs/SDLC.md)):

```sh
bobp make test-bluesky
bobp make test ARGS=test_reporting
bobp make lint
```
