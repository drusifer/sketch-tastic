# Security Review: Sprint 7 Phase 2 — Vendored Chart.js & Offline HTML Renderer

- **Verdict:** No blocking findings
- **Date / reviewer:** 2026-11-21 / Switch
- **Target and version:** `src/sketchtastic/dashboard.py`, `src/sketchtastic/assets/*`, `tests/test_dashboard.py` on `sprint-7`
- **Assurance level:** L2 standard — bundles third-party JS and renders untrusted sketch data into HTML/JS.
- **Findings:** 0 total: Critical 0, High 0, Medium 0, Low 0, Info 0
- **Related work:** `agents/switch/reviews/2026-11-21-sprint7-design.md`, `STORY-SKT-12`..`14`

## Next Action

| Who | Does what | By / trigger |
|---|---|---|
| Morpheus | Review Phase 2 diff and hand off Phase 3 (`sketchtastic analyze` CLI) | Before Phase 2 commit |
| Switch | Review Phase 3 atomic output / symlink checks and run full `bobp make security-scan` | Phase 3 Step 5a |

## Scope and Threat Model

- **In scope / out of scope:** In scope: `src/sketchtastic/dashboard.py`, vendored `src/sketchtastic/assets/chart.umd.min.js` (v4.4.9, MIT), `CHARTJS_LICENSE.txt`, `CHARTJS_SHA256.txt`, and `tests/test_dashboard.py`. Out of scope: CLI file writing (Phase 3).
- **Assets worth protecting:** Browser DOM integrity when opening generated HTML, offline data confidentiality, supply-chain integrity of Chart.js.
- **Entry points and trust boundaries:** Analysis payload JSON embedded in `<script id="skt-data">`, `--title` HTML header, vendored Chart.js script.
- **Threats considered:** XSS / `<script>` breakout, prototype pollution via token keys (`__proto__`, `constructor`), outbound network egress, vendored JS tampering. Auth/authz/elevation N/A (local offline single-user HTML).

## Method and Coverage

- **Reviewed by:** Full manual read of `src/sketchtastic/dashboard.py` and `tests/test_dashboard.py`; SHA-256 verification of `chart.umd.min.js` (`bce154080959c574be0bb6b1a924ff32f08ebc6ff460c159171f51c53802c844`); `bobp make test ARGS=test_dashboard` (including `node --check`); `bobp make security-scan-secrets`.
- **Tool results:** `gitleaks detect --source . --redact`: 0 leaks; `unittest tests/test_dashboard.py`: 4/4 OK; `node --check`: exit 0; `ruff check` + `ruff format --check`: clean.
- **Not covered:** `pip-audit` (no Python lockfile changes in Phase 2; full `bobp make security-scan` runs in Phase 3 & Tank closeout).

## Area Checklist

| Area | What to check | Result |
|---|---|---|
| Input handling and injection | `_safe_json_for_script` escapes `<`, `>`, `&`, U+2028, U+2029; `html.escape` on header/title; `textContent` DOM nodes; `Map` + `Object.prototype.hasOwnProperty` in JS | Pass |
| Authentication and sessions | N/A | N/A: local offline HTML |
| Authorization and access control | N/A | N/A: single-user local file |
| Secrets and cryptography | SHA-256 pinned in `CHARTJS_SHA256.txt` and tested; gitleaks clean | Pass |
| Data protection and privacy | Strict CSP (`default-src 'none'; connect-src 'none'; font-src 'none'; img-src data:`) blocks all network egress | Pass |
| Error handling and logging | Empty sketch renders cleanly with zero JS exceptions | Pass |
| Dependencies and supply chain | Chart.js v4.4.9 MIT license bundled; zero `</script` sequences; zero new PyPI deps | Pass |
| Configuration, build, and CI | No workflow/CI changes; Hatchling packages `src/sketchtastic/assets/*` | Pass |
| Files, processes, and network | Pure in-memory string rendering; zero file/subprocess/network I/O | Pass |
| Business logic and abuse cases | Statistical scope banner distinguishes observation-weighted vs across-skit stats | Pass |

## Findings

| ID | Title | Severity | Status | Owner |
|---|---|---|---|---|
| No findings | — | — | — | — |

## Root Causes and Recommendations

None.

## Sign-off

- **Re-review needed:** Phase 3 Step 5a when CLI file I/O is added.
- **Risk acceptance:** None.
- **Verification:** `test_dashboard` (4/4), `lint`, `security-scan-secrets` passed on 2026-11-21.
