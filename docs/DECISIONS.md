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
