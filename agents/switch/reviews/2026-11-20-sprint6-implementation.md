# Security Review: Sprint 6 generic CLI reports and regression samples

- **Verdict:** No blocking findings
- **Date / reviewer:** 2026-11-20 / Switch
- **Target and version:** Sprint 6 working tree: src/sketchtastic/reporting.py, cli.py integration, examples/bluesky/input.py and demo.py; tests/test_reporting.py inspected
- **Assurance level:** L1 baseline — operator-invoked local analysis, no service, authentication or new dependency
- **Findings:** 0: Critical 0, High 0, Medium 0, Low 0, Info 0
- **Related work:** Sprint 6 design review; owner steering moves report/export/coverage into the generic core CLI

## Next Action

| Who | Does what | By / trigger |
|---|---|---|
| Morpheus | Complete functional review after QA and resolve default profile compilation | Before sprint close |
| Tank | Run required secrets gate on completed changes | Before delivery |

## Scope and Threat Model

- **In scope / out of scope:** generic sketch ranking, sample export, profile-matched coverage and demo input/preparation; excludes re-auditing pre-existing YAML/Profile/Sketch internals, third-party services, and default profile compilation correctness.
- **Assets worth protecting:** existing files, terminal integrity, bounded JSONL reads and trustworthy interpretation of baseline frequencies.
- **Entry points and trust boundaries:** local baseline/profile files chosen by operator; public post and regression JSONL untrusted. Baseline artifacts are local observations, not authenticated provenance. Displayed sample locators are text, not paths automatically opened from metadata.
- **Threats considered:** output clobbering, terminal control injection, malformed input, forged IDs/counts, regression duplicate inflation. No remote session/privilege boundary is introduced. Public posts intentionally remain in exported records.

## Method and Coverage

- **Reviewed by:** manual implementation and relevant contract-test inspection; VIA discovery followed by direct reads of new unindexed files.
- **Tool results:** no make runs or scans in this review per coordination request; root owns final secrets scan and QA owns executing tests. Existing enabled redacted staged hook was checked at design review. No dependencies/build changes proposed by this reviewed implementation.
- **Not covered:** final executed test/scan results, exhaustive hostile YAML documents, resource benchmarks and profile compilation blocker. These are not represented as passed by this report.

## Area Checklist

| Area | What to check | Result |
|---|---|---|
| Input handling and injection | Validation and no code execution | Pass: object-only bounded regression JSONL, strict UTF-8, rejected NaN/Infinity constants, recomputed token IDs; JSON data remains data |
| Authentication and sessions | Credentials/session exposure | N/A: local CLI and unchanged capture |
| Authorization and access control | Local least privilege | Pass: explicit operator-selected files, no privileged operations |
| Secrets and cryptography | New secret handling | N/A: no new secrets or cryptographic protocol; final scan pending |
| Data protection and privacy | Original record retention | Pass: deliberate local export of retained original JSON objects, no new upload |
| Error handling and logging | Terminal output | Pass: tokens serialized with ensure_ascii; paths/errors escaped; rendered raw IDs validated against token hashes |
| Dependencies and supply chain | New dependencies | N/A: none |
| Configuration, build, and CI | Build changes | N/A: no new mechanism in reviewed files |
| Files, processes, and network | Export and resource limits | Pass: validate selected IDs/samples, stage then hard-link output without replace; explicit dangling-symlink rejection; 4 MiB JSONL reads; preparation reserves new directory |
| Business logic and abuse cases | Coverage weights/profile matching | Pass: exact baseline profile identity required, token-derived ID checks, integer nonnegative counts, unique regression IDs, baseline-weighted intersection, empty denominator N/A |

## Findings

| ID | Title | Severity | Status | Owner |
|---|---|---|---|---|

No findings.

## Root Causes and Recommendations

Contract tests inspected cover no-clobber existing/symlink/concurrent paths, escaped terminal tokens, mismatched/missing profile identity, invalid weights, missing retained samples, malformed/oversized regression lines, duplicate regression records and zero denominators. Execute them through the coordinated QA gate. A source profile with unrestricted token cardinality can consume memory proportional to distinct kinds; this remains an operator-controlled local analysis workload. Reports validate identity consistency but do not authenticate baseline data or prove tests executed.

The default Bluesky profile currently has a separately reported compilation-complexity blocker. Security clearance does not clear that functional acceptance issue. Parser-source consultation identified cumulative expression-depth counting with a default limit of 30; no dependency or parser modification was made during consultation.

## Sign-off

- **Re-review needed:** Only for security-relevant implementation changes; functional profile changes require normal QA.
- **Risk acceptance:** None.
- **Verification:** manual security review complete; executed final tests/scans remain with parent/QA. Review rubric checked for scope, evidence, all areas, limitations and ownership.

Severity: Info | Verdict: No blocking findings | Owner: Morpheus
