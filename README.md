# fingerprint-sampler

Fingerprint and sample JSONL event streams.

`fingerprint` reads events — logs, traces, audit records, anything with one JSON object per
line — and reduces each to a **fingerprint**: a stable ID for "this shape of event". It keeps a
**fingerprint set** with one entry per distinct fingerprint: how often it was seen, statistics you
ask for, and a few recent samples. The set is a file that grows across runs:

```
existing set  +  stream of events  ->  updated set
```

A million near-identical log lines become a handful of entries you can actually read.

## Install

```sh
pip install fingerprint-sampler
```

Python 3.14 or newer. Installs the `fingerprint` command (also available as
`fingerprint-sampler` and `python -m fingerprint_sampler`).

**New in 0.2.0:** modifier arguments are written as YAML mappings
(`{name: IN_RANGE, low: 200, high: 399}`); the 0.1 string form (`"IN_RANGE(200, 399)"`) is no
longer accepted. Added `GLOB`, `REGEX` and `REGSUB` modifiers and the `fingerprint check` command. Since then
(mainline): `LAST` is written `{name: LAST, n: 3}`, not `"LAST(3)"`.
While the version is 0.x, releases may break profiles and set files without a migration path.

## Quickstart

Paste this into a shell. It writes a profile and a few events, then fingerprints them:

```sh
cat > profile.yaml <<'YAML'
version: 1
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

fingerprint merge -p profile.yaml -s app.fingerprints.yaml events.jsonl
```

```
fingerprint: 4 events read from events.jsonl
  fingerprints: 3 new, 0 updated, 3 total in set
  skipped: 0 malformed lines, 0 aggregate values
  wrote app.fingerprints.yaml (profile f50d7a5f85ddf9f7f4c72370f454ae2e)
```

Four events, three fingerprints: the two successful `db` queries share one. Run the same command
again and the counts add up instead of new entries appearing — that is the merge.

`app.fingerprints.yaml` now starts like this (the other two fingerprints follow):

```yaml
version: 1
profile_id: f50d7a5f85ddf9f7f4c72370f454ae2e
fingerprints:
  b738d17a6a5f7265cb4cef73937afd4f:
    tokens:
      level: INFO
      component: db
      failed: 'FALSE'
    total_occurrences: 2
    first_seen: '2026-10-14T03:59:19.796868+00:00'
    last_seen: '2026-10-14T03:59:19.796991+00:00'
    aggregates:
      took_ms:
        MIN: 1
        MAX: 3
        AVG:
          avg: 2.0
          sum: 4
          count: 2
      example:
        LAST:
        - query ok
        - query ok (cached)
```

## Usage

```
fingerprint merge -p PROFILE -s SET [EVENTS|-] [-o OUTPUT] [--force-profile]
```

| Option | Meaning |
|---|---|
| `-p`, `--profile PROFILE` | YAML profile (below). Required. |
| `-s`, `--set SET` | Fingerprint set to merge into. Created if missing, **updated in place**. Required. |
| `EVENTS` | JSONL file; `-` or omitted reads stdin. |
| `-o`, `--output OUTPUT` | Write the merged set here instead; `SET` is left unchanged. |
| `--force-profile` | Merge even though `SET` was built with a different profile. |

```sh
# read from a pipe
tail -n 1000 app.jsonl | fingerprint merge -p profile.yaml -s app.fingerprints.yaml -

# trial run: see the result without touching the set
fingerprint merge -p profile.yaml -s app.fingerprints.yaml -o /tmp/preview.yaml new.jsonl
```

The summary goes to stderr and stdout stays empty. Exit status: `0` set written and every line
used · `1` set written but some lines were skipped (listed by line number) · `2` nothing written.

### Check a profile

```
fingerprint check PROFILE [PROFILE ...]
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
# yaml-language-server: $schema=https://raw.githubusercontent.com/drusifer/fingerling/main/packages/fingerprint-sampler/src/fingerprint_sampler/profile.schema.json
```

## Profiles

```yaml
version: 1

# fields define identity: events with the same tokens share one fingerprint
fields:
  - key: method
    path: "$.request.method"                 # modifier defaults to DEFAULT
  - key: status_ok
    path: "$.response.status"
    modifier: {name: IN_RANGE, low: 200, high: 399}
  - key: slow_upstreams
    path: "$.upstreams[?(@.ms > 500)].name"  # full JSONPath, including filters

# aggregates are tracked per fingerprint and never affect identity
aggregates:
  - key: latency_ms
    path: "$.response.ms"
    fn: [MIN, MAX, AVG]
  - key: recent_paths
    path: "$.request.path"
    fn: {name: LAST, n: 3}
```

**Paths** are full JSONPath: dot and bracket access, `[*]`, slices, negative indexes, unions,
recursive descent (`..`) and filters. If a path selects several values, each is tokenized and the
results are de-duplicated, sorted and joined, so array order never changes a fingerprint.

**Modifiers** turn the selected value into a token. Pick ones that collapse high-cardinality
values (IDs, timestamps, sizes) so similar events share a fingerprint:

| Modifier | Arguments | Token |
|---|---|---|
| `DEFAULT` | — | the value as a string; `NULL` if absent |
| `IS_PRESENT` | — | `TRUE` / `FALSE` — present and non-null? |
| `IS_NULL` | — | `TRUE` / `FALSE` — absent or null? |
| `IN_RANGE` | `low`, `high` (numbers) | `TRUE` if `low <= value <= high` |
| `ANY` | `values` (a list) | `TRUE` if the value is one of those listed |
| `GLOB` | `pattern` | `TRUE` if the whole value matches the shell-style pattern (`*`, `?`, `[a-z]`), case-sensitive |
| `REGEX` | `pattern`, optional `flags` | `TRUE` if the regular expression matches anywhere in the value; anchor with `^` and `$` |
| `REGSUB` | `pattern`, `replace`, optional `flags` | the value with every match replaced (`\1` refers to a group); `NULL` if absent |

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

**Aggregates** are computed across every event that lands on the same fingerprint, over all runs:

| Function | Keeps |
|---|---|
| `SUM`, `MIN`, `MAX` | running sum / smallest / largest |
| `AVG` | the average, with the sum and count that make it mergeable |
| `{name: LAST, n: N}` | the `N` most recent values — use path `$` to keep whole events as samples |

`fn` is one function or a list, written like modifiers: a bare name, or a mapping for `LAST`.
Numeric functions accept numbers and numeric strings. A missing or non-numeric value is skipped
for that aggregate and counted in the summary.

`merge` checks the profile before reading any event; run `fingerprint check` (above) to see
every problem at once.

## The fingerprint set

- `tokens` shows what each ID stands for.
- `first_seen` / `last_seen` are when the tool read the events, not times from the events.
- A set records the profile that built it (`profile_id`, derived from `fields`). Merging under a
  profile with different `fields` is refused, because the fingerprints would not be comparable.
  Changing `aggregates` is always fine.
- Splitting a stream across several runs gives the same set as one run over all of it.
- The file is replaced atomically; a failed or interrupted run leaves the previous set intact.

## As a library

```python
from fingerprint_sampler import Warehouse, load_profile, tokenize

profile = load_profile("profile.yaml")
fingerprints = Warehouse(aggregates=profile.aggregates, profile_id=profile.profile_id)

event = {"level": "INFO", "logger": "db", "msg": "query ok", "took_ms": 3}
fingerprint_id = fingerprints.upsert(tokenize(event, list(profile.fields)), event)

fingerprints.get(fingerprint_id).total_occurrences   # 1
fingerprints.save("app.fingerprints.yaml")
```

`load_profile` and `parse_profile` raise `ProfileError`; its `problems` attribute lists every
problem, located, in the same form `fingerprint check` prints. `check_profile(data, source)`
returns `(profile_or_None, problems)` without raising.

Without a profile file, build the rules directly. A `MaskEntry`'s modifier is a bare name or a
mapping, exactly as in YAML, and is validated when the entry is created (`ValueError` if wrong):

```python
from fingerprint_sampler import MaskEntry, tokenize

rules = [
    MaskEntry("method", "$.request.method", "DEFAULT"),
    MaskEntry("route", "$.request.path", {"name": "REGSUB", "pattern": r"\d+", "replace": "N"}),
]
tokenize({"request": {"method": "GET", "path": "/items/17"}}, rules)
# {'method': 'GET', 'route': '/items/N'}
```

## License

MIT
