# UAT Plan: Sprint 7 — Interactive Sketch Analysis Dashboard

- **Stories / criteria:** `STORY-SKT-12` (AC1–5), `STORY-SKT-13` (AC1–5), `STORY-SKT-14` (AC1–5) (`docs/sprints/USER_STORIES_SPRINT7.md`)
- **Environment and build:** Python 3.14 & 3.15 (`.venv`), `sketch-tastic 0.2.0` on branch `sprint-7`, Chromium headless visual check via `html_preview`, Node JS syntax check
- **Date / tester:** 2026-11-21 / Trin (QA) & Smith (HCI / User Acceptance)
- **Entry conditions:** All 298 unit tests and `make lint` pass; Chart.js v4.4.9 SHA-256 verified; Switch Phases 1–3 security gates clear
- **Exit conditions:** Every in-scope acceptance criterion passes with recorded evidence; zero blocking defects

## Scenarios

### UAT-SKT-701: Offline self-contained HTML dashboard generation and CSP
- **Linked criterion:** `STORY-SKT-12` AC1
- **Preconditions and data:** `data/bluesky-posts-aggs/posts.sketch.yaml` (20,789 observations, 860 skits, 18 fields, 11 aggregates)
- **Steps:** `bobp make -vvv run ARGS="analyze data/bluesky-posts-aggs/posts.sketch.yaml -o data/bluesky-posts-aggs/analysis.html --force"` and inspect CSP/external tags + render in Chromium (`html_preview`).
- **Expected observable outcome:** Exit `0`, single self-contained HTML file bundling Chart.js v4.4.9, strict offline CSP (`default-src 'none'`, `connect-src 'none'`), zero external CDN tags, zero browser console errors.
- **Actual outcome:** Generated 3.0 MB `data/bluesky-posts-aggs/analysis.html` (`20,789 observations, 860 skits, 0 history runs`); `test_dashboard` confirmed strict CSP, SHA-256 match, and valid JS via `node --check`; Chromium `html_preview` rendered with `consoleMessages: []`.
- **Verdict:** PASS
- **Evidence / issue:** `tests/test_dashboard.py`, `data/bluesky-posts-aggs/analysis.html`, Chromium `html_preview` verified clean.

### UAT-SKT-702: No-clobber, `--force`, symlink refusal, and invalid input handling
- **Linked criterion:** `STORY-SKT-12` AC2, AC3; `STORY-SKT-14` AC4
- **Preconditions and data:** Temporary directory fixtures in `tests/test_analyze_cli.py`
- **Steps:** Run `sketchtastic analyze` against existing output (no `--force`), with `--force`, against a symlink target (with `--force`), against a directory, against missing/malformed sketches, and against a missing explicit `--history DIR`.
- **Expected observable outcome:** Exit `2` with clear stderr error and zero target modification on all rejection paths; `--force` atomically replaces only regular files.
- **Actual outcome:** All 4 CLI contract tests in `tests/test_analyze_cli.py` passed (`OK`).
- **Verdict:** PASS
- **Evidence / issue:** `tests/test_analyze_cli.py` (`Ran 4 tests ... OK`).

### UAT-SKT-703: Empty sketch and XSS / prototype-pollution safety
- **Linked criterion:** `STORY-SKT-12` AC4, AC5
- **Preconditions and data:** Empty sketch (`skits: {}`) and adversarial sketch containing `</script><img src=x onerror=alert(1)><!--`, `__proto__`, `constructor`, `toString` in tokens, aggregates, records, and `--title`.
- **Steps:** `bobp make test ARGS=test_analysis` and `bobp make test ARGS=test_dashboard`.
- **Expected observable outcome:** Empty sketch produces `0` counts, `N/A` ratios, and valid HTML; XSS breakout sequences are escaped (`\u003c`, `&lt;`) with zero raw `<img` or `</script>` inside embedded JSON.
- **Actual outcome:** Both test suites passed with zero failures; no raw breakout tags present.
- **Verdict:** PASS
- **Evidence / issue:** `tests/test_analysis.py` (8/8 OK), `tests/test_dashboard.py` (4/4 OK).

### UAT-SKT-704: Pareto concentration, weighted enum distributions, field/aggregate min/max & mean/median, and time/run sliders
- **Linked criterion:** `STORY-SKT-13` AC1–5; `STORY-SKT-14` AC1–2, AC5
- **Preconditions and data:** Synthetic numeric/enum/date/datetime sketches + live `data/bluesky-posts-aggs/posts.sketch.yaml`
- **Steps:** Verify computed concentration thresholds, observation- vs skit-weighted field distributions, exact numeric weighted mean & median, global aggregate rollups vs across-skit medians, dual-handle `posted_at` range slider, and full-width All Fields / Aggregates tables visually in `html_preview`.
- **Expected observable outcome:** All metrics match exact formulas; all columns visible without broken clipping; `posted_at` dual slider (`2026-07-31` to `2026-11-20`) active with Overlap/First-appeared/Contained modes; Chart.js Pareto, Field Distribution, and Aggregate charts render cleanly.
- **Actual outcome:** Verified in unit tests and Chromium `html_preview` on live Bluesky dashboard (50% obs = 11 skits, 80% = 52, 90% = 125, 95% = 251, 99% = 653; 360 singletons; all 18 fields and 11 aggregates displayed cleanly after Smith's table-width polish).
- **Verdict:** PASS
- **Evidence / issue:** `tests/test_analysis.py`, Chromium `html_preview` post-polish verification.

### UAT-SKT-705: Multi-run history discovery, timeline, and run-over-run drift
- **Linked criterion:** `STORY-SKT-14` AC3, AC4, AC5
- **Preconditions and data:** Two-run sketch with `.history/261120-0001.yaml`, `.history/261120-0002.yaml`, and a corrupt extra YAML file; also zero-history Bluesky sketch.
- **Steps:** `bobp make test ARGS=test_analysis` and `bobp make test ARGS=test_analyze_cli`.
- **Expected observable outcome:** Auto-detects `<sketch>.history/`, sorts runs chronologically, maps timestamps to runs slider, reports new (`+1`), disappeared (`-1`), persisted (`1`), and share shift (`-60.0 pp`), warns on corrupt file without aborting, and renders graceful empty state when no history exists.
- **Actual outcome:** All assertions passed; Bluesky zero-history state renders cleanly with drift selector hidden.
- **Verdict:** PASS
- **Evidence / issue:** `tests/test_analysis.py::AnalysisHistoryDriftTests`, `tests/test_analyze_cli.py::test_analyze_auto_detects_history_directory`.

### UAT-SKT-706: Installed-wheel packaging smoke verification
- **Linked criterion:** `STORY-SKT-12` AC1
- **Preconditions and data:** Built wheel in `dist/` installed in isolated throwaway venv
- **Steps:** `bobp make smoke`
- **Expected observable outcome:** `sketchtastic analyze app.sketch.yaml -o dashboard.html` runs from the installed wheel and bundles `assets/chart.umd.min.js` cleanly.
- **Actual outcome:** Verified in Stage 3 Tank conformance check (`make smoke`).
- **Verdict:** PASS
- **Evidence / issue:** `smoke/test_smoke.py::test_analyze_writes_offline_dashboard_from_wheel`.

## Results and Handoff

- **Passed / failed / blocked:** 6 passed / 0 failed / 0 blocked (`UAT-SKT-701`..`UAT-SKT-706`)
- **Open issues and impact:** None.
- **Overall verdict:** PASS — all Sprint 7 acceptance criteria verified with automated and visual evidence.
- **Handoff evidence:** `agents/CHAT.md` Phase 3 UAT & Smith closeout sign-off.
