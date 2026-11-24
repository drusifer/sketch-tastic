# Sprint 8 User Stories & Architecture: Lean Refactor, Modular Dashboard & Code Hygiene

*   **Tier**: Tier 2 (Tech Debt / Maintenance — combined Story + Architecture)
*   **Planning Size**: 8 points
*   **Branch**: `sprint-8`
*   **Source**: Owner request 2026-11-23 (`$bob-protocol init time for a tech debt sprint` → Option 1 audit → "yes and I agree with keep lean /sprint plan & impl sprint 8")
*   **Status**: Approved (Smith STORIES/ARCH/DOMAIN + Switch design gate passed)

## Goal

Eliminate the structural code smells accumulated during rapid feature delivery: formalize the domain model, break circular/private cross-module coupling and double YAML parsing, slim `analysis.py` into a lean dashboard payload builder (removing ~600 lines of unused Python math that JS already computes live), decompose the 3,582-line `dashboard.py` string monolith into real modular web assets with `node`-backed unit tests, simplify the CLI merge pipeline and histogram helpers, and retire legacy `fid`/`wh`/`fingerprint` internal names. All existing CLI behavior, output contracts, offline single-file HTML dashboard functionality, and merge performance remain intact.

## Assumptions made for the owner

1. Because `analyze_sketch` is not part of `sketchtastic.__all__` and the owner confirmed **"keep lean"**, `analyze_sketch` returns the lean view-model payload required by the offline dashboard (`meta`, `fields` keys, `aggregates` metadata, `weightings`, `time_axes`, `history`, `skits`) rather than duplicating client-side statistics in Python.
2. Dashboard JS/CSS/HTML files live under `src/sketchtastic/assets/dashboard/` as static package data concatenated into the single inline `<script>` / `<style>` at render time — preserving 100% offline single-file output, strict CSP, zero external network calls, and zero frontend build toolchain.
3. No PyPI runtime dependencies are added; existing `PyYAML`, `jsonpath-rfc9535`, and `jsonschema` remain the only runtime dependencies.

---

## STORY-SKT-15: Formalize Domain Model & Untangle Module Boundaries
**Points:** 2 · **Owner:** Neo (with Morpheus/Cypher `docs/DOMAIN.md`)

**As a** maintainer of `sketch-tastic`,
**I want** a documented domain model and clean, acyclic internal boundaries for sketch loading, history paths, and atomic file publication,
**so that** `reporting.py`, `analysis.py`, `sketch.py`, and `cli.py` do not reach into each other's private functions, hide lazy imports, or parse sketch YAML files twice.

### Acceptance Criteria
1. `docs/DOMAIN.md` documents the three bounded contexts, ubiquitous language, aggregate roots, and invariants and passes the DOMAIN check.
2. Zero modules in `src/sketchtastic/` import `_`-prefixed private symbols from another module, and zero lazy function-body imports (`PLC0415`) exist in `src/sketchtastic/`.
3. `analyze_sketch` and `_load_run_file` each parse each YAML file only once (no duplicate `_read_set_file` + `Sketch.load` reads).
4. Shared internal helpers exist in one place for: numeric guard (`is_number`), `<sketch>.history` path resolution, validated ranked sketch loading, and atomic no-symlink file publication (reused by `sketch.py` and `reporting.py`).
5. Failure behavior is preserved: malformed sketches, mismatched `profile_id`, symlink targets, and existing files without `--force` fail with the same error classes and CLI exit code `2` without creating or clobbering output.

---

## STORY-SKT-16: Lean Analysis Payload Builder
**Points:** 2 · **Owner:** Neo

**As a** maintainer and dashboard user,
**I want** `src/sketchtastic/analysis.py` to build only the data the dashboard actually consumes (ranked skits, field/aggregate descriptors, additive weightings, time/run axes, and `.history/` drift) without duplicating client-side statistical engines,
**so that** generated HTML files are smaller, worst-case complexity hotspots disappear, and there is a single source of truth for interactive dashboard statistics.

### Acceptance Criteria
1. `analyze_sketch()` produces the lean payload (`meta`, `fields`, `aggregates`, `weightings`, `time_axes`, `history`, `skits`) without unused precomputed `ablation`, `correlations`, `concentration`, or per-field/per-aggregate dashboard stat blobs; generated Bluesky HTML payload size decreases while all interactive views render identically.
2. `analysis.py` reuses Python 3.14 native `datetime.fromisoformat` / `DatetimeType` without manual `"Z"` string-mangling workarounds.
3. Every function in `src/sketchtastic/analysis.py` has radon cyclomatic complexity **≤ 10 (Grade A or B)** and **0 extended ruff warnings** (`bobp make quality`).
4. Invalid sketches, missing explicit `--history` directories, and unknown `--weight` keys continue to raise `SketchError` / `ValueError` (CLI exit `2`); corrupted files inside a history directory are skipped with warnings as before.

---

## STORY-SKT-17: Modular Dashboard Web Assets & Direct JS Unit Tests
**Points:** 2 · **Owner:** Neo (verified by Trin & Smith)

**As a** maintainer of the offline HTML dashboard,
**I want** the CSS, HTML template, and JS modules extracted from `src/sketchtastic/dashboard.py` into real package-data files under `src/sketchtastic/assets/dashboard/`, with long JS functions decomposed and pure JS statistical functions directly unit-tested via `node`,
**so that** frontend code is navigable, maintainable, testable as the single source of truth, and still ships as a 100% offline single-file HTML report inside the wheel.

### Acceptance Criteria
1. `src/sketchtastic/dashboard.py` is reduced to a thin renderer (~100 lines or fewer) loading `styles.css`, `template.html`, and ordered `.js` modules from `src/sketchtastic/assets/dashboard/` via `importlib.resources.files`.
2. Large JS monolith functions (`initControls`, `renderAggChart`, `renderCorrNetwork`, `renderSankey`, `computeCorrelations`) are decomposed into focused, readable helpers.
3. Generated HTML retains strict offline CSP (`default-src 'none'`, `connect-src 'none'`), script-safe JSON escaping, prototype-safe DOM/Map usage, vendored Chart.js v4.4.9 SHA-256 verification, and zero external requests.
4. `tests/test_dashboard.py` runs `node` unit tests directly against the modular JS stats (`weightedMedian`, `plainMedian`, `computeFields` boolean/numeric/enum, `computeAblation`, `computeCorrelations`, `mergeHistStates` & `expandHistogram` log/fixed quantiles, and weighted re-computation), plus syntax validation and XSS/prototype tests.
5. `bobp make smoke` proves the built wheel bundles `assets/dashboard/*` and renders a valid offline HTML dashboard from an installed wheel with zero network access; live Bluesky dashboard generation succeeds cleanly.
6. Failure behavior is preserved: empty sketches render cleanly without JS errors, and XSS/prototype payloads are escaped before embedding.

---

## STORY-SKT-18: CLI Merge Pipeline, Histogram Helpers & Stale Vocabulary Cleanup
**Points:** 2 · **Owner:** Neo

**As a** maintainer of `sketch-tastic`,
**I want** the CLI merge pipeline and histogram helpers decomposed below radon Grade C, all extended ruff warnings in `src/` eliminated, and legacy `fid`/`wh`/`fingerprint` internal names replaced with `skit`/`sketch` vocabulary,
**so that** the entire `src/` package meets a clean static quality bar (`0` extended ruff findings, `0` radon C+ functions) with zero performance or behavioral regression.

### Acceptance Criteria
1. `bobp make quality` reports **0 extended ruff errors**, **0 vulture dead-code hits**, and **0 radon Grade C/D/E/F functions** across all of `src/`.
2. `_fold_stream`, `_fold_lines`, `_fold_parallel`, `_show_columns`, `histogram_bins`, `histogram_quantiles`, `export_samples`, and `coverage` are cleanly factored with no parameter clumps (`PLR0913`), no unused lambda arguments (`ARG005`), and no loop-variable overwrites (`PLW2901`).
3. Internal stale names `fid` (in `src/` and `tests/`) and `wh`/`fingerprint*` internal test identifiers (Sprint 1 retro backlog) are renamed to `sid`/`skit`/`sketch` vocabulary without altering any public API, CLI flag, YAML key, or error contract.
4. All unit tests, Python 3.14 & 3.15 `test-all`, wheel `smoke`, `lint`, `security-scan`, and `profile` (same deterministic `-j 1` sketch SHA-256 and comparable wall time) pass with zero regressions.

---

## Out of Scope
- New dashboard features (`--no-samples`, browser CSV/JSON export, cross-tab heatmap — remain in backlog).
- Adding new PyPI runtime dependencies or vendoring new JS libraries (no `numpy`/`scipy`/`chartjs-chart-sankey`).
- Profile evolution / schema version changes (`version: 0` stays unchanged).
- Package version bump, git push, or PyPI release.

## Open Questions
None — owner confirmed "keep lean" and full Tier 2 Sprint 8 scope.

---

# Sprint 8 Architecture & Design (Morpheus)

*   **Status**: Approved (Smith STORIES/ARCH/DOMAIN + Switch design gate passed)
*   **Author**: Morpheus
*   **Last Updated**: 2026-11-23
*   **Scope**: Sprint 8 Tier 2 Refactoring Architecture

## 1. Executive Summary & System Overview

Sprint 8 aligns the physical module structure with the three bounded contexts in `docs/DOMAIN.md` without changing any public CLI or library contract (`sketchtastic.__all__` and all CLI subcommands/flags/exit codes stay identical). The single biggest structural win is removing ~600 lines of dead Python statistical duplication in `analysis.py` and extracting `dashboard.py`'s inline web assets into real static files under `src/sketchtastic/assets/dashboard/`.

## 2. System Context & Boundaries

- **Trust boundary:** Local CLI reading untrusted JSONL streams, YAML profiles/sketches, and writing atomic YAML/JSONL/HTML files. Generated HTML runs offline inside a local browser under a strict CSP with zero external network access.
- **No external services or new network surfaces** are introduced.

## 3. Component Architecture

| Component | Responsibility | Inputs | Outputs |
|---|---|---|---|
| `src/sketchtastic/_io.py` *(new internal)* | Shared low-level primitives: `is_number()`, `history_dir_for()`, `atomic_write_text()`, `atomic_publish_file()` (symlink-safe, optional `--force`), `safe_text()` | Paths, text/writer callbacks, values | Atomically written files, normalized paths, safe strings |
| `src/sketchtastic/sketch.py` | `Sketch` & `Skit` core inventory + single-pass `read_sketch_file()` and `load_ranked_skits()` returning `(raw_header, ranked_rows)` | Sketch YAML path, optional `profile_id` | Validated `Sketch` / `(header, [(sid, Skit), ...])` |
| `src/sketchtastic/reporting.py` | Generic CLI `report`, `export`, `coverage`, `analyze` subcommand wiring and atomic HTML publication (top-level imports of `analysis` and `dashboard`) | Sketch/profile/regression paths, CLI args | Formatted text, exported JSONL, written HTML summary |
| `src/sketchtastic/analysis.py` | Lean Dashboard Payload Builder: ranked skit projection, field/aggregate descriptors, additive weighting discovery, time/run axes, `.history/` loading & drift | Sketch path, optional `history_dir`, `default_weight` | JSON-safe dashboard view-model `dict` |
| `src/sketchtastic/dashboard.py` | Thin offline HTML assembler (~70–100L): loads `assets/chart.umd.min.js` + `assets/dashboard/*`, embeds script-safe JSON under strict CSP | Payload `dict`, optional title | Single standalone HTML document string |
| `src/sketchtastic/assets/dashboard/` *(new static assets)* | `styles.css`, `template.html`, `core.js`, `stats.js`, `charts.js`, `correlations.js`, `sankey.js`, `explorer.js`, `url_state.js`, `app.js` | Loaded via `importlib.resources.files` | Concatenated inline CSS/HTML/JS in single HTML file |
| `src/sketchtastic/cli.py` | Argparse wiring, `show` table formatting, `_Sequencer`, and decomposed streaming/parallel merge helpers (`_FoldOptions`) | CLI argv, JSONL stream, Profile, Sketch | Updated sketch + `.history/` run file, exit code |
| `src/sketchtastic/aggregators.py` | Associative `Aggregator` monoids + decomposed `_log_histogram_bins`, `_fixed_histogram_bins`, `_interpolate_bin_quantile` | Event values, stored states | Merged states, bin descriptors, quantiles |

### Dependency Graph (Acyclic)
```text
model ← aggregators ← profile ← sketch ← _io
                                   ↑
              ┌────────────────────┼────────────────────┐
              │                    │                    │
          analysis             dashboard              cli
              └──────────┬─────────┘                    │
                         ↓                              │
                     reporting ◄────────────────────────┘
```
Every arrow goes one direction: **zero cycles**, **zero `_private` cross-module imports**, **zero lazy imports**.

## 4. Runtime Interaction & Critical Flows

1. **`sketch analyze SKETCH -o REPORT.html`**:
   - `reporting.analyze_to_html` validates output target (not symlink, not directory, no-clobber unless `--force`, parent exists) → calls `analysis.analyze_sketch` (single YAML read of sketch + single read per history file) → calls `dashboard.render_dashboard` (reads cached static assets from `assets/dashboard/` + `assets/chart.umd.min.js`, escapes title & JSON) → writes atomically via `_io.atomic_write_text`.
2. **Browser Dashboard Load & Interaction**:
   - Single inline `<script id="skt-app-script">` runs IIFE over `DATA.skits`, `DATA.fields`, `DATA.aggregates`, `DATA.weightings`, `DATA.time_axes`, `DATA.history`, `DATA.meta`. `stats.js` computes all KPIs, Pareto concentration, field stats, ablation, correlations, and aggregate/histogram summaries dynamically for the active filters and weighting.

## 5. Interface & Contract Specifications

- **Public Python API (`sketchtastic.__all__`):** Unchanged.
- **CLI commands, flags, output text, and exit codes:** Unchanged (`merge`, `check`, `show`, `report`, `export`, `coverage`, `analyze`).
- **Internal `analyze_sketch()` payload:** Keeps top-level keys `meta`, `fields`, `aggregates`, `weightings`, `time_axes`, `history`, `skits`. Removes unused precomputed keys `ablation`, `correlations`, `meta.concentration`, and per-field/per-aggregate computed stats that JS computes live. `fields` entries carry `{"key": ...}`; `aggregates` entries carry `{"key": ..., "kind": ..., "functions": [...], "metric": ...}`.

## 6. Cross-Cutting Concepts & Resilience

| Failure Mode | Trigger | System Behavior | User Impact | Blast Radius |
|---|---|---|---|---|
| Symlink output target | `-o` points to symlink | Refused before and during atomic publish (`ValueError`) | Error message, exit 2 | Zero writes |
| Existing output without `--force` | `-o` / `--output` already exists | Refused via `os.link` / pre-check (`FileExistsError`) | Error message, exit 2 | Existing file untouched |
| XSS / `</script>` in tokens or title | Malicious event payload | HTML-escaped title + `_safe_json_for_script` (`\u003c`/`\u003e`/`\u0026`/U+2028/U+2029) + `textContent`/`createElementNS` DOM | Rendered as inert text | Isolated to document |
| Prototype-pollution keys (`__proto__`, `constructor`) | Crafted field/token names | `Map` + `Object.hasOwn` / allowlists against `DATA` keys | Treated as ordinary strings | None |
| Malformed history YAML | Corrupt file in `.history/` | Caught per file, recorded in `history.warnings`, analysis continues | Warning banner in History section | Single history file skipped |

## 7. Technical Stack & SDLC / Build Impact

- **Languages & Runtime:** Python `>=3.14` (tested on 3.14 & 3.15), static offline ES2020 JS (no build step; optional `node` in dev/tests for JS unit & syntax checks).
- **Core Libraries:** Unchanged (`PyYAML`, `jsonpath-rfc9535`, `jsonschema`, vendored MIT `Chart.js v4.4.9`).
- **Build-Environment Check (CRITICAL):** Does this design add a new language, package manager, runtime version, or external tool? **No.** Hatchling automatically ships `src/sketchtastic/assets/dashboard/*` as part of `packages = ["src/sketchtastic"]`. No Tank Phase 0 required; Tank verifies wheel contents and full conformance at Sprint Close (`*devops sdlc-check`).

## 8. Architectural Decisions (ADRs)

- **ADR-2026-11-23 (recorded in `docs/DECISIONS.md` at closeout):** *Single Source of Truth for Interactive Dashboard Statistics & Modular Offline Web Assets.* Interactive dashboard statistics live solely in modular JS (`src/sketchtastic/assets/dashboard/stats.js`) verified by `node` unit tests; Python's `analysis.py` acts solely as a lean, single-pass payload and history-drift builder rather than duplicating client-side analytics. Static web assets are concatenated into one inline HTML document at render time to preserve 100% offline CSP and zero frontend build tooling.
