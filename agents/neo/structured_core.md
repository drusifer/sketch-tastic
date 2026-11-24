# Structured Core Subtask State

## Context
- Sprint 9 owner expanded scope to structured tokens, explicitly no backward compatibility; owner will recapture.
- Final revised design/plan gates approved at 2026-11-24 00:53:09.
- Scalar nonnull tokens remain strings. DEFAULT arrays become canonical recursive sets; multiple selected tokens become canonical arrays, singleton unique selections stay scalar.
- DEFAULT, REGSUB and TRUNC preserve MISSING (omitted field) vs explicit null (None); predicates retain existing TRUE/FALSE strings.
- Key/value pairs in profile order now define skit IDs; sketch format version is 1. Legacy version 0 is refused with recapture/rebuild guidance.
- Native structured arrays still do not encode whether a list came from one selected array or several matches. Derivation must conservatively reject array transformations where that distinction matters; IS_PRESENT remains safe for untyped DEFAULT.

## Current Task
- Implementation complete: model.py, sketch.py, profile.py; new tests/test_structured_tokens.py and updated core model/sketch/types expectations.
- Initial red test: 8 tests, 6 expected failures + 1 error before production changes.
- Targeted green results: structured_tokens 12, model 57, sketch 44, types 12, profile 39, event_time 6, aggregators 28.
- Additional regular-load corruption test demonstrated red (4 invalid variants accepted), then green after canonical tokens and keyed identity validation moved into Sketch.load_data. Ranked loading reuses that validation without duplicate hashing.
- No commits; shared root handles formatting, full regression suite, integration and review.
- README quickstart skit ID for INFO/db/FALSE changed to 549439e519c9cad471036ab7ebb4e2a6.

## Next Steps
1. Root runs shared bobp make format after concurrent edits settle, then lint/full suite.
2. Root and views worker update consumers and remaining version0/golden-ID fixtures.
3. Regular Sketch.load_data now validates canonical tokens and identity for merge as well as inspection; root should include this in final review.
4. Preserve owner edits to capture.py and its tests; do not commit independently.
