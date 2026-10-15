# Task Board

## Sprint 1: Move and Rename

**Status:** In progress — Stage 0 done (Tank)
**Branch:** `sprint-1`

### Stage 0: Import and build environment — Tank
- [x] Import `packages/fingerprint-sampler` from fingerling with history (subtree split, 31 commits).
- [x] Build environment at the root: `pyproject.toml` dev group + ruff, `Makefile`, `uv.lock`, `.python-version`, `.githooks`, CI/publish workflows (manual CI).
- [x] `docs/SDLC.md`, `docs/DECISIONS.md`.

## Backlog (unscheduled)
Carried over from fingerling's `task.md`:
- `show --sort KEY` (any column, including `%` columns) and `--top N` — top priority.
- History weight: merge ~1.7x slower since history (second fold); fold once and derive the run.
- `-o`: owner may revisit (keep or drop).
- In-run duplicate detection if a stream needs it.
- JSON Schema for sketch files; set-to-set (sketch-to-sketch) merge; more aggregate ops (`LEN`, `ABS`).
