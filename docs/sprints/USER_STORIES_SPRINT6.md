# Sprint 6: Post kinds and regression coverage

* **Branch:** `sprint-6`
* **Source:** Owner, 2026-11-20: keep one original post per row, define kinds in the sketch,
  locate regression samples, measure frequency-weighted real-world coverage. Reporting must
  live in the sketch-tastic tool as a generic first-class use case.
* **Status:** Complete. Implementation, independent reviews, clean conformance and live UAT passed.

## Goal
Explore sketch kinds and export representative regression samples using the core CLI.
Measure which observed kinds a regression corpus represents and their share of observations.
Demonstrate this on original Bluesky posts, with no per-image preprocessing.

## Assumptions made for the owner
The baseline is unique accepted post-create observations in a capture, not the whole network.
A supplied regression corpus means samples selected for testing, not proof of test execution.
The tool remains offline after optional capture. Profile changes define a new coverage universe.

## STORY-SKT-10: Locate original post samples
As an app developer I want a frequency-ranked list of post kinds and their original samples
so that I can assemble regression data without constructing a derived domain model.

### Acceptance Criteria
1. Each accepted input contributes exactly one unchanged post; zero-image posts remain.
2. Identity comes from JSONPath fields and modifiers in a saved user-selectable profile.
3. Generic ASCII output lists full skit IDs, frequencies, tokens and sample locations.
4. Export all kinds or specified kinds to original-post JSONL, without overwriting files.
5. Bad input and invalid IDs fail clearly; representative IDs reproduce baseline kind IDs.

## STORY-SKT-11: Measure regression coverage
As an app developer I want to compare regression posts with a baseline sketch
so that I can prioritize missing kinds by real observation frequency.

### Acceptance Criteria
1. Covered kinds are the intersection of regression and baseline skit IDs under the saved profile.
2. Weighted coverage is sum of counts for covered baseline kinds divided by all baseline counts.
3. Show distinct-kind coverage separately; repeated samples do not increase either percentage.
4. Show uncovered kinds in descending baseline frequency, with exportable representative IDs.
5. Identify regression kinds absent from the baseline separately; define empty-baseline results.
6. State capture scope and that sample representation is not branch coverage or test execution.

## Out of Scope
Test execution, global completeness, new web/TUI dependencies, post-to-image row expansion,
and a general MAP/REDUCE engine. No core feature is added unless native profile expressions
cannot represent the required distinctions.

## Architecture
Replace the image-normalization demo with a profile-driven post explorer. The input adapter only
unwraps supported Jetstream create envelopes, deduplicates identified creates, and yields the
original record plus source-line provenance. Bare posts remain unchanged. Existing Profile and
Sketch APIs define all identity and sample retention. Keep capture unchanged.

The demo prepares a standard sketch plus its exact profile, source hash/window, representatives
and a skit-ID-to-source/sample-line index. The core CLI owns `report`, `export` and `coverage`,
works on any standard sketch, and imports nothing from the demo. `coverage` requires a matching
profile and recomputes regression kinds, never trusting user-provided IDs or counts. Generic
reports accept profile fields; no hard-coded derived model or enum domain validation.
Escape untrusted terminal output and preserve bounded JSONL reads and fresh-output publication.
Empty-baseline percentages are N/A; unseen regression kinds do not increase covered counts.

### Default post profile
Use native JSONPath/modifiers for embed/media discriminators, reply presence, facet-type sets,
languages and labels. Each of four containers (images, gallery and their quoted-media forms)
has present/any/multiple fields. The owner explicitly requested the fourth state: no image array.
These bits distinguish absent, present with zero images, one and multiple, without derived rows.
Separate expressions stay within the JSONPath parser's cumulative complexity limit. IS_PRESENT
checks member existence, not type validity; null is present. Gallery counts exclude non-image items.
Array matches are set-like tokens; this does not assert per-image cross-field correlations.
Count only recognized direct images or typed gallery images, including own quoted-post media;
never quoted-post references or external-link thumbnails. Structural image members count even
when malformed; the demo does not validate the entire Bluesky schema or download image blobs.

## Verification
Contract tests include zero/single/multiple-image posts, original-record equality, native array
tokenization, profile changes, 90/9/1 weighted distribution, duplicate regression rows, unknown
kinds, empty inputs, malformed data and no-clobber exports. Independent QA/security/code review
and live ASCII UAT use the existing ten-minute capture.

## Open Questions
None blocking. The default profile is explicitly a demo definition, editable for the target app.
