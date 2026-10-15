# Agent State

## Important Notes
- 2026-10-14 Repository created: the fingerprint tool moved here from drusifer/fingerling (subtree split, history kept). Sprint 1 (5/5 pts) renamed it to sketch-tastic / sketchtastic / skt with the sketch/skit vocabulary. Sprint 2 (2/2 pts, 0 fix cycles, 2026-10-14) added `show --sort KEY` (lowest first, default COUNT; --top N dropped by owner). Sprint 3 (5/5, 2026-10-14) made merge 2.6x faster (make profile: 106.35 -> 40.83 s, same sketch). Post-Sprint 3 fixes (RFC 9535 JSONPath, fold once then merge, no copies) and Sprint 4 (merge -j N, libyaml; 13.54 s on 4 cores, 29.55 s -j 1) merged to main. Agents push only when the owner says so.
- Owner rules carried over: no backwards compatibility before 1.0, formats `version: 0`; mainline development (no tags/releases); CI by hand only, never poll it; KISS; no ad hoc testing (tests + `bobp make` only, smoke sparingly); no `rm` (use `bobp make clean`); `*fix` diagnoses and confirms first; integrity errors abort runs.

## Current Task
**Status:** No sprint in flight.

## Next Steps
1. Done: fingerling Sprint 18 already depends on sketch-tastic (git pin 6c4606f, pushed). Bumping its pin is optional; its parked code does not use `show`.
2. Backlog in `task.md` (next candidates: test-internal fingerprint names, JSON Schema for sketch files).
3. Next sprint is sprint-5, next story STORY-SKT-08. Speed: measure only with `make profile`. Keep chat messages under 512 characters and check every `bobp chat` result.

---
*Last updated: 2026-10-14T21:50:00-04:00*
