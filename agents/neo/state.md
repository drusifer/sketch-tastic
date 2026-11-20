# Agent State

## Context
### Recent Decisions
- 2026-10-15 Skit id = MD5 of `json.dumps(list(tokens.values()))` in profile order (`sketch.skit_id`); profile id hashes field specs in order (`profile.profile_id`).
- 2026-10-15 Every skit is created with every aggregate and built-in in profile order at `Aggregator.initial()` (`Aggregate.init`, `Sketch._new_skit`); `load` rebuilds in profile order. No EMPTY sentinel.
- 2026-10-14/15 Merge pipeline: `_fold_lines` (cli.py) is the only fold (parse bytes, sequence check, upsert into a run sketch). `-j 1` or input <= `_BATCH_LINES` (5000) folds in-process; otherwise `_fold_parallel` starts N `Process` workers fed `(first lineno, [line bytes])` batches through `Queue(3*N)`; each worker puts one fold on an output queue at the `None`; the parent merges folds as they arrive (first fold becomes the run), then `sketch.merge(run)` once.
- `Aggregator.merge` per function (add, min/max with kind check, AVG from sum/count, FIRST/LAST concat+trim); FIRST/LAST samples with -j > 1 are any matching events (owner).
- All YAML through `sketchtastic/_yaml.py` (libyaml CSafeLoader/CSafeDumper).

### Key Findings
- Measured and dropped: plain-JSONPath shortcut (owner: complexity, not root cause), select-once API, JSON copy memo, ProcessPoolExecutor per-batch partial sketches (17-19 s), shared-memory ring with per-line messages (25.7 s: queue cost per message).
- cProfile inflates small Python calls (queues); trust the no-profiler wall times in `make profile`.

### Important Notes
- `Sketch.upsert` keeps references (caller must not modify the record); `Sketch.merge` deep-copies the later sketch's skits.

## Current Task
**Status:** Not started
**Assigned to:** N/A
**Started:** N/A

### Task Description
No active task

### Progress
- [ ] Not started

### Blockers
None

### Oracle Consultations
None yet

## Next Steps
### Immediate Next Action
None planned

### Waiting On
None

### Planned Work
- [ ] No planned work

---
*Last updated: [timestamp]*

## Sprint 5 implementation checkpoint (2026-11-19)
Owner authorized sprint until done, local ASCII output and persona subagents. Implemented
examples/bluesky model/profile/demo plus capture (delegated); 24 new tests and full suite
267 passed; lint passed. Real v2 one-frame capture and prepare/report passed. Retained samples
reproduce skit IDs. Four demo make targets and optional dependency, five security targets and
hook updates installed/reviewed by Switch. Owner permits Bob skill migration in same commits.
Next: Morpheus final review, clean-env SDLC gates, larger capture/UAT, docs/retro/launch/merge.
No push requested. Preserve user migration; all old agent skills moved to .agents/skills.

## Final Sprint 5 checkpoint — supersedes pending work above
Context: local ASCII Bluesky demo complete; six enum dimensions preserve observed image variants. Owner skill migration included. No core package semantics changed.
Current Task: complete (100%). Independent code/security/doc reviews and Smith live UAT passed. Clean gates: 267 tests on Python 3.14/3.15, lint, three wheel smoke tests, build and scans. Two-minute capture: 4,587 events -> 821 image rows -> 70 representatives; exact observed skit-ID preservation verified, public CLI re-sketch yields 70 skits.
Next Steps: read task.md and sprint UAT before new work. Sprint close integrates locally to main; no push, tag or version bump. Use git log/status to confirm integration after interruption. Generated data/bluesky-demo is available locally but clean deletes data. Do not rerun unchanged tests or restart planning; await next user task.
