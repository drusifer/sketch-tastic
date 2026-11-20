# Security Review: Sprint 5 Bluesky ASCII implementation

- **Verdict:** No blocking findings
- **Date / reviewer:** 2026-11-19 / Switch
- **Target and version:** sprint-5 working tree: examples/bluesky/{capture,model,demo}.py, profile.yaml, capture tests, security Makefile targets, hook, manifest and lockfile
- **Assurance level:** L1 baseline — operator-invoked local metadata analysis without credentials or elevated privileges
- **Findings:** 0 open: Critical 0, High 0, Medium 0, Low 0, Info 0
- **Related work:** Sprint 5 stories; 2026-11-19-sprint5-design.md

## Next Action

| Who | Does what | By / trigger |
|---|---|---|
| Morpheus | Complete phase review after Trin verification | Implementation security gate clear |
| Tank | Record security targets and gate in SDLC | Sprint close |

## Scope and Threat Model

- **In scope / out of scope:** new local capture/preparation/report implementation and security tooling; excludes auditing third-party Bluesky systems, existing sketch package internals and Bob skill migration prose.
- **Assets worth protecting:** local files, terminal integrity, bounded capture resources, retained public metadata.
- **Entry points and trust boundaries:** remote WSS JSON and local JSONL are untrusted; user chooses input/output paths and optional endpoint. Saved report metadata is checked before labels print.
- **Threats considered:** malformed input/resource exhaustion, terminal controls, output clobbering, unintended credential handling. No sessions or remote privilege boundary exist. Public source identity is not authenticated evidence. Concurrent malicious filesystem modification by a process already able to write the output parent is outside this local CLI threat model.

## Method and Coverage

- **Reviewed by:** manual source review; VIA returned no indexed symbols for new demo files, followed by direct reads. Reviewed capture tests and revised preparation publication/report escaping after owner applied recommendations.
- **Tool results:** `bobp make security-install` passed. `bobp make security-scan`: gitleaks 8.26.0 scanned 67 commits (~1.02 MB), no leaks; pip-audit audited frozen exported versions from all lockfile groups, no known vulnerabilities. `bobp make security-test-hook` rejected a synthetic staged key using an alternate index and removed scratch output without changing the real index. Evidence is in ignored build/security-scan-evidence.log and build/security-hook-evidence.log.
- **Not covered:** historical secrets scan does not inspect uncommitted files; enabled staged hook scans them at commit. Full suite/formatting and final boundary-test run remain with Trin/parent. Capture agent reported successful mocked tests and one-frame public smoke. No service penetration testing or exhaustive memory benchmark performed.

## Area Checklist

| Area | What to check | Result |
|---|---|---|
| Input handling and injection | Validate external data and avoid execution | Pass: strict JSON objects, finite normalized enums, no eval or shell interpolation |
| Authentication and sessions | Credentials | N/A: no login; capture rejects URL userinfo |
| Authorization and access control | Local least privilege | Pass: explicit operator invocation, no privileged actions |
| Secrets and cryptography | Redaction, encryption, hook | Pass: WSS-only capture; redacted history/staged scanner; enabled executable hook |
| Data protection and privacy | Minimize fetched data | Pass: metadata only; original public text retained locally as documented, no image fetching |
| Error handling and logging | Terminal controls | Pass: capture diagnostics use ascii; prepare diagnostics/source use safe_text; saved enum domains match constants, scope constant and count labels escaped |
| Dependencies and supply chain | Exact dependency versions | Pass: uv.lock exported frozen for all groups; pip-audit found none; security/demo optional groups excluded from runtime requirements |
| Configuration, build, and CI | Repeatable security gates | Pass: five Makefile security targets, existing hook installation configured; no workflow changes |
| Files, processes, and network | Bounds and no clobber | Pass: 1 MiB frames, queue 4, finite time/count, 2-second close; 4 MiB JSONL reads; capture hard-link publication and prepare exclusive directory reservation |
| Business logic and abuse cases | Observed coverage claims | Pass: weighted counts and retained skit-ID verification; explicitly disclaims global and branch coverage |

## Findings

| ID | Title | Severity | Status | Owner |
|---|---|---|---|---|

No open findings. During review, Neo strengthened output publication against cooperating-writer collisions and validated saved report domains before rendering.

## Root Causes and Recommendations

Keep public input as data and terminal labels as a finite application vocabulary. Capture limits bound each window, not a fixed total memory budget; preparation retains a duplicate identity set proportional to input size and retains source examples. Local operators should size observation windows for their available resources. Saved sketch/YAML artifacts remain local inputs rather than a hardened arbitrary-document upload interface.

## Sign-off

- **Re-review needed:** No, unless security-relevant source or dependency versions change.
- **Risk acceptance:** None; no acceptance bypass or ignored advisories configured.
- **Verification:** scans/hook proof passed; final full-suite gate owned by Trin. Review rubric checked for scope, evidence, all checklist areas, verdict and ownership.

Severity: Info | Verdict: No blocking findings | Owner: Morpheus
