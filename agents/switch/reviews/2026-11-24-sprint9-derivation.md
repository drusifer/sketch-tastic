# Security Review: Sprint 9 Structured Core and Derivation

- **Verdict:** No blocking findings — final reviewed implementation and integration checks clear.
- **Date / reviewer:** 2026-11-24 / Switch, independent review agent.
- **Target and version:** `sprint-9` working changes in `model.py`, `profile.py`, `sketch.py`,
  `derive.py`, `_derive_validation.py`, `derive_io.py`, `derive_cli.py` and focused tests.
- **Assurance level:** L2 standard — local-file integrity, safe publication and untrusted YAML.
- **Findings:** 0 open security findings; 4 correctness/validation findings resolved by Neo.
- **Related work:** SKT-19/20/21, S9-D1..D7, revised design gate.

## Next Action

| Who | Does what | By / trigger |
|---|---|---|
| Morpheus | Complete architecture gate and approve phase commits | After this security gate |
| Tank | Execute SDLC closeout before launch | After phase commits |

## Scope and Threat Model

- **In scope:** Canonical token validation and keyed identity, conservative profile proof rules,
  raw aggregate/header validation, no-clobber bundle publication, rollback ownership and CLI errors.
- **Out of scope:** Dashboard JavaScript independently reviewed by structured-core owner;
  preexisting capture/profile changes; package release and concurrent malicious filesystem actors.
- **Assets:** Existing source sketches/history, destination files, exact counts/statistics and
  future duplicate-protection marks.
- **Entry points:** Caller-supplied profiles, sketch/history YAML and output paths. All operations
  use local user filesystem permissions; no network, secrets, subprocess evaluation or services.
- **Threats:** Tampering/corruption through malformed state, clobbering via aliases/symlinks,
  misleading partial-publication success, terminal injection in error text. Credential/session
  threats do not apply to this local command.

## Method and Coverage

- Manual code/diff inspection of the target files, their token/aggregate/publication helpers and
  focused tests. Original four findings independently re-reviewed after fixes and regression tests.
- Gitleaks prerequisite check: version 8.26.0 available; `.githooks/pre-commit` executable and
  calls `gitleaks git --pre-commit --staged --redact`; `core.hooksPath=.githooks`.
- Root executed `bobp make security-scan-secrets`: 128 commits, no leaks (00:58:50 CHAT evidence).
- No separate dependency audit required for this phase: no manifest/dependency changes.
- Root owns integration execution; reviewer runs no duplicate suites. Derivation12, CLI8,
  full364 tests and lint passed after helper cleanup/final show-cell fix. Quality reports no
  extended ruff, vulture or radon C+ findings. Final CLI display safely escapes controls and
  distinguishes missing/null/literal/array token values.
- **Not covered:** Crash-atomic transactions across multiple paths and concurrent source mutation,
  both documented exclusions. No unsupported security guarantee is made for them.

## Area Checklist

| Area | Result |
|---|---|
| Input handling and injection | Pass: safe YAML loader, explicit profile/token/state validation, no eval or shell interpolation |
| Authentication and sessions | N/A: local CLI has no authentication/session surface |
| Authorization and access control | Pass: normal process filesystem permissions; source/output and history aliases refused |
| Secrets and cryptography | Pass: staged hook active, secret scan clear; existing MD5 is identity hashing, not authentication |
| Data protection and privacy | Pass: no network/exfiltration path; original samples copied only into requested derived artifacts |
| Error handling and logging | Pass: terminal-safe exception/output formatting; existing-output guidance corrected |
| Dependencies and supply chain | N/A: no dependency changes; existing lockfile unchanged |
| Configuration, build and CI | Pass: existing Makefile gates and hook used; no pipeline changes |
| Files, processes and network | Pass: regular source/history checks, symlink refusal, exclusive hard-link publication, inode-aware owned cleanup |
| Business logic and abuse cases | Pass: one result per old skit, unsupported refinements refused, counts/state cannot be filled from absent statistics |

## Findings

| ID | Title | Severity | Status | Owner |
|---|---|---|---|---|
| QA-S9-01 | Required predicate keys/domain validation | Correctness | Fixed and reviewed | Neo |
| QA-S9-02 | Canonical histogram bin/state validation | Correctness | Fixed and reviewed | Neo |
| QA-S9-03 | Continuation sequence/last-run validation | Correctness | Fixed and reviewed | Neo |
| QA-S9-04 | Nonexistent --force recovery hint | UX | Fixed and reviewed | Neo |

No open security findings. These QA findings were raised before gate signoff; no risk acceptance.

## Root Causes and Recommendations

Generic loaders initialize missing state and generic output helpers mention overwrite flags;
derivation needs stricter validation and command-specific recovery instructions. Fixes enforce
those boundaries. Keep regression tests alongside the new derivation behavior.

## Sign-off

- **Re-review needed:** Only if production code changes after this review.
- **Risk acceptance:** None.
- **Verification:** Focused tests, full364, lint, quality and secret scan passed. All phase
  findings resolved; no risk acceptance requested or made.
