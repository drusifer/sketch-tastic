# Decisions

Decisions made while the code lived in `drusifer/fingerling` are recorded in that repository's
`docs/DECISIONS.md` (Sprints 8-17 and the fixes after them). New decisions are recorded here.

**Decision (owner, 2026-10-14):** The fingerprint tool moves out of fingerling into its own
repository, `drusifer/sketch-tastic`, with its git history (`git subtree split`). Names:
distribution `sketch-tastic`, import `sketchtastic`, commands `sketchtastic` and `skt`. The set
file is a **sketch** (the data-sketch term for a compact, mergeable stream summary); one
fingerprint in it is a **skit**. fingerling depends on this repository through git.
**Consequences:** One Makefile and SDLC for one package (ported from fingerling). fingerling
drops `packages/fingerprint-sampler` once this repository is pushed.

**Decision (owner, 2026-10-14, Sprint 2):** `show` sorts by one column, `--sort KEY` (a header
in any case), always lowest first with no reverse option; the default KEY is `COUNT`, so plain
`show` lists the least frequent skit first. `--top N` is dropped: `| tail` and `| head` do it.
**Consequences:** The largest rows end next to the prompt. `-` sorts first, numbers before text,
ties keep file order. Breaking for anyone reading the old most-frequent-first order (0.x, no
shim).

**Decision (owner, 2026-10-14, Sprint 3):** Speed is measured only with `make profile` (stdlib
cProfile on the GH Archive hour, plus wall time and a hash of the sketch), and tuned best effort
within KISS. Results on a Raspberry Pi 5, 180,387 events, byte-identical sketch throughout:
106.35 s baseline → 54.48 s (plain JSONPaths `$`/`$.a.b` walk dicts instead of python-jsonpath's
general matcher) → 40.83 s (each event selected once for the sketch and its run file; stored
samples copied once per event with a JSON-specific copy). 2.6x overall.
**Consequences:** The library contract stays: stored samples never alias the caller's record
(dropping the copy was tried and rejected for that reason). What remains is spread thin: one copy
of each event (~16% profiled), folding, JSON parsing, and SIZE's JSON encoding. Further gains need
bigger changes (e.g. a copy-free ownership mode for the CLI, a faster JSON parser), not taken.

**Decision (owner, 2026-10-14, after Sprint 3):** JSONPath is evaluated by `jsonpath-rfc9535` 2.x
(strict RFC 9535, no extensions) instead of `python-jsonpath`, and the Sprint 3 plain-path
shortcut is removed. The point of JSONPath is a standard; a hand-written evaluator for some paths
adds complexity without fixing the cause. The cause was python-jsonpath building a match node and
a path string for every step (compilation was already cached); jsonpath-rfc9535's `findall` uses
a resolver that tracks no locations.
**Consequences:** `make profile` 40.83 s with the shortcut → 46.25 s without it, same sketch; path
evaluation ~19 s of profiled time (146 s with python-jsonpath). Profiles must use RFC 9535 syntax
only. New transitive runtime dependencies: `regex` and `iregexp-check` (for I-Regexp in
`match()`/`search()`).

**Decision (owner, 2026-10-14, after Sprint 3):** `merge` folds each event once, into the run, and
then merges the run into the sketch once (`Sketch.merge`; each aggregate function has a `merge`
of two states). This replaces Sprint 3's select-once/`upsert(selected=)` change and its
JSON-specific copy, which are removed; FIRST/LAST keep `copy.deepcopy`.
**Consequences:** `make profile` 39.36 s, same sketch (46.25 s with select-once). Merging is
exact for SUM, COUNT, MIN, MAX, AVG (from stored sum and count), FIRST and LAST; with floats a
different summation order can change the last digits. A MIN/MAX value of another kind than the
sketch's keeps the sketch's value and is not counted as skipped. `Sketch.merge` is also the base
for sketch-to-sketch merge (backlog).

**Decision (owner, 2026-10-14, after Sprint 3):** FIRST and LAST store values without copying;
`Sketch.upsert` documents that the sketch keeps references, so the caller must not modify a
record after passing it. The two tests that pinned the old copy guarantee are removed.
**Consequences:** `make profile` 39.36 s → 32.88 s, same sketch (LAST deep-copied every event to
keep one per skit). `Sketch.merge` still copies, so a sketch and its run never share state.

**Decision (owner, 2026-10-14, Sprint 4):** All YAML is read and written through libyaml
(`CSafeLoader`/`CSafeDumper`, included in PyYAML's wheels), in one module, `sketchtastic._yaml`,
for sketches, run files, profiles and the built-ins alike.
**Consequences:** `make profile` -j 1 31.99 s → 29.55 s, parallel 16.46 s → 13.54 s (writing the
sketch and run file was the largest serial cost of a parallel merge). The bytes of a sketch file
change (libyaml formats differently; new hash bd657fe6fd331918), its content does not (tested
by a round trip of strings that look like other YAML types, unicode, multi-line and long text).

**Decision (owner, 2026-10-15):** The profile is the only source of key order. Every skit is
created with every aggregate (and built-in) in profile order, each at its initial state: `0` for
SUM and COUNT, `[]` for FIRST/LAST, `{avg: null, sum: 0, count: 0}` for AVG, `null` for MIN/MAX
(where 0 would be wrong). Loading rebuilds skits in profile order. Replaces "a key appears when
its first value arrives", which made key order follow event order and, with `-j`, made `show`'s
columns depend on which worker finished first.
**Consequences:** `show` columns are in profile order for any `-j`; aggregates without values
show `0` (SUM/COUNT) or `-` (MIN/MAX). Sketch files change (all keys present; new hash
86d122f56e81d95c). No speed change.

**Decision (owner, 2026-10-15):** A skit id is the MD5 of its token values in profile order,
JSON-encoded (`["INFO","db","FALSE"]`); token keys are no longer hashed or sorted. The profile id
now hashes the field specs in profile order, so reordering fields is a different profile (merge
refuses it without `--force-profile`) and can never silently re-key skits.
**Consequences:** every skit id and profile id changes (v0: sketches are rebuilt, no
migration); README quickstart ids updated (9312137e…, profile 3f0dd0d9…). The two-id design
itself (skit id vs profile id) is backlogged with profile evolution.

## ADR-2026-11-19: Bluesky enum-based ASCII demo

**Status:** Superseded by ADR-2026-11-20 below. **Date:** 2026-11-19. **Deciders:** Owner (ASCII scope), Morpheus
(architecture), Tank (build mechanisms). **Related:** [Sprint 5 stories](sprints/USER_STORIES_SPRINT5.md).

### Context and drivers

The owner wants a large public dataset to demonstrate compact regression test data: preserve
meaningful application variants while eliminating repeated cases. The demo must live in this
repository, print ASCII, use enumerated application decisions, and preserve real source data.

### Considered options

| Option | Benefits | Costs / risks | Decision |
|---|---|---|---|
| Group whole posts using nested image attributes | Direct raw-record ingestion | Loses per-image attribute correlations and makes image counts ambiguous | Rejected |
| Normalize one image occurrence per row, retaining its source | Correlated fields, exact image counts and original samples | Extra derived rows and explicit normalization policy | Selected |

### Outcome and consequences

Six identity fields encode reply status, embed kind, attachment-count class, MIME, orientation
and alt-text state. Exact counts and original values remain available in samples; byte sizes
are aggregates. The existing Profile/Sketch APIs perform all grouping and sample retention.
ASCII counts use full-sketch weights; one retained row per skit is re-folded and its ID set
must equal the full sketch's ID set. This preserves observed variants under this profile;
it does not prove branch coverage, combination reachability or global Bluesky completeness.

Bounded capture saves endpoint/window provenance. Preparation hashes the raw source and saves
the profile with original posts/events and image indexes. Identified create events deduplicate
by DID/key; bare posts count as supplied. Normalized representative exports are valid input for
the existing merge CLI, while demo preparation expects raw posts/events. Fresh output paths and
staged publication protect prior captures and artifacts. A bounded capture may miss rare enums;
the report displays absent values explicitly rather than treating them as covered.

The optional `demo` group supplies websockets for capture; offline preparation uses existing
dependencies. The optional `security` group supplies pip-audit. Make targets install and audit
these groups in the project environment; neither expands package runtime requirements. The
cost is extra development tooling and finite capture windows, with no web/frontend deployment.

## ADR-2026-11-20: Original posts and generic regression coverage

**Status:** Accepted. **Deciders:** Owner, Morpheus. Supersedes per-image normalization above.

### Context
The owner clarified that the unit of regression data is an original post. The sketch profile
defines a kind of post; coverage means representing observed kinds and their real frequencies.
Reporting is a core use case and must not be confined to a Bluesky application.

### Considered options
| Option | Benefit | Cost | Decision |
|---|---|---|---|
| Derived image model and demo-only reports | Simple per-image charts | Changes the unit under test and duplicates sketch semantics | Rejected |
| Unchanged post rows, profile-native fields, generic CLI | Original test inputs and reusable coverage analysis | Explicit profiles can be verbose | Selected |
| New general MAP/REDUCE engine | Broader derived-value support | Unneeded core complexity for this example | Deferred |

### Outcome and consequences
The demo only unwraps create-event envelopes and deduplicates identified observations; all
feature selection uses the saved profile. Original posts are retained. (Amended by
ADR-2026-11-24-b: the `prepare` command and its source line locators are retired.)
`report`, `export` and `coverage` live in the package CLI and know nothing about Bluesky.
(`report` was later retired in favour of the `analyze` dashboard; ADR-2026-11-24-c.)
Coverage is unique baseline-kind intersection and the sum of original baseline counts for that
intersection, divided by total baseline observations. Duplicate regression records never inflate
coverage; unseen kinds are separate. Profile mismatch fails, empty denominators display N/A.
No metric implies test execution, path coverage or unseen/global completeness.

The owner authorized separate image-container expressions and an absent-array state. Each direct
or quoted-media image/gallery container has presence, >=1 and >=2 bits, preserving absent,
zero, one and multiple image members. Mixed galleries count only typed image entries.
IS_PRESENT means a member exists (including null); this is not schema validation. Splitting
keeps native JSONPath count expressions within the parser's cumulative complexity limit.
Array token sets remain unordered/deduplicated; no claim of cross-field image pairing is made.

## ADR-2026-11-21: Offline interactive HTML analysis dashboard with vendored Chart.js

**Status:** Accepted. **Date:** 2026-11-21. **Deciders:** Owner, Morpheus, Switch. **Related:** [Sprint 7 stories & architecture](sprints/USER_STORIES_SPRINT7.md).

### Context and drivers
The owner requested a generic `sketchtastic` CLI capability for a sketch analysis report delivered as an interactive, self-contained HTML dashboard using a charting library: weighted enumerated value distributions, min/max and numeric mean/median statistics across fields and aggregates, dual-handle time/run range sliders (`MIN`/`MAX` dates and `first_seen`/`last_seen`), interactive skit/sample exploration, and run-over-run history drift. The package must remain offline-capable with minimal PyPI runtime dependencies and no frontend build toolchain.

### Considered options
| Option | Benefits | Costs / risks | Decision |
|---|---|---|---|
| Vendored Chart.js v4.4.9 UMD (MIT) inlined as package data | Polished interactive charts, 100% offline, zero CDN/network calls, zero new PyPI deps, no Node build step | ~200 KB increase in wheel and generated HTML size; requires SHA-256 pinning and license bundling | Selected |
| CDN-loaded Chart.js with SRI hash | Minimal wheel/HTML size | Fails offline; breaks air-gapped/local analysis | Rejected |
| Pure hand-written SVG/Canvas | Zero third-party JS | Lower chart ergonomics and higher custom maintenance cost | Rejected |
| Heavyweight suite (Plotly / ECharts) | Built-in box plots/heatmaps | 1–3.5 MB wheel and HTML bloat | Rejected |

### Outcome and consequences
`sketchtastic analyze SKETCH -o REPORT.html` generates a single standalone HTML file with a strict offline CSP (`default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; font-src 'none'; connect-src 'none';`), vendored Chart.js v4.4.9 (`src/sketchtastic/assets/chart.umd.min.js` + MIT license + SHA-256 checksum), script-safe JSON escaping, and safe DOM rendering. Existing ASCII `report` and `show` commands remain unchanged. Because sketches retain per-skit summaries rather than raw per-event distributions, exact observation-weighted mean/median are reported for numeric token fields and skit counts, exact observation-weighted mean is reported for `AVG` aggregates (`sum / count`), and aggregate medians are explicitly labeled as across-skit statistics.

## ADR-2026-11-23: Lean dashboard payload builder & modular offline web assets

**Status:** Accepted. **Date:** 2026-11-23. **Deciders:** Owner ("keep lean"), Morpheus, Switch. **Related:** [Sprint 8 stories & architecture](sprints/USER_STORIES_SPRINT8.md), [Domain Model](DOMAIN.md).

### Context and drivers
After Sprint 7 and follow-up dashboard features (boolean types, ablation, Cramér's V / Theil's U correlations, Sankey, additive weightings, per-event histograms), `src/sketchtastic/dashboard.py` grew to 3,582 lines of inline Python strings while `src/sketchtastic/analysis.py` grew to 1,146 lines with 13 radon C/D functions (up to Grade D(24)). Auditing `dashboard.py` showed the browser never read Python's precomputed `ablation`, `correlations`, `concentration`, or computed field/aggregate statistics — JS already recomputed everything dynamically from `DATA.skits` to support live filtering, sliders, and `Weight by` re-weighting. Meanwhile `reporting.py` and `analysis.py` had a circular import (`PLC0415`) and parsed sketch YAML files twice.

### Considered options
| Option | Benefits | Costs / risks | Decision |
|---|---|---|---|
| Keep duplicated Python + JS statistical engines in sync | Preserves an internal Python stats dict | ~600L dead computation for the dashboard, larger HTML payloads, shotgun surgery and parity drift | Rejected |
| Lean Python payload builder + modular static `assets/dashboard/*` with direct `node` JS unit tests | Single source of truth for interactive stats, smaller HTML output, zero Python/JS drift, 0 radon C+ across `src/`, zero new runtime deps or frontend build toolchain | `analyze_sketch()` returns view-model metadata + skits/history rather than precomputed aggregates (not in `__all__`) | Selected |
| Introduce frontend bundler (Vite/esbuild) or heavy Python stats libs (`numpy`/`scipy`) | Standard JS/stats ecosystem tooling | Violates `docs/SDLC.md` minimal PyPI deps and zero-frontend-toolchain principles | Rejected |

### Outcome and consequences
`src/sketchtastic/analysis.py` is now a lean, single-pass dashboard payload and `.history/` drift builder (`meta`, `fields` keys, `aggregates` metadata, `weightings`, `time_axes`, `history`, `skits`). All interactive dashboard CSS, HTML, and JS live as static package-data files under `src/sketchtastic/assets/dashboard/` (concatenated into one inline HTML file at render time via single-pass regex substitution under a hardened offline CSP including `base-uri 'none'; form-action 'none';`), with `stats.js` kept 100% pure and unit-tested directly via `node`. Shared internal primitives (`src/sketchtastic/_io.py`) and single-pass `sketch.load_ranked_skits` eliminate circular/private cross-module imports and double YAML parsing. All of `src/` now passes `bobp make quality` with 0 extended ruff warnings, 0 vulture hits, and 0 radon C+ functions.

## ADR-2026-11-24: Structured tokens and validated sketch derivation

**Status:** Accepted. **Date:** 2026-11-24. **Deciders:** Owner, Morpheus; Smith and Switch
reviewed. **Related:** [Sprint 9 stories/architecture](sprints/USER_STORIES_SPRINT9.md),
[Sprint 9 UAT](sprints/UAT_PLAN_SPRINT9.md), [Domain Model](DOMAIN.md).

### 1. Context and problem statement

The owner requested a new named sketch derived from retained summaries, including history,
when the new profile only collapses distinctions. Format-0 tokens joined sets with commas and
represented missing/null/literal NULL ambiguously, limiting safe proofs. The owner then
explicitly requested structured tokens and rejected backward compatibility, accepting recapture.

### 2. Decision drivers

- Preserve observation totals and retained statistics while never fabricating missing detail.
- Make missing, explicit null, literal strings and arrays distinguishable throughout ingestion,
  identity, inspection and derivation.
- Preserve source files and all available history under a new output name.
- Keep dependencies/build tooling unchanged and implement bounded, reviewable proof rules.

### 3. Considered options

| Option | Benefits | Costs / risks | Decision |
|---|---|---|---|
| Keep format-0 strings and allow only provably safe legacy collapses | Reuses existing files immediately | Null/delimiter ambiguity rejects useful transforms and encourages unsafe inference | Superseded by owner's structured-token request |
| Structured format 1 plus legacy readers/migration | New captures retain detail while old files remain inspectable | Dual contracts and irrecoverable ambiguity; cannot truthfully restore missing information | Rejected by owner: no compatibility, recapture accepted |
| Structured format 1 only, conservative profile proofs and new output/history | Clear retained-value semantics; exact supported collapses; small implementation surface | Old files require recapture/replay; some array remaps remain unprovable | Selected |
| Arbitrary token remapping or sample-based re-sketching | Flexible and easy to appear successful | May disagree with future target-profile ingestion or fabricate population statistics | Rejected: violates conservation/proof requirement |

### 4. Decision outcome and justification

Sketches now require format 1. Value-producing DEFAULT/REGSUB/TRUNC preserve missing by omitted
keys and explicit null as real null. DEFAULT scalar values remain strings; native arrays become
recursively canonical sets. Repeated path matches are deduplicated and scalarized when only one
unique result remains. Boolean modifiers retain their explicit TRUE/FALSE behavior. Skit IDs
hash ordered key/value pairs so omitted dimensions cannot alias other dimensions. Profile YAML
stays version 0; no package release/version bump is implied. This owner-directed format decision
supersedes the earlier convention that sketch files would remain version 0 before package v1.0.

`sketch derive SOURCE --source-profile ORIGINAL -p TARGET -o NEWNAME` requires a fresh destination.
It supports unchanged/drop/reorder/rename fields, untyped DEFAULT-to-presence, scalar/null/missing
DEFAULT-to-IS_NULL/ANY/GLOB/REGEX/REGSUB, and typed time coarsening. Unsupported refinements and
array mappings reject rather than guessing. Direct arrays versus several selected values can
share the same set token but differ under a modifier, so structure alone does not prove every map.

The supplied original profile is authoritative: its hash covers identity fields, not aggregate
paths. Strict raw-state validation precedes reducers that might otherwise initialize absent
statistics. Collisions merge sufficient statistics, reject incompatible extrema kinds, and
recompute shares. Each available history file is transformed independently of the main sketch;
run IDs/times/counts/sequence marks survive and provenance records source/target profile IDs.

All outputs stage before no-clobber publication, with the main file published last. Handled
failures remove only owned output links/directories. Source data must be quiescent. FIRST/LAST
retain bounded matching samples, without claiming lost chronological order. A multi-path crash
transaction and migration tooling are explicitly excluded.

### Consequences

- Supported derivation conserves observations and cannot increase skit count. UAT demonstrated
  5 skits/5 observations -> 2 skits/5 observations with 1 preserved history run.
- Exact-set inspection uses canonical value keys separate from display labels; per-member
  charts and inherited field-name delimiter edge cases remain follow-up work.
- Format-0 captures require recapture or replay of original events. Legacy data is not deleted
  automatically. Source/target profiles and complete retained aggregate state remain necessary.
- Phase commits: `c7d53ec` (structured tokens), `d51518f` (validated derivation), `b9f4484`
  (CLI/history). Full 364-test suite, lint, quality and independent phase reviews passed before
  SDLC closeout; final release remains separately governed.

## ADR-2026-11-24-b: One streaming ingestion path; examples are stream filters

**Status:** Accepted. **Date:** 2026-11-24. **Deciders:** Owner, Morpheus. **Amends:**
ADR-2026-11-20 (Bluesky preparation).

### Context
`sketch merge` already reads a file or stdin as lines arrive, with back-pressure, run history and
`--max-seconds`/`--max-events`. The Bluesky example nevertheless grew a second, batch-shaped
ingestion path: `capture` staged its output and published only at the end, and `prepare` had its
own reader, a dedup set that grew with every post, its own `Sketch.upsert` loop (no workers, no
history) and a staged publish. Unwrapping was also implemented twice (`prepare` and
`capture --unwrap-posts`). The owner rejected this as batch processing and a DRY violation.

### Considered options
| Option | Benefit | Cost | Decision |
|---|---|---|---|
| Keep `prepare`, bound its dedup set | Small change | Still a second fold path beside `merge` | Rejected |
| Unwrap inside `capture` only (`--unwrap-posts`) | No extra module | Cannot process saved raw captures; capture mixes transport and domain | Rejected |
| One stdin→stdout unwrap filter; `capture \| unwrap \| sketch merge -` | One mechanism for live and saved data | `samples.json` line locators and `summary.json` go away | Selected |

### Outcome and consequences
`capture` only captures: it streams raw frames, flushing each line, and writes `.meta.json` last
(also on failure, with `stop_reason: "error"`). It has no default frame limit. `unwrap` is the
only unwrapping code; its dedup window is bounded (100,000 recent identities). `prepare`
(`examples/bluesky/demo.py`) is deleted. Representatives come from core `sketch export`;
coverage from core `sketch analyze --regression`. Make targets: `bluesky` (saved capture) and `bluesky-live`
(live), both one `bash -o pipefail` pipeline into `sketch merge -`.
Lost: per-kind source line locators (meaningless for a live stream) and the input SHA-256
summary. Live pipelines report capture counts on stderr only; persisting producer provenance in
the sketch is a backlog item. Stdin merges fold in-process (no `-j` workers).

## ADR-2026-11-24-c: The HTML dashboard is the one kind report

**Status:** Accepted. **Date:** 2026-11-24. **Deciders:** Owner. **Amends:** ADR-2026-11-20,
ADR-2026-11-21 ("Existing ASCII `report` ... remain unchanged").

### Context
`sketch report` printed a ranked ASCII kind list (IDs, counts, shares, tokens, aggregates, sample
locators). The `analyze` dashboard's skit explorer shows the same ranking with search, sorting,
weighting and retained samples. Two reports of one thing violate DRY.

### Considered options
| Option | Benefit | Cost | Decision |
|---|---|---|---|
| Keep both reports | Terminal-only users keep a text ranking | Two implementations of one view drift apart | Rejected |
| Dashboard only | One report; richer filtering and samples | Needs a browser; breaking CLI change | Selected |

### Outcome and consequences
`sketch report` and `reporting.report` are removed. Kind exploration is `sketch analyze`; IDs for
`export --id` are copied from the dashboard. `coverage` still prints its uncovered-kind list,
which shares the row formatter; its tests now cover that formatter. This is a breaking CLI change
(pre-1.0, no compatibility path).

## ADR-2026-11-24-d: Regression coverage is part of the dashboard, per history run

**Status:** Accepted. **Date:** 2026-11-24. **Deciders:** Owner, Morpheus. **Amends:**
ADR-2026-11-20 (generic `coverage` command).

### Context
`sketch coverage` printed two percentages plus ranked uncovered-kind rows: a second kind report
beside the dashboard, always exiting 0 (so no CI gate either). It ignored history, although each
run file is a sketch of that run and coverage over time is what shows a new capture's gaps.

### Considered options
| Option | Benefit | Cost | Decision |
|---|---|---|---|
| Keep `sketch coverage` text output | Scriptable text | Duplicate kind report; no history; no gate anyway | Rejected |
| Add history to the text command | History without a browser | Still a second report beside the dashboard | Rejected |
| Fold into `analyze --regression`, per run | One report; live filters; per-run gaps | Browser needed; no CI exit gate yet | Selected |

### Outcome and consequences
`sketch coverage` and its text formatter are removed. `sketch analyze --regression FILE -p
PROFILE` (both or neither) computes coverage in `sketchtastic.coverage` and adds it to the
payload: a per-skit `covered` flag, unknown regression kinds, and per history run the run's own
and cumulative kind / frequency-weighted coverage and the kinds it introduced that the corpus
does not cover. The browser computes the headline percentages live over the current filters and
weighting, and a Coverage filter (all / covered / uncovered) drives every view, so the explorer
is the uncovered-kind list. Runs under another profile ID are marked not comparable. Lists are
capped at 200 entries per run. No CI threshold/exit gate exists; add one to `analyze` if needed.

## ADR-2026-11-24-e: Retire `sketch show`; the dashboard is the only kind view

**Status:** Accepted. **Date:** 2026-11-24. **Deciders:** Owner. **Supersedes:**
the owner decision of 2026-10-14, Sprint 2 (`show --sort KEY`).
**Amends:** ADR-2026-11-24-c (one report).

### Context
After `report` and `coverage` were folded into the dashboard, `sketch show` remained as a
second, terminal-only kind table, with its own column, sort and token-cell rules to maintain.

### Considered options
| Option | Benefit | Cost | Decision |
|---|---|---|---|
| Keep `show` as a quick terminal view | No browser needed | Second kind report; duplicated formatting rules | Rejected |
| Remove `show`; use `analyze` | One kind view; less CLI code | A browser is needed to read a sketch | Selected |

### Outcome and consequences
`sketch show`, its `--sort` option and its table helpers are removed outright (pre-1.0, no
alias). The CLI is `merge`, `check`, `analyze`, `export` and `derive`. Read a sketch or a history
run file with `sketch analyze`, or as YAML.
