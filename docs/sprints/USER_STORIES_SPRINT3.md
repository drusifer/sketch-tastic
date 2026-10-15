# Sprint 3 User Stories: Faster Merge

*   **Total Points**: 5 (Tier 2)
*   **Branch**: `sprint-3`
*   **Source**: owner, 2026-10-14 in session: performance tuning with a profiler. Owner decisions:
    target `merge` on the GH Archive hour; profile through a `make profile` target with the
    standard-library cProfile (no new dependency); best effort within KISS, report before/after
    wall time.
*   **Status**: Draft

## Goal

`merge` is fast enough that an hour of GitHub events folds in a fraction of today's time, with
byte-identical output, and anyone can measure it again with one make target.

## Baseline (`make profile`, 2024-01-01-15, 180,387 events, this Raspberry Pi 5)

Wall time without the profiler: **109.5 s**. Under cProfile (306 s, 424M calls):

| Hot spot | Cumulative | Cause |
|---|---|---|
| `Path.values` → python-jsonpath `findall` | 146 s (48%) | every field and aggregate path goes through the general JSONPath matcher (selector objects, match nodes, a canonical JSON path string per match), even plain `$.a.b` |
| `Sketch.upsert` called 360,774 times | 229 s | each event is folded twice, into the sketch and into the run file (history), so every aggregate path is evaluated twice |
| `copy.deepcopy` (built-in FIRST/LAST of the whole event) | 51 s (17%) | LAST deep-copies every event, twice |

## Assumptions made for the owner

1. "Same output" means the sketch file and the run file are byte-identical to what the current
   code writes for the same input on the same day.
2. Plain paths (`$`, `$.name.name...`) are the common case; other JSONPath features
   (wildcards, filters, indexes, quoted names) keep using python-jsonpath unchanged.
3. No change to the profile format, the sketch format, the CLI or the library API.

---

## STORY-SKT-04: Measure merge
**Points:** 1

**As a** maintainer,
**I want** `make profile` to time and profile the GH Archive merge,
**so that** I can find where `merge` spends its time and check a speed-up, without ad hoc commands.

### Acceptance Criteria
1. `make profile` downloads the hour once (shared with `make gharchive`), merges it into a fresh
   sketch under `build/profile/` (never touching `data/gharchive/gh.sketch.yaml`), and prints
   the wall time without the profiler, a short hash of the sketch written, and the top 25
   functions by own time and by cumulative time.
2. The full report is in `build/profile/profile.txt`; `make clean` removes it.
3. `docs/SDLC.md` lists the target.

## STORY-SKT-05: Faster merge, same output
**Points:** 4

**As a** user merging large streams,
**I want** `merge` to take much less time,
**so that** an hour of GitHub events is quick to fold and re-fold.

### Acceptance Criteria
1. `make profile` reports a lower wall time than the 109.5 s baseline; the before/after times
   and the remaining top hot spots are recorded in the sprint chat and `docs/DECISIONS.md`.
2. The sketch hash `make profile` prints is unchanged from the baseline (same day), and every
   existing test passes unmodified.
3. A plain path selects exactly what python-jsonpath selects, including a missing key, a `null`
   value, a list or string where an object is expected, and names such as `true`, `null` and
   `length` (tested against python-jsonpath directly).
4. A saved sketch never contains YAML anchors or aliases (`&id`, `*id`), even when FIRST and LAST
   hold the same event.

---

## Out of Scope
- `show`, `check` and profile loading (fast already).
- Multiprocessing, C extensions, new dependencies, a different JSON parser.
- Changing what history stores (run files stay as they are).

## Open Questions
None.

---

## Architecture (Morpheus)

Tier 2: stories and architecture in one document. One new make target (mechanism change, owner
approved, Tank's Phase 0); otherwise code in `model.py`, `aggregators.py`, `sketch.py` and
`cli.py`.

**D1 — `make profile` (Tank).** As in STORY-SKT-04: a timed run, then
`python -m cProfile -o build/profile/profile.out -m sketchtastic merge ...`, then `pstats`
(top 25 by `tottime` and `cumulative`). The GH Archive download becomes a file rule both
targets depend on.

**D2 — Plain-path fast path.** In `model.py`, `_compile_path` returns either the compiled
python-jsonpath object or, when the text matches `^\$(\.[A-Za-z_][A-Za-z0-9_]*)*$`, a
`_PlainPath(names)` whose `findall(value)` walks `dict`s: each name must be a key of a `dict`,
else `[]`; at the end, `[value]`. `Path.values` is unchanged (it calls `findall`). Equivalence is
tested against `jsonpath.findall` over a table of documents (AC3).

**D3 — Select once, fold twice.** Split `Aggregate.update` into `select(event) -> list` (path,
then op or type conversion) and `fold(states, values) -> skipped`; `update` stays as
`fold(states, select(event))`. `Sketch.select(record, run)` returns the selected values of the
profile and built-in aggregates for one event; `Sketch.upsert` takes an optional `selected=`
and folds those instead of reading the record again. `_fold_stream` selects once per event and
passes the selection to both `run.upsert` and `sketch.upsert` (both sketches are built from the
same profile aggregates).

**D4 — No deep copies.** FIRST and LAST store the value itself. Events come fresh from
`json.loads` per line and nothing mutates stored state, so sharing is safe; the only reason for
the copy was YAML writing anchors for an object stored twice. `Sketch.save` uses a `SafeDumper`
subclass with `ignore_aliases` returning `True`, so output stays alias-free (AC4) and identical.

**D5 — Stop rule.** After D2-D4, Neo re-runs `make profile`. A further change is made only if one
function still dominates and the fix is local and simple; otherwise the sprint stops and the
remaining hot spots go to the backlog.

**Build environment:** one new standard make target, `profile` (Phase 0, Tank). No dependency.
