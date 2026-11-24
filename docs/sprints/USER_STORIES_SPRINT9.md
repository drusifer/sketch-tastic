# Sprint 9 User Stories: Derive a Sketch Without Recapture

* **Planning Size:** 13 points
* **Branch:** `sprint-9`
* **Source:** Owner's 2026-11-24 `/sprint` request, recorded in `agents/CHAT.md`.
* **Status:** Implementation phase gates passed: Trin UAT, Switch security and Morpheus review complete. Phase commits and sprint closeout pending.

## Goal

Users can create a separately named sketch from an existing sketch when their new distinctions
can be computed entirely from retained information. The command preserves observation totals,
mergeable statistics and each available history run, and refuses changes that require unseen
event detail. The source remains usable and unchanged. New captures retain unambiguous missing,
null and set-valued tokens, enabling exact derivation without delimiter inference.

## Assumptions made for the owner

- A new output filename represents the derived sketch name/version; package version is unchanged.
- **Owner decision:** no backward compatibility or migration; the owner will recapture. Sketch
  format becomes version 1 for structured tokens and all readers reject version 0.
- The user supplies the original and target profiles because existing sketch headers retain
  a profile hash, not the complete field and aggregate specifications.
- Equality is allowed: copying, renaming and reordering retained fields do not refine a skit.
- Validation may conservatively reject transformations the current representation cannot prove.
- Historical samples remain representative original records, without claiming to recover the
  chronological first/last event across groups whose ordering was not retained.

---

## STORY-SKT-19: Derive a coarser inventory with exact retained statistics
**Points:** 5 · **Owner:** Cypher

**As a** user changing a sketch's identity fields,
**I want** to derive its new inventory from existing skits when each old skit has one determinable
new identity,
**so that** I can reuse captured observations without collecting or replaying the original stream.

### Acceptance Criteria
1. Dropping, reordering or renaming retained fields produces the target profile identity and
   recomputed skit IDs. Colliding skits merge, preserving total observations and exact mergeable
   SUM/COUNT/MIN/MAX/AVG/HISTOGRAM state; shares are recomputed.
2. Supported value collapses include retained values to presence where presence is provable,
   and coarsening typed dates/timestamps. Tests compare results with direct folding of the same
   original fixture events under the target profile.
3. An added distinction, changed source selection/type, unprovable value mapping, temporal refinement,
   unsupported modifier change, or incompatible aggregate/sequence/event-time specification is
   rejected with an explanation identifying the field or setting and stating that original data
   or a compatible transform is required. Representative samples are never used as population
   evidence.
4. Validation inspects the supplied source profile, stored profile identity, every skit identity
   and retained state needed for derivation; corrupt/incomplete state is rejected instead of
   silently initialized or discarded.
5. Built-in observation counts and first/last-seen bounds survive collisions; retained original
   samples still belong to their derived skit. No exact chronological sample ordering is promised.
6. Neither successful nor failed derivation changes the source sketch, source profile or target
   profile. Empty sketches and identity-preserving transforms are supported.

## STORY-SKT-20: Publish a separately named sketch with its transformed history
**Points:** 3 · **Owner:** Cypher · **Dependency:** STORY-SKT-19

**As a** user maintaining longitudinal sketches,
**I want** one command to create a new sketch and consistently transformed history,
**so that** I can inspect drift and continue merging under the new profile without losing provenance.

### Acceptance Criteria
1. The command requires a distinct, unused output sketch name and rejects existing output files,
   existing output history, aliases to the source, and unsafe output symlinks without overwriting.
2. Every available source history run is transformed using the same validation and mapping as
   the main sketch. Run IDs, times and source counts are retained; history records refer to the
   new sketch, and derivation provenance identifies the source.
3. A bad history file fails the operation before final outputs are published. Handled write or
   publication failures remove only outputs created by this operation and preserve all sources.
4. A sketch with no history can be derived. The command reports the number of history runs
   copied, and it does not invent missing historical observations or a new capture run.
5. CLI help and README describe supported collapses, information-loss rejections, output naming,
   history behavior, representative-sample limitations and exit statuses. The command reports
   source/output skit counts and preserved observations on success.
6. Output is readable by existing `show`, `report` and `analyze` commands and accepts subsequent
   `merge` operations using the target profile, including sequence high-water protection.

---

## STORY-SKT-21: Retain missing, null and set values unambiguously
**Points:** 5 · **Owner:** Cypher · **Dependency:** Enables SKT-19/20

**As a** user capturing structured JSON events,
**I want** missing fields, explicit nulls and arrays represented distinctly in sketch tokens,
**so that** inspection and later collapse operations preserve information without guessing from
comma-delimited strings or sentinel words.

### Acceptance Criteria
1. For DEFAULT fields, a missing selection omits the token key, explicit null is a real null,
   and a selected native array is a sorted, deduplicated array, including empty and singleton
   arrays. Literal `"NULL"`, literal comma strings, null and arrays have distinct identities.
2. Multiple matching values are deduplicated and canonicalized; repeated identical matches do
   not create a distinct skit. Nested arrays remain nested sets, not flattened into leaf values.
3. Modifiers retain their explicit absence behavior: IS_PRESENT emits FALSE for no selection
   and TRUE for a selected member including null or an empty array. DEFAULT nonnull scalars
   continue using existing string tokens; this story does not introduce numeric/boolean tokens.
   All value-producing modifiers (DEFAULT/REGSUB/TRUNC) omit missing results and preserve
   explicit null as real null; failed type conversion yields missing, without a `"NULL"` sentinel.
4. Skit identities include field names and structured values in profile order, preventing
   omitted fields from aliasing other fields with the same value. Load/save preserves structures
   and rejects invalid token shapes or unsupported sketch versions.
5. `show`, `report`, `analyze`, dashboard filters/distributions and coverage work with omitted,
   null and array values without conflating values, throwing errors or interpreting token text
   as markup. Scalar/null/set display distinctions and selection state survive filtering.
6. Version 0 sketches are rejected with a clear recapture/rebuild explanation. No compatibility
   reader, shim or migration path is implemented. Existing version-0 fixtures are updated or
   retained only as rejection tests.

---

## Out of Scope

- Recapture, replay of original events, backfilling genuinely new distinctions, or inferring the
  distribution from retained representative samples.
- Arbitrary user code, guessed comma splitting for untyped values, lossy coercions presented as
  exact transformations, or a general proof engine for every modifier combination.
- Aggregate schema evolution, changed sequence/event-time semantics, migration or compatibility
  support for old sketches, unrelated browser UI changes, or package release/tag/push.
- Crash-consistent transactions spanning multiple output paths and concurrent writers modifying
  the source during derivation. The source must be quiescent; handled failures are cleaned up.

## Open Questions

None. These assumptions and conservative first-version boundaries are recorded for owner review.

---

# Architecture Document: Validated Sketch Derivation

* **Status:** Revised architecture approved by Smith Gate 2 and Switch design gate.
* **Author:** Morpheus
* **Last Updated:** 2026-11-24
* **Scope:** Sprint 9 Architecture

## 1. Executive Summary & System Overview

Introduce `sketch derive` as a transformation of retained skit state. A validated plan maps each
source token vector to exactly one target token vector. The mapping must agree with target
profile tokenization for every event represented by the retained state; matching just a sample
or reducing the number of skits is not proof. This is a conservative supported-transform engine,
not a general inference engine.

## 2. System Context & Boundaries

Local files are the boundary: the caller supplies source sketch, original profile, target
profile and a fresh output path. Existing profiles are authoritative configuration; the source
profile hash authenticates only identity fields, not aggregate semantics. The caller must supply
the actual source aggregate specifications; strict state-shape validation prevents accidental
defaults from silently replacing absent statistics, but cannot reconstruct missing provenance.
No network, service, dependency, external code execution or raw-event replay is introduced.

## 3. Component & Container Architecture

| Component | Responsibility | Inputs | Outputs |
|---|---|---|---|
| Token model | Canonical missing/null/scalar/set representations and keyed identity | Profile selections | Version-1 token mappings and skit IDs |
| Inspection surfaces | Render and key structured values without ambiguity | Version-1 tokens | CLI/report/dashboard displays, filtering and analysis |
| Derivation planner | Prove supported field mappings and compatible retained statistics | Original/target Profile, stored tokens | Validated per-field transforms or actionable refusal |
| Derivation reducer | Rekey skits and combine collisions using existing aggregate algebra | Source skits, validated plan | Target Sketch with recomputed shares |
| Bundle publisher | Validate main/history and publish separate output paths | Source file/history, profiles, destination | New sketch and transformed available history |
| CLI adapter | Parse flags, summarize results, render errors | CLI arguments | Exit 0/2 and concise messages |
| Sketch header | Retain derivation provenance through load/save/continued merge | Source path and profile IDs | Optional `derivation` mapping |

Use a focused new core module rather than growing ingestion logic. Extend `Sketch` with only
the small reusable state/provenance operations needed by derivation; reuse aggregate merging
and share calculations. Raw source-state validation precedes loading that would fill defaults.

## 4. Runtime Interaction & Critical Flows

1. Read and validate both profiles, including exact equality of aggregate, sequence and
   event-time specifications. Compile a conservative field mapping.
2. Resolve source/output locations; reject existing output/history and source aliases.
3. Read the main sketch and every available history YAML file; require source profile identity,
   valid version-1 IDs, a profile-ordered subset of source field keys (DEFAULT/REGSUB/TRUNC
   may be absent), canonical structured tokens and complete valid aggregate/built-in states.
4. Apply one mapping to the main sketch and each history run. A failure anywhere prevents final
   publication. Preserve each available run independently; never rebuild the main sketch by
   summing potentially incomplete history.
5. Preserve `last_run`, sequence high-water mark and run metadata; point a run's `sketch` at the
   destination. Record derivation source and source/target profile IDs. Do not create a capture
   run or pretend historical timestamps are derivation time.
6. Stage outputs locally, publish destination history without clobbering existing paths, then
   publish the main file last using no-overwrite filesystem operations. On handled failure,
   remove only paths owned by this invocation. Keep sources untouched.

## 5. Interface & Contract Specifications

```sh
sketch derive SOURCE --source-profile ORIGINAL.yaml -p TARGET.yaml -o NEW.sketch.yaml
```

- `SOURCE`: existing sketch; `--source-profile`: its complete original profile.
- `-p/--profile`: target profile; `-o/--output`: required fresh sketch filename.
- The output filename is the new name/version, e.g. `posts-v2.sketch.yaml`. Schema `version: 1`
  is required for all sketches; version 0 is rejected per owner direction. The target profile's
  existing hash scheme identifies the field contract within this new format.
- Exit 0: complete publication. Exit 2: invalid/unprovable input or handled output failure.
- Success summary states source/target skit counts, preserved observation count, output path
  and number of available history runs transformed. No claim that available history is complete.

### Structured token contract

- DEFAULT receives no selected value: return internal MISSING and omit that field key.
- DEFAULT receives explicit null: store `null` (Python `None`), distinct from string `"NULL"`.
- DEFAULT nonnull scalar: retain existing string conversion. Objects retain their existing
  scalar string conversion; native object token schemas are outside this change.
- DEFAULT receives a native array: recursively canonicalize members, sort and deduplicate by
  a deterministic type-aware encoding; retain an array even for `[]` and singleton arrays.
- Several JSONPath matches: canonicalize each selected value, deduplicate, then return the
  unique value if only one remains, otherwise an array of unique values. Repetition cannot
  change identity. Do not flatten nested array values.
- A wildcard with no matches omits the DEFAULT key; it cannot distinguish an absent parent
  array from an empty parent array. Select the parent directly if that distinction matters.
- Boolean modifiers keep their current missing/null behavior and TRUE/FALSE string outputs
  (IS_PRESENT is TRUE for explicit null). Value-producing DEFAULT/REGSUB/TRUNC all preserve
  missing as internal MISSING with omitted field keys, and explicit null as real null. Failed
  type conversions yield MISSING. No implicit missing/null conflation or generated `"NULL"`
  sentinel remains. Modifiers apply to original selected members, including arrays, rather
  than flattened array contents.
- `skit_id` hashes ordered key/value pairs, not only values. Reader validation enforces the
  supported canonical token algebra (strings, nulls, recursively nested arrays) and version 1.
- Inspection uses one explicit, collision-free value key for aggregation/filtering and a
  separate readable display. Missing, null, literal strings and arrays must remain distinguishable.
  Arrays remain set-valued categories in this sprint; per-member dashboard analysis is separate.

### Supported proof rules

| Change | Proof / guard |
|---|---|
| Keep/drop/reorder/rename a field | Retained source selection, modifier and type are unchanged; copy the existing token whole. Mapping must resolve unambiguously. |
| Untyped DEFAULT to IS_PRESENT | Same path; omitted key is FALSE, any retained value is TRUE, including real null, empty arrays and literal `"NULL"`. |
| Untyped DEFAULT to IS_NULL/ANY/GLOB/REGEX/REGSUB | Same path; scalar/null/omitted tokens can be evaluated with the target modifier. Array tokens reject unless a specific proof resolves directly selected array versus multiple selected values. Literal commas are ordinary scalar characters, never split. |
| Typed DATE/DATETIME DEFAULT to TRUNC | Same path/type; transform canonical retained temporal scalars/sets, map missing/null using target modifier semantics, deduplicate/sort. No delimiter decoding. |
| Typed TRUNC to coarser TRUNC | Same path/type, target unit no finer than source; canonical prefix truncation plus deduplication preserves identity. |

All other changes reject with field-specific explanations. Typed DEFAULT-to-presence remains
conservative because failed type conversion may lose selected-value information. A structured
array can represent a directly selected native array or multiple matches; modifiers applied to
the original selected value may differ between these interpretations, so reject unsupported
array remappings. A field not captured at all still cannot be reconstructed from representative
samples. Version-0 ambiguities are not guessed or migrated; the owner will recapture.
Proof is over the retained inventory (main and history), not an assertion that every possible
future event would have been derivable from the old profile. Future events use the target profile.

### Collision algebra

Counts, sums, extrema, AVG sufficient statistics and histogram state merge using their existing
implementations. Reject colliding MIN/MAX states with incompatible kinds rather than silently
discarding an extremum. Recompute shares over the new inventory. FIRST/LAST bounded samples
merge deterministically as retained matching samples; event-level chronological interleaving
cannot be recovered and is explicitly outside the contract.

## 6. Cross-Cutting Concepts & Resilience

| Failure Mode | Trigger / Condition | Behavior | User Impact | Blast Radius |
|---|---|---|---|---|
| Insufficient information | Unsupported mapping or ambiguous token | Refuse before publication, name field/reason | Supply compatible transform or original data | None |
| Wrong/corrupt inputs | Mismatched profile, IDs or missing/invalid state | Refuse whole bundle | Correct input/profile | None |
| Unsafe destination | Existing file/history, alias or symlink | Refuse without replacement | Choose new output name | None |
| Bad history | Invalid historical state/profile | Refuse whole bundle | Correct history first | None |
| Write/publication failure | Filesystem error | Clean operation-owned staged/published files on handled failure | Fix path/storage and retry | New output only |

Security boundaries: safe YAML loading, no execution of input strings, no synthesized paths
from unvalidated run headers, no overwrites of source/destination, and no arbitrary cleanup of
preexisting directories. Existing gitleaks staged hook is present; phase reviews run secret scan.
Source files must be quiescent. Multiple filesystem paths cannot form a portable crash-atomic
transaction; an abrupt process/host failure may leave an orphan destination history directory,
which a retry refuses rather than silently adopting. This limitation is documented.

## 7. Technical Stack & SDLC / Build Impact

Python 3.14+, existing PyYAML and profile validation stack. **Build-environment change: No.**
Use existing `bobp make test ARGS=test_derive`, `lint`, `test`, `test-all`, `smoke`, `build` and
security targets. No new language, dependency, mechanism or Make target; no Tank Phase 0 needed.
Preserve the user's pending capture/profile edits and data when running closeout checks.
The owner explicitly overrides the existing format-version-0 convention for this breaking
representation change; Tank records version 1 and no legacy support in SDLC at closeout.

## 8. Architectural Decisions (ADRs) & Technical Debt

- **S9-D1:** Validate original-to-target profile transformations using explicit conservative
  proofs; raw-event-compatible output is preferable to arbitrary token remapping that could
  disagree with later ingestion.
- **S9-D2:** Carry complete source profiles as command inputs; defer embedding full profiles in
  all sketches. State-shape validation is essential because existing hashes cover fields only.
- **S9-D3:** Preserve main inventory and each history independently, with separate name and
  provenance; never infer completeness from available history or backfill from samples.
- **S9-D4:** New files only, staged publication and main last; handled failures roll back owned
  paths. Portable multi-path crash transactions and concurrent source mutation are deferred.
- **S9-D5:** Exact additive/mergeable statistics; explicitly bounded representative sample
  semantics for FIRST/LAST after coarsening, consistent with existing parallel folding caveats.
- **S9-D6 (owner-directed scope expansion):** Structured DEFAULT tokens distinguish omission,
  real null and canonical array sets. Keep existing nonnull scalar/modifier token strings and
  recursively preserve nested arrays. Hash keys and values to avoid missing-field collisions.
- **S9-D7 (owner-directed compatibility policy):** Write/read sketch format version 1 only;
  reject version 0. No backward compatibility or migration; the owner will recapture. Update
  inspection surfaces and fixtures coherently instead of maintaining dual representations.
