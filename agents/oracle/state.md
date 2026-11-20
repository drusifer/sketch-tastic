# Agent State

## Context
- Owner wants a large public dataset with many attributes and available producer code to demonstrate regression-data reduction, as previously done for electronic trading orders.
- Correction: do not introduce replay, trace reconstruction, anomaly detection, or a separate test-selection algorithm as requirements.
- Reread README.md in full, examples/access_log.yaml and access_log.jsonl, docs/DECISIONS.md, Sprint 1 stories, and Neo/Morpheus state on 2026-11-19.
- Profile JSONPaths and modifiers produce tokens; the combination of token values determines a skit. Unselected attributes and differences collapsed by modifiers do not create new skits. Aggregates do not affect identity.
- Each skit already retains complete original records under meta.first/meta.last, plus counts, shares and requested aggregates. FIRST/LAST aggregates allow more samples. Thus representative test data is retained by existing sketch behavior, not something requiring a new selection algorithm.
- Example: authenticated successful GETs to /items/{id} with no slow upstreams share a skit despite different item/user IDs, timings and bytes; original records remain available as samples.
- HDFS research so far only inspected published samples, templates and documentation; no full-data experiment or reduction measurement. Templates in the 2k sample and full-data template file use different EventId mappings; do not join blindly.
- HDFS remains a candidate, not a validated choice. Evaluate richness of row attributes and useful source-informed modifiers without assuming a need for complete block traces.

## Current Task
Documentation reread complete. Owner now requests a Bluesky image-count visualization application whose chosen attributes are represented by sketch skits and retained samples. Research confirmed image blobs carry MIME type/size, alt text and optional aspectRatio; current schemas also include galleries. Canonical app.bsky lexicons moved to bluesky-social/bsky. Proceed to Cypher planning under the existing Bloop sprint workflow.

## Next Steps
1. Explain existing token grouping and built-in original-record samples using the access-log example.
2. Continue HDFS suitability research only in that frame; do not impose coverage formulas or claim built-in comparison/replay.
3. No sprint or implementation has been authorized by this clarification. Preserve existing research chat changes; no commit/push requested.


## Current checkpoint — 2026-11-19 (supersedes earlier Sprint 5 plans)

The owner authorized `$sprint until done` and clarified **local ASCII output**, with no browser,
web app or TUI. Sprint 5 implementation and independent Trin/Switch/Morpheus reviews passed;
Tank clean-environment gates and final Smith UAT remain pending. Six shared enum dimensions
preserve observed image variants using the existing sketch/sample APIs. Original post/event
and attachment indexes are retained. No global coverage or replay claim is made.

Resume from `task.md` and `docs/sprints/UAT_PLAN_SPRINT5.md`; do not restart HDFS research or
web design. Root coordinates final evidence, sprint close and handoffs. No push/release requested.

### Oracle grooming review

Reviewed root/demo README onboarding, Sprint 5 stories/UAT/task, SDLC mechanism documentation
and decision record. Updated stale planning status and appended current checkpoints without
removing history. Recorded the enum/image-row/provenance decision in docs/DECISIONS.md.

Groom: ACCURACY=PASS USABILITY=PASS CONSISTENCY=PASS SYNC=PASS (no packaged doc mirrors).
Rubric DECISION: WHY=PASS OPTS=PASS CONS=PASS STATE=PASS.
Rubric SDLC: TRUE=PASS WHOLE=PASS CLEAN=PASS CLASS=PASS CHECK=PASS GAPS=PASS.
These verdicts review documentation; clean-environment execution remains Tank's pending gate.
SDLC explicitly records the unverified conformance status; root updates it after actual gates.
Next: root records final UAT/conformance evidence and logs Oracle handoff to Smith/Cypher.

## Final Sprint 5 checkpoint — supersedes pending work above
Context: local ASCII Bluesky demo complete; six enum dimensions preserve observed image variants. Owner skill migration included. No core package semantics changed.
Current Task: complete (100%). Independent code/security/doc reviews and Smith live UAT passed. Clean gates: 267 tests on Python 3.14/3.15, lint, three wheel smoke tests, build and scans. Two-minute capture: 4,587 events -> 821 image rows -> 70 representatives; exact observed skit-ID preservation verified, public CLI re-sketch yields 70 skits.
Next Steps: read task.md and sprint UAT before new work. Sprint close integrates locally to main; no push, tag or version bump. Use git log/status to confirm integration after interruption. Generated data/bluesky-demo is available locally but clean deletes data. Do not rerun unchanged tests or restart planning; await next user task.

## Sprint 6 documentation sign-off
Context: owner corrected regression unit to original posts and required coverage in core. ADR-2026-11-20 supersedes the Sprint5 per-image decision; old lesson explicitly superseded for this demo.
Current Task: complete. README generic commands, post demo guide with four presence/count states, sprint stories/UAT, SDLC and task updated. STORIES/ARCH/DECISION/LESSON/SDLC documentation rubrics PASS; claims match 279-test clean verification and actual live post runs.
Next Steps: Smith final acceptance, retro/Cypher launch, archive chat and local merge; no release/push. Future extensions must retain original records and generic reporting.

## Sprint 6 final checkpoint — supersedes pending work above
Context: original post rows are the regression unit. Generic report/export/coverage live in sketch-tastic; Bluesky only unwraps post-create envelopes. Owner approved split native profile fields and absent-array distinction.
Current Task: complete (100%). Four container groups use present/any/multiple bits; mixed galleries count image entries only. Core and profile reviews, clean gates (279 tests on3.14/3.15, lint,3wheel smokes/build/security scans) and live UAT passed. Final dataset data/bluesky-posts:20789 posts,860 kinds; all representatives100% kind/frequency coverage. Selected sample represents3331 observations (16.0%),1/860 kinds. No pending questions/blockers.
Next Steps: sprint launch/archive/local main integration; confirm git log/status if interrupted. No push, version bump or release. Existing data preserved; clean deletes it. Read task.md before new work; do not rerun unchanged tests or restore the superseded image model.
