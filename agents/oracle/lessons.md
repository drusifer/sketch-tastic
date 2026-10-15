# Project Lessons Learned

This file contains critical lessons and rules derived from past errors, technical discoveries, and architectural decisions. All agents MUST review this file before starting new implementation or architectural tasks.

---

## 2026-10-14 — Look for the contract before removing a defensive copy (Sprint 3)

**What happened:** Phase 2 removed `copy.deepcopy` from FIRST/LAST for speed, reasoning that
nothing mutates events. Two existing tests failed: they pin a library contract (a stored sample
never aliases the caller's record). A pre-check had grepped tests for `copy`, which misses
`copies` and `alias`.
**Rule:** Before removing a copy, lock or check, search the tests for the behaviour it protects
(`copies|copy|alias|mutat`), not just the call. If a contract exists, make the protection cheaper
(copy once, specialise it) instead of removing it.
