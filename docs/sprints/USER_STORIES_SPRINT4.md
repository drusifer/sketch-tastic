# Sprint 4 User Stories: Parallel Merge

*   **Total Points**: 5 (Tier 2)
*   **Branch**: `sprint-4`
*   **Source**: owner, 2026-10-14 in session: feed the stream to a worker pool and merge each
    worker's sketch at the end. Owner decisions: processes (not threads); `-j/--jobs N`, default
    all cores; FIRST/LAST need not be exact ("any matching skit is indistinguishable"), so
    partial sketches merge in the order they finish.
*   **Status**: Approved (Smith Gates 1 and 2, 2026-10-14)

## Goal

`merge` uses every core, so the GH Archive hour folds in a fraction of 32.88 s
(`make profile`, single process, after the post-Sprint 3 fixes).

---

## STORY-SKT-06: Merge with a worker pool
**Points:** 4

**As a** user merging large streams,
**I want** `merge` to fold events on all cores,
**so that** big inputs finish several times faster.

### Acceptance Criteria
1. `merge -j N` / `--jobs N` uses N worker processes; the default is the number of cores.
   `-j 1` folds in-process, as today. N must be at least 1 (else a usage error, exit 2).
2. With any N, the sketch has the same skits, tokens, counts, sums, MIN/MAX, AVG,
   first_seen/last_seen, sequence mark and summary line as with `-j 1`. FIRST/LAST samples come
   from matching events but not necessarily the first/last ones.
3. Skipped-line warnings name the right line numbers and are listed in line order, at most
   10, as today. An event without the declared sequence still fails the run and writes nothing.
4. Input that fits in one batch is folded in-process (no pool start-up cost).
5. Memory stays bounded: at most 2 batches per worker are in flight.
6. `merge --help` and the README document `-j` and the FIRST/LAST caveat.

## STORY-SKT-07: Measure parallel merge
**Points:** 1

### Acceptance Criteria
1. `make profile` prints the wall time with the default jobs and with `-j 1`; the hash comes
   from the `-j 1` run (deterministic); cProfile profiles `-j 1` (workers are not profiled).

---

## Out of Scope
- Threads / free-threaded Python. Exact FIRST/LAST across workers (would need a position stamp
  in the envelope; owner: not needed).

## Architecture (Morpheus)

**D1 — One fold, two drivers.** `_fold_lines(numbered_lines, profile, run_id, mark_path, mark)`
folds `(lineno, line)` pairs into a fresh run `Sketch` and returns it with its stats, its
sequencer counts (dropped, low, high) and up to 11 `(lineno, reason)` warnings. `-j 1` (or one
batch) calls it directly; the pool calls it per batch.

**D2 — Pool.** `concurrent.futures.ProcessPoolExecutor(max_workers=N)`; the parent reads the
stream in batches of `_BATCH_LINES` (5,000) and keeps at most `2 * N` futures in flight; as each
completes (`wait(..., FIRST_COMPLETED)`) its run sketch is merged into the run with
`Sketch.merge`, stats are summed, sequencer counts combined, warnings collected. A worker's
`_NotWritten` re-raises in the parent; remaining futures are cancelled.

**D3 — Warnings** are printed after folding, sorted by line, first 10, then the "further
skipped lines" note, so the output does not depend on completion order.

**D4 — make profile (Tank).** Timed run with default jobs, timed run with `-j 1` + hash,
cProfile with `-j 1`.

**Build environment:** the `profile` target changes (D4); no dependency.
