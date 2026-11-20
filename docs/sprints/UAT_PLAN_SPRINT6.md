# Sprint 6 UAT: generic regression coverage

**Owner:** Trin / Smith. **Status:** core reporting and default post-profile reviews accepted.

## Acceptance evidence

- Final from-clean gates: 279 tests pass on Python 3.14 and 3.15, including 15 reporting,
  seven original-post preparation and six profile contracts (plus unchanged capture tests).
  Lint, three installed-wheel smoke tests, wheel/sdist build, secret scan and locked audit pass.
- Independent Morpheus review approved after an export error-handling fix. Switch implementation
  gate: no blocking security findings. Serialization failures now return clear errors and leave
  no output file. No dependencies or build targets changed.
- `prepare` on the existing ten-minute capture with `data/post-reporting-uat.yaml` retained
  20,789 original posts and 796 kinds. This valid six-field UAT profile omits image cardinality
  while that separate expression is unresolved. Zero-image posts remain in the baseline.
- `report ... --limit 3` ranks full IDs, counts, weight, cumulative percentage and original
  sample pointers. `export ... --id` selected three unchanged posts, with JSONL line locators.
- `coverage` on those three records reports 6,362 / 20,789 observations (30.6%) and
  3 / 796 kinds (0.4%). All representatives report 100% for both, no unknown kinds.
- Unit fixtures verify 90/9/1 weighting, duplicate candidates, unknown kinds, empty/zero-weight
  baselines, mismatched/missing profile IDs, malformed rows, safe ASCII and no-clobber exports.

## Reproduce the live walkthrough

```sh
bobp make -vvv run ARGS="report data/posts-reporting-uat/posts.sketch.yaml --limit 3"
bobp make -vvv run ARGS="coverage data/posts-reporting-uat/posts.sketch.yaml -p data/posts-reporting-uat/profile.yaml data/regression-top3-posts.jsonl --limit 3"
bobp make -vvv run ARGS="coverage data/posts-reporting-uat/posts.sketch.yaml -p data/posts-reporting-uat/profile.yaml data/posts-reporting-uat/representatives.jsonl --limit 3"
```

## Profile resolution

The combined default 0/1/2+ image profile expression exceeded the JSONPath library's cumulative
parse-complexity limit twice. Oracle located `max_expression_depth=30` and the increment-only
parser accounting. The owner authorized splitting and adding absence as a fourth state.
Six profile tests now pass with present/any/multiple bits for each of four typed containers,
including missing vs empty, mixed galleries, unsupported outer embed, null presence and no
post mutation. Independent review approved after adding the outer quoted-media type guard.

## Final default-profile live UAT

The owner-approved profile prepares **20,789 original posts into 860 skits** under profile ID
`5613b15ed319835056c13b1e4dd2d58f`. All representatives re-fold to exactly the baseline kind IDs.
Core coverage reports 100% of 860 kinds and 20,789 observations, with no unseen regression kinds.
The report lists full IDs and exact sample pointers; selected export produces original-post JSONL.

```sh
bobp make -vvv run ARGS="report data/bluesky-posts/posts.sketch.yaml --limit 3"
bobp make -vvv run ARGS="coverage data/bluesky-posts/posts.sketch.yaml -p data/bluesky-posts/profile.yaml data/bluesky-posts/representatives.jsonl --limit 3"
```

Existing captures were temporarily preserved outside data during clean targets, then restored.
Smith verdict: UAT COVER/STEPS/FAIL/DATA/EVID=PASS. No browser needed for the ASCII CLI.
