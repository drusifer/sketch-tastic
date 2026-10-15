# Agent State

## Important Notes
- 2026-10-14 Repository created from drusifer/fingerling (subtree split, history kept). Sprint 1 renamed it to sketch-tastic / `sketchtastic` / `skt` (sketch = the file, skit = one event shape). Sprint 2: `show --sort KEY` (lowest first, default COUNT; no --top). Sprint 3 + owner review: RFC 9535 JSONPath via jsonpath-rfc9535, fold each event once into the run then `Sketch.merge`, no FIRST/LAST copies. Sprint 4: `merge -j N` (long-lived workers, bounded task queue, output queue), libyaml for all YAML.
- 2026-10-15 post-Sprint 4 fixes, pushed (636243e): every aggregate is created in profile order at its initial state (SUM/COUNT 0, FIRST/LAST [], AVG {avg: null, sum: 0, count: 0}, MIN/MAX null); skit id = MD5 of the JSON-encoded token values in profile order; profile id = field specs in profile order.
- `make profile` (GH Archive hour, 180,387 events, Pi 5, 4 cores): parallel ~14 s, `-j 1` ~29 s (106 s before Sprint 3). Ids changed after the last profile run, so the next run prints a new `-j 1` hash.
- Owner rules: no backwards compatibility before 1.0 (v0, no migrations); mainline (no tags/releases); CI by hand only, never poll it; KISS; no ad hoc testing (tests + `bobp make` only); no `rm` (use `bobp make clean`); `*fix` diagnoses and confirms first; integrity errors abort runs; agents push only when the owner says so; leave ../fingerling alone unless asked.
- Owner working style: steers designs live; explain options and trade-offs before building; no shortcuts or side paths (one mechanism; producers wait on full buffers); the profile is the only source of key order.

## Current Task
**Status:** No sprint in flight. Prepared for a context clear on 2026-10-15.

## Next Steps
1. Cold start: read the bottom of `agents/CHAT.md` and `task.md` (Backlog), then ask the owner what to pick up.
2. Backlog highlights: **profile evolution** (owner: its own future sprint) — updating a sketch's profile, adding/removing fields, and whether to keep both the skit id and the profile id; test-internal "fingerprint" names; JSON Schema for sketch files.
3. Next sprint is sprint-5, next story STORY-SKT-08. Measure speed only with `make profile` (`PROFILE_ARGS=` profiles a parallel run's parent). Keep chat messages under 512 characters and check every `bobp chat` result.

---
*Last updated: 2026-10-15T09:55:00-04:00*
