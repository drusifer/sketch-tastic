# Task Board

**No sprint in flight.** Last sprint: 1 (below). Next: fingerling depends on this repository (after it is pushed).

## Sprint 1: Move and Rename

**Status:** Complete — launched 2026-10-14 (5/5 pts); merged to `main`; no release (mainline)
**Branch:** `sprint-1` (merged and deleted)
**Record:** `agents/chat_archive/CHAT_SPRINT_1.diagram.md`

### Stage 0: Import and build environment — Tank
- [x] Import `packages/fingerprint-sampler` from fingerling with history (subtree split, 31 commits).
- [x] Build environment at the root: `pyproject.toml` dev group + ruff, `Makefile`, `uv.lock`, `.python-version`, `.githooks`, CI/publish workflows (manual CI).
- [x] `docs/SDLC.md`, `docs/DECISIONS.md`.

**Source:** `docs/sprints/USER_STORIES_SPRINT1.md` (stories + architecture D1-D3) · **Points:** 5 · **Tier:** 2

### Phase 1: New names (STORY-SKT-01, D1) — Neo
- [x] **1.1** `src/sketchtastic`, pyproject name/scripts/URLs/tagline, `prog` from argv, `--version`; Makefile `CLI`; `uv lock`. [Neo]
- [x] **1.2** UAT + review. [Trin, Morpheus]

### Phase 2: Sketch and skit (STORY-SKT-02, D2) — Neo
- [x] **2.1** Module/class/key/flag/message renames; README and help. [Neo]
- [x] **2.2** UAT + review. [Trin, Morpheus]

### Close
- [x] Tank `*devops sdlc-check` · Oracle groom · Smith user test · retro + launch · chat report · merge [Tank, Oracle, Smith, All]

## Backlog (unscheduled)
Carried over from fingerling's `task.md`:
- Test-internal names still say fingerprint (`wh`, `fingerprints` variables, test class names) — rename (Sprint 1 retro).
- `show --sort KEY` (any column, including `%` columns) and `--top N` — top priority.
- History weight: merge ~1.7x slower since history (second fold); fold once and derive the run.
- `-o`: owner may revisit (keep or drop).
- In-run duplicate detection if a stream needs it.
- JSON Schema for sketch files; set-to-set (sketch-to-sketch) merge; more aggregate ops (`LEN`, `ABS`).
