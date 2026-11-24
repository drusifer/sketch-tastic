# UAT Plan: Sprint 9 Structured Tokens and Sketch Derivation

- **Stories / criteria:** SKT-19/20/21 in `docs/sprints/USER_STORIES_SPRINT9.md`.
- **Environment and build:** Local `sprint-9`, Python 3.14+ virtualenv; version-1 sketch format.
- **Date / tester:** 2026-11-24 / Trin (independent review), Smith (runtime closeout pending).
- **Entry conditions:** Revised planning gates approved; test-first failures recorded before
  implementation; no backward compatibility per owner direction.
- **Exit conditions:** Scenarios pass, required lint/full-suite/security gates pass, reported
  defects resolved, and Smith records runtime CLI acceptance. No user capture data is modified.

**Final phase evidence:** 2026-11-24 01:04:50, root's full suite passed **364 tests** after the
validation-helper cleanup and final `show` token-cell regression fix; lint passed. Quality at
01:03:15 reported 0 extended ruff, 0 vulture and 0 radon C+ results. `derive --help` executed
at 01:03:46. Final CLI display diff independently reviewed: omitted/null/literal/array cells
are distinct and terminal-safe. Earlier 363-test references below record intermediate evidence.

## Scenarios

### UAT-S9-01: Preserve structured-token distinctions

- **Linked criterion:** SKT-21 AC1–4.
- **Preconditions and data:** Synthetic events with absent values, explicit null, literal NULL,
  comma strings, direct empty/singleton/nested arrays, repeated wildcard matches and typed invalid values.
- **Steps:** `bobp make test ARGS=test_model`; `bobp make test ARGS=test_sketch`;
  `bobp make test ARGS=test_types`.
- **Expected observable outcome:** Omitted value-producing keys, native null and canonical set
  arrays remain distinct; duplicate matches do not split identities; keyed hash and round trips work.
- **Actual outcome:** Focused core checks and root's full 363-test suite passed. Independent
  review confirmed the keyed hash, nested canonical arrays, missing/null modifiers, defensive
  token copies and version1-only reader align with the contract.
- **Verdict:** PASS; final 364-test cleanup regression run passed.
- **Evidence / issue:** Root full-suite report (363 tests), structured-core focused checks.

### UAT-S9-02: Derive exact coarser population statistics

- **Linked criterion:** SKT-19 AC1/2/5/6.
- **Preconditions and data:** `tests/test_derive.py` synthetic multi-skit populations; SUM,
  COUNT, MIN/MAX, AVG, HISTOGRAM; original samples removable without changing derivation.
- **Steps:** `bobp make test ARGS=test_derive`.
- **Expected observable outcome:** Drop/reorder/rename, presence, scalar predicates and temporal
  coarsening match direct target-profile folding; counts/shares/statistics preserved and skits do
  not increase. Source mappings unchanged, samples remain representative.
- **Actual outcome:** Root reports 12 focused derivation tests and full 363-test suite passed.
  Assertions compare target IDs, aggregate states, shares, totals and source immutability.
  Actual Make-driven fixture derived 5 skits/5 observations to 2 skits/5 observations.
- **Verdict:** PASS; final 364-test cleanup regression run passed.
- **Evidence / issue:** `test_drop_reorder_rename_and_merge_preserve_population_statistics`,
  presence/null/string/time-coarsening tests.

### UAT-S9-03: Refuse refinements and malformed retained data

- **Linked criterion:** SKT-19 AC3/4; SKT-20 AC3/6.
- **Preconditions and data:** Unsupported profiles and edited synthetic sketch state only.
- **Steps:** `bobp make test ARGS=test_derive`; `bobp make test ARGS=test_derive_cli`.
- **Expected observable outcome:** Added distinctions, unsupported array remaps, changed
  aggregates/sequence/event-time, missing required modifier tokens, invalid state/bin keys,
  mismatched IDs/profile and corrupt sequence headers fail without final outputs.
- **Actual outcome:** All four review findings fixed and independently inspected. Added cases
  reject omitted/invalid predicate tokens, invalid histogram bins and invalid sequence/last-run
  headers. Focused derive12 and CLI8 plus full363 tests passed.
- **Verdict:** PASS; final 364-test cleanup regression run passed.
- **Evidence / issue:** QA-S9-01 required modifier token keys/domain; QA-S9-02 invalid histogram
  keys; QA-S9-03 retained sequence-header integrity. All reported to implementation owner.

### UAT-S9-04: Preserve available history and continue merging

- **Linked criterion:** SKT-20 AC2/4/6.
- **Preconditions and data:** `DeriveCliTests` builds two isolated merge runs, with sequence mark.
- **Steps:** `bobp make test ARGS=test_derive_cli`.
- **Expected observable outcome:** Same run filenames/IDs/times/counts, target profile and output
  sketch references, provenance, sequence mark and last_run; duplicate replay is dropped; new
  event increments counts. No-history input succeeds without inventing runs.
- **Actual outcome:** Reviewed end-to-end test executes merge, derive, show, report, analyze and
  subsequent duplicate/new-event merges. CLI8 and full363 pass after fixture serialization fix.
  Actual Make-driven fixture preserves 1 history run and all 5 observations; source unchanged.
- **Verdict:** PASS; final 364-test cleanup regression run passed.
- **Evidence / issue:** `test_history_provenance_counts_and_continued_merge`,
  `test_no_history_is_supported_and_does_not_invent_runs`.

### UAT-S9-05: Refuse clobbering and roll back handled publication failures

- **Linked criterion:** SKT-20 AC1/3; SKT-19 AC6.
- **Preconditions and data:** Temporary output files/directories, symlinks, bad history and
  injected write/link failures; no real captures.
- **Steps:** `bobp make test ARGS=test_derive_cli`.
- **Expected observable outcome:** Existing output/history, source aliases and symlinks fail;
  bad history/staging failure publishes nothing; a competing output survives rollback; only
  operation-owned links/directories are removed.
- **Actual outcome:** Source read-only paths, staging, exclusive links and inode-aware cleanup
  inspected. CLI8/full363 tests pass, covering competing main output and staging failure.
- **Verdict:** PASS; final 364-test cleanup regression run passed.
- **Evidence / issue:** Existing-output, bad-history, symlink-history, staging-failure and
  publication-race tests in `test_derive_cli.py`.

### UAT-S9-06: Inspect structured values without collisions

- **Linked criterion:** SKT-21 AC5.
- **Preconditions and data:** Structured-value analysis/dashboard fixtures with missing/null,
  literal strings, repeated arrays and markup-looking token values.
- **Steps:** `bobp make test ARGS=test_analysis`; `bobp make test ARGS=test_dashboard`;
  `bobp make test ARGS=test_reporting`; `bobp make test ARGS=test_analyze_cli`.
- **Expected observable outcome:** Whole-set distribution/filter identity is stable and
  collision-free; safe display labels; no null-length errors or array-object-identity grouping;
  report/export/coverage remain usable.
- **Actual outcome:** Independent inspection review reports dashboard12, analysis10 and
  reporting17 passed; root full363 passes. Exact-set value-key producers/consumers inspected by
  a separate agent; no member-count interpretation is introduced.
- **Verdict:** PASS; final 364-test cleanup regression run passed.
- **Evidence / issue:** Canonical token-key/label and exact-set chart/filter regression tests.

### UAT-S9-07: Explain format rejection and recovery

- **Linked criterion:** SKT-21 AC6; SKT-20 AC5.
- **Preconditions and data:** Version-0 synthetic fixture; existing output path; implemented help/docs.
- **Steps:** `bobp make run ARGS="derive --help"`; format-rejection tests; existing-output CLI test.
- **Expected observable outcome:** Clear version1-only recapture/rebuild explanation; help
  documents supported collapse/history/no-overwrite contract and no nonexistent override flag.
- **Actual outcome:** Version rejection tests pass; nonexistent --force hint corrected and
  regression checked. README format/version and example IDs match the new representation.
  Root executed `derive --help` at 01:03:46; final full364/lint checks passed after cleanup.
- **Verdict:** PASS.
- **Evidence / issue:** QA-S9-04 misleading output-exists recovery hint.

## Results and Handoff

- **Passed / failed / blocked:** 7 PASS, 0 failures, 0 blocked.
- **Open issues and impact:** None. QA-S9-01..04 fixed/re-reviewed; cohesive helper cleanup and
  final show-cell fix inspected, all364 tests/lint pass and quality has no reported findings.
- **Overall verdict:** PASS for phase acceptance. Tank SDLC closeout and final Smith user
  acceptance remain sprint-close responsibilities.
- **Handoff evidence:** Root full363/lint pass; secret scan128 commits/no leaks. Actual UAT
  files under `build/sprint9-uat`: source5skits/5obs -> v2 2skits/5obs, 1history, source unchanged.
  Codex sessions are not covered by bobp's Claude trace annotator; no numeric trace score claimed.

## Sprint-close runtime acceptance (Smith, 2026-11-24 16:05)

Real public data: `data/bluesky-30min-20261124.sketch.yaml` (207,882 posts, 349 skits, 1 run),
built by the Phase 4 streaming pipeline. Scratch outputs under ignored `data/uat-s9/`.

| # | Command (abridged) | Expected | Actual | Verdict |
|---|---|---|---|---|
| R1 | `sketch derive --help` | usage shows SOURCE, `--source-profile`, `-p`, `-o` | as expected | PASS |
| R2 | `derive ... -p coarse.yaml` (drops `labels`, `tags`) | fewer skits, all observations, history kept | 349 -> 186 skits; 207,882 observations; 1 run; source unchanged | PASS |
| R3 | `derive ... -p finer.yaml` (adds `lang0`) | refused, nothing written | exit 2, "cannot prove a collapsing transform"; no output | PASS |
| R4 | `derive` onto an existing output | refused, nothing changed | exit 2, "Output already exists" | PASS |
| R5 | `show coarse.sketch.yaml` | readable table, event-time first/last seen | 186 rows; top kind 44.1% | PASS |
| R6 | 20 s live `capture \| unwrap \| sketch merge -p coarse.yaml -s coarse...` | merge continues under target profile, new run file | 920 posts, 0 new / 61 updated skits, run `261124-0002` | PASS |
| R7 | `export` + `analyze --regression ... -p coarse.yaml` | dashboard with coverage and 2 runs | 208,802 observations, 186 skits, 2 runs; 186/186 covered | PASS |

Phase 4 (owner-directed) evidence: `capture` streamed a 30-minute window (216,583 frames) to disk
while readable; `make bluesky` turned it into 207,882 posts / 349 skits at ~45 MB RSS per stage;
a malformed line fails the pipeline with exit 2 and keeps the partial sketch; spaces in paths work.

Observation (not a defect): some posts carry `createdAt` years in the past or hours in the future
(e.g. 2022-09-28, 2026-11-25), so event-time first/last seen spans client clock skew.

**Smith acceptance:** ACCEPTED. Commands are discoverable from `--help`, refusals say what to do
next and publish nothing, and the derived sketch keeps merging live data.
