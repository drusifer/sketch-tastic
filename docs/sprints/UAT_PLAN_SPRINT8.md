# UAT Plan: Sprint 8 — Lean Architecture, Modular Dashboard & Code Hygiene

- **Stories / criteria:** `STORY-SKT-15`, `STORY-SKT-16`, `STORY-SKT-17`, `STORY-SKT-18` ([USER_STORIES_SPRINT8.md](USER_STORIES_SPRINT8.md)), [DOMAIN.md](../DOMAIN.md)
- **Environment and build:** Local `.venv` (Python 3.14.8 + Node.js), throwaway wheel env (`bobp make smoke`), branch `sprint-8`
- **Date / tester:** 2026-11-23 / Trin (`*qa`)
- **Entry conditions:** Phases 1–3 implemented by Neo; `bobp make lint`, `bobp make test`, `bobp make quality`, and `bobp make security-scan` green.
- **Exit conditions:** Every acceptance criterion across `STORY-SKT-15`..`18` passes with observed evidence; zero blocking defects remain.

## Scenarios

### UAT-S8-01: Domain model, acyclic boundaries & single-pass YAML loading
- **Linked criterion:** `STORY-SKT-15` AC1–AC4
- **Preconditions and data:** Clean `sprint-8` checkout with `docs/DOMAIN.md` and `src/sketchtastic/`.
- **Steps:**
  1. Inspect `docs/DOMAIN.md` for all 3 bounded contexts, ubiquitous language, aggregate roots, and invariants.
  2. Run `grep -rn 'from sketchtastic' src/sketchtastic/` to verify zero `_`-prefixed private symbol cross-imports and zero circular/lazy imports.
  3. Run `bobp make test ARGS="test_analysis"` (`test_single_pass_yaml_read_for_sketch_and_history_files`).
- **Expected observable outcome:** Acyclic import graph; `read_sketch_file` spy records exactly 2 calls for 1 sketch + 1 history run file; tests pass.
- **Actual outcome:** Zero private cross-module imports and zero `PLC0415` lazy imports across all 13 `src/sketchtastic/` modules; `test_analysis` passed (9/9) confirming single-pass YAML parsing.
- **Verdict:** PASS
- **Evidence / issue:** Commit `85344d3`, `tests/test_analysis.py:69-83`.

### UAT-S8-02: Failure & rejection paths preserved (symlinks, no-clobber, malformed sketches & history)
- **Linked criterion:** `STORY-SKT-15` AC5, `STORY-SKT-16` AC4
- **Preconditions and data:** Temporary isolated directories in `tests/test_reporting.py`, `tests/test_analyze_cli.py`, and `tests/test_analysis.py`.
- **Steps:** Run `bobp make test ARGS="test_reporting" && bobp make test ARGS="test_analyze_cli" && bobp make test ARGS="test_analysis"`.
- **Expected observable outcome:** Symlink targets refused even with `--force` (exit 2), existing output without `--force` refused without clobbering, dangling symlinks rejected on `export`, profile mismatch rejected, corrupt/non-dict/symlink `.history/` entries skipped safely without leaking symlink content, unknown `--weight` rejected with exit 2.
- **Actual outcome:** `test_reporting` (16/16), `test_analyze_cli` (5/5), and `test_analysis` (9/9) all passed; all error classes and exit-2 semantics preserved.
- **Verdict:** PASS
- **Evidence / issue:** Phase 1 commit `85344d3` + `SEC-S8-01`..`05` hardening tests.

### UAT-S8-03: Lean dashboard payload & live Bluesky HTML generation
- **Linked criterion:** `STORY-SKT-16` AC1–AC3, `STORY-SKT-17` AC1–AC3, AC6
- **Preconditions and data:** Existing local capture sketch `data/bluesky-posts-multi-lang/posts.sketch.yaml` (20,789 observations, 172 skits) and unit fixtures.
- **Steps:**
  1. Run `bobp make test ARGS="test_dashboard"` (asset integrity, `node --check`, XSS/prototype, `SEC-S8-06` placeholder injection, direct `node` `stats.js` unit tests).
  2. Run `bobp make run ARGS="analyze data/bluesky-posts-multi-lang/posts.sketch.yaml -o data/bluesky-posts-multi-lang/analysis-s8.html --force"` and compare size vs pre-Sprint-8 `analysis.html`.
- **Expected observable outcome:** `dashboard.py` ≤ 100 lines, 10 modular assets under `assets/dashboard/*`, zero duplicate JS function declarations, strict offline CSP (`default-src 'none'`, `connect-src 'none'`, `base-uri 'none'`, `form-action 'none'`), placeholder tokens not second-order expanded, direct `node` JS stats unit tests pass, live Bluesky HTML smaller than prior 1.2M build.
- **Actual outcome:** `dashboard.py` is 96 lines; `test_dashboard` passed 9/9 (including `node` execution of `stats.js` for medians, concentration, boolean/numeric/enum fields, ablation, Cramér's V / Theil's U / φ / clusters, log & fixed histograms, and additive weightings, plus `SEC-S8-06` regression test); live Bluesky HTML shrunk from 1.2M → 1.1M.
- **Verdict:** PASS
- **Evidence / issue:** Commit `0a8ffcd`, `tests/test_dashboard.py`.

### UAT-S8-04: Wheel packaging & offline smoke verification
- **Linked criterion:** `STORY-SKT-17` AC5, `STORY-SKT-18` AC4
- **Preconditions and data:** Built wheel in isolated throwaway uv environment (`bobp make smoke`).
- **Steps:** Run `bobp make smoke`.
- **Expected observable outcome:** Wheel builds cleanly, bundles `assets/dashboard/*` and `assets/chart.umd.min.js`, and all 4 smoke tests pass against the installed `sketch` command (including README Quickstart and offline `sketch analyze`).
- **Actual outcome:** `sketch-tastic 0.2.0` wheel and sdist built; 4/4 smoke tests passed in 2.1s.
- **Verdict:** PASS
- **Evidence / issue:** `build/build.out` (`make smoke` exit 0).

### UAT-S8-05: Static quality bar (0/0/0), CLI/histogram refactoring & legacy vocabulary cleanup
- **Linked criterion:** `STORY-SKT-18` AC1–AC4
- **Preconditions and data:** Full `sprint-8` source and test tree.
- **Steps:** Run `bobp make lint && bobp make test && bobp make -vvv quality && bobp make security-scan`.
- **Expected observable outcome:** `lint` clean; full test suite green (325 tests incl. streaming limits, parallel merge, histograms, and `VocabularyTests`); `quality` reports 0 extended ruff warnings, 0 vulture dead-code hits, and 0 radon Grade C+ functions across all of `src/`; `security-scan` reports 0 gitleaks leaks and 0 pip-audit vulnerabilities.
- **Actual outcome:** `lint` clean (33 files); 325/325 tests passed; `quality` reported 0 extended ruff / 0 vulture / 0 radon C+ across all of `src/`; `security-scan` reported 0 leaks (119 commits) and 0 known vulnerabilities.
- **Verdict:** PASS
- **Evidence / issue:** Phase 3 commit on `sprint-8`, `build/build.out`.

## Results and Handoff

- **Passed / failed / blocked:** 5 passed (`UAT-S8-01`..`05`), 0 failed, 0 blocked.
- **Open issues and impact:** None blocking. Non-blocking Low/Info items logged by Switch (`log_bin_key` subnormal float edge case, `_fold_parallel` SIGKILL feed guard) fed to Sprint 8 retro backlog.
- **Overall verdict:** **PASS** — all Sprint 8 acceptance criteria (`STORY-SKT-15`..`18`) verified with observed evidence.
- **Handoff evidence:** Phase 1–3 verdicts recorded in `agents/CHAT.md`; ready for Stage 3 closeout (`Tank *devops sdlc-check` → `Oracle` → `Smith`).
