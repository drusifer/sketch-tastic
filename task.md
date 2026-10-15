# Task Board

**No sprint in flight.** Last sprint: 4 (below). fingerling depends on this repository (pin at 849b4ec, merged locally in fingerling, not yet pushed).

## Sprint 4: Parallel Merge

**Status:** Complete — launched 2026-10-15 (5/5 pts); merged to `main`; no release (mainline)
**Branch:** `sprint-4` (merged and deleted)
**Record:** `agents/chat_archive/CHAT_SPRINT_4.diagram.md`
**Source:** `docs/sprints/USER_STORIES_SPRINT4.md` (STORY-SKT-06..07 + architecture D1-D4) · **Points:** 5 · **Tier:** 2
**Result:** `make profile` parallel 13.54 s (4 cores), `-j 1` 29.55 s; libyaml for all YAML

- [x] **1** `_fold_lines` as the one fold; `-j N`; workers + bounded task queue + output queue (after a pool version and a shared-memory version were measured and dropped). [Neo, owner]
- [x] **2** `make profile`: all cores and `-j 1`, `PROFILE_ARGS`. [Tank]
- [x] **3** libyaml everywhere (`sketchtastic._yaml`); docs for `-j`. [Neo]
- [x] Close: Tank `*devops sdlc-check` · Oracle groom · Smith user test · retro + launch · chat report · merge [All]

Between Sprints 3 and 4 (owner review of Sprint 3): JSONPath via `jsonpath-rfc9535` (no shortcut), fold once then merge (`Sketch.merge`), no FIRST/LAST copies.

## Sprint 3: Faster Merge

**Status:** Complete — launched 2026-10-14 (5/5 pts); merged to `main`; no release (mainline)
**Branch:** `sprint-3` (merged and deleted)
**Record:** `agents/chat_archive/CHAT_SPRINT_3.diagram.md`
**Source:** `docs/sprints/USER_STORIES_SPRINT3.md` (STORY-SKT-04..05 + architecture D1-D5) · **Points:** 5 · **Tier:** 2
**Result:** `make profile` 106.35 s → 40.83 s (2.6x), 180,387 events, byte-identical sketch

### Phase 0: make profile (STORY-SKT-04, D1) — Tank
- [x] **0.1** `profile` target (timed run, sketch hash, cProfile top 25); shared download rule; `clean` removes `build/profile`; SDLC targets table; `build:` commit. [Tank]

### Phase 1: Plain-path fast path (STORY-SKT-05 AC3, D2) — Neo
- [x] **1.1** Equivalence tests vs python-jsonpath first; `_PlainPath`; `make test`; `make profile` (time + hash). [Neo]
- [x] **1.2** UAT + review; `perf:` commit. [Trin, Morpheus]

### Phase 2: Select once, no deep copies (STORY-SKT-05 AC1-AC4, D3-D5) — Neo
- [x] **2.1** Alias test first; `Aggregate.select/fold`, `Sketch.select`, `upsert(selected=)`, `_fold_stream`; FIRST/LAST without deepcopy + alias-free dumper; `make profile`; D5 stop rule. [Neo]
- [x] **2.2** UAT + review; `perf:` commit. [Trin, Morpheus]

### Close
- [x] Tank `*devops sdlc-check` · Oracle groom (DECISIONS: before/after) · Smith user test · retro + launch · chat report · merge [Tank, Oracle, Smith, All]

## Sprint 2: Sort the Show

**Status:** Complete — launched 2026-10-14 (2/2 pts); merged to `main`; no release (mainline)
**Branch:** `sprint-2` (merged and deleted)
**Record:** `agents/chat_archive/CHAT_SPRINT_2.diagram.md`
**Source:** `docs/sprints/USER_STORIES_SPRINT2.md` (STORY-SKT-03 + architecture D1-D3) · **Points:** 2 · **Tier:** 2

### Phase 1: Columns as data (D1) — Neo
- [x] **1.1** Refactor `show` to one column list `(header, value, cell)`; table unchanged, `ShowTests` green unmodified; `refactor(cli)` commit. [Neo]
- [x] **1.2** Trin: `make test` + `make lint` green, no test edits · Morpheus review. [Trin, Morpheus]

### Phase 2: --sort KEY, default COUNT (D2, D3) — Neo
- [x] **2.1** Tests first for AC1-AC8; `--sort` (default `COUNT`), key lookup and exit 2, stable sort; help epilog + README; `feat(cli)!` commit with `BREAKING CHANGE:` footer. [Neo]
- [x] **2.2** Trin UAT against AC1-AC8 · Morpheus review. [Trin, Morpheus]

### Close
- [x] Tank `*devops sdlc-check` · Oracle groom · Smith user test · retro + launch · chat report · merge [Tank, Oracle, Smith, All]


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
- `-o`: owner may revisit (keep or drop).
- In-run duplicate detection if a stream needs it.
- JSON Schema for sketch files; set-to-set (sketch-to-sketch) merge; more aggregate ops (`LEN`, `ABS`).
- **Profile evolution (future sprint, owner 2026-10-15):** updating a sketch's profile, and what adding or removing fields does to existing skits. Revisit the two ids then: the skit id (token values) vs the profile id (a hash of the field specs that guards `merge`); e.g. store the fields in the sketch header instead of a hash, or drop the check.
