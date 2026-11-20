# Agent State

## Context
### Recent Decisions
- The profile is the single source of truth for key order (aggregates, functions, meta, show columns, skit id value order, profile id). See docs/DECISIONS.md 2026-10-15 entries.
- Design rule (owner): one mechanism that covers every case; producers wait on full buffers; no fallback side channels; prefer a standard library to a partial reimplementation.

### Key Findings
- Parallel speed-up is bounded by serial parent work (reading, YAML writing); libyaml removed the largest piece.

### Important Notes
- Backlog for a future sprint: profile evolution (updating a profile, adding/removing fields, two ids).

## Current Task
**Status:** Sprint 5 independent final architecture review approved (2026-11-19); final runtime gates owned by root.
**Assigned to:** N/A
**Started:** N/A

### Task Description
Bluesky Image Explorer: normalized image rows preserve original posts; existing Sketch API retains variants. Profile fields drive ASCII grouping/filter dimensions. Weighted sketch counts power charts; first samples power representative export. See Sprint 5 stories for architecture and limitations.

Reviewed model/demo/capture, profile, independent boundary and capture tests, Makefile additions and demo/SDLC documentation. No blocking design or correctness defects found. Identity includes all six displayed dimensions; optional bytes stay aggregate-only. Image rows preserve original event, post and attachment index. Representative validation uses the same profile and exact skit-ID set equality; README correctly distinguishes raw preparation input from normalized representative input for the public merge CLI. Population weights come from full sketch counts, not representative frequency. Enum absence and reachable combination/branch coverage are correctly distinguished.

Publication uses staged artifacts plus exclusive directory reservation; capture links metadata before raw commit marker and refuses existing paths. Finite frames/lines and explicit malformed-input failure keep resource boundaries understandable. Source SHA-256, capture endpoint/window and saved profile provide provenance. Optional capture/security groups remain outside library runtime dependencies; no web stack or core API changes.

### Progress
- [x] Architecture and implementation reviewed against owner ASCII/enumeration requirements.
- [x] No blocking findings; tests and live capture execution remain with root.

### Blockers
None

### Oracle Consultations
None yet

## Next Steps
### Immediate Next Action
Root completes final tests/security gates and live capture; Smith conducts terminal UAT, Tank confirms SDLC. Root logs Morpheus handoff to Smith. No additional architectural work required unless those gates expose a defect.

### Waiting On
None

### Planned Work
- [ ] No planned work

---
*Last updated: [timestamp]*

## Final Sprint 5 checkpoint — supersedes pending work above
Context: local ASCII Bluesky demo complete; six enum dimensions preserve observed image variants. Owner skill migration included. No core package semantics changed.
Current Task: complete (100%). Independent code/security/doc reviews and Smith live UAT passed. Clean gates: 267 tests on Python 3.14/3.15, lint, three wheel smoke tests, build and scans. Two-minute capture: 4,587 events -> 821 image rows -> 70 representatives; exact observed skit-ID preservation verified, public CLI re-sketch yields 70 skits.
Next Steps: read task.md and sprint UAT before new work. Sprint close integrates locally to main; no push, tag or version bump. Use git log/status to confirm integration after interruption. Generated data/bluesky-demo is available locally but clean deletes data. Do not rerun unchanged tests or restart planning; await next user task.

## Owner correction and raw inspection — 2026-11-20
Context: owner explicitly rejects per-image normalization/model; one row must remain one post. Avoid bespoke preprocessing. Prior image-demo architecture is superseded for next implementation; existing files remain unchanged pending design.
Current Task: raw-data investigation complete. Ran core CLI directly on all 21,976 raw frames with data/bluesky-post-inspection.yaml, no model/prepare. Seven exploratory fields produced 811 skits (includes create/update/delete; not a final post-only profile). Observed embed enums images/gallery/video/external/record/recordWithMedia; facet feature types links/mentions/tags plus bold/custom; languages and label arrays. Native JSONPath multi-match tokenization deduplicates/sorts per record without unnesting; COUNT aggregates do not define identity.
Next Steps: design post-level profile from raw record paths; separate create records from stream operations. Need 0/1/2+ image cardinality across direct/quoted/gallery forms; first/second presence can encode it for ordinary images, while a general per-record count/bucket reduction is the cleaner possible engine extension. Keep image-level predicates scoped to same array element if correlations matter. Do not reuse 92/125 counts as post-level results. No application code changed or tests rerun.

## Sprint 6 design checkpoint — 2026-11-20

Owner correction supersedes Sprint 5 image-row architecture: one unchanged original post per
row, profile-defined kinds, ASCII sample locators, frequency-weighted regression corpus coverage.
Native profile design approved; no core changes required by the proposed design. Two IS_PRESENT
fields filter the actual root embed using threshold counts >=1 and >=2, with explicit type guards
for images/gallery/recordWithMedia and gallery image-item discriminators. Never use recursive
count(@..image), which could include quoted/unsupported descendants. Bits FALSE/FALSE, TRUE/FALSE,
TRUE/TRUE denote 0, 1, 2+ own images. Field.token applies modifiers per value then sorts/deduplicates,
so counting cannot be inferred from repeated TRUE tokens. Root must compile and fixture-test the
expressions; review inspected Path/Field/IsPresent after VIA lookup but did not execute tests.

Coverage design approved: sum baseline meta.count for unique covered baseline IDs / total baseline
meta.count. Distinct-kind coverage is a separate fraction. Repeated candidate samples add no coverage;
unknown candidate kinds are separate, and the saved baseline profile defines the comparison universe.
Unwrap envelopes only; keep original post, source line and sample index separate. Preserve malformed
input/no-clobber/terminal escaping boundaries. Next: root implementation and independent QA.

## Sprint 6 independent core review — 2026-11-20
Context: owner moved reporting/export/coverage into generic core. Reviewed reporting.py,
cli.py registration and 14 reporting tests independently of own preparation implementation.
Current Task: review complete with one narrow blocker pending Neo response. Weight = sum
baseline counts for unique intersecting IDs / total; distinct-kind denominator, duplicate
handling, unknown kinds and empty N/A semantics correct. Export validates selected IDs and
samples before atomic no-clobber publication. Structure is proportionate, no framework drift.
Exact sketch sample object pointers plus exported JSONL line locators are usable generic UX;
source-line sidecar rendering is absent but not necessary for export selection.
Blocker: safe YAML permits non-JSON nested values (dates/sets/binary) in first records;
export json.dumps raises TypeError not caught by CLI. Asked QA implementer to translate this
to ValueError with skit context and add malformed nested-sample CLI regression coverage.
Next Steps: parent checks that fix and test, then approve core review. Default Bluesky profile
compilation and user decision are separate. No make execution or code edits during review.

### Sprint 6 core review final verdict
APPROVED. Inspected export fix: TypeError, ValueError and RecursionError during retained-record
serialization become ValueError naming the skit, before atomic publication. Regression test
uses nested YAML date through CLI, verifies exit 2, clear JSON error, empty stdout and absent
output. QA reports red reproduced then all 15 reporting tests green. No blockers remain in
reviewed core reporting/export/coverage scope. Parent proceeds with remaining sprint gates.

## Sprint 6 checkpoint — 2026-11-20
Context: owner moved report/export/coverage into core tool. Core implemented and committed on sprint-6 at 7146434, independently reviewed. User asked what 'profile check' means; clarified it means ordinary YAML JSONPath/modifier field producing a token, not validation/preprocessing.
Current Task: core complete; default Bluesky image-cardinality profile remains blocked awaiting user guidance after two parse-complexity failures. Oracle confirmed increment-only parser depth budget30; avoid third retry until guidance. Core 258 tests, 15 reporting contracts, lint, 3 wheel smoke tests/build/secrets pass. Separate 7 post-adapter tests pass. Core live UAT uses valid data/post-reporting-uat.yaml: 20789 posts,796 kinds; all representatives100% coverage; top3 represent6362 observations. No full-suite claim.
Next Steps: resolve pending profile question; no first/second raw-position workaround for mixed galleries. Then profile/full/all-Python tests, default live UAT, Tank conformance, docs/retro/launch and local merge. Root default profile and 3 profile tests currently fail compilation; do not ship them or claim sprint closed. Other demo/docs/state changes uncommitted. Preserve data captures; no push/release. Task board and UAT_PLAN_SPRINT6.md contain remaining gates.

## Sprint 6 final checkpoint — supersedes pending work above
Context: original post rows are the regression unit. Generic report/export/coverage live in sketch-tastic; Bluesky only unwraps post-create envelopes. Owner approved split native profile fields and absent-array distinction.
Current Task: complete (100%). Four container groups use present/any/multiple bits; mixed galleries count image entries only. Core and profile reviews, clean gates (279 tests on3.14/3.15, lint,3wheel smokes/build/security scans) and live UAT passed. Final dataset data/bluesky-posts:20789 posts,860 kinds; all representatives100% kind/frequency coverage. Selected sample represents3331 observations (16.0%),1/860 kinds. No pending questions/blockers.
Next Steps: sprint launch/archive/local main integration; confirm git log/status if interrupted. No push, version bump or release. Existing data preserved; clean deletes it. Read task.md before new work; do not rerun unchanged tests or restore the superseded image model.
