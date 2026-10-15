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
