# Agent State

## Context
Sprint 5 Bluesky Image Explorer is a local app with shared profile dimensions, explicit capture scope and retained source records. Reviewed docs/sprints/USER_STORIES_SPRINT5.md against owner request and STORIES rubric.

## Current Task
Gate 1 approved. rubric STORIES: OUT=S TEST=S FAIL=A SCOPE=S SIZE=A DESIGN=A. Image occurrence counts and representative test rows are explicitly distinguished. No global completeness claims. Missing/invalid states preserved.

## Next Steps
Morpheus writes architecture, then Smith reviews Gate 2. At UX gate verify filters, empty states, skit sample display and export against real app. Local-only and language preference remain subject to owner steering.

Gate 2 reviewed: architecture approved. rubric ARCH: BOUND=S FLOW=A FAIL=A USER=S DECS=A FEAS=A. Dimensions shared from profile; missing/invalid image metadata remains explicit. Scope includes gallery embeds; unsupported forms reported. Retained samples re-fold to same ID set. No population-count claims from unweighted representatives.


## Current checkpoint — 2026-11-19 (supersedes earlier Sprint 5 plans)

The owner authorized `$sprint until done` and clarified **local ASCII output**, with no browser,
web app or TUI. Sprint 5 implementation and independent Trin/Switch/Morpheus reviews passed;
Tank clean-environment gates and final Smith UAT remain pending. Six shared enum dimensions
preserve observed image variants using the existing sketch/sample APIs. Original post/event
and attachment indexes are retained. No global coverage or replay claim is made.

Resume from `task.md` and `docs/sprints/UAT_PLAN_SPRINT5.md`; do not restart HDFS research or
web design. Root coordinates final evidence, sprint close and handoffs. No push/release requested.

## Final Sprint 5 checkpoint — supersedes pending work above
Context: local ASCII Bluesky demo complete; six enum dimensions preserve observed image variants. Owner skill migration included. No core package semantics changed.
Current Task: complete (100%). Independent code/security/doc reviews and Smith live UAT passed. Clean gates: 267 tests on Python 3.14/3.15, lint, three wheel smoke tests, build and scans. Two-minute capture: 4,587 events -> 821 image rows -> 70 representatives; exact observed skit-ID preservation verified, public CLI re-sketch yields 70 skits.
Next Steps: read task.md and sprint UAT before new work. Sprint close integrates locally to main; no push, tag or version bump. Use git log/status to confirm integration after interruption. Generated data/bluesky-demo is available locally but clean deletes data. Do not rerun unchanged tests or restart planning; await next user task.

## Larger capture — 2026-11-20
Context: owner requested more live data; previous sample remains intact.
Current Task: capture in progress, 600-second/100000-frame bound, output data/bluesky-10min-20261120.jsonl (process session 69255).
Next Steps: await capture completion; prepare into data/bluesky-demo-10min-20261120; inspect report and summary, verifying representative ID preservation. Record results; no code change/test rerun or push needed.

## Larger capture completed — 2026-11-20
Context: ten-minute public capture completed at time limit with 21,976 frames and 20,789 accepted post creates; prior sample preserved.
Current Task: complete (100%). Prepared 4,125 image rows into 125 skits and representatives; exact observed skit-ID preservation passed. ASCII report verified. All four embed kinds observed, including quote_gallery; MIME other observed. attachment_count=11+ remains unobserved.
Next Steps: display with bobp make -vvv bluesky ARGS="report data/bluesky-demo-10min-20261120 --group-by orientation". Dataset and representatives are under ignored data/; clean removes them. No code changes, test reruns, commit or push performed. Await owner direction.

## Single/multiple profile measurement — 2026-11-20
Context: owner requested running a modifier to collapse image-count classes.
Current Task: complete. Core merge ran with data/bluesky-single-multiple.yaml on all 125 retained rows; yielded 92 skits, no skipped inputs. ANY [1] on positive integer image_count means TRUE=single, FALSE=multiple. Other fields unchanged: reply, embed_kind, mime, orientation, alt. This coarsening preserves the exact distinct variant count; weights in this experimental sketch count old representatives, not all 4,125 images.
Next Steps: report 92 and fields. Original demo profile/artifacts remain unchanged; experiment is under ignored data/. For population charts, apply the profile to all normalized image rows in a follow-up implementation if requested.

## Sprint 6 story/design gate — 2026-11-20

Reviewed docs/sprints/USER_STORIES_SPRINT6.md following the owner's original-post correction.
Approved: STORIES OUT=PASS TEST=PASS FAIL=PASS SCOPE=PASS SIZE=PASS DESIGN=PASS;
ARCH BOUND=PASS FLOW=PASS FAIL=PASS USER=PASS DECS=PASS FEAS=PASS.

Implementation guidance: empty baseline percentages should be N/A (0/0); show baseline counts
explicitly and still list regression-only kinds. Label weighted percentage baseline post-frequency
coverage and show distinct-kind percentage with numerator/denominator alongside. Sample locators
must identify copyable source/sample paths and line numbers. Custom-profile multi-match tokens are
set-like, not per-image correlations; explain this. No test-execution or branch-coverage claims.
Next: independent QA/security review and ASCII UAT on original posts; prior image-row UAT is superseded.

## Sprint 6 final user acceptance
Context: one original post per row; profile defines kinds; report/export/coverage belong to core CLI. Four array states across direct and quoted images/galleries use native fields only.
Current Task: complete. Live final default:20789 posts->860 kinds; original representatives reproduce all IDs; coverage all100% no unknowns. Selected sample export and partial weighted coverage verified; locators/fullIDs usable. 279 tests on both Pythons and clean gates pass. UAT COVER/STEPS/FAIL/DATA/EVID=PASS; LESSON WHEN/WHAT/RULE/CAUSE/PLACE=PASS.
Next Steps: retro/launch/local integration; keep captures in data and warn clean removes them. No push/release. No pending user question remains.

## Sprint 6 final checkpoint — supersedes pending work above
Context: original post rows are the regression unit. Generic report/export/coverage live in sketch-tastic; Bluesky only unwraps post-create envelopes. Owner approved split native profile fields and absent-array distinction.
Current Task: complete (100%). Four container groups use present/any/multiple bits; mixed galleries count image entries only. Core and profile reviews, clean gates (279 tests on3.14/3.15, lint,3wheel smokes/build/security scans) and live UAT passed. Final dataset data/bluesky-posts:20789 posts,860 kinds; all representatives100% kind/frequency coverage. Selected sample represents3331 observations (16.0%),1/860 kinds. No pending questions/blockers.
Next Steps: sprint launch/archive/local main integration; confirm git log/status if interrupted. No push, version bump or release. Existing data preserved; clean deletes it. Read task.md before new work; do not rerun unchanged tests or restore the superseded image model.


## Sprint 7 final checkpoint — 2026-11-21
- **Context:** Approved Stories (Gate 1), Architecture (Gate 2), and live Bluesky HTML dashboard UAT (`data/bluesky-posts-aggs/analysis.html`, 20,789 obs / 860 skits, Chromium 0 console errors). Caught and verified fix for full-width Aggregates table and clipped long Min/Max cells.
- **Current Task:** Complete (100%) — UAT and LESSON rubrics passed.
- **Next Steps:** Await next sprint; keep visual viewport checks part of HTML UAT.
