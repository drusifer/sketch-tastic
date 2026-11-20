# Engineering lessons

## [2026-11-19] Preserve per-item correlations before sketching nested records

**Historical scope; superseded for this demo by the 2026-11-20 lesson below.** The original
post, not each nested image, is the owner's regression-test unit. Do not reinstate image rows.

> **Tags:** #data-modeling #bluesky #Oracle

### Context
Sprint 5 counts individual images inside posts and selects representative image variants.

### Observation and Cause
A post can contain a portrait PNG and a landscape JPEG. Independent arrays of MIME types and
orientations would discard which properties belong to each image. That representation cannot
support exact per-image counts or a faithful representative for the combined properties.

### Rule
When the application operates on nested items, emit one correlated row per item before
sketching. Preserve the original parent and item index, and verify that exported representative
rows reproduce the full observed skit-ID set. Use original sketch weights for population counts.

### Evidence and Scope
- **References:** `examples/bluesky/model.py`, `examples/bluesky/demo.py`,
  `tests/test_bluesky.py`; implementation commit `f6d1365`.
- **Applies when:** grouping or selecting representative nested items by combined properties.
  ID-set preservation covers the selected profile on observed data, not all application paths.

## [2026-11-20] Keep the regression-test unit intact

> **Tags:** #profiles #regression-coverage #Oracle

### Context
The Bluesky demo initially modeled one row per image. The owner needed representative original
posts, with meaningful kinds defined by the sketch and reusable reporting in the core tool.

### Observation and Cause
Image expansion removed zero-image posts and made coverage measure image occurrences instead
of post observations. The implementation chose a reporting unit before confirming the test unit.

### Rule
Keep each original input record intact when it is the unit under test. Put kind distinctions in
the sketch profile and weight covered kinds by baseline counts. Distinguish array-member
absence from presence with zero matching items; IS_PRESENT and native count predicates suffice
here. Keep reporting generic so the same analysis works for other datasets.

### Evidence and Scope
- **References:** ADR-2026-11-20, `examples/bluesky/profile.yaml`,
  `src/sketchtastic/reporting.py`, `tests/test_bluesky_profile.py`.
- **Applies when:** selecting representative original records for regression tests; completeness
  is relative to the observed baseline and profile, not all possible program behavior.
