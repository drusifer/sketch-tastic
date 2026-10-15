# Sprint 2 User Stories: Sort the Show

*   **Total Points**: 2 (Tier 2)
*   **Branch**: `sprint-2`
*   **Source**: owner, 2026-10-14 in session: `show --sort KEY` (top of the backlog since
    fingerling Sprint 15). Owner decisions: sort lowest to highest, no reverse option; KEY is a
    column header in any case; `--top N` is dropped (not needed); the default sort key is the
    record count (`COUNT`), so plain `show` is `show --sort COUNT`.
*   **Status**: Approved (Smith Gates 1 and 2, 2026-10-14)

## Goal

`show` can rank skits by any column, so questions like "which skit carries the most bytes?" are
answered by reading the end of the table instead of grepping YAML.

## Assumptions made for the owner

1. A skit with no value in the sort column (`-`) sorts first, below every value, so the largest
   values are always at the end (`| tail`).
2. Rows with equal values keep file order.
3. Numbers sort as numbers, everything else as text; in a column that mixes them, numbers come
   before text. `%` columns sort by the share itself, not the rounded text.
4. `ID` sorts by the full skit id.
5. If KEY matches one header exactly, that column is used; otherwise it must match exactly one
   header ignoring case. (A token key `count` and the `COUNT` column can both exist.)

---

## STORY-SKT-03: Sort show by a column
**Points:** 2

**As a** user reading a sketch,
**I want** `show --sort KEY` to order the skits by any column,
**so that** I can rank them by count, share, run or aggregate without leaving the table.

### Acceptance Criteria
1. `skt show --sort KEY SKETCH` prints the same columns and rows as `skt show SKETCH`, ordered by
   column KEY, lowest value first. The header stays the first line.
2. Without `--sort`, KEY is `COUNT`: `show` lists the least frequent skit first and the most
   frequent last (was most frequent first). `--help` and the README say so.
3. KEY is any printed header: `ID`, `COUNT`, `COUNT %`, `FIRST RUN`, `LAST RUN`, every aggregate
   value and `%` column (e.g. `payload_bytes.SUM %`), and every token column. Case does not
   matter: `--sort 'count %'` sorts by `COUNT %`.
4. Example: aggregate `size` (SUM) with skits a=40, b=60, c=5 → `--sort size.SUM` lists c, a, b;
   `--sort 'size.SUM %'` lists the same order.
5. Missing values (`-`) sort first; equal values keep file order.
6. An unknown or ambiguous KEY prints
   `sketchtastic: no column 'KEY' in SKETCH; columns: ID, COUNT, ...` (ambiguous:
   `sketchtastic: column 'KEY' is ambiguous in SKETCH: count, COUNT`) to stderr, prints nothing
   on stdout and exits 2.
7. An empty sketch still prints `SKETCH: no skits` with any KEY.
8. `show --help` documents `--sort KEY` with an example
   (`sketchtastic show --sort 'payload_bytes.SUM %' gh.sketch.yaml | tail`) and the exit status
   for a bad KEY. README's `show` section mentions it.

---

## Out of Scope
- `--top N` and any reverse/descending option (owner: not needed; use `| tail` / `| head`).
- Sorting by more than one key.
- Changes to columns or formatting.

## Open Questions
None.

---

## Architecture (Morpheus)

Tier 2: stories and architecture in one document. One module (`cli.py`), no new mechanism, no
new dependency, so there is no Tank phase.

**D1 — Columns as data.** Today `_show_table` builds the header and `_show_row` builds the cells
in parallel lists. Replace both with one list of columns, each `(header, value, cell)`:
`value(fid, skit)` returns the raw value (full id, count, share float, aggregate value, token
value, or `None`), and `cell(value)` formats it (`fid[:8]`, `_cell`, `_percent`, token text). The
header row and every data row are produced from that list, so the printed table is unchanged and
sorting can read raw values. Existing `ShowTests` must pass unmodified (refactor first, green,
then the feature).

**D2 — Sort.** `show` gains `--sort KEY` (metavar `KEY`). `_find_column(columns, key)` applies
assumption 5 and raises a small error carrying the message of AC6; `_cmd_show` turns it into
stderr + `EXIT_NOT_WRITTEN` (2). `--sort` defaults to `COUNT`. Rows start in file order and
get one stable `sorted(..., key=lambda r: _sort_key(column.value(*r)))` with
`_sort_key(v) = (0, 0)` for `None`, `(1, v)` for `int`/`float` (not `bool`), else `(2, str(v))`.

**D3 — Docs.** `_SHOW_EPILOG` gains the example and `2  SKETCH could not be read, or KEY is not
one of its columns`; the `show` description says least frequent first by default and mentions
`--sort`; README `show` section one line. The default-order change is breaking (0.x, no shim):
`feat(cli)!` with a `BREAKING CHANGE:` footer; `ShowTests` expectations that assumed most
frequent first are updated in the same commit (the refactor commit stays order-neutral).

**Build environment:** none.
