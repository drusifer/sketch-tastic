# Security Review: Sprint 6 post-level regression explorer design

- **Verdict:** No blocking findings
- **Date / reviewer:** 2026-11-20 / Switch
- **Target and version:** docs/sprints/USER_STORIES_SPRINT6.md, Sprint 6 proposed demo replacement and current capture/demo trust boundaries
- **Assurance level:** L1 baseline — local operator-driven public-data analysis without credentials or a server
- **Findings:** 0: Critical 0, High 0, Medium 0, Low 0, Info 0
- **Related work:** Sprint 6 stories STORY-SKT-10/11; Sprint 5 security reviews

## Next Action

| Who | Does what | By / trigger |
|---|---|---|
| Mouse | Proceed to implementation with the safeguards below | Design gate clear |
| Switch | Review actual export, generic output and coverage paths | Implementation gate after Trin |

## Scope and Threat Model

- **In scope / out of scope:** proposed prepare/report/export/coverage commands and unchanged capture boundary; excludes core package internals, Bluesky infrastructure and future application execution of exported test data.
- **Assets worth protecting:** local output files, terminal integrity, bounded input resources and accurate baseline coverage measurements.
- **Entry points and trust boundaries:** captured public JSONL and regression records are untrusted; operator-selected profiles define identity. Saved local baseline artifacts are not an authenticated dataset. No operation executes source post contents.
- **Threats considered:** terminal escape injection through generic tokens/profile labels, output overwrite and path misuse, malformed/oversized JSON, incorrect coverage through duplicate regression samples or trusting supplied IDs/counts. Public metadata may include personal text and identifiers; exports retain it intentionally. Authentication/session and remote privilege attacks are inapplicable because no service or credentials are introduced.

## Method and Coverage

- **Reviewed by:** read story/design, current demo/capture and existing hook configuration; no implementation claimed for proposed changes.
- **Tool results:** read-only inspection confirms gitleaks on PATH, hook invoking staged redacted git scan and core.hooksPath=.githooks. No make or security scans run: design-only task, no dependency/build changes authorized.
- **Not covered:** Sprint 6 implementation and tests are pending; scans are not fresh evidence for later code changes.

## Area Checklist

| Area | What to check | Result |
|---|---|---|
| Input handling and injection | External data boundaries | Pass: planned bounded JSONL, profile-driven data evaluation, escaped terminal rendering |
| Authentication and sessions | Credentials/session exposure | N/A: local commands and unchanged public capture |
| Authorization and access control | Least privilege | Pass: operator-controlled paths, no elevated actions |
| Secrets and cryptography | Secret handling | Pass: unchanged WSS capture, no new secrets, enabled staged hook |
| Data protection and privacy | Data retention | Pass: original public posts deliberately retained/exported locally; no additional network disclosure |
| Error handling and logging | Escape external text | Pass: design explicitly retains escaping; generic labels/tokens must be included |
| Dependencies and supply chain | Dependency changes | N/A: no changes proposed |
| Configuration, build, and CI | Build changes | N/A: no changes proposed |
| Files, processes, and network | Safe export/publication | Pass: fresh-output requirement, bounded reads and unchanged capture limits |
| Business logic and abuse cases | Coverage integrity | Pass: saved profile, recomputed regression IDs, set intersection and baseline weights |

## Findings

| ID | Title | Severity | Status | Owner |
|---|---|---|---|---|

No findings.

## Root Causes and Recommendations

Implementation review must verify:

- Removing fixed enum validation requires escaping every profile key, token, path and error string printed to the terminal. Original records remain unchanged in JSONL, rather than terminal-sanitized in storage.
- Apply bounded JSONL reading to regression input as well as baseline input; reject malformed records before publishing results.
- Validate all selected kind IDs before export; publish a complete fresh file using exclusive creation or no-replace hard links, including dangling-symlink and collision checks. Do not derive output filenames or files to open from arbitrary token/index values.
- Use the saved profile consistently across baseline and regression, verify artifact/profile compatibility, and sum baseline counts only once per covered kind. Explicitly handle empty denominators. Sample locations are provenance, not execution directives.
- Keep observation-scope and sample-representation caveats; a frequency-weighted score is neither global prevalence nor evidence that tests ran. Original public text remains in exported files.

## Sign-off

- **Re-review needed:** Yes, separate implementation security gate.
- **Risk acceptance:** None.
- **Verification:** design reviewed; no test or scan runs for this design-only task. Review rubric checked for explicit scope, evidence, checklist and ownership.

Severity: Info | Verdict: No blocking findings | Owner: Mouse
