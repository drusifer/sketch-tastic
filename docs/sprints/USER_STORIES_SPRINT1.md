# Sprint 1 User Stories: Move and Rename

*   **Total Points**: 5 (Tier 2)
*   **Branch**: `sprint-1`
*   **Source**: owner, 2026-10-14 in session (fingerling): move the tool to `drusifer/sketch-tastic`; command `sketchtastic` plus a short alias `skt`; rename the vocabulary during the move — the set is a **sketch**, one fingerprint is a **skit**; keep history; fingerling depends on this repository through git.
*   **Status**: Approved (Smith Gates 1 and 2, 2026-10-14)

## Goal

The tool lives in its own repository under its own name, and speaks one vocabulary: you
**merge** events into a **sketch**, and a sketch holds **skits**, one per distinct event shape.
Nothing about how it counts, aggregates, shares, deduplicates or keeps history changes.

## Assumptions made for the owner

1. The short alias is `skt`; it is not an existing command on this machine.
2. Skit ids are computed exactly as fingerprint ids were (same tokens → same MD5), so an id
   seen before the move means the same shape after it.
3. "Fingerprint" survives only as a verb in the docs ("how to fingerprint an event"); every noun
   becomes sketch or skit. The profile keeps its name.
4. Existing set files are not converted (0.x, no migration): they are rebuilt from events.
5. The README title is `sketch-tastic` (the repository name); your stub's tagline
   "Mergeable sketches of JSONL event streams for regression testing and flow analysis" becomes
   the description.

---

## STORY-SKT-01: Install and run as sketch-tastic
**Points:** 2

**As a** user,
**I want** to install `sketch-tastic` and run it as `sketchtastic` or `skt`,
**so that** the tool's name matches its repository and is short to type.

### Acceptance Criteria
1. The built wheel is `sketch_tastic-<version>-py3-none-any.whl`. Installing it provides the
   commands `sketchtastic` and `skt`, which behave identically, and `python -m sketchtastic`.
2. `sketchtastic --version` prints `sketch-tastic <version>`. `--help` shows the program name
   `sketchtastic` (and `skt` when run as `skt`).
3. The library is imported as `sketchtastic`; `fingerprint_sampler` no longer exists.
4. The package description and README use the tagline. Repository URLs point to
   `drusifer/sketch-tastic`, including the schema `$id` and the editor hint.
5. `make gharchive`, `make run`, `make build` and `make smoke` use the new command.

## STORY-SKT-02: Sketches and skits
**Points:** 3

**As a** user reading commands, output and files,
**I want** one consistent vocabulary,
**so that** "sketch" always means the file and "skit" always means one entry in it.

### Acceptance Criteria
1. `merge` takes `-s/--sketch SKETCH` (no `--set`). Example:
   `skt merge -p web.yaml -s web.sketch.yaml events.jsonl`. History goes to
   `web.sketch.history/<run id>.yaml`.
2. The summary reads `  skits: <n> new, <m> updated, <t> total in sketch`. Every message that
   said "set" or "fingerprint(s)" says "sketch" or "skit(s)", for example
   `cannot use sketch file: ...`, `<SKETCH>: no skits`, and `--force-profile` help.
3. A sketch file's entries are under `skits:` (was `fingerprints:`). `show` reads it.
4. The library exposes `Sketch`, `Skit`, `SketchError`, `ProfileMismatchError` and `skit_id`.
   `FingerprintSet`, `Fingerprint` and `fingerprint_id` are gone.
5. A skit's id is unchanged from the fingerprint id of the same tokens (test with a known
   value).
6. README and help texts use the vocabulary throughout, and the README explains it in one
   sentence near the top.

---

## Out of Scope
- fingerling's switch to depend on this repository (it follows once this repository is pushed).
- Any behaviour change.
- Releasing to PyPI (mainline development).

## Open Questions
None.

---

## Architecture (Morpheus)

Tier 2: stories and architecture in one document. Names and paths change, not mechanisms, so
there is no Tank phase; Tank updates SDLC section 11 and the targets table at close.

**D1 — Package.** `git mv src/fingerprint_sampler src/sketchtastic`. In `pyproject.toml`:
`name = "sketch-tastic"`, the description is the tagline, keywords gain `sketch`, URLs point to
`drusifer/sketch-tastic`, `[project.scripts]` has `sketchtastic` and `skt`, both
`sketchtastic.__main__:main`, and hatch builds `src/sketchtastic`. `prog` comes from
`os.path.basename(sys.argv[0])` (falling back to `sketchtastic`), so help shows the name it was
invoked as. `--version` prints `sketch-tastic <version>`. Run `uv lock`.

**D2 — Modules and names.** `fingerprint_set.py` → `sketch.py`. `FingerprintSet` → `Sketch`,
`Fingerprint` → `Skit`, `FingerprintSetError` → `SketchError`, `fingerprint_id` → `skit_id`
(same hashing), `SET_VERSION` → `SKETCH_VERSION`. The file key `fingerprints` → `skits`. In the
CLI, `--set`/`set_path` → `--sketch`/`sketch_path`, and `_open_set` → `_open_sketch`. All
messages are reworded per STORY-SKT-02 AC2. `__init__.__all__` is updated.

**D3 — Order.** Phase 1 does D1 only, with the old vocabulary still in place, and keeps all
tests green. Phase 2 does D2 and the docs. Each is a mechanical rename, followed by grep for
leftovers (`fingerprint_sampler`, `FingerprintSet`, `--set`, `fingerprints:`).

**Build environment:** names only (Makefile `CLI` variable, gharchive output path); no new
mechanism.
