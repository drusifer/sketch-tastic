# Agent State

## Important Notes
- 2026-10-14 Repository created: the fingerprint tool moved here from drusifer/fingerling (subtree split, history kept). Sprint 1 (5/5 pts) renamed it to sketch-tastic / sketchtastic / skt with the sketch/skit vocabulary. Sprint 2 (2/2 pts, 0 fix cycles, 2026-10-14) added `show --sort KEY` (lowest first, default COUNT; --top N dropped by owner). Both merged to main; not pushed (owner pushes).
- Owner rules carried over: no backwards compatibility before 1.0, formats `version: 0`; mainline development (no tags/releases); CI by hand only, never poll it; KISS; no ad hoc testing (tests + `bobp make` only, smoke sparingly); no `rm` (use `bobp make clean`); `*fix` diagnoses and confirms first; integrity errors abort runs.

## Current Task
**Status:** No sprint in flight.

## Next Steps
1. Done: fingerling Sprint 18 already depends on sketch-tastic (git pin 6c4606f, pushed). Bumping its pin is optional; its parked code does not use `show`.
2. Backlog in `task.md` (show --sort done; next candidates: test-internal fingerprint names, history fold speed).
3. Next sprint is sprint-3, next story STORY-SKT-04. Keep chat messages under 512 characters and check every `bobp chat` result.

---
*Last updated: 2026-10-14T21:50:00-04:00*
