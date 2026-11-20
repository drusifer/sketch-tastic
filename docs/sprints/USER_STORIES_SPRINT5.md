# Sprint 5 User Stories: Bluesky Image Counts

* **Total Points:** 8 (Tier 1)
* **Branch:** `sprint-5` (integrated at close)
* **Source:** Owner 2026-11-19: image counts by properties; sketch retains meaningful variants. Clarified local repository, ASCII output, enumerated values and branch/mapping distinctions. Explicit `$sprint until done`.
* **Status:** Complete, 8/8 points. Trin, Switch, Morpheus, Tank and Smith gates passed; see [UAT evidence](UAT_PLAN_SPRINT5.md). Mainline demo delivery; no release/version bump.

## Goal
Show image counts from a public Bluesky capture as ASCII charts. Use sketch-tastic's existing
profile and retained samples to capture every observed combination of the properties the demo
uses. Inspect and export those representatives as compact test data.

## Assumptions made for the owner
- Count image attachments from unique captured create events; this is a capture window, not
  the current global image inventory or unique image blobs.
- First-version dimensions: reply status, embed type, attachment-count class, MIME class,
  orientation and alt-text state. Define finite enum domains, including missing/invalid cases.
- Retain all observed combinations; report unobserved enum values separately. Observed variant
  preservation does not establish application code coverage or reachability of every combination.

## STORY-SKT-08: Capture and sketch images
**Points:** 5

**As a** demo author, **I want** repeatable capture-to-sketch processing,
**so that** meaningful attribute variants retain real example data.

### Acceptance Criteria
1. Bounded public capture saves JSONL for offline reuse and records endpoint and capture window.
2. Direct image arrays, galleries and own media attached alongside quoted records are supported.
   Referenced quoted-post images, video, and link-card thumbnails are excluded.
3. Duplicate identified create events are excluded. Update/delete/non-post events are reported.
4. Every displayed grouping/filter property is an identity field in the sketch profile.
5. Missing/invalid metadata and empty alt text remain explicit states.
6. Each image representative retains its original post and image index.
7. Re-sketching one representative per skit yields exactly the full sketch's skit-ID set.
8. Malformed input reports its line and does not publish a partial output directory.

## STORY-SKT-09: Read image counts and variants in the terminal
**Points:** 3 · **Depends on:** STORY-SKT-08

**As a** demo user, **I want** ASCII charts grouped and filtered by image properties,
**so that** I can explore counts and inspect the compact set of meaningful variants.

### Acceptance Criteria
1. Report states input/capture scope, accepted post count, image count, skit count and retained examples.
2. Choose any profile dimension for grouping; filters combine with AND; counts sum matching skit weights.
3. Report lists observed enum values and absent enum values without labeling absent cases as covered.
4. Export contains one original-image representative per skit; repeated inputs collapse while
   changing any meaningful property produces a distinct skit.
5. Empty input or zero-match filters have explicit output; unknown field/value filters fail clearly.
6. CLI help and README describe reproducible make commands; output contains plain ASCII charts.
7. Printed source metadata cannot inject terminal control sequences.

## Out of Scope
Web apps, TUIs, hosting, image binary downloads, live dashboards, replay, automated regression
execution, global completeness claims, changes to the core sketch API.

## Open Questions
None blocking. Owner can steer dimension definitions as the demo develops.

## Architecture (Morpheus)

### System and boundaries
A Python demo lives in `examples/bluesky`. Capture uses optional websockets; all offline work
uses existing project dependencies. No browser, server or frontend language is introduced.

### Components and flow
- `capture.py`: bounded public Jetstream capture, raw JSONL and capture metadata. No credentials.
- `model.py`: extracts post create records, excludes duplicates, normalizes one row per image,
  and defines the finite categories used by the application. Preserve full source post on rows.
- `profile.yaml`: JSONPaths select those normalized dimensions; existing Profile/Sketch APIs
  perform tokenization and folding. Aggregates summarize byte sizes without changing identity.
- `demo.py`: prepare fresh output directory, validate representative skit IDs, save YAML sketch,
  representative JSONL and summary metadata; report ASCII charts and enum observations.

### Interfaces and resilience
`prepare INPUT --output DIR` rejects existing DIR; writes via staging directory only after
successful validation. `report DIR --group-by FIELD --where FIELD=VALUE` reads saved artifacts.
`capture --seconds N --limit N --output FILE` bounds collection; failures do not promote partial
captures. Source strings printed by the terminal app are escaped. Retained records remain exact.

### Decisions
Normalize per image so correlations across image attributes are preserved. Derive enums from
explicit branches/mappings; test enum partitions and missing cases. Attachment counts preserve
1/2/3/4 (the legacy grid switches on these) then 5-10 and 11+ for gallery ranges, with exact count
retained in the original normalized row. MIME classes: jpeg/png/webp/gif/other/missing/invalid.
Orientation: portrait/square/landscape/missing/invalid. Alt: present/empty/missing/invalid.
Reply: original/reply/invalid. Embed: images/gallery/quote_images/quote_gallery.

### Build impact and verification
Tank adds four make targets (bluesky-install, bluesky-capture, bluesky, test-bluesky), documents
optional `demo` dependency group. Tests run in existing unittest suite, including both supported
Python versions. No version bump/push requested. Real capture after clean-build gates avoids
losing demo artifacts to the existing clean target.

### Sources
- https://github.com/bluesky-social/bsky/blob/main/lexicons/app/bsky/embed/images.json
- https://github.com/bluesky-social/bsky/blob/main/lexicons/app/bsky/embed/gallery.json
- https://github.com/bluesky-social/social-app/blob/main/src/components/images/ImageLayoutGrid.tsx
- https://bsky.network/docs/jetstream/
