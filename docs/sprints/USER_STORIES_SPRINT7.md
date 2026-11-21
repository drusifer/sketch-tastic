# Sprint 7 User Stories: Interactive Sketch Analysis Dashboard

*   **Planning Size**: 8 points
*   **Branch**: `sprint-7`
*   **Source**: Owner, 2026-11-21 (`agents/CHAT.md`): generic `sketchtastic` CLI capability producing a self-contained offline HTML interactive analysis dashboard (bundling MIT Chart.js) with weighted enum distributions, min/max and summary statistics across fields and aggregates, time/run range sliders, interactive skit/sample exploration, and run-over-run history drift.
*   **Status**: Approved (Smith Gate 1 & Gate 2, Switch Gate 2b) — ready for implementation

## Goal

Give any `sketchtastic` user a single command (`sketchtastic analyze`) that turns a sketch file—and its optional run history—into an interactive, offline, self-contained HTML dashboard. Users can inspect weighted token distributions, min/max and numeric summary statistics across all fields and aggregates, scrub time and run range sliders to see which skits appeared when, explore retained JSON samples, and track drift across runs without running a server or installing frontend tooling.

## Assumptions made for the owner

- CLI command is `sketchtastic analyze SKETCH -o/--output REPORT.html` with optional `--history DIR` (auto-detecting `<sketch>.history/`), `--title TEXT`, and `--force` to overwrite an existing file (default refuses to clobber). Existing `sketchtastic report` stays unchanged as the fast ASCII ranked-skit command.
- Because a sketch stores per-skit summaries rather than every raw event value, exact observation-weighted mean and median are computed for numeric token fields and skit counts, exact observation-weighted mean is computed for `AVG` aggregates (`sum / count`), and aggregate medians are explicitly labeled as across-skit (and skit-weighted) statistics—never misrepresented as raw-event medians.
- Chart.js v4.4.9 (MIT) is vendored inside the package and inlined into the generated HTML with a strict offline Content Security Policy (zero CDN/network requests, zero new PyPI runtime dependencies).
- Mainline development continues per `docs/SDLC.md`: no version bump, git tag, push, or PyPI release.

---

## STORY-SKT-12: Generate a self-contained offline HTML analysis dashboard
**Points:** 2 · **Owner:** Neo

**As a** developer or analyst working with a sketch file,
**I want** to run `sketchtastic analyze SKETCH --output REPORT.html` and receive a single self-contained HTML file with bundled interactive charts,
**so that** I can open and share a rich visual analysis offline in any browser without running a web server or hitting external CDNs.

### Acceptance Criteria
1. Running `sketchtastic analyze SKETCH -o REPORT.html` (or `--output`) writes a valid standalone HTML file containing all styles, scripts, Chart.js library code, and analyzed sketch data inline, with zero external script/style/image network URLs.
2. Default output refuses to overwrite an existing file or symlink and exits with status `2` and a clear stderr error; passing `--force` atomically replaces a regular file (still refusing to follow or overwrite a symlink).
3. Missing, unreadable, non-YAML, wrong-version, or malformed sketch files fail cleanly with exit status `2` and leave no partial output file behind.
4. An empty sketch (zero skits) produces a valid dashboard displaying `0` observations, `0` skits, `N/A` ratios, and an explicit empty-state message with no runtime errors.
5. Untrusted strings in sketch tokens, aggregate values, paths, titles, and retained sample records cannot break out of embedded `<script>` blocks or inject executable HTML/JS when rendered in the browser.

---

## STORY-SKT-13: Interactive distributions, field/aggregate statistics, and time/run sliders
**Points:** 4 · **Owner:** Neo

**As a** developer analyzing an event stream sketch,
**I want** an interactive dashboard showing concentration curves, weighted enumerated value distributions, min/max and numeric summary statistics for every field and aggregate, and dual-handle time/run range sliders,
**so that** I can understand data shape, spot anomalies, and see which skits appeared in any time or run window.

### Acceptance Criteria
1. The overview displays total observations, distinct skits, singleton count/share, head-vs-tail thresholds (minimum skits needed to cover 50%, 80%, 90%, 95%, and 99% of observations), and an interactive Pareto/cumulative coverage Chart.js chart.
2. For every token field, the dashboard displays its enumerated values with both observation-weighted counts/shares (`meta.count`) and distinct-skit counts/shares, rendered as an interactive Chart.js bar chart plus table, with constant-field and high-cardinality callouts.
3. Every token field displays its observed Min and Max; when all non-`NULL` observed values of a field are finite numbers, it also computes and displays observation-weighted Mean and exact observation-weighted Median (otherwise showing cardinality, mode, and non-numeric notice).
4. Every aggregate in the sketch displays its global rollup (SUM, COUNT, global MIN, global MAX, exact observation-weighted MEAN from `AVG.sum / AVG.count` when present), plus clearly labeled across-skit Min, Max, Mean, and Median and top outlier skits, with an interactive Chart.js chart.
5. The dashboard detects available time/run axes automatically—both `DATETIME`/`DATE` aggregates with `MIN`/`MAX` (such as `posted_at`) and `meta.first_seen`/`meta.last_seen` run ranges—and provides dual-handle range sliders (with Overlap vs. Contained mode) that dynamically filter the active skits and recompute all KPIs, charts, field distributions, aggregate rollups, and tables in real time.

---

## STORY-SKT-14: Interactive skit explorer, sample inspector, and history drift
**Points:** 2 · **Owner:** Neo

**As a** developer assembling regression sets or monitoring stream changes,
**I want** to filter and sort skits interactively, inspect their retained original JSON samples, and view run-over-run drift when sketch history exists,
**so that** I can drill from high-level patterns directly to concrete sample records and detect new, vanished, or shifting event shapes across runs.

### Acceptance Criteria
1. Clicking any enumerated field value bar (or using the filter/search controls) cross-filters the dashboard; active filters appear as removable chips with a one-click Reset control and live filtered count/share readout.
2. The skit explorer table supports sorting by observation count, weight %, first/last seen, or numeric aggregate values, one-click copying of the full skit ID, and expanding any row to inspect its retained original `first`/`last` JSON sample and copyable sample locator.
3. When `<sketch>.history/*.yaml` exists (or `--history DIR` is supplied), the dashboard loads valid run files in run-ID order, maps run IDs to their `started`/`finished` timestamps for the run slider, plots a Chart.js run timeline (events and skits per run), and shows run-over-run drift (newly appeared skits, disappeared skits, and largest share/count shifts between consecutive runs).
4. When no history directory exists, the history section displays a clear non-error empty state while all other dashboard features remain fully functional; if an explicitly passed `--history DIR` is missing or unreadable, the CLI exits with status `2`.
5. Live verification succeeds on `data/bluesky-posts-aggs/posts.sketch.yaml` (20,789 posts, 860 skits, 18 fields, 11 aggregates) and on a multi-run sketch with history.

---

## Out of Scope
- Live web server, backend API, or Node/npm frontend build toolchain.
- External CDN script/font loading or telemetry/network calls from the generated HTML.
- Computing exact raw-event quantiles/medians for aggregates whose raw per-event values are not retained in the sketch format.
- Modifying the sketch YAML format (`version: 0`), `sketchtastic report` ASCII output, or `sketchtastic show` table output.
- Pushing to remote, bumping package version, or publishing to PyPI.

## Open Questions
None — deliverable surface, offline HTML + bundled MIT Chart.js, interactive dashboard sections, and CLI subcommand were confirmed by the owner on 2026-11-21.

---

# Architecture Document: Sprint 7 Interactive Sketch Analysis Dashboard

*   **Status**: Approved — Smith Gate 2 & Switch Gate 2b passed
*   **Author**: Morpheus
*   **Last Updated**: 2026-11-21
*   **Scope**: Sprint 7 Architecture (`STORY-SKT-12`, `STORY-SKT-13`, `STORY-SKT-14`)

---

## 1. Executive Summary & System Overview

Sprint 7 adds `sketchtastic analyze SKETCH -o REPORT.html` to turn any `sketch-tastic` sketch (and optional `.history/` directory) into a single, offline, self-contained HTML dashboard with bundled Chart.js v4.4.9 (MIT). The architecture separates pure statistical analysis (`analysis.py`), offline HTML/Chart.js rendering (`dashboard.py`), vendored JS assets (`assets/`), and CLI file I/O (`reporting.py`) so every metric is unit-testable in Python and also dynamically recomputable in client-side JS as the user drags time/run sliders or filters by field values.

## 2. System Context & Boundaries

- **Input boundary (untrusted local files):** A YAML sketch file (`version: 0`), an optional history directory (`<sketch without last ext>.history/` or `--history DIR`), and optional CLI `--title`. All token values, aggregate strings, file paths, and retained sample JSON objects are treated as untrusted text for HTML/JS rendering.
- **Output boundary (local filesystem):** One self-contained `.html` file written atomically to `--output` (default no-clobber; `--force` replaces regular files only, never following symlinks).
- **Browser runtime boundary (strictly offline):** Opened directly via `file://` or local viewer with a strict Content Security Policy (`default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; font-src 'none'; connect-src 'none';`). Zero network requests, zero web server, zero external CDN dependencies.

## 3. Component & Container Architecture

| Component | Responsibility | Inputs | Outputs |
|---|---|---|---|
| `src/sketchtastic/analysis.py` | Load & validate sketch and optional history run files; compute ranked skits, concentration thresholds, per-field weighted distributions & min/max/numeric stats, per-aggregate global rollups & across-skit stats, detected time/run axes, and run-over-run drift | Sketch path, optional history dir | Structured JSON-serializable `dict` analysis payload |
| `src/sketchtastic/assets/chart.umd.min.js` | Vendored Chart.js v4.4.9 UMD bundle (+ `CHARTJS_LICENSE.txt` and `CHARTJS_SHA256.txt`) shipped as package data | Loaded via `importlib.resources` | Minified JS string for inline `<script>` |
| `src/sketchtastic/dashboard.py` | Render self-contained HTML document: strict CSP, CSS layout, safely escaped JSON data block, inlined Chart.js, and client-side interactive dashboard engine | Analysis payload, optional title | Complete UTF-8 HTML document string |
| `src/sketchtastic/reporting.py` | Register `analyze` subcommand via `add_commands`; handle CLI flags, atomic no-clobber / `--force` output writing, and clean exit status `2` errors | CLI `argparse.Namespace` | Written HTML file + stdout confirmation / stderr error |

## 4. Runtime Interaction & Critical Flows

1. **CLI Analysis Generation Flow:**
   - User runs `sketchtastic analyze SKETCH -o REPORT.html [--history DIR] [--title TEXT] [--force]`.
   - `reporting._cmd_analyze` validates output target upfront (refusing symlinks, directories, or existing files unless `--force`).
   - `analysis.analyze_sketch(sketch_path, history_dir=...)` loads the sketch through `Sketch.load`, validates skit IDs/tokens/counts, discovers or validates the history directory, parses history run files, and returns a normalized analysis payload.
   - `dashboard.render_dashboard(payload, title=...)` reads vendored `chart.umd.min.js` via `importlib.resources`, encodes `payload` with script-safe JSON escaping (`<`, `>`, `&`, `\u2028`, `\u2029`), and returns the full HTML string.
   - `reporting._write_html_atomic` writes to a staging temp file in `output.parent`, then publishes atomically via `os.link` (no-clobber) or `os.replace` (`--force`).
2. **Interactive Browser Filtering Flow (Client-Side JS):**
   - On `DOMContentLoaded`, inline JS parses the embedded payload JSON and initializes state (`activeAxis`, `rangeMin`, `rangeMax`, `rangeMode: "overlap"|"contained"`, `fieldFilters: Map<key, Set<val>>`, `searchQuery`, `weightMode: "observations"|"skits"`, `selectedField`, `selectedAggregate`, `sortBy`, `sortDir`).
   - Any slider movement, field bar click, chip removal, or search edit filters `payload.skits` in memory, recomputes live KPIs, Pareto concentration thresholds, per-field weighted distributions & min/max/numeric stats, and per-aggregate global & across-skit stats, then updates Chart.js instances and the skit explorer table without page reload.

## 5. Interface & Contract Specifications

* **Command:** `sketchtastic analyze SKETCH -o OUTPUT [--history DIR] [--title TEXT] [--force]`
* **Parameters / Flags:**
  * `SKETCH`: Path to a `version: 0` sketch YAML file (required).
  * `-o`, `--output OUTPUT`: Destination `.html` file path (required).
  * `--history DIR`: Optional history directory containing `YYMMDD-SEQ.yaml` run files. If omitted, auto-detects `<sketch without last extension>.history` when present; if supplied explicitly and missing/not a directory, fails with exit status `2`.
  * `--title TEXT`: Optional dashboard header title (defaults to sketch filename).
  * `--force`: Allow replacing an existing regular file at `OUTPUT` (still refuses symlinks and directories).
* **Exit Codes:** `0` HTML dashboard written; `2` invalid input sketch, unreadable/missing explicit `--history`, existing output without `--force`, symlink/directory output, or I/O error (no partial file written).
* **Statistical Honesty Contract:**
  * Token field stats: exact observation-weighted counts & percentages (`sum(meta.count)`), exact distinct-skit counts & percentages, exact Min/Max, and (when all non-`NULL` values parse as finite numbers) exact observation-weighted Mean and exact observation-weighted Median.
  * Aggregate stats: exact global `SUM`, `COUNT`, `MIN`, `MAX`, and exact observation-weighted `MEAN` (`sum(AVG.sum) / sum(AVG.count)` when `AVG` is present); per-skit `Min`, `Max`, `Mean`, and `Median` across active skits are explicitly labeled as **across-skit** statistics.

## 6. Cross-Cutting Concepts & Resilience

### Failure Modes & Error Handling
| Failure Mode | Trigger / Condition | System Behavior | User / Client Impact | Blast Radius |
|---|---|---|---|---|
| Missing / malformed sketch | Missing file, invalid YAML, wrong version, bad count/tokens | Abort before staging output | Clear stderr error, exit `2` | None (zero files written) |
| Output collision or symlink | `OUTPUT` exists (no `--force`) or is a symlink/dir | Abort before or at atomic publish | Clear stderr error, exit `2`; existing file untouched | None |
| Empty sketch (0 skits) | Valid sketch with `skits: {}` | Render valid HTML with `0` counts, `N/A` ratios, empty-state UI | Opens cleanly with zero JS errors | Isolated |
| Corrupt history file | One unreadable/non-sketch file in auto-detected history dir | Skip bad file and record a visible warning banner in History panel (or fail exit `2` if explicit `--history` dir does not exist) | Rest of dashboard works; warning explains skipped file | Isolated to history panel |
| Untrusted sketch text (XSS) | Tokens, records, titles containing `</script>`, `<img onerror=...>`, HTML tags | Script-safe JSON escaping + `textContent` DOM rendering + strict CSP | Rendered literally as text; zero script execution | None |

### Security & Privacy
* **Trust / access boundaries:** All sketch fields, aggregates, retained records, and paths are untrusted strings. Inline JSON escapes `<`, `>`, `&`, `\u2028`, `\u2029`. DOM rendering uses `textContent` / safe element creation rather than untrusted `innerHTML`. Strict CSP `<meta>` blocks any outbound network request or external script.
* **Supply chain:** Chart.js v4.4.9 UMD minified bundle is vendored once with its MIT license and verified SHA-256 recorded in `src/sketchtastic/assets/CHARTJS_SHA256.txt` and tested by unit tests.
* **Sensitive data:** Offline file stays local; retained samples already present in the sketch are displayed only inside the generated local HTML file.

## 7. Technical Stack & SDLC / Build Impact

* **Languages & Runtime:** Python `>=3.14` (unchanged); vanilla ES2020 browser JS + Chart.js v4.4.9 UMD (MIT) inlined into HTML output.
* **Core Libraries & Tools:** No new PyPI runtime or dev dependencies (`PyYAML`, `jsonpath-rfc9535`, `jsonschema` unchanged). Hatchling `packages = ["src/sketchtastic"]` and sdist `include = ["src", ...]` automatically package `src/sketchtastic/assets/*`.
* **Build-Environment Check (CRITICAL):**
  * Does this design add a new language, package manager, runtime version, or external tool? **No.**
  * No Tank Phase 0 mechanism change is required. Tank verifies wheel/sdist inclusion and full conformance (`make distclean`, `install`, `lint`, `test`, `test-all`, `smoke`, `security-scan`) at Sprint Close.

## 8. Architectural Decisions (ADRs) & Technical Debt

### Decision Records
* `ADR-2026-11-21`: Self-contained offline HTML analysis dashboard with vendored Chart.js (`docs/DECISIONS.md`).

### Acknowledged Technical Debt & Trade-offs
* **Wheel size (~200 KB increase):** Accepted per owner choice to guarantee 100% offline interactivity with zero CDN dependency.
* **Across-skit aggregate medians:** Sketches do not store raw per-event distributions (e.g., t-digest/HDR histograms). Rather than changing sketch format `version: 0`, aggregate medians are computed across skits and explicitly labeled as across-skit stats.
