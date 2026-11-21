# Security Review: Sprint 7 Design — Offline HTML Sketch Analysis Dashboard

- **Verdict:** No blocking findings
- **Date / reviewer:** 2026-11-21 / Switch
- **Target and version:** Sprint 7 architecture (`docs/sprints/USER_STORIES_SPRINT7.md`, ADR-2026-11-21) on `sprint-7`
- **Assurance level:** L2 standard — CLI reads untrusted YAML/JSON sketch records and renders an HTML/JS file opened in a user's browser, introducing XSS, symlink/file-clobber, and vendored-JS supply-chain surfaces.
- **Findings:** 0 total: Critical 0, High 0, Medium 0, Low 0, Info 0
- **Related work:** `STORY-SKT-12`, `STORY-SKT-13`, `STORY-SKT-14`, `ADR-2026-11-21`

## Next Action

| Who | Does what | By / trigger |
|---|---|---|
| Mouse | Schedule Switch security review tasks after every Sprint 7 coding phase | Sprint 7 Step 3 plan (`task.md`) |
| Neo | Enforce script-safe JSON escaping (`<`, `>`, `&`, U+2028, U+2029), strict offline CSP, `textContent`-only DOM rendering for untrusted fields, atomic no-symlink output writes, and SHA-256 pinned Chart.js v4.4.9 asset | Phases 1–3 implementation |
| Switch | Verify diff, vendored Chart.js SHA-256/license, XSS regression tests, and `bobp make security-scan` | Phases 1–3 Step 5a gates |

## Scope and Threat Model

- **In scope / out of scope:** In scope: `sketchtastic analyze` CLI boundary, `analysis.py` sketch/history loading, vendored Chart.js v4.4.9 UMD asset, `dashboard.py` HTML/JS generation and client-side DOM rendering. Out of scope: live web servers, authentication, remote APIs, network capture (not part of Sprint 7).
- **Assets worth protecting:** Integrity of the user's browser execution context when opening generated HTML (`file://` origin), local filesystem integrity around `--output`, supply-chain integrity of bundled JS, and confidentiality of local sketch data (must never leak over the network).
- **Entry points and trust boundaries:**
  1. Untrusted YAML sketch files (arbitrary strings in `tokens`, `aggregates`, `meta.first`/`last` records, `profile_id`, filenames).
  2. Untrusted history YAML files in `<sketch>.history/` or `--history DIR`.
  3. CLI flags (`--output`, `--history`, `--title`, `--force`).
  4. Third-party vendored JS (`chart.umd.min.js` v4.4.9).
- **Threats considered:**
  - **Tampering / XSS (HTML & `<script>` breakout):** Malicious event payloads containing `</script><script>alert(1)</script>`, `<!--`, HTML tags in tokens/aggregates/titles, or prototype-pollution keys (`__proto__`, `constructor`) when rendering in the browser. Mitigated by escaping `<`, `>`, `&`, `\u2028`, `\u2029` in embedded JSON, avoiding untrusted `innerHTML`, using `Object.create(null)`/`Map` for dynamic key aggregation in JS, and enforcing strict CSP.
  - **Information disclosure (exfiltration via network):** Generated HTML calling external CDNs, fonts, or image URLs from untrusted content. Mitigated by zero external URLs and `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; font-src 'none'; connect-src 'none';">`.
  - **Tampering (symlink / clobber on `--output`):** Writing through a symlink or overwriting existing files unexpectedly. Mitigated by refusing symlinks/directories always, default no-clobber via `os.link`, and atomic temp-file staging in `output.parent`.
  - **Supply chain (vendored JS):** Compromised or unpinned JS library. Mitigated by pinning Chart.js v4.4.9 UMD from immutable jsDelivr/npm release, storing `CHARTJS_LICENSE.txt` and `CHARTJS_SHA256.txt`, and verifying the SHA-256 digest in automated tests.
  - **Denial of service (large sketches / malformed YAML):** Bounded YAML parsing via `CSafeLoader` (no arbitrary Python object deserialization), ignoring non-YAML/malformed history entries with warnings, and paginated skit rendering in the DOM so 860+ skits stay responsive.
  - **Spoofing / Elevation of privilege / Repudiation:** N/A — local offline single-user CLI with no auth, multi-tenant access control, or privileged daemon.

## Method and Coverage

- **Reviewed by:** Manual threat-model review of `docs/sprints/USER_STORIES_SPRINT7.md` and `ADR-2026-11-21` against OWASP XSS Prevention, CSP, and safe-file-publication controls.
- **Tool results:** Design gate only — scanners (`bobp make security-scan`) run during Phase 2/3 implementation gates when files/assets are added.
- **Not covered:** Implementation code and vendored asset bytes (not yet written; covered in Phase 1–3 Step 5a reviews).

## Area Checklist

| Area | What to check | Result |
|---|---|---|
| Input handling and injection | YAML `CSafeLoader` only; script-safe JSON escaping; `textContent`/safe DOM; `Map` for untrusted keys | Pass (mandated in architecture; verified in Phase 1–2 tests) |
| Authentication and sessions | N/A | N/A: local offline CLI with no auth or sessions |
| Authorization and access control | N/A | N/A: single-user local file tool |
| Secrets and cryptography | No secrets; SHA-256 integrity pin for vendored Chart.js | Pass (mandated in design) |
| Data protection and privacy | Strict offline CSP blocks network egress of local sketch records | Pass (mandated in design) |
| Error handling and logging | Clean stderr errors, exit `2`, `safe_text` escaping for terminal messages | Pass (mandated in design) |
| Dependencies and supply chain | Zero new PyPI deps; Chart.js v4.4.9 MIT pinned with SHA-256 and license | Pass (to be verified upon vendoring in Phase 2) |
| Configuration, build, and CI | Existing Hatchling packaging; no new workflows or permissions | Pass |
| Files, processes, and network | Atomic temp staging, no-clobber default, symlink refusal, zero subprocess/network calls | Pass (mandated in design) |
| Business logic and abuse cases | Statistical labels prevent misleading raw-median claims; empty sketch safe | Pass |

## Findings

| ID | Title | Severity | Status | Owner |
|---|---|---|---|---|
| No findings | — | — | — | — |

## Root Causes and Recommendations

- Enforce an automated XSS payload test in Phase 2 (`</script><img src=x onerror=alert(1)>` in token key, token value, aggregate string, title, and retained sample) plus a SHA-256 verification test for `chart.umd.min.js`.
- Use `Map` (never plain `{}` indexing) in browser JS when aggregating arbitrary token values so keys like `__proto__`, `constructor`, or `toString` cannot corrupt counts.

## Sign-off

- **Re-review needed:** Yes — Step 5a security review after each coding phase (Phases 1, 2, and 3).
- **Risk acceptance:** None.
- **Verification:** Pending Phase 1–3 implementation and `bobp make security-scan`.
