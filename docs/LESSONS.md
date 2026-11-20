# Engineering lessons

## [2026-11-19] Preserve per-item correlations before sketching nested records

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
