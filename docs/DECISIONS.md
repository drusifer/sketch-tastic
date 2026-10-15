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
