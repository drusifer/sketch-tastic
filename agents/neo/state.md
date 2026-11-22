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

## Sprint 6 preparation handoff (2026-11-20)
Context: owner requires original posts per row, and reporting in core. Removed the image
model and demo reporting. New input.py only unwraps bare/v1/v2 create records, deduplicates
DID/rkey creates, counts ignored events, bounds JSONL reads, and yields source line numbers.
Current Task: preparation subtask complete (100%). build(source, output, profile_path=PROFILE)
saves exact profile.yaml, standard posts.sketch.yaml, unchanged representatives.jsonl,
samples.json keyed by full skit ID with source/source_line/representative_line, and summary.json
with source SHA256, counts, scope and optional capture sidecar. Output uses staged publication
and refuses preexisting paths. TDD red observed; targeted 3 pipeline + 4 boundary tests pass.
First boundary run found invalid test-only JSONPath '$.$type'; corrected to $.text and green.
Capture implementation/tests unchanged. Generic reporting/export/coverage delegated separately.
Next Steps: parent runs repository formatter at integration, reviews default profile separately
(its native nested-count expressions currently under investigation), then Trin/Switch/Morpheus
gates. No commit made. Do not repeat these unchanged tests except final integrated verification.

## Sprint 6 core reporting checkpoint — 2026-11-20

Owner steered all generic reporting into sketch-tastic CLI. Implemented reporting.py and cli.py
registration for report/export/coverage; no Bluesky import or dependency changes. report ranks
counts descending with full IDs, weight/cumulative percentages, tokens and original-sample
locators. export selects unique full IDs, validates samples, and publishes original JSON objects
through a same-directory staged file plus exclusive hardlink. coverage requires exact nonnull
profile identity and recomputes regression IDs from bounded strict UTF-8 JSONL; intersection
weights come from baseline counts, not candidate repetition. Empty denominators are N/A.

TDD: tests/test_reporting.py RED at 07:30:01 (missing reporting module), GREEN 11 tests at
07:31:10; expanded 14 contracts GREEN 07:32:01. Shared bobp make format passed 07:32:02.
Contracts cover 90/9/1 weights, duplicates/unknown kinds, profile mismatch/missing identity,
ASCII control escaping, full original exports, symlink/concurrent no-clobber, missing samples,
invalid/zero counts, malformed/NaN/UTF8/oversize lines, empty inputs and row limits.

Next: root independent security/code review and integration tests. Native Bluesky profile is
root-owned and remains under investigation; this generic implementation does not depend on it.
No commits made. Root coordinates shared chat handoff to Trin/Switch/Morpheus.

Independent capture-agent review found non-JSON retained YAML values could raise uncaught
TypeError during export. Added CLI date-value regression: RED 07:32:31, fixed serialization
errors to report skit-context ValueError before publication, GREEN 15 tests 07:32:39. Format
passed 07:32:40. Root independent review/integration remains next; no outstanding known core defect.

## Sprint 6 resumed implementation complete
Context: owner authorized split native image count and absence distinction. Each of images/gallery/media_images/media_gallery has present/any/multiple bits. Present with zero includes empty and video-only gallery; IS_PRESENT is member existence, not schema validation.
Current Task: complete implementation; native profile compiles, six focused tests pass after independent review found and fixed missing outer recordWithMedia guard. First full 278-test/both-Python run passed before final guard regression; final clean run pending.
Next Steps: Trin final conformance tests, existing Switch/Morpheus approvals plus profile re-review, default live UAT, close docs/retro/local merge. Preserve captures; no push/version bump.

## Sprint 6 final checkpoint — supersedes pending work above
Context: original post rows are the regression unit. Generic report/export/coverage live in sketch-tastic; Bluesky only unwraps post-create envelopes. Owner approved split native profile fields and absent-array distinction.
Current Task: complete (100%). Four container groups use present/any/multiple bits; mixed galleries count image entries only. Core and profile reviews, clean gates (279 tests on3.14/3.15, lint,3wheel smokes/build/security scans) and live UAT passed. Final dataset data/bluesky-posts:20789 posts,860 kinds; all representatives100% kind/frequency coverage. Selected sample represents3331 observations (16.0%),1/860 kinds. No pending questions/blockers.
Next Steps: sprint launch/archive/local main integration; confirm git log/status if interrupted. No push, version bump or release. Existing data preserved; clean deletes it. Read task.md before new work; do not rerun unchanged tests or restore the superseded image model.

## Aggregate follow-up complete — 2026-11-20
Context: owner requested aggregates on the shown skit. Added native profile summaries for four typed image-container counts and byte stats, UTF8 text bytes, facet-feature count and UTC post time range. Core report now displays aggregates including date values safely.
Current Task:100% complete. RED tests captured missing aggregates/report output;282 full tests and lint passed; independent Trin/Morpheus review approved. Full capture rebuilt at data/bluesky-posts-aggs:20789 posts,860 skits, unchanged profile_id. Sample be55... retains163posts/images,155435222 image bytes,812 facet features,27306 text bytes.
Next Steps: commit/local integrate reviewed single change; no push/release. Use new aggregate dataset (old datasets intentionally unchanged). Aggregates need full observations, not representative-only rebuild.


## Sprint 7 final checkpoint — 2026-11-21
- **Context:** Implemented `src/sketchtastic/analysis.py`, `src/sketchtastic/dashboard.py`, vendored Chart.js v4.4.9 (`src/sketchtastic/assets/`), `sketchtastic analyze` CLI in `reporting.py`, unit tests (`test_analysis.py`, `test_dashboard.py`, `test_analyze_cli.py`), wheel smoke test, and README docs.
- **Current Task:** Complete (100%) — 298 tests green on Python 3.14 & 3.15, lint clean, zero radon D/F.
- **Next Steps:** Await next sprint assignment from `task.md`.


## `*impl` event_time complete — 2026-11-21
- **Context:** Added optional top-level profile `event_time` (JSONPath) in `profile.schema.json`, `profile.py`, `builtin.yaml`, `sketch.py`, `cli.py`, `analysis.py`, `dashboard.py`, `examples/bluesky/demo.py`, and `README.md`.
- **Current Task:** Complete (100%) — TDD RED confirmed (`test_event_time`), then GREEN (`6/6` new tests, `305/305` full suite, lint & gitleaks clean), merged locally to `main`.
- **Next Steps:** Context is healthy; ready for next user request or push if requested.

## `*impl` correlations & Sankey complete — 2026-11-21
- **Context:** Promoted correlated value clusters, directional Theil's U / symmetric Cramér's V field matrix, redundancy diagnostics (`≡` / `←` badges on All Fields), and 2–3 field Alluvial / Sankey flow explorer into `src/sketchtastic/analysis.py`, `src/sketchtastic/dashboard.py`, `tests/test_analysis.py`, `tests/test_dashboard.py`, and `README.md`.
- **Current Task:** Complete (100%) — TDD RED confirmed (`KeyError: 'correlations'`), GREEN (`310/310` tests incl. `node --check`, CSP, XSS, Chart.js integrity), `make lint`, `make quality` (max radon C(15)), `make security-scan-secrets` (gitleaks clean), Chromium visual verification clean (`consoleMessages: []`), Bluesky dashboard regenerated at `data/bluesky-posts-is-english/analysis.html`.
- **Next Steps:** Commit on `fix/correlations-and-sankey`, local `--no-ff` merge to `main`, delete branch; do not push unless owner asks.

## `*impl` dashboard weightings & URL state capture complete — 2026-11-21
- **Context:** Auto-discovered non-negative additive aggregate weightings (`SUM`, `AVG.sum`, `COUNT`, non-negative `VALUE`) in `src/sketchtastic/analysis.py`, optional `--weight KEY` CLI flag in `src/sketchtastic/reporting.py`, live **Weight by** selector re-weighting KPIs, Pareto, field distributions, correlations, Sankey, and skit explorer in `src/sketchtastic/dashboard.py`, plus full URL hash state persistence (`readUrlState`/`syncUrlState`/`hashchange`) and **Copy View Link** header action.
- **Current Task:** Complete (100%) — TDD RED confirmed (`KeyError: 'weightings'`, `TypeError: default_weight`), GREEN (`312/312` tests incl. `node --check`, CSP, XSS), `make lint`, `make quality` (max radon C(18)), `make security-scan-secrets` (gitleaks clean), Chromium visual verification passed for both default and `#w=images_bytes&f=is_english:TRUE&ct=clusters` views (`consoleMessages: []`).
- **Next Steps:** Commit on `fix/dashboard-weightings`, local `--no-ff` merge to `main`, delete branch; do not push unless owner asks.

## `*impl` per-event HISTOGRAM aggregator complete — 2026-11-21
- **Context:** Added mergeable per-event `HISTOGRAM` aggregator (`mode: "log"` sparse log-decimal 1-1.5-2-3-5-7 bins and `mode: "fixed"` explicit strictly-increasing `buckets: [...]`) across `profile.schema.json`, `aggregators.py`, `analysis.py`, `dashboard.py`, `examples/bluesky/profile.yaml`, and `README.md`. Live dashboard merges per-skit histograms across any filter slice and displays interpolated p50/p90/p95/p99 badges + cumulative % curve (`#av=events`).
- **Current Task:** Complete (100%) — TDD RED confirmed on `test_aggregators`, GREEN (`317/317` tests incl. `node --check`, CSP, XSS), `make lint`, `make quality` (max radon C(18)), `make security-scan-secrets` (gitleaks clean). Rebuilt Bluesky dataset with histograms at `data/bluesky-posts-histograms/` and verified visually in Chromium.
- **Next Steps:** Commit on `fix/histogram-aggregator`, local `--no-ff` merge to `main`, delete branch; do not push unless owner asks.

## Bluesky `is_multi_lang` update complete — 2026-11-21
- **Context:** Replaced `is_english` with `is_multi_lang` (`path: "$.langs[1]"`, `modifier: IS_PRESENT`, true iff `langs` array has size > 1) in `examples/bluesky/profile.yaml`, `examples/bluesky/README.md`, and `tests/test_bluesky_profile.py`. Rebuilt Bluesky capture into `data/bluesky-posts-multi-lang/` and generated `analysis.html`.
- **Current Task:** Complete (100%) — `317/317` tests green, lint clean.
- **Next Steps:** Commit on `fix/bluesky-is-multi-lang`, local `--no-ff` merge to `main`, delete branch; await user direction on push.

## CLI command renamed to `sketch` — 2026-11-21
- **Context:** Renamed installed CLI script from `sketchtastic` / `skt` to `sketch` only in `pyproject.toml`, `Makefile`, `src/sketchtastic/{cli,reporting,dashboard}.py`, `smoke/test_smoke.py`, `tests/{test_cli,test_analyze_cli}.py`, `README.md`, `examples/`, and `docs/SDLC.md` (distribution `sketch-tastic` and Python package `sketchtastic` unchanged).
- **Current Task:** Complete (100%) — `make install`, `make lint`, `make test` (317/317), `make smoke` (wheel build + installed `sketch` + README Quickstart), `make run ARGS="--version"`, and `gitleaks` passed.
- **Next Steps:** Commit on `fix/cli-command-sketch`, local `--no-ff` merge to `main`, delete branch; await user direction on push.

## `*impl` streaming line-by-line + `--max-events` / `--max-seconds` complete — 2026-11-22
- **Context:** Added immediate line-by-line streaming ingestion on stdin (`-`) and `--max-events N` / `--max-seconds S` stop limits in `src/sketchtastic/cli.py` (using `select.select` + raw `os.read` on non-seekable pipes so idle pauses still exit cleanly on deadline, without eager 5,001-line buffering), plus `--output -` stdout streaming in `examples/bluesky/capture.py`, tests in `tests/test_cli.py` and `tests/test_bluesky_capture.py`, and docs in `README.md`.
- **Current Task:** Complete (100%) — TDD RED confirmed, GREEN (`322/322` tests including live open-pipe tests), `make lint`, `make quality` (no radon D/E/F), and `gitleaks` passed.
- **Next Steps:** Commit on `fix/streaming-limits`, local `--no-ff` merge to `main`, delete branch; await user direction on push.
