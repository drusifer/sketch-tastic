# Task Board

## Sprint 8: Lean Architecture, Modular Dashboard & Code Hygiene

*   **Goal**: Formalize the domain model (`docs/DOMAIN.md`), untangle circular/private module boundaries and double YAML reads, slim `analysis.py` into a lean dashboard payload builder, decompose the 3,582-line `dashboard.py` into modular static web assets with `node` unit tests, and bring all of `src/` to 0 extended ruff warnings and 0 radon C+ functions while retiring legacy `fid`/`wh`/`fingerprint` internal names.
*   **Tier**: Tier 2 (Tech Debt / Fast-track) · **Total Points**: 8 · **Branch**: `sprint-8`
*   **Source**: `docs/sprints/USER_STORIES_SPRINT8.md` (`STORY-SKT-15`..`18`, `ADR-2026-11-23`) & `docs/DOMAIN.md`
*   **Status**: Complete — launched 2026-11-24; merged locally to `main` (325 tests on Python 3.14 & 3.15, 4 wheel smoke tests, 0 extended ruff / 0 vulture / 0 radon C+ across `src/`, security-scan clean)

### Stage 0: SDLC Gate (Blocker)
- [x] **Task 0.1 (L1):** Verify `docs/SDLC.md` exists and is current; create `sprint-8` branch from `main`. (*Owner: Mouse | Trace: N/A — sprint gate | Verification: `test -f docs/SDLC.md && git branch --show-current`*)

### Phase 1: Shared Internal Boundaries, Single-Pass Loading & Lean Analysis Builder
*Phase goal: Introduce `src/sketchtastic/_io.py`, single-pass ranked sketch loading in `sketch.py`, break the `reporting.py` ↔ `analysis.py` cycle, and slim `analysis.py` into a lean dashboard payload builder (≤ radon B, 0 extended ruff).*
- [x] **Task 1.1 (L3):** Create `src/sketchtastic/_io.py` (`is_number`, `history_dir_for`, `safe_text`, `atomic_write_text`, `atomic_publish_file`), add single-pass `read_sketch_file` / `load_ranked_skits` to `sketch.py`, refactor `reporting.py` to top-level imports & ≤ radon B, and slim `analysis.py` to a lean single-pass dashboard payload builder (`meta`, `fields`, `aggregates`, `weightings`, `time_axes`, `history`, `skits`) using native Python 3.14 `fromisoformat`; update `tests/test_analysis.py` & `tests/test_reporting.py`. (*Owner: Neo | Trace: STORY-SKT-15, STORY-SKT-16 / ADR-2026-11-23 | Verification: `bobp make test ARGS="test_analysis" && bobp make test ARGS="test_reporting" && bobp make lint`*)
- [x] **Task 1.2 (L2):** Run Phase 1 UAT verifying single-pass loading, lean payload contract, error/exit-2 behavior, zero circular/private imports, and `bobp make quality` on `sketch.py`, `_io.py`, `reporting.py`, `analysis.py`. (*Owner: Trin | Trace: STORY-SKT-15 AC1–5, STORY-SKT-16 AC1–4 | Verification: UAT verdict in `agents/CHAT.md`*)
- [x] **Task 1.3 (L2):** Security review of Phase 1 diff (symlink refusal, atomic publication, history directory validation, safe YAML, gitleaks). (*Owner: Switch | Trace: STORY-SKT-15 AC5 / sprint8-design | Verification: `security gate (phase 1): ...` in `agents/CHAT.md`*)
- [x] **Task 1.4 (L2):** Code & architecture review of Phase 1; commit `refactor(core): ...`. (*Owner: Morpheus | Trace: ADR-2026-11-23 | Verification: review verdict in `agents/CHAT.md`*)

### Phase 2: Modular Offline Dashboard Web Assets & Direct JS Unit Tests
*Phase goal: Extract `dashboard.py` CSS/HTML/JS into `src/sketchtastic/assets/dashboard/*`, decompose large JS functions, update `dashboard.py` for the lean payload, and add `node`-backed unit tests for `stats.js`.*
- [x] **Task 2.1 (L3):** Extract `styles.css`, `template.html`, and modular JS (`core.js`, `stats.js`, `charts.js`, `correlations.js`, `sankey.js`, `explorer.js`, `url_state.js`, `app.js`) into `src/sketchtastic/assets/dashboard/`, decompose `initControls`/`renderAggChart`/`renderCorrNetwork`/`renderSankey`/`computeCorrelations`, slim `src/sketchtastic/dashboard.py` to a thin cached assembler, and add direct `node` unit tests for `stats.js` in `tests/test_dashboard.py`. (*Owner: Neo | Trace: STORY-SKT-17 / ADR-2026-11-23 | Verification: `bobp make test ARGS="test_dashboard" && bobp make test ARGS="test_analyze_cli" && bobp make lint`*)
- [x] **Task 2.2 (L2):** Run Phase 2 UAT (offline CSP, XSS/prototype tests, `node` JS stats unit tests, empty sketch, and live Bluesky HTML generation confirming reduced file size and clean rendering). (*Owner: Trin | Trace: STORY-SKT-17 AC1–6 | Verification: UAT verdict in `agents/CHAT.md`*)
- [x] **Task 2.3 (L2):** Security review of Phase 2 diff (fixed asset allowlist, no `</script` sequences, CSP unchanged, XSS & prototype guards, Chart.js SHA-256). (*Owner: Switch | Trace: STORY-SKT-17 AC3 / sprint8-design | Verification: `security gate (phase 2): ...` in `agents/CHAT.md`*)
- [x] **Task 2.4 (L2):** Code & architecture review of Phase 2; commit `refactor(dashboard): ...`. (*Owner: Morpheus | Trace: ADR-2026-11-23 | Verification: review verdict in `agents/CHAT.md`*)

### Phase 3: CLI Merge Engine, Histogram Decomposition & Stale Vocabulary Cleanup
*Phase goal: Bring `cli.py` and `aggregators.py` to 0 extended ruff warnings and 0 radon C+ functions, and retire legacy `fid`/`wh`/`fingerprint` internal identifiers across `src/` and `tests/`.*
- [x] **Task 3.1 (L2):** Refactor `cli.py` (`_FoldOptions`, `_merge_folded_parts`, `_emit_line_warnings`, clean `_show_columns` lambdas, loop var overwrites) and `aggregators.py` (`_log_histogram_bins`, `_fixed_histogram_bins`, `_interpolate_bin_quantile`, `_LOG_BASE`), and rename stale `fid`/`wh`/`fingerprint` internal identifiers across `src/` and `tests/`. (*Owner: Neo | Trace: STORY-SKT-18 | Verification: `bobp make test && bobp make lint && bobp make -vvv quality`*)
- [x] **Task 3.2 (L2):** Run Phase 3 UAT (`docs/sprints/UAT_PLAN_SPRINT8.md`): full test suite, 0 extended ruff / 0 vulture / 0 radon C+ across `src/`, and wheel smoke test verifying `assets/dashboard/*` bundling. (*Owner: Trin | Trace: STORY-SKT-18 AC1–4 | Verification: UAT verdict in `docs/sprints/UAT_PLAN_SPRINT8.md` & `agents/CHAT.md`*)
- [x] **Task 3.3 (L1):** Security review of Phase 3 diff (stream limits, no new deps, `bobp make security-scan`). (*Owner: Switch | Trace: STORY-SKT-18 / sprint8-design | Verification: `security gate (phase 3): ...` in `agents/CHAT.md`*)
- [x] **Task 3.4 (L2):** Code & architecture review of Phase 3; commit `refactor(cli): ...`. (*Owner: Morpheus | Trace: STORY-SKT-18 | Verification: review verdict in `agents/CHAT.md`*)

### Stage 3: Sprint Closeout
- [x] **Task C.1 (L2):** SDLC conformance check (preserve `data/` across `distclean`, run `install`, `lint`, `test`, `test-all` 3.14/3.15, `smoke`, `build`, `security-scan`, `uv lock --check`; verify `assets/dashboard/*` ships in wheel). (*Owner: Tank | Trace: N/A — closeout | Verification: `docs/SDLC.md` section 10 checks pass*)
- [x] **Task C.2 (L2):** Document grooming (`docs/DECISIONS.md` ADR-2026-11-23, `docs/LESSONS.md`, `README.md` check) and sprint chat report. (*Owner: Oracle | Trace: N/A — closeout | Verification: `bobp chat-report --moniker SPRINT_8 ...`*)
- [x] **Task C.3 (L2):** End-to-end user usability testing on live CLI & Bluesky dashboard, UAT rubric & lesson rubric review. (*Owner: Smith | Trace: STORY-SKT-15..18 | Verification: `*user approve` recorded in `agents/CHAT.md`*)
- [x] **Task C.4 (L1):** Sprint retrospective & backlog grooming. (*Owner: Mouse | Trace: N/A — closeout | Verification: Retros posted in `agents/CHAT.md`*)
- [x] **Task C.5 (L1):** Sprint launch announcement and local `--no-ff` merge to `main` (no push/release). (*Owner: Cypher | Trace: N/A — release decision | Verification: Cypher launch in `agents/CHAT.md` & `git log -n 2`*)

---

## Sprint 7: Interactive Sketch Analysis Dashboard

*   **Goal**: Deliver `sketchtastic analyze SKETCH -o REPORT.html` to turn any sketch (and optional history) into a 100% offline, interactive HTML dashboard bundling Chart.js v4.4.9 (MIT) with weighted enum distributions, min/max and numeric mean/median stats, time/run range sliders, skit/sample explorer, and history drift.
*   **Tier**: Tier 1 (Major) · **Total Points**: 8 · **Branch**: `sprint-7`
*   **Source**: `docs/sprints/USER_STORIES_SPRINT7.md` (`STORY-SKT-12`..`14`, `ADR-2026-11-21`)
*   **Status**: Complete — launched 2026-11-21; merged locally to `main` (298 tests on Python 3.14 & 3.15, 4 wheel smoke tests, security scans & live Bluesky dashboard verified)

### Stage 0: SDLC Gate (Blocker)
- [x] **Task 0.1 (L1):** Verify `docs/SDLC.md` exists and is current; create `sprint-7` branch from `main`. (*Owner: Mouse | Trace: N/A — sprint gate | Verification: `test -f docs/SDLC.md && git branch --show-current`*)

### Phase 1: Analysis Data Engine & History Drift Loader
*Phase goal: Compute verified sketch statistics, field distributions/min/max/numeric stats, aggregate rollups, time/run axes, and history drift in `src/sketchtastic/analysis.py`.*
- [x] **Task 1.1 (L3):** Write unit tests (`tests/test_analysis.py`) first and implement `src/sketchtastic/analysis.py` (ranked skits, Pareto thresholds, per-field observation/skit weighted distributions & min/max/numeric mean/median, per-aggregate global & across-skit stats, datetime/run axes, history discovery & run-over-run drift). (*Owner: Neo | Trace: STORY-SKT-13, STORY-SKT-14 / ADR-2026-11-21 | Verification: `bobp make test ARGS=test_analysis && bobp make lint`*)
- [x] **Task 1.2 (L2):** Run Phase 1 UAT against analysis acceptance criteria (empty sketch, numeric/enum fields, aggregates, history drift, malformed inputs). (*Owner: Trin | Trace: STORY-SKT-13 AC1–4, STORY-SKT-14 AC3–4 | Verification: UAT verdict in `agents/CHAT.md`*)
- [x] **Task 1.3 (L1):** Security review of Phase 1 diff (safe YAML loading, bounds, history path handling). (*Owner: Switch | Trace: STORY-SKT-12 AC3 / sprint7-design | Verification: `security gate (phase 1): ...` in `agents/CHAT.md`*)
- [x] **Task 1.4 (L2):** Code & architecture review of Phase 1; commit `feat(analysis): ...`. (*Owner: Morpheus | Trace: ADR-2026-11-21 | Verification: review verdict in `agents/CHAT.md`*)

### Phase 2: Vendored Chart.js Asset & Self-Contained HTML Dashboard Renderer
*Phase goal: Vendor MIT Chart.js v4.4.9 with SHA-256 verification and build the interactive offline HTML dashboard in `src/sketchtastic/dashboard.py`.*
- [x] **Task 2.1 (L3):** Vendor Chart.js v4.4.9 (`src/sketchtastic/assets/chart.umd.min.js`, `CHARTJS_LICENSE.txt`, `CHARTJS_SHA256.txt`), write tests (`tests/test_dashboard.py`) first, and implement `src/sketchtastic/dashboard.py` (strict offline CSP, script-safe JSON escaping, `Map`/safe-DOM interactive JS with dual time/run sliders, weighted enum charts, min/max & mean/median panels, aggregate rollups, skit explorer/sample inspector, and history drift). (*Owner: Neo | Trace: STORY-SKT-12, STORY-SKT-13, STORY-SKT-14 / ADR-2026-11-21 | Verification: `bobp make test ARGS=test_dashboard && bobp make lint`*)
- [x] **Task 2.2 (L2):** Run Phase 2 UAT (offline self-containment, JS syntax check via `node`, XSS breakout resistance, empty sketch, interactive filtering logic). (*Owner: Trin | Trace: STORY-SKT-12 AC1,4,5; STORY-SKT-13 AC1–5; STORY-SKT-14 AC1–3 | Verification: UAT verdict in `agents/CHAT.md`*)
- [x] **Task 2.3 (L2):** Security review of Phase 2 diff (Chart.js SHA-256/license audit, CSP, XSS & prototype-pollution checks, `bobp make security-scan`). (*Owner: Switch | Trace: STORY-SKT-12 AC5 / sprint7-design | Verification: `security gate (phase 2): ...` in `agents/CHAT.md`*)
- [x] **Task 2.4 (L2):** Code & architecture review of Phase 2; commit `feat(dashboard): ...`. (*Owner: Morpheus | Trace: ADR-2026-11-21 | Verification: review verdict in `agents/CHAT.md`*)

### Phase 3: CLI Integration (`sketchtastic analyze`), Docs, Smoke & Live UAT
*Phase goal: Wire `sketchtastic analyze` with atomic no-clobber output, document it, add wheel smoke coverage, and verify live on Bluesky data.*
- [x] **Task 3.1 (L2):** Write CLI tests (`tests/test_analyze_cli.py`) first, add `analyze` subcommand in `src/sketchtastic/reporting.py` (`-o/--output`, `--history`, `--title`, `--force`, atomic no-symlink publish), update `README.md`, `examples/bluesky/README.md`, and `smoke/test_smoke.py`. (*Owner: Neo | Trace: STORY-SKT-12 AC1–3, STORY-SKT-14 AC4–5 | Verification: `bobp make test && bobp make lint`*)
- [x] **Task 3.2 (L2):** Execute Sprint 7 UAT plan (`docs/sprints/UAT_PLAN_SPRINT7.md`) including live Bluesky dataset (`data/bluesky-posts-aggs/posts.sketch.yaml`) and multi-run history sketch. (*Owner: Trin | Trace: STORY-SKT-12..14 | Verification: UAT verdict in `docs/sprints/UAT_PLAN_SPRINT7.md` & `agents/CHAT.md`*)
- [x] **Task 3.3 (L2):** Security review of Phase 3 diff (atomic output & symlink refusal, terminal escaping, full `bobp make security-scan`). (*Owner: Switch | Trace: STORY-SKT-12 AC2–3 / sprint7-design | Verification: `security gate (phase 3): ...` in `agents/CHAT.md`*)
- [x] **Task 3.4 (L2):** Code & architecture review of Phase 3; commit `feat(cli): ...`. (*Owner: Morpheus | Trace: ADR-2026-11-21 | Verification: review verdict in `agents/CHAT.md`*)

### Stage 3: Sprint Closeout
- [x] **Task C.1 (L2):** SDLC conformance check (preserve `data/` across `distclean`, run `install`, `lint`, `test`, `test-all` 3.14/3.15, `smoke`, `build`, `security-scan`; verify `chart.umd.min.js` ships inside wheel). (*Owner: Tank | Trace: N/A — closeout | Verification: `docs/SDLC.md` section 10 checks pass*)
- [x] **Task C.2 (L2):** Document grooming, lesson archiving (`docs/LESSONS.md`), and sprint chat report. (*Owner: Oracle | Trace: N/A — closeout | Verification: `bobp chat-report --moniker SPRINT_7 ...`*)
- [x] **Task C.3 (L2):** End-to-end user usability testing on live Bluesky dashboard & lesson review. (*Owner: Smith | Trace: STORY-SKT-12..14 | Verification: `*user approve` recorded in `agents/CHAT.md`*)
- [x] **Task C.4 (L1):** Sprint retrospective & backlog grooming. (*Owner: Mouse | Trace: N/A — closeout | Verification: Retros posted in `agents/CHAT.md`*)
- [x] **Task C.5 (L1):** Sprint launch announcement and local `--no-ff` merge to `main` (no push/release). (*Owner: Cypher | Trace: N/A — release decision | Verification: Cypher launch in `agents/CHAT.md` & `git log -n 2`*)

---

## Follow-up: Bluesky aggregate summaries (2026-11-20)

- [x] Native profile aggregates for typed image counts/bytes, text bytes, facet features and post times.
- [x] Generic report displays aggregate values, including typed dates; no identity changes.
- [x] 282 tests and lint pass; independent review approved; full capture rebuilt in
  `data/bluesky-posts-aggs` (20,789 posts, 860 skits, original profile ID preserved).

## Sprint 6: Original post kinds and regression coverage

**Status:** Complete — launched 2026-11-20; generic core reporting and original-post demo verified.
**Branch:** `sprint-6`.
**Scope:** STORY-SKT-10..11, Tier 2; docs/sprints/USER_STORIES_SPRINT6.md.

- [x] Phase 1 `*impl` Neo (L3): profile-native post identity, bounded envelope extraction and sample provenance; preserve original records; absent/zero/one/multiple image states.
- [x] Phase 1 `*impl` Neo (L3): generic core CLI report/export/coverage, independent of the Bluesky example; 258 core tests and live UAT passed.
- [x] Phase 1 gates: Trin (L2) 279 tests on both Pythons, Switch (L2) security, Morpheus (L2) code/profile review.
- [x] Close `*uat` Smith (L2): 20,789 posts / 860 kinds, exact representative IDs and weighted coverage; Oracle (L2) docs; Tank (L2) clean SDLC check; retro and Cypher launch.

No recapture, push or package release required. Preserve existing captures during clean checks.

## Sprint 5: Bluesky Image Explorer

**Status:** Complete; 8/8 points, launched 2026-11-19. **Branch:** `sprint-5` (integrated at close).
**Scope:** STORY-SKT-08..09, 8 points, Tier 1. See `docs/sprints/USER_STORIES_SPRINT5.md`.

- [x] Stage 0: SDLC read; main matched origin before branch creation. Existing research notes preserved.
- [x] Phase 0 — Tank (L2): add documented demo make targets and capture dependency; install passed.
- [x] Phase 1 `*impl` — Neo (L2): bounded public capture and provenance; mocked capture tests plus live smoke.
- [x] Phase 1 `*impl` — Neo (L3): image normalization, enum profile, sketch/export pipeline and retained-ID equality.
- [x] Phase 1 `*impl` — Neo (L2): ASCII report and guide, weighted counts and AND filters.
- [x] Phase 1 gates — Trin (L2): 24 demo tests, full 267-test suite; Switch (L2): no blocking findings; Morpheus (L2): approved; Tank (L2): tooling approved.
- [x] Close — Tank (L2): clean SDLC conformance, both supported Pythons, installed wheel, lint and security scans.
- [x] Close — Oracle (L2) documentation, Smith (L2) live UAT, all-persona retro and Cypher (L1) launch.

Execution note: the proposed separate report phase was implemented and reviewed with the pipeline
as one three-task phase, sharing its enum contract. All final code was covered by the same QA,
Switch and Morpheus gates. Live UAT passed: 821 images to 70 representatives, preserving all
70 observed skits. Both supported Pythons pass 267 tests; no package version bump.

No push or release requested. Leave fingerling alone. Prior sprint history follows.

## Sprint 4: Parallel Merge

**Status:** Complete — launched 2026-10-15 (5/5 pts); merged to `main`; no release (mainline)
**Branch:** `sprint-4` (merged and deleted)
**Record:** `agents/chat_archive/CHAT_SPRINT_4.diagram.md`
**Source:** `docs/sprints/USER_STORIES_SPRINT4.md` (STORY-SKT-06..07 + architecture D1-D4) · **Points:** 5 · **Tier:** 2
**Result:** `make profile` parallel 13.54 s (4 cores), `-j 1` 29.55 s; libyaml for all YAML

- [x] **1** `_fold_lines` as the one fold; `-j N`; workers + bounded task queue + output queue (after a pool version and a shared-memory version were measured and dropped). [Neo, owner]
- [x] **2** `make profile`: all cores and `-j 1`, `PROFILE_ARGS`. [Tank]
- [x] **3** libyaml everywhere (`sketchtastic._yaml`); docs for `-j`. [Neo]
- [x] Close: Tank `*devops sdlc-check` · Oracle groom · Smith user test · retro + launch · chat report · merge [All]

Between Sprints 3 and 4 (owner review of Sprint 3): JSONPath via `jsonpath-rfc9535` (no shortcut), fold once then merge (`Sketch.merge`), no FIRST/LAST copies.

## Sprint 3: Faster Merge

**Status:** Complete — launched 2026-10-14 (5/5 pts); merged to `main`; no release (mainline)
**Branch:** `sprint-3` (merged and deleted)
**Record:** `agents/chat_archive/CHAT_SPRINT_3.diagram.md`
**Source:** `docs/sprints/USER_STORIES_SPRINT3.md` (STORY-SKT-04..05 + architecture D1-D5) · **Points:** 5 · **Tier:** 2
**Result:** `make profile` 106.35 s → 40.83 s (2.6x), 180,387 events, byte-identical sketch

### Phase 0: make profile (STORY-SKT-04, D1) — Tank
- [x] **0.1** `profile` target (timed run, sketch hash, cProfile top 25); shared download rule; `clean` removes `build/profile`; SDLC targets table; `build:` commit. [Tank]

### Phase 1: Plain-path fast path (STORY-SKT-05 AC3, D2) — Neo
- [x] **1.1** Equivalence tests vs python-jsonpath first; `_PlainPath`; `make test`; `make profile` (time + hash). [Neo]
- [x] **1.2** UAT + review; `perf:` commit. [Trin, Morpheus]

### Phase 2: Select once, no deep copies (STORY-SKT-05 AC1-AC4, D3-D5) — Neo
- [x] **2.1** Alias test first; `Aggregate.select/fold`, `Sketch.select`, `upsert(selected=)`, `_fold_stream`; FIRST/LAST without deepcopy + alias-free dumper; `make profile`; D5 stop rule. [Neo]
- [x] **2.2** UAT + review; `perf:` commit. [Trin, Morpheus]

### Close
- [x] Tank `*devops sdlc-check` · Oracle groom (DECISIONS: before/after) · Smith user test · retro + launch · chat report · merge [Tank, Oracle, Smith, All]

## Sprint 2: Sort the Show

**Status:** Complete — launched 2026-10-14 (2/2 pts); merged to `main`; no release (mainline)
**Branch:** `sprint-2` (merged and deleted)
**Record:** `agents/chat_archive/CHAT_SPRINT_2.diagram.md`
**Source:** `docs/sprints/USER_STORIES_SPRINT2.md` (STORY-SKT-03 + architecture D1-D3) · **Points:** 2 · **Tier:** 2

### Phase 1: Columns as data (D1) — Neo
- [x] **1.1** Refactor `show` to one column list `(header, value, cell)`; table unchanged, `ShowTests` green unmodified; `refactor(cli)` commit. [Neo]
- [x] **1.2** Trin: `make test` + `make lint` green, no test edits · Morpheus review. [Trin, Morpheus]

### Phase 2: --sort KEY, default COUNT (D2, D3) — Neo
- [x] **2.1** Tests first for AC1-AC8; `--sort` (default `COUNT`), key lookup and exit 2, stable sort; help epilog + README; `feat(cli)!` commit with `BREAKING CHANGE:` footer. [Neo]
- [x] **2.2** Trin UAT against AC1-AC8 · Morpheus review. [Trin, Morpheus]

### Close
- [x] Tank `*devops sdlc-check` · Oracle groom · Smith user test · retro + launch · chat report · merge [Tank, Oracle, Smith, All]


## Sprint 1: Move and Rename

**Status:** Complete — launched 2026-10-14 (5/5 pts); merged to `main`; no release (mainline)
**Branch:** `sprint-1` (merged and deleted)
**Record:** `agents/chat_archive/CHAT_SPRINT_1.diagram.md`

### Stage 0: Import and build environment — Tank
- [x] Import `packages/fingerprint-sampler` from fingerling with history (subtree split, 31 commits).
- [x] Build environment at the root: `pyproject.toml` dev group + ruff, `Makefile`, `uv.lock`, `.python-version`, `.githooks`, CI/publish workflows (manual CI).
- [x] `docs/SDLC.md`, `docs/DECISIONS.md`.

**Source:** `docs/sprints/USER_STORIES_SPRINT1.md` (stories + architecture D1-D3) · **Points:** 5 · **Tier:** 2

### Phase 1: New names (STORY-SKT-01, D1) — Neo
- [x] **1.1** `src/sketchtastic`, pyproject name/scripts/URLs/tagline, `prog` from argv, `--version`; Makefile `CLI`; `uv lock`. [Neo]
- [x] **1.2** UAT + review. [Trin, Morpheus]

### Phase 2: Sketch and skit (STORY-SKT-02, D2) — Neo
- [x] **2.1** Module/class/key/flag/message renames; README and help. [Neo]
- [x] **2.2** UAT + review. [Trin, Morpheus]

### Close
- [x] Tank `*devops sdlc-check` · Oracle groom · Smith user test · retro + launch · chat report · merge [Tank, Oracle, Smith, All]

## Backlog (unscheduled)
- Defense-in-depth hardening (Sprint 8 retro / Switch): scale subnormal floats (`5e-324`) in `aggregators.log_bin_key` & catch `OverflowError` in `as_number`; add dead-worker guard to `tasks.put` in `cli._fold_parallel`.
- Bob Protocol tooling (Sprint 8 retro): run `bobp update` when convenient to sync project from bobp 0.2.0 to 0.3.0.
- Interactive dashboard (`analyze`): optional `--no-samples` flag to omit retained sample payloads for ultra-compact HTML on very large sketches; optional CSV/JSON export of filtered skits from the browser; browser-side multi-field cross-tab heatmap (Sprint 7 retro).
- Bluesky demo: collect a longer observation window to find rare gallery/enum combinations;
  continue to report unobserved values explicitly. No additional implementation required now.
Carried over from fingerling's `task.md`:
- `-o`: owner may revisit (keep or drop).
- In-run duplicate detection if a stream needs it.
- JSON Schema for sketch files; set-to-set (sketch-to-sketch) merge; more aggregate ops (`LEN`, `ABS`).
- **Profile evolution (future sprint, owner 2026-10-15):** updating a sketch's profile, and what adding or removing fields does to existing skits. Revisit the two ids then: the skit id (token values) vs the profile id (a hash of the field specs that guards `merge`); e.g. store the fields in the sketch header instead of a hash, or drop the check.
