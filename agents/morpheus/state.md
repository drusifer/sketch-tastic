# Agent State

## Context
### 2026-11-24 — One report: dashboard (owner, DRY)
- Removed `sketch report` (ADR-2026-11-24-c) and `sketch coverage` (ADR-2026-11-24-d). Coverage now `analyze --regression FILE -p PROFILE` via new `sketchtastic.coverage` (streamed corpus, per-skit covered flag, unknown kinds, per-run own/cumulative kind+weighted coverage, new uncovered kinds per run; runs under other profile_id not comparable; lists capped 200). JS coverage.js card + Coverage filter (URL `cv`), explorer badges; shared tokenSummary/fillRows hoisted to core.js. Demo: data/cov-demo.html (2 runs, 116/349 kinds, 99.34% weighted).
- Open owner question: `sketch show` is still a second terminal kind table.
### 2026-11-24 — Streaming-input diagnosis (owner escalation)
- Owner: prepare/capture batching unacceptable. Root cause: examples/bluesky built a parallel ingest path beside core `sketch merge` (streams stdin as events arrive, back-pressure, history, --max-seconds; commit 9fa597c). capture() staged to temp then linked (fixed 2026-11-24: streams + flushes, sidecar last, no default limit). prepare (demo.py build) duplicates merge: own reader, unbounded `seen` dedup, direct Sketch.upsert loop, staged publish; extras = unwrap/dedup (already in capture --unwrap-posts, bounded), representatives (core `sketch export`), samples.json line locators, summary.json.
- DECIDED (owner: 'only 1, DRY'): unwrap filter chosen; prepare + capture --unwrap-posts removed. ADR-2026-11-24-b, DOMAIN 'Ingestion: one streaming path' invariants + Stream Filter term, LESSONS entry, SDLC/README/example README updated. Make: `bluesky INPUT= SKETCH=`, `bluesky-live SKETCH= ARGS=`. Follow-up backlog: persist producer provenance in sketch for live pipes.
- (superseded) Proposal: retire prepare; one pipeline `capture --output - | <streaming unwrap filter> | sketch merge -p profile -s sketch -`. Alternative: keep capture --unwrap-posts and drop separate filter. Existing 30-min capture (data/bluesky-30min-20261124.jsonl, raw envelopes) needs the unwrap filter or recapture.
### Sprint 9 Phase 1 inspection architecture review
- Independent review of structured_views changes approved: canonical keys separate equality from labels; every changed filter producer passes those keys; Python canonical array ordering is preserved by JS serialization, with no array sorting mismatch. Numeric/boolean classifiers exclude arrays and chart lengths operate on labels.
- Trin39 targeted tests and Switch inspection gate passed. This approval excludes reviewer's own structured-core implementation; combine with root/planning review and full integration checks before commit.
- Nonblocking inherited follow-up: structural correlation [field, tokenKey] IDs and URL field/token pair encoding would fix '=' / ':' field-name delimiter collisions. See agents/trin/structured_views_review.md.
### Sprint 9 structured-token revision (supersedes delimiter design)
- Owner requests no compatibility and recapture: version1 only. DEFAULT/REGSUB/TRUNC no match omitted, null None; DEFAULT nonnull scalars existing strings, native arrays recursive canonical sets. Multi-matches dedup to scalar at unique cardinality1 else list; direct arrays stay arrays. Boolean modifiers keep explicit missing outputs.
- Identity hashes ordered key/value pairs. Inspection canonical keys distinguish absent/null/literal strings/arrays; exact-set filtering retained. Presence derivation now handles all untyped shapes; scalar/null/omitted IS_NULL and predicate/substitution transforms safe; array remaps conservative due direct-array vs multiselect ambiguity.
- Structured-core and structured-views owners consulted; no compatibility path. Three phases: token core/views, core derivation, CLI/history.
### Sprint 9 architecture
- Source/target profiles plus a fresh output path; conservative proofs for unchanged/drop/reorder/rename, untyped DEFAULT collapses and typed temporal coarsening. Reject ambiguous NULL/comma/type information loss.
- Validate raw retained state before defaults; same aggregate/sequence/event-time specs. Preserve main and all available history independently; provenance survives merges. Reject heterogeneous MIN/MAX collisions.
- Staged no-overwrite publication, main last; handled failures clean only operation-owned output. No portable multi-path crash atomicity. FIRST/LAST remain matching retained samples, not guaranteed chronological originals.
### 2026-11-24 — Enum-set display advice
- User asked whether tags/features should be unnested as enum sets. Profile selects facet_types through $.facets[*].features[*]['$type']; README documents multi-match tokens as deduplicated, sorted, joined sets.
- Recommendation (advice only): expose per-member weighted post counts and membership filtering, preserving full combinations for skit identity and an optional combination view. Deduplicate each member within each post; percentages may sum above 100%. Raw hashtag strings are open vocabulary, unlike feature-type categories. Current profile has no tags field; clarify exact field when implementing.
### Recent Decisions
- 2026-11-23: Sprint 8 Phase 3 Code & Architecture Review **PASSED** and committed on `sprint-8`. Handed off to Tank for Stage 3 closeout (`*devops sdlc-check`).

## Current Task
**Final Sprint 9 code/architecture review:** APPROVED (100%) for phase1 core and phases2/3 after Trin/Switch gates; separate views review approved. Final helper extraction and CLI token cells reviewed. All364/lint/quality tests clear; no blocking findings.
**Latest:** Revised three-phase plan approved (100%); PLAN all PASS. Structured core/views production implementation may proceed after red tests. Earlier two-phase and format0 approvals superseded.
**Latest:** Revised structured architecture ready for Smith Gate 2; prior format0 plan superseded.
**Sprint 9 latest:** Plan approved (100%). PLAN SIZE/GATE/VERIF/ALIGN/OWNER/LEVEL all PASS. Neo may start Phase 1 after recorded failing tests.
**Sprint 9:** Architecture written and self-reviewed (100%), pending Smith Gate 2. Previous consultation/Sprint 8 entries below are historical.
**Latest consultation:** Enum-set recommendation complete (100%); no implementation or tests requested/performed. Sprint status below is historical.
**Status:** All 3 coding phases reviewed and committed; handed off to Tank (`@Tank *devops sdlc-check`).
**Assigned to:** Tank (`*devops`)
**Started:** 2026-11-23

### Progress
- [x] Phase 1, 2, 3 code & architecture reviews passed & committed

## Next Steps
Streaming ingestion change implemented and arch/domain reviewed (2026-11-24). Uncommitted; owner decides commit. Backlog: live-pipe provenance in sketch.
Root may commit the three reviewed phase slices with Conventional Commits, excluding preexisting capture/profile edits. Then Tank SDLC closeout, Oracle docs/report, Smith user acceptance, retro and Cypher launch. No push/tag/package bump authorized.
Smith/Switch revised gates, Mouse revised three-phase board, Morpheus approval; then structured implementation. Tank must record owner-overridden format-version convention during closeout.
Review Phase 1 implementation after Trin/Switch gates, then Phase 2. Keep original/target profile contracts, exact NULL presence rule and strict aggregate validation aligned with reviewed architecture.
Smith Gate 2, Switch security design gate, Mouse two-phase task plan, then Morpheus plan review. Plan core collapse tests first, then CLI/history bundle tests. Do not touch preexisting capture/profile edits.
For a requested enum-set implementation, first confirm which tags/features UI fields are intended, inspect token encoding and dashboard classification through VIA, and define explicit set metadata rather than guessing from delimiters. Preserve post counts and skit identity.
### Immediate Next Action
Post Morpheus's Sprint 8 retrospective during Stage 3 closeout.

---
*Last updated: 2026-11-23T23:59:30-05:00*
