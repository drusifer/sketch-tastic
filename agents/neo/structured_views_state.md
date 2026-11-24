# Structured Views Working State

## Context
Sprint 9 worker owns analysis/reporting/dashboard consumers and tests. Owner approved structured tokens with no backward compatibility; new captures use sketch v1. Missing keys, null, scalar strings and recursive array sets must stay distinct. Root/planning approved minimal exact-set display and filtering; per-member distributions are deferred. Fully missing fields cannot be discovered from token-only sketches and are not invented.

## Current Task
Complete (100%). Added pure canonical token key/label helpers and own-property lookup in stats.js. Field distributions, ablation, correlations and Sankey group arrays by content; filters use canonical exact keys; chips, explorer and tooltips render explicit null/missing/array labels safely. Enum-set fields say Exact set combinations. Null and missing percentages are separate. Python payload annotations now admit structured values; existing report JSON rendering already works.

Tests first: dashboard run initially failed in 2 new cases (null .length TypeError and missing canonical helpers). After implementation, targeted dashboard 12/12, reporting 17/17, analysis 10/10 pass. No browser launched, no commits. Parent owns global formatting, lint and review.

## Next Steps
1. Parent runs format/lint/full suite and independent review.
2. If failures touch these consumers, preserve canonical exact-filter keys across charts/correlations/Sankey/URLs; do not revert to string coercion or array identity.
3. Per-member enum-set charts remain future work; current charts compare whole retained sets.
