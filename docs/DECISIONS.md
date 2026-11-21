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
feature selection uses the saved profile. Original posts and source line locators are retained.
`report`, `export` and `coverage` live in the package CLI and know nothing about Bluesky.
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
