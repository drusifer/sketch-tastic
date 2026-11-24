# sketch-tastic — SDLC

How this project is built, tested, changed and released — the source of truth for change
management. **Owned by Tank**; to change anything here, ask `@Tank *devops sdlc <what and why>`
— the mechanism and this document change together.

The code moved here from `drusifer/fingerling` (`packages/fingerprint-sampler`) on 2026-10-14,
with its git history (`git subtree split`). The process below is fingerling's, carried over and
cut down to one package; owner decisions made there still apply unless this file says otherwise.

## 1. Toolchain

| | Python |
|---|---|
| Runtime version | 3.14 and later — `requires-python = ">=3.14"`; 3.14 and 3.15 are tested; development uses 3.14 (`.python-version`) |
| Manifest | `pyproject.toml` at the root: the package, dev tools in `[dependency-groups] dev`, tool config |
| Lockfile | `uv.lock` (committed) |
| Package manager | `uv`; build backend `hatchling` |
| Local environment | `.venv/` (gitignored, isolated from system site-packages) |

Other required tools:

- `make`.
- `uv` — install once per machine with `pipx install uv` (no sudo). It also supplies the
  interpreters for `make test-all`.
- `gitleaks` — on `PATH`; needed by `make secrets` and the pre-commit hook.
- `curl` and `gunzip` — only for `make gharchive` and `make profile`.
- `bobp` — team tooling (`bobp make`, `bobp chat`, `bobp tldr`); wraps this Makefile but adds
  no targets to it. `via` — behind `make via_index`. Neither is a project dependency.

## 2. Setup

From a clean checkout:

```sh
pipx install uv   # once per machine
make install      # uv sync --all-extras, and points git at .githooks/
make test
```

Nothing is installed into the system Python (it is externally managed, PEP 668). Never use
`sudo pip` or `--break-system-packages`.

## 3. Make targets

There is exactly one Makefile, at the repository root, and it is the only entry point: no
included or generated make files, no wrapper scripts. Environment-using recipes run tools from
`.venv/bin/` and stop with "No .venv - run 'make install' first" if it is missing. Agents invoke
targets as `bobp make <target>`.

| Target | Runs | Notes |
|---|---|---|
| `install` | `uv sync --all-extras` + `install-hooks` | exact install from `uv.lock`; idempotent |
| `install-hooks` | `git config core.hooksPath .githooks` | enables the gitleaks pre-commit hook |
| `test` | `unittest discover -s tests` | `ARGS=test_cli` runs one module |
| `test-all` | the tests on Python 3.14 and 3.15 in throwaway uv environments | downloads interpreters on first use |
| `smoke` | `build`, then the `smoke/` suite inside a throwaway environment holding only the built wheel | runs the installed command, the shipped examples and the README's own examples |
| `lint` | `ruff check .` and `ruff format --check .` | changes nothing |
| `quality` | extended `ruff` rules, `vulture`, `radon cc -nc` over `src/` | report only, always exits 0; Trin reads it at UAT |
| `format` | `ruff check --select I --fix .` and `ruff format .` | rewrites files |
| `secrets` | `gitleaks detect --source .` | git-aware: scans history and tree |
| `build` | `uv build --out-dir dist`, then runs the built wheel's command in a clean environment | wheel + sdist in `dist/` (gitignored) |
| `release-check` | compares `TAG=v<x.y.z>` with the package version | used by the publish workflow |
| `check` | `python -m compileall -q` over `src`, `tests`, `smoke` | syntax check only |
| `run` | `.venv/bin/sketch $(ARGS)` | the CLI |
| `gharchive` | downloads one GH Archive hour (`GH_HOUR`) into `data/` once, then merges it with `examples/gharchive.yaml` into `data/gharchive/` | example at scale; needs network and `curl` |
| `profile` | same hour, merged into fresh sketches in `build/profile/`: wall time with all cores and with `-j 1`, a short hash of the `-j 1` sketch (deterministic), then a cProfile run (`PROFILE_ARGS`, default `-j 1`; `PROFILE_ARGS=` profiles a parallel run's parent) with the top 25 functions in `build/profile/profile.txt` | the only way to measure speed (owner, Sprint 3); the hash shows output is unchanged on the same day |
| `clean` | removes `__pycache__`, `.ruff_cache`, `dist`, `data` | keeps `.venv` |
| `distclean` | `clean` + removes `.venv/` | |
| `help` | lists targets | default goal |
| `via_index` | `via index .` | builds the code index for the `via` tool |

Lint rules are pinned in `[tool.ruff.lint] select` (`E4`, `E7`, `E9`, `F`, `I`); widening them
is a Mechanism-class change. `agents/` (BobProtocol tooling) and Markdown are excluded.

## 4. Dependencies

### Optional Bluesky terminal demo

`bobp make bluesky-install` installs the `demo` dependency group (websockets) into the same
project environment. It is not a package runtime dependency. `bobp make bluesky-capture
ARGS="--seconds 60 --output data/bluesky.jsonl"` streams public JSON metadata to a file; `bobp make
bluesky INPUT=... SKETCH=...` pipes a saved capture through `examples.bluesky.unwrap` into
`sketch merge -`, and `bobp make bluesky-live SKETCH=... ARGS="--seconds N"` does the same live.
Generic reporting, representative
export and regression coverage live in the package CLI, via `bobp make run ARGS="analyze ..."`
(coverage with `--regression FILE -p PROFILE`) and `export ...`. `bobp make test-bluesky` runs the focused input/profile tests;
`bobp make test ARGS=test_reporting` runs generic reporting tests. Both run in the normal suite.
No frontend toolchain or web server is used. Captures and generated sketches live under ignored
`data/`; `clean` removes them. Preserve captures before from-clean conformance checks.

### Security tooling

`bobp make security-install` installs the optional `security` (pip-audit) and `demo` groups.
`bobp make security-scan` runs `security-scan-secrets` (git-aware, redacted gitleaks) and
`security-scan-python` (all lockfile groups exported with frozen versions and audited without
dependency resolution). Both must pass before release. `bobp make security-test-hook` verifies
that the staged hook rejects a synthetic key using a temporary alternate index; the real index
is untouched. The hook uses `gitleaks git --pre-commit --staged --redact`. Scanner inputs and
output are under ignored `build/`. No advisories are ignored or accepted by default.

- **Add a runtime dependency:** `uv add <package>`. Every runtime dependency becomes an install
  requirement for PyPI users — keep them minimal (today: PyYAML, jsonpath-rfc9535, jsonschema).
- **Add a dev tool:** `uv add --dev <package>` (the `dev` dependency group).
- **Upgrade / remove:** `uv lock --upgrade-package <package>` / `uv remove <package>`, then
  `make install`.
- **Commit afterwards:** `pyproject.toml` **and** `uv.lock`, together. Never hand-edit `uv.lock`.
- **Who:** Neo adds and bumps dependencies. A new package manager, language or Python version is
  a mechanism change — Tank's.

## 5. Quality gates

| Gate | Target | Required before |
|---|---|---|
| Lint + format | `make lint` | every handoff to Trin; sprint close |
| Tests | `make test` | every handoff to Trin; sprint close |
| Smoke (installed wheel + README) | `make smoke` | sprint close only; keep the suite small — behaviour is tested in the unit tests |
| Tests, all Pythons | `make test-all` | sprint close |
| Secret scan | `make secrets` | sprint close; staged changes are scanned on every commit by the hook |
| Package build | `make build` | sprint close; before any tag |

Verification happens only through tests and `make` targets — no throwaway commands (owner rule
carried over from fingerling). A change that renames or removes a public name runs the whole
`make test` before it merges.

## 6. Change management

### Change classes

| Class | Examples | Proposed by | Approved by | Must pass | Recorded in |
|---|---|---|---|---|---|
| Routine | feature, fix, refactor, docs, adding a dependency via section 4 | the user, or a Cypher story | Trin UAT, then Morpheus review | section 5 gates | commit, `task.md`, sprint stories |
| Mechanism | toolchain, manifest layout, make targets, gates, CI, this document | anyone, via `@Tank *devops sdlc` | Tank; the project owner for a new policy | from-clean rebuild + section 5 gates | this file, `docs/DECISIONS.md` |
| Release | version bump, tag, publish | Cypher at sprint launch | project owner pushes the tag | section 5 gates on the merge commit | tag, sprint chat report |
| Emergency | fix outside a sprint | the user | the user | section 5 gates | commit; reviewed at next sprint close |

### Flow

1. **Request** — the user asks in the session; it is logged to `agents/CHAT.md`. Anything larger
   than one concrete change runs as a sprint (`sprint` skill; Tier 1 or 2 per `AGENTS.md`).
2. **Branch** — every sprint works on its own branch, `sprint-<N>`, created from an up-to-date,
   clean `main`. A single concrete change uses `fix/<slug>`. Nothing is committed directly to
   `main`.
3. **Implement** — through `make` targets only; tests accompany behaviour changes, written first.
4. **Gate** — the section 5 gates pass locally before each handoff.
5. **Review** — Trin verifies each acceptance criterion; Morpheus reviews the code; Smith tests
   user-facing behaviour at sprint close.
6. **Commit** — agents commit on the branch as work passes review (at least once per phase),
   using Conventional Commits (below).
7. **Integrate** — after Tank's `*devops sdlc-check` passes and Cypher launches the sprint, and
   once the chat log holds every phase marker, Smith's approvals, the retro and the launch,
   agents merge to `main` with `git merge --no-ff`, and delete the branch. **Agents push only
   when the owner says so.**
8. **Record** — the sprint chat report (`bobp chat-report`), `docs/DECISIONS.md` for decisions,
   user docs.

### Commit messages — Conventional Commits

```
<type>(<scope>)<!>: <summary in the imperative, no full stop>

<why, and the story id, e.g. STORY-SKT-01>

BREAKING CHANGE: <what breaks and what to do>      (only when applicable)
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `build` (manifest, lockfile, Makefile), `ci`,
`chore`. A breaking change carries `!` after the scope and a `BREAKING CHANGE:` footer.

### Rules

- Never commit `.venv/`, build output, `data/`, local settings, or secrets.
- A sprint merges to `main` only after Tank's `*devops sdlc-check` (section 10) passes.
- **Rollback:** `git revert -m 1 <merge commit>` on a `fix/` branch backs out a whole sprint.
- **Changing this document:** only Tank edits it; every edit updates the Last verified line.

## 7. Versioning and release

- **What is versioned:** the package; its version is `[project] version` in `pyproject.toml`
  (currently `0.2.0`, carried over).
- **Scheme:** Semantic Versioning; while the version is `0.x`, a breaking change bumps the minor.
- **No backwards compatibility before 1.0** (owner): no shims, aliases, deprecation paths or
  migrations. Old forms are deleted outright.
- **Mainline development** (owner, 2026-10-14, carried over): no tags, version bumps or release
  commits until the owner says otherwise.
- **Data formats:** profiles retain `version: 0`. Sketch files use `version: 1` for structured
  tokens (omitted missing keys, real nulls, canonical array sets, and keyed identity hashing).
  The owner authorized this format change during Sprint 9 on 2026-11-24 and explicitly declined
  backward compatibility: version-0 sketches are rejected, with no adapter or migration; the
  owner will recapture. Derivation operates on version-1 sketches and all available history.
  This data-format version is independent of the unchanged package version.
- **Published:** pushing a `v<version>` tag triggers the publish workflow (section 8); only the
  owner pushes tags.

## 8. CI / deploy

Both workflows call only `make` targets, so CI cannot drift from the local gates.

| Workflow | Trigger | Does |
|---|---|---|
| `.github/workflows/ci.yml` | by hand only (`workflow_dispatch`), as in fingerling | Matrix over Python 3.14 and 3.15: `make install`, `make lint`, `make test`. Separate job: `make secrets` over the full history. |
| `.github/workflows/publish.yml` | push of a tag `v*` | Reruns the CI gates; `make release-check`; `make build`; publishes `dist/` to PyPI by trusted publishing (no stored token). |

Release `v0.2.0` was published with owner authorization on 2026-11-17 (America/New_York).
Trusted publishing is configured for `drusifer/sketch-tastic`, workflow `publish.yml`,
environment `pypi`. The GitHub environment has no approval gate. Publish run `44212325102`
passed all CI gates and published the wheel and sdist, verified on PyPI. There is no deploy target.

## 9. Known deviations

- **`uv` and `gitleaks` are machine prerequisites**, not installed by `make install`.

## 10. Conformance check

Run by Tank at sprint close (`*devops sdlc-check`):

1. `make distclean && make install && make lint && make test && make secrets && make build`
   passes, and `make test-all` passes on every supported Python.
2. Every third-party import is declared in `pyproject.toml` (the package imports only PyYAML,
   jsonpath-rfc9535 and jsonschema), and `uv lock --check` reports the lockfile is up to date.
3. `.venv/pyvenv.cfg` still says `include-system-site-packages = false`.
4. Every target in section 3 exists and still does what the table says; there is still only one
   Makefile, with no team-tooling targets.
5. No doc or script tells people to run bare `python3`/`pip` against the project.
6. `.venv/`, `dist/` and `data/` are ignored; `git config core.hooksPath` is `.githooks`.
7. This sprint's changes followed section 6: on the sprint branch, Conventional Commits, chat
   report with a section for every phase and for close, nothing pushed without the owner.
8. `make smoke` passes, and a second `make install` changes nothing.
9. The workflows invoke only `make` targets that exist.

## 11. Agreed changes not yet built

None. Distribution `sketch-tastic`, Python import `sketchtastic`, CLI command `sketch` (renamed
from `sketchtastic`/`skt` per owner request; sketch and skit vocabulary preserved).

---
*Last verified: 2026-11-24 by Tank at Sprint 9 close (`*devops sdlc-check`, re-run after the
owner-directed Phase 4). From-clean `bobp make distclean`, `install` (x2, tree unchanged), `lint`,
`test`, `secrets`, `build`, `test-all` (364 tests on 3.14 and 3.15), `smoke` (4 installed-wheel
tests, bundled Chart.js and 11 `assets/dashboard/*` files), `security-install`, `security-scan`
(0 leaks, 0 vulns) and `uv lock --check` passed; `bobp make quality` reports 0 extended ruff,
0 vulture and 0 radon C+ results. The virtualenv excludes system packages, `.githooks` is active,
`.venv`, `dist` and `data` are ignored, and the 545 MB of `data/` captures were moved aside and
restored. Phase 4 changed make targets (`bluesky` now pipes a saved capture through
`examples.bluesky.unwrap` into `sketch merge -`; new `bluesky-live`; both use bash pipefail) and
the CLI (`report` and `coverage` removed; `analyze --regression -p`). Package runtime
dependencies and release workflows are unchanged. v0.2.0 remains the published release.*
