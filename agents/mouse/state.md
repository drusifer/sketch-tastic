# Agent State

## Important Notes
- 2026-10-14 Repository created: the fingerprint tool moved here from drusifer/fingerling (subtree split, history kept). Sprint 1 (Stage 0 + 2 phases, 5/5 pts, 0 fix cycles) renamed it to sketch-tastic / sketchtastic / skt with the sketch/skit vocabulary. Merged to main; not pushed (owner pushes).
- Owner rules carried over: no backwards compatibility before 1.0, formats `version: 0`; mainline development (no tags/releases); CI by hand only, never poll it; KISS; no ad hoc testing (tests + `bobp make` only, smoke sparingly); no `rm` (use `bobp make clean`); `*fix` diagnoses and confirms first; integrity errors abort runs.

## Current Task
**Status:** No sprint in flight.

## Next Steps
1. After the owner pushes this repo: fingerling (`../fingerling`) drops `packages/fingerprint-sampler` and depends on sketch-tastic via git (pinned commit), updating its parked code to the new names.
2. Backlog in `task.md`; top item `show --sort KEY` / `--top N`.
3. Next sprint is sprint-2, next story STORY-SKT-03. Keep chat messages under 512 characters and check every `bobp chat` result.

---
*Last updated: 2026-10-14T21:25:00-04:00*
