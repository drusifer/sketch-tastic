# sketch-tastic

Mergeable sketches of JSONL event streams for regression testing and flow analysis.

`sketchtastic` reads events — logs, traces, audit records, anything with one JSON object per
line — and reduces each to a **skit**: a stable ID for "this shape of event". It keeps a
**sketch** (the data-sketch term for a compact, mergeable summary of a stream) with one entry per
skit: how often it was seen, statistics you ask for, and a sample. The sketch is a file that
grows across runs:

```
existing sketch  +  stream of events  ->  updated sketch
```

A million near-identical log lines become a handful of entries you can actually read.

## Install

```sh
pip install sketch-tastic
```

Python 3.14 or newer. Installs the `sketchtastic` command and its short alias `skt` (also
runnable as `python -m sketchtastic`).

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

sketchtastic merge -p profile.yaml -s app.sketch.yaml events.jsonl
```

```
sketchtastic: 4 events read from events.jsonl
  skits: 3 new, 0 updated, 3 total in sketch
  skipped: 0 malformed lines, 0 unusable aggregate values
  wrote app.sketch.yaml (profile f50d7a5f85ddf9f7f4c72370f454ae2e)
  history: app.sketch.history/261014-0001.yaml
```

Four events, three skits: the two successful `db` queries share one. Run the same command
again and the counts add up instead of new entries appearing — that is the merge. Each run also
leaves a file with just its own skits in `app.sketch.history/` (see History below).

`app.sketch.yaml` now starts like this (the other two skits follow):

```yaml
version: 0
profile_id: f50d7a5f85ddf9f7f4c72370f454ae2e
last_run: 261014-0001
skits:
  b738d17a6a5f7265cb4cef73937afd4f:
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

To read a sketch without the YAML, print it as a table with `sketchtastic show app.sketch.yaml`:

```
ID        COUNT  COUNT %  FIRST RUN    LAST RUN     component  failed  level
5c56a234  1      25.0     261014-0001  261014-0001  db         TRUE    ERROR
0a13defd  1      25.0     261014-0001  261014-0001  http       FALSE   INFO
b738d17a  2      50.0     261014-0001  261014-0001  db         FALSE   INFO
```

## Usage

```
sketchtastic merge -p PROFILE -s SKETCH [EVENTS|-] [-o OUTPUT] [-j N] [--force-profile]
```

| Option | Meaning |
|---|---|
| `-p`, `--profile PROFILE` | YAML profile (below). Required. |
| `-s`, `--sketch SKETCH` | Sketch to merge into. Created if missing, **updated in place**. Required. |
| `EVENTS` | JSONL file; `-` or omitted reads stdin. |
| `-o`, `--output OUTPUT` | Write the merged sketch here instead; `SKETCH` is left unchanged. |
| `-j`, `--jobs N` | Worker processes that fold the events (default: all cores). `-j 1`, or input of up to 5,000 lines, folds in-process. |
| `--force-profile` | Merge even though `SKETCH` was built with a different profile. |

```sh
# read from a pipe
tail -n 1000 app.jsonl | sketchtastic merge -p profile.yaml -s app.sketch.yaml -

# trial run: see the result without touching the sketch
sketchtastic merge -p profile.yaml -s app.sketch.yaml -o /tmp/preview.yaml new.jsonl
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
(counts, aggregates and shares from that run only), so `sketchtastic show` reads it. It starts
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
sketchtastic check PROFILE [PROFILE ...]
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

### Show a sketch

```
sketchtastic show [--sort KEY] SKETCH
```

Prints one row per skit, least frequent first: the first 8 characters of its ID, its count
and `COUNT %` (its share of all events), the first and last run that saw it, then a value and
a `%` column for each `SUM` or `COUNT` aggregate (`payload_bytes.SUM`, `payload_bytes.SUM %`), and
one column per token. Shares come from the sketch file's `share` section; a sketch written before
shares existed shows `-` until its next merge. A sketch with no skits prints
`SKETCH: no skits`. Long values are not cut; pipe to `less -S` to scroll sideways.

`--sort KEY` orders the rows by the column headed KEY, in any case, lowest first (default
`COUNT`), so the largest are at the end: `sketchtastic show --sort 'payload_bytes.SUM %'
gh.sketch.yaml | tail` shows the heaviest skits. `-` sorts first, numbers before text, and
equal values keep file order. Exit status: `0` printed · `2` the sketch file could not be read,
or KEY is not one of its columns (the message says why, and lists the columns).

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
results are de-duplicated, sorted and joined, so array order never changes a skit.

**Modifiers** turn the selected value into a token. Pick ones that collapse high-cardinality
values (IDs, timestamps, sizes) so similar events share a skit:

| Modifier | Arguments | Token |
|---|---|---|
| `DEFAULT` | — | the value as a string; `NULL` if absent |
| `IS_PRESENT` | — | `TRUE` if the key exists, even when its value is `null` |
| `IS_NULL` | — | `TRUE` only if the key exists and is set to `null` (a missing key is `FALSE`) |
| `IN_RANGE` | `low`, `high` (numbers) | `TRUE` if `low <= value <= high` |
| `ANY` | `values` (a list) | `TRUE` if the value is one of those listed |
| `GLOB` | `pattern` | `TRUE` if the whole value matches the shell-style pattern (`*`, `?`, `[a-z]`), case-sensitive |
| `REGEX` | `pattern`, optional `flags` | `TRUE` if the regular expression matches anywhere in the value; anchor with `^` and `$` |
| `REGSUB` | `pattern`, `replace`, optional `flags` | the value with every match replaced (`\1` refers to a group); `NULL` if absent |
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
map by function name (`{MIN: 1, MAX: 3}`). Numbers and numeric strings count as numbers. A value
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

`merge` checks the profile before reading any event; run `sketchtastic check` (above) to see
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
- The tool records runs, not times, per skit; a run's start and finish times are in its run
  file. To track a time field inside your records, add it to your profile's `aggregates`.
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
problem, located, in the same form `sketchtastic check` prints. `check_profile(data, source)`
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

## License

MIT
