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
