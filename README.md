# sketch-tastic

Mergeable sketches of JSONL event streams for regression testing and flow analysis.

`sketch` reads events — logs, traces, audit records, anything with one JSON object per
line — and reduces each to a **skit**: a stable ID for "this shape of event". It keeps a
**sketch** (the data-sketch term for a compact, mergeable summary of a stream) with one entry per
skit: how often it was seen, statistics you ask for, and a sample. The sketch is a file that
grows across runs:

```
existing sketch  +  stream of events  ->  updated sketch
```

A million near-identical log lines become a handful of entries you can actually read.

**Contents:** [Install](#install) · [Quickstart](#quickstart) · [Usage](#usage) ·
[Regression data coverage](#regression-data-coverage) · [Derive a new sketch](#derive-a-new-sketch) ·
[Profiles](#profiles) · [The sketch](#the-sketch) · [As a library](#as-a-library) ·
[Bluesky demo](#bluesky-demo) · [Documentation](#documentation)

## Install

```sh
pip install sketch-tastic
```

Python 3.14 or newer. Installs the `sketch` command (also runnable as `python -m sketchtastic`).

Moved from [drusifer/fingerling](https://github.com/drusifer/fingerling), where it was
`fingerprint-sampler`. While the version is 0.x, releases may break profiles and sketch files
without a migration path.

## Quickstart

Paste this into a shell. It writes a profile and a few events, then sketches them:

```sh
cat > profile.yaml <<'YAML'
version: 0
fields:
  - {key: level,     path: "$.level"}
  - {key: component, path: "$.logger"}
  - {key: failed,    path: "$.error", modifier: IS_PRESENT}
aggregates:
  - {key: took_ms, path: "$.took_ms", fn: [MIN, MAX, AVG]}
  - {key: example, path: "$.msg",     fn: {name: LAST, n: 2}}
YAML

cat > events.jsonl <<'JSONL'
{"level": "INFO", "logger": "db", "msg": "query ok", "took_ms": 3}
{"level": "INFO", "logger": "db", "msg": "query ok (cached)", "took_ms": 1}
{"level": "ERROR", "logger": "db", "msg": "query timed out", "error": "TimeoutError", "took_ms": 5000}
{"level": "INFO", "logger": "http", "msg": "GET /health", "took_ms": 0.4}
JSONL

sketch merge -p profile.yaml -s app.sketch.yaml events.jsonl
```

```
sketch: 4 events read from events.jsonl
  skits: 3 new, 0 updated, 3 total in sketch
  skipped: 0 malformed lines, 0 unusable aggregate values
  wrote app.sketch.yaml (profile 3f0dd0d9f280ba32064a891dcd3b17cb)
  history: app.sketch.history/261014-0001.yaml
```

Four events, three skits: the two successful `db` queries share one. Run the same command
again and the counts add up instead of new entries appearing — that is the merge. Each run also
leaves a file with just its own skits in `app.sketch.history/` (see History below).

`app.sketch.yaml` now uses sketch format 1 (the other two skits follow):

```yaml
version: 1
profile_id: 3f0dd0d9f280ba32064a891dcd3b17cb
last_run: 261014-0001
skits:
  549439e519c9cad471036ab7ebb4e2a6:
    tokens:
      level: INFO
      component: db
      failed: 'FALSE'
    aggregates:
      took_ms:
        MIN: 1
        MAX: 3
        AVG:
          avg: 2.0
          sum: 4
          count: 2
      example:
      - query ok
      - query ok (cached)
    meta:
      count: 2
      first_seen: 261014-0001
      last_seen: 261014-0001
      first:
      - meta: {run: 261014-0001}
        record: {level: INFO, logger: db, msg: query ok, took_ms: 3}
      last:
      - meta: {run: 261014-0001}
        record: {level: INFO, logger: db, msg: query ok (cached), took_ms: 1}
    share:
      meta:
        count: 50.0
```

To explore a sketch without reading the YAML, open it in the HTML dashboard:
`sketch analyze app.sketch.yaml -o analysis.html` (see [Regression data coverage](#regression-data-coverage)).

## Usage

```
sketch merge -p PROFILE -s SKETCH [EVENTS|-] [-o OUTPUT] [-j N] [--max-events N] [--max-seconds S] [--force-profile]
```

| Option | Meaning |
|---|---|
| `-p`, `--profile PROFILE` | YAML profile (below). Required. |
| `-s`, `--sketch SKETCH` | Sketch to merge into. Created if missing, **updated in place**. Required. |
| `EVENTS` | JSONL file; `-` or omitted reads stdin line-by-line as events arrive. |
| `-o`, `--output OUTPUT` | Write the merged sketch here instead; `SKETCH` is left unchanged. |
| `-j`, `--jobs N` | Worker processes that fold the events (default: all cores). `-j 1`, streaming input, or files up to 5,000 lines fold in-process. |
| `--max-events N` | Stop reading after `N` valid events have been folded, then save the sketch. |
| `--max-seconds S` | Stop reading after `S` seconds have elapsed (including idle waits on pipes), then save the sketch. |
| `--force-profile` | Merge even though `SKETCH` was built with a different profile. |

```sh
# stream from a live producer, stopping after 60 seconds or 1,000 events
tail -f app.jsonl | sketch merge -p profile.yaml -s app.sketch.yaml --max-seconds 60 -
tail -f app.jsonl | sketch merge -p profile.yaml -s app.sketch.yaml --max-events 1000 -

# trial run: see the result without touching the sketch
sketch merge -p profile.yaml -s app.sketch.yaml -o /tmp/preview.yaml new.jsonl
```

The summary goes to stderr and stdout stays empty. Exit status: `0` sketch written and every line
used · `1` sketch written but some lines were skipped (listed by line number) · `2` nothing written
· `3` sketch written but its history file was not (takes precedence over `1`).

**Parallel merge.** With more than one job, the input is read in batches of 5,000 lines that
worker processes fold into sketches of their own, merged at the end. Counts, sums, MIN/MAX, AVG,
first and last run, the sequence mark and the summary are exactly what one process gives;
`FIRST`/`LAST` samples (and the built-in first and last record) come from matching events, but
with several jobs not necessarily the very first or last ones, since any of them shows the same
shape. Skipped-line warnings still name the right lines, in line order.

### History

Each run gets a **run id**, `YYMMDD-SEQ`: the UTC date, then a number that only goes up for this
sketch (`261015-0003`). The sketch keeps the latest as `last_run`, and every skit's
`first_seen` / `last_seen` name the first and last run that saw it.

Every run that updates `SKETCH` also writes just that run's skits to a file named by its run
id in `<SKETCH without extension>.history/`:

```
web.sketch.yaml                  # last_run: 261015-0003
web.sketch.history/
  261014-0001.yaml
  261014-0002.yaml
  261015-0003.yaml
```

So `last_seen: 261014-0002` points straight at the file for that run. A run file is a sketch
(counts, aggregates and shares from that run only). It starts
with a `run:` header: `id`, `started`, `finished` (UTC), `source`, `events`, `skipped_lines` and
`sketch`. A new run's number is one past the highest in the sketch and its history, so a rebuilt sketch
never overwrites an old run file. History is always on; a run with `-o`, or one that writes
nothing, leaves no run file and uses up no run id. Nothing is pruned.

### Duplicate protection

If your events carry a number that only grows (an event id, an offset), name it in the profile:

```yaml
sequence: $.id
```

The sketch then keeps the highest sequence merged so far (`sequence: {path: $.id, max: 34541893465}`)
and every later run drops events at or below it, so running twice over the same file, or over
files that overlap, adds nothing twice:

```
  dropped: 180387 events already merged (sequence ≤ 34541893465)
```

Events are compared with the mark as it stood when the run started, so events slightly out of
order within one run are all kept (and duplicates within one run are not caught). Numbers and
numeric strings work. Duplicate detection has to be exact, so an event whose sequence is
missing, not a number, or selected more than once is an **error**: the run stops at that line,
nothing is written (no sketch update, no run file) and the exit status is `2`. The run file's header records the range
merged, `sequence: {min, max}`. Changing the profile's `sequence` path makes the next run ignore
the old mark and say so.

### Check a profile

```
sketch check PROFILE [PROFILE ...]
```

Checks profiles without reading any events and lists **every** problem, one per line, with the
file and where in it:

```
app.yaml: fields[0] (key 'route') → modifier: 'replace' is a required property
app.yaml: fields[1] (key 'method') → modifier.flags: 'q' does not match '^[imsx]*$'
```

A valid profile prints `app.yaml: OK`. Exit status: `0` all valid · `1` problems found. The
structure is checked against a JSON Schema (`profile.schema.json`, shipped in the package) by the
standard [`jsonschema`](https://python-jsonschema.readthedocs.io/) validator. Regexes, JSONPaths,
`IN_RANGE` bounds, duplicate keys and aggregate functions are checked as well. `merge` runs the
same check first and writes nothing if it fails.

**In your editor.** Put this line at the top of a profile, and an editor with YAML language-server
support (for example VS Code with the Red Hat YAML extension) checks the profile as you type and
completes modifier names:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/drusifer/sketch-tastic/main/src/sketchtastic/profile.schema.json
```

## Regression data coverage

The profile defines each kind of event (a skit). Explore kinds in the HTML dashboard, export
regression data, and measure how much of an observed baseline that data represents:

```sh
sketch export baseline.sketch.yaml --output regression.jsonl
sketch analyze baseline.sketch.yaml -o analysis.html --regression regression.jsonl -p profile.yaml
```

### Interactive HTML analysis dashboard

```
sketch analyze SKETCH -o REPORT.html [--history DIR] [--title TEXT] [--weight KEY] [--force]
               [--regression REGRESSION.jsonl -p PROFILE]
```

Generates a single, 100% offline HTML dashboard bundling Chart.js (MIT) with a strict Content
Security Policy and zero external network requests. All interactive filters, weighting selections,
tabs, and Sankey stages are captured in the URL hash (`#...`) with a **Copy View Link** button so
specific report views can be bookmarked or shared. Open `REPORT.html` directly in any browser to
explore:

- **Auto-discovered additive weightings (`Weight by` / `--weight KEY`):** every non-negative
  additive aggregate (`SUM`, `AVG.sum`, `COUNT`) in the sketch is automatically available in the
  dashboard's **Weight by** selector (defaulting to raw observation `count`, or pre-selected with
  `--weight KEY`). Switching weightings re-weights KPIs, Pareto concentration, field distributions,
  correlations, Sankey flows, and the skit explorer live.

- **Overview & Pareto concentration curve:** observation totals, distinct skits, singletons, and
  how many skits cover 50%, 80%, 90%, 95%, and 99% of observations.
- **Field distributions & min/max/type stats:** observation-weighted and skit-weighted bar charts
  for every field (click any bar to cross-filter), automatic **Boolean**, **Numeric**, and **Enum**
  classification, min/max across all fields, boolean true-rate %, constant/high-cardinality
  diagnostics, and exact observation-weighted mean and median for numeric token fields.
- **Drop-one field ablation:** ranks every profile field by how many skits and singletons collapse
  when that field is removed alone (plus singleton-only value counts), helping spot cardinality
  drivers to coarsen with modifiers.
- **Correlated value clusters, field associations & Sankey flow:** interactive correlated-value
  network graph (live $|\phi|$ slider, positive/anti-correlation filter, 1:1 schema-lock toggle,
  click-to-filter), Cramér's $V$ and directional Theil's $U$ field heatmap with automatic
  redundancy badges in *All Fields*, discovered cluster cards & association rules table, and a
  2–3 field Alluvial / Sankey flow diagram.
- **Time & run range sliders:** dual-handle sliders automatically populated for `DATETIME`/`DATE`
  aggregates (`MIN`/`MAX`) and `first_seen`/`last_seen` runs (with overlap, first-appeared, and
  fully-contained modes) that dynamically recompute every chart and metric.
- **Aggregates, per-event histograms & outliers:** global SUM, COUNT, MIN, MAX, exact
  observation-weighted MEAN (`AVG.sum / AVG.count`), clearly labeled across-skit mean/median,
  top outlier / across-skit distribution charts, and — for aggregates configured with `HISTOGRAM`
  (auto sparse log-decimal bins or explicit `buckets: [...]`) — live-merged per-event histograms
  with interpolated **p50 / p90 / p95 / p99** quantiles.
- **Interactive skit explorer & history drift:** searchable, sortable skit table with copyable full
  IDs, expandable retained original JSON samples, and run-over-run drift when
  `<sketch>.history/` is present (or supplied with `--history DIR`).

By default `analyze` refuses to overwrite an existing file (pass `--force` to replace a regular
file; symlinks are always refused). Exit status: `0` written · `2` invalid input or output error.

The dashboard's skit explorer is the ranked kind report: full IDs, counts, shares, tokens,
aggregates and retained samples. `export` writes one original retained record per kind to a
**new** JSONL file, in frequency order. Repeat `--id FULL_ID` (copied from the dashboard) to export
only selected kinds; omitting it exports all. Aggregates summarize observations without changing
kind identity or the baseline-count weights used for coverage.

**Regression coverage** (`--regression FILE -p PROFILE`, always given together) adds a
*Regression Coverage* card to the dashboard. The profile must be the sketch's own (a mismatched
or missing profile ID is rejected); each regression record is tokenized with it, and a baseline
kind is *covered* when at least one record has its skit ID. Two separate measures:

- **Kind coverage:** distinct covered baseline kinds / all baseline kinds.
- **Frequency-weighted coverage:** baseline observations in covered kinds / all baseline observations.

Both follow the dashboard's filters and weighting live. A *Coverage* filter (all / covered /
uncovered) narrows every chart and the skit explorer, so the explorer ranks the uncovered kinds
to sample next (`export --id`). Regression kinds absent from the baseline are listed separately.
Repeated regression examples of one kind do not increase coverage; empty percentages are N/A.
Input is strict JSONL objects, read as a stream; a malformed line fails with its line number and
no dashboard is written.

**History aware.** Each run in `<sketch>.history/` is a sketch of that run's events, so the card
also charts, per run: the run's own kind and frequency-weighted coverage, cumulative coverage up
to that run, and the kinds the run introduced that the corpus does not cover yet (listed per run).
Runs written under another profile are marked not comparable.

These numbers describe sample representation under this profile, not branch coverage or proof
that tests ran successfully. Their real-world scope is the data represented by the baseline.
Completeness means all observed profile-defined kinds, not every theoretically possible input.

## Derive a new sketch

Reuse captured observations when a new profile only collapses retained distinctions:

```sh
sketch derive baseline.sketch.yaml --source-profile baseline-profile.yaml \
  --profile coarse-profile.yaml --output baseline-v2.sketch.yaml
```

The output name is required and must be unused, including its companion history directory.
The source is unchanged. Source and output sketches use structured-token format 1; legacy files
require recapture or replay of original events. The suffix `v2` is your dataset name/version,
not the sketch serialization version or package version.

Supported changes are dropping, reordering and renaming retained fields; changing an untyped
`DEFAULT` field to `IS_PRESENT`; scalar `DEFAULT` values to `IS_NULL`, `ANY`, `GLOB`, `REGEX`
or `REGSUB`; and coarsening typed dates/timestamps with `TRUNC`. Selection paths and value
types must match an original field. Adding a genuinely new distinction, refining a truncated
time, or an unsupported change is rejected with an explanation. Aggregate specifications,
`sequence` and `event_time` must remain unchanged.

For example, change only the modifier on an existing tag selection:

```yaml
# Original field
- {key: tags, path: $.tags}
# Target field
- {key: tags, path: $.tags, modifier: IS_PRESENT}
```

For this parent-array selection, missing becomes `FALSE`; explicit null, empty arrays and
populated arrays become `TRUE`. To distinguish empty from populated arrays, the original
profile must already select a member such as `$.tags[0]`. Changing the path during derivation
is conservatively rejected. `IS_NULL` is a different predicate: it tests explicit null, not
absence. Scalar-to-predicate changes preserve real nulls and literal strings distinctly.
Array transformations beyond presence may be rejected because a selected array and several
selected values can have the same stored set but different modifier behavior.

Each original skit maps to exactly one new skit. Collisions merge counts, SUM/COUNT/MIN/MAX,
AVG sum/count and histogram states; shares are recalculated. **Observation totals stay the
same and skit counts cannot increase.** Incompatible MIN/MAX value kinds or incomplete retained
statistics are rejected. The original profile is authoritative for aggregate definitions:
the stored profile hash covers identity fields, not aggregate paths.

Every available run in the source's companion `.history/` directory is transformed by the
same rules. Run IDs, times, counts and sequence marks are preserved; run headers point to the
new sketch. Provenance records source and target profile IDs and survives subsequent merges.
Missing history is not invented. FIRST/LAST samples remain bounded, matching original records;
cross-skit chronological ordering cannot be reconstructed from the summary alone.

All main/history files are validated and staged before publication. Existing files and symlinks
are refused; handled failures remove only files created by the operation. Keep the source
quiescent during derivation. Publishing the sketch and its history is not crash-atomic across
two paths. Exit status is `0` on success, `2` for rejection/failure, or `130` for interruption.

Continue capturing into the derived sketch with its target profile:

```sh
sketch merge -p coarse-profile.yaml -s baseline-v2.sketch.yaml new-events.jsonl
```

## Profiles

```yaml
version: 0

# fields define identity: events with the same tokens share one skit
fields:
  - key: method
    path: "$.request.method"                 # modifier defaults to DEFAULT
  - key: status_ok
    path: "$.response.status"
    modifier: {name: IN_RANGE, low: 200, high: 399}
  - key: slow_upstreams
    path: "$.upstreams[?(@.ms > 500)].name"  # full JSONPath, including filters

# aggregates are tracked per skit and never affect identity
aggregates:
  - key: latency_ms
    path: "$.response.ms"
    fn: [MIN, MAX, AVG]
  - key: recent_paths
    path: "$.request.path"
    fn: {name: LAST, n: 3}
```

**Paths** are standard JSONPath ([RFC 9535](https://www.rfc-editor.org/rfc/rfc9535), evaluated by
[jsonpath-rfc9535](https://github.com/jg-rp/python-jsonpath-rfc9535)), with no extensions: dot and bracket access, `[*]`, slices, negative indexes, unions,
recursive descent (`..`) and filters. If a path selects several values, each is tokenized and the
results are de-duplicated and sorted into structured arrays; a single distinct match remains
a scalar. Directly selected arrays remain arrays, including empty and singleton arrays, and
are recursively sorted/deduplicated. Array order and repetition never create a new skit.

Sketch format **1** distinguishes omitted keys (missing), YAML `null` (explicit null), the
literal string `"NULL"`, and array sets such as `["xyz", null]`. `DEFAULT`, `REGSUB` and `TRUNC`
omit missing or unconvertible values and retain explicit nulls. A wildcard with no matches
cannot distinguish a missing parent from an empty parent array; select the parent itself if
that distinction matters. Skit IDs include field names as well as values. Legacy format-0
sketches are rejected: recapture or replay original events; there is no migration layer.
Profile YAML still uses `version: 0`; its schema has not changed.

**Modifiers** turn the selected value into a token. Pick ones that collapse high-cardinality
values (IDs, timestamps, sizes) so similar events share a skit:

| Modifier | Arguments | Token |
|---|---|---|
| `DEFAULT` | — | scalar as a string, null as null, arrays as sets; missing key omitted |
| `IS_PRESENT` | — | `TRUE` if the key exists, even when its value is `null` |
| `IS_NULL` | — | `TRUE` only if the key exists and is set to `null` (a missing key is `FALSE`) |
| `IN_RANGE` | `low`, `high` (numbers) | `TRUE` if `low <= value <= high` |
| `ANY` | `values` (a list) | `TRUE` if the value is one of those listed |
| `GLOB` | `pattern` | `TRUE` if the whole value matches the shell-style pattern (`*`, `?`, `[a-z]`), case-sensitive |
| `REGEX` | `pattern`, optional `flags` | `TRUE` if the regular expression matches anywhere in the value; anchor with `^` and `$` |
| `REGSUB` | `pattern`, `replace`, optional `flags` | the value with every match replaced (`\1` refers to a group); missing omitted, null retained |
| `TRUNC` | `unit` | a `DATE`/`DATETIME` value cut to `year` … `second`, e.g. hour → `2024-01-01T15` |

A modifier without arguments is written as its bare name (`modifier: IS_PRESENT`); one with
arguments is a mapping with `name` and its arguments:

```yaml
  - key: status_ok
    path: $.response.status
    modifier: {name: IN_RANGE, low: 200, high: 399}
  - key: port_ok
    path: $.dport
    modifier: {name: ANY, values: [80, 443]}
  - key: in_tmp
    path: $.file
    modifier: {name: GLOB, pattern: '/tmp/*'}                  # TRUE / FALSE
  - key: route
    path: $.request.path
    modifier: {name: REGSUB, pattern: '\d+', replace: N}       # /items/17 -> /items/N
  - key: greeting
    path: $.body.text
    modifier:
      name: REGEX
      pattern: '^hello\s.*\sgoodbye\.$'
      flags: i
```

`flags` is any of `i` (ignore case), `m` (`^` and `$` match at line breaks), `s` (`.` matches a
newline) and `x` (verbose). Patterns use Python's `re` syntax. Write patterns in single quotes:
YAML leaves backslashes alone there, and a pattern starting with `*`, `[` or `{`, or containing
`: ` or ` #`, would otherwise not parse as you meant. Changing a field's modifier changes the
profile's identity, like any other change to `fields`.

**Dates and times.** Add `type: DATETIME` (or `type: DATE`) to a field or aggregate whose path
holds ISO-8601 text. Values are compared as real times in UTC, so `MIN`/`MAX` are right across
time zones, and the sketch stores them as YAML timestamps. A value that isn't valid ISO-8601 counts as
missing (and is skipped by aggregates). For fields, `TRUNC` buckets a time so events group
together:

```yaml
  - key: hour
    path: $.created_at
    type: DATETIME
    modifier: {name: TRUNC, unit: hour}     # year, month, day, hour, minute or second
```

**Aggregates** are computed across every event that lands on the same skit, over all runs:

| Function | Keeps |
|---|---|
| `SUM` | running sum of numbers |
| `MIN`, `MAX` | smallest / largest — numbers, dates and times (with `type`), or text |
| `AVG` | the average, with the sum and count that make it mergeable |
| `COUNT` | how many values the path selected (of any type) |
| `{name: FIRST, n: N}` | the `N` earliest values of the path (with `-j` above 1: some early values) |
| `{name: LAST, n: N}` | the `N` most recent values of the path (with `-j` above 1: some late values) |

`fn` is one function or a list, written like modifiers: a bare name, or a mapping for `FIRST`
and `LAST`. With one function the sketch stores its value directly (`count: 12`); with several, a
map by function name (`{MIN: 1, MAX: 3}`). Every skit holds every aggregate, in the order the
profile lists them (functions too), from its first event on: before any value, `SUM` and `COUNT`
are `0`, `FIRST`/`LAST` are `[]`, `AVG` is `{avg: null, sum: 0, count: 0}`, and `MIN`/`MAX` are
`null`. So the profile alone decides the order of keys in the file. Numbers and numeric strings count as numbers. A value
a function can't use (text for `SUM`, text after numbers for `MIN`) is skipped and counted in the
summary as an unusable aggregate value. A record where the path matches nothing is simply not
aggregated and is not counted.

**Weighted aggregates.** Add `op: SIZE` to aggregate each value's size in bytes instead of the
value itself: UTF-8 bytes for text, the compact JSON encoding for anything else (`null` is 4).
Every function gets the size, so one entry gives `SUM(SIZE(payload))` and more:

```yaml
aggregates:
  - {key: payload_bytes, path: $.payload, op: SIZE, fn: [SUM, AVG, MAX]}
```

`op` and `type` cannot be combined on one aggregate. Like any aggregate change, adding an `op`
keeps the profile id, so existing sketches keep merging.

`merge` checks the profile before reading any event; run `sketch check` (above) to see
every problem at once.

## The sketch

- `tokens` shows what each ID stands for.
- `aggregates` holds what your profile asked for. `meta` holds what every skit gets for
  free: `count`, `first_seen` / `last_seen` (the first and last run id that saw it, see History
  above), and the first and last record (one each, to keep
  sketches and run files small; add `FIRST`/`LAST` aggregates to your profile for more samples).
- `meta` comes from a small built-in profile shipped with the package (`builtin.yaml`), which
  uses the same aggregate functions you can. It reads each record wrapped in an envelope,
  `{meta: {run: <run id>}, record: <the parsed record>}`, so the fields the tool adds can never
  clash with the record's own, and the stored first/last records carry the run they came from.
- `share` gives each skit's percentage of the whole sketch for every value that adds up:
  `share.meta.count` is its share of all events, and `share.aggregates` holds the share of each
  `SUM` and `COUNT`, laid out like `aggregates` (`payload_bytes: {SUM: 31.25}`, or `requests: 25.0`
  for a single-function aggregate). It is recomputed on every write; a value whose total is 0 has
  no share.
- The tool records runs, not times, per skit by default; a run's start and finish times are in its
  run file. To ingest historical data using each event's own timestamp for `first_seen` /
  `last_seen`, add `event_time: $.created_at` (any JSONPath to an ISO-8601 date or datetime) at
  the top level of your profile — `first_seen` and `last_seen` then store the earliest and latest
  UTC timestamps per skit instead of run IDs (without changing `profile_id`). To track additional
  time fields, add them to your profile's `aggregates`.
- A sketch records the profile that built it (`profile_id`, derived from `fields`). Merging under a
  profile with different `fields` is refused, because the skits would not be comparable.
  Changing `aggregates` is always fine.
- Splitting a stream across several runs gives the same sketch as one run over all of it.
- The file is replaced atomically; a failed or interrupted run leaves the previous sketch intact.

## As a library

```python
from sketchtastic import Sketch, load_profile

profile = load_profile("profile.yaml")
sketch = Sketch(profile.aggregates, profile.profile_id)

event = {"level": "INFO", "logger": "db", "msg": "query ok", "took_ms": 3}
skit_id = sketch.upsert(profile.tokens(event), event, run="261015-0001")

sketch.get(skit_id).meta["count"]   # 1
sketch.save("app.sketch.yaml")
```

`load_profile` and `parse_profile` raise `ProfileError`; its `problems` attribute lists every
problem, located, in the same form `sketch check` prints. `check_profile(data, source)`
returns `(profile_or_None, problems)` without raising.

Without a profile file, build the pieces directly. `Field` and `Aggregate` take the same keys
as the YAML (`key`, `path`, `modifier` / `fn`) and are checked when created (`ValueError` if
wrong):

```python
from sketchtastic import Field, Profile

profile = Profile(fields=(
    Field("method", "$.request.method"),
    Field("route", "$.request.path", {"name": "REGSUB", "pattern": r"\d+", "replace": "N"}),
))
profile.tokens({"request": {"method": "GET", "path": "/items/17"}})
# {'method': 'GET', 'route': '/items/N'}
```

Every modifier and aggregate function is a `Rule` subclass, registered by its `name`; the
schema checks its arguments and the class checks the rest.

## Bluesky demo

The [Bluesky post demo](examples/bluesky/README.md) streams public posts through a small unwrap
filter into `sketch merge -`, one unchanged post per row. Its profile defines post kinds using
native JSONPath/modifiers; the core `analyze` (with `--regression` coverage) and `export`
commands then support regression-data selection.

## Documentation

| Document | What it holds |
|---|---|
| [docs/DOMAIN.md](docs/DOMAIN.md) | Domain model: glossary, contexts, invariants (incl. the one streaming ingestion path) |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architecture decision records, newest last |
| [docs/LESSONS.md](docs/LESSONS.md) | Engineering lessons, newest first |
| [docs/SDLC.md](docs/SDLC.md) | How the project is built, tested, changed and released (`make` targets) |
| [examples/bluesky/README.md](examples/bluesky/README.md) | Live Bluesky capture → sketch → dashboard and coverage walkthrough |
| [docs/sprints/](docs/sprints/) | Per-sprint user stories and UAT plans (historical) |
| [AGENTS.md](AGENTS.md), [task.md](task.md) | Agent team operating rules and the sprint task board |

## License

MIT
