<!--
Taskfile.yml (go-task v3) build and operations template.
Owned by Tank (DevOps Engineer) — see .agents/skills/tank/SKILL.md and .agents/skills/build-env/SKILL.md.
Instantiate the fenced YAML block below as `Taskfile.yml` at the repository root (go-task discovers `Taskfile.yml` automatically).
Replace every `{placeholder}`, omit tasks that have no meaning for the project (and document omissions in `docs/SDLC.md`), and remove this note, the Markdown wrapper, and the check block when creating the real `Taskfile.yml`.
-->
# Template: `Taskfile.yml` (go-task v3)

Authoritative build, test, lint, security-scan, and operational tasks for the project, fronted by the thin `Makefile` shim (`_template_MAKEFILE.md`) and using tools pinned in `mise.toml` (`_template_MISE.md`).

```yaml
# ==============================================================================
# {Project}: {one-line description}
#
# Quickstart:
#   mise install        # install pinned runtimes and CLI tools from mise.toml
#   bobp make install   # sync project dependencies and enable git hooks
#   bobp make test      # run the test suite
#
# A thin Makefile shim forwards `make <target>` / `bobp make <target>` here.
# ==============================================================================

version: '3'

# Uncomment when the project uses a gitignored .env file:
# dotenv: ['.env']

vars:
  TASK_BIN:
    sh: command -v task 2>/dev/null || command -v go-task 2>/dev/null || echo task

env:
  PATH: '{{.HOME}}/.local/share/mise/shims:{{.HOME}}/.local/bin:/snap/bin:{{.PATH}}'

tasks:
  default:
    aliases: [help]
    desc: Show available tasks
    silent: true
    cmds:
      - '{{.TASK_BIN}} --list'

  # --- Setup & Hooks ---

  install:
    desc: Create local environment, install locked dependencies, and enable git hooks
    cmds:
      - task: install-hooks
      - '{native-install-command, e.g. uv sync --locked --extra dev | npm ci | go mod download}'

  install-hooks:
    desc: Enable repo git hooks (gitleaks pre-commit secret scan)
    silent: true
    preconditions:
      - sh: command -v gitleaks >/dev/null 2>&1
        msg: "gitleaks is not installed. Run 'mise install' first."
    cmds:
      - |
        if [ -d .git ]; then
          git config core.hooksPath .githooks
          chmod +x .githooks/pre-commit
          echo "Installed: .githooks/pre-commit (gitleaks protect --staged) via core.hooksPath"
        fi

  # --- Quality Gates ---

  test:
    desc: Run the test suite (pass extra args via ARGS="..." or -- <args>)
    preconditions:
      - sh: '{env-check, e.g. test -d .venv || test -d node_modules}'
        msg: "Local environment missing. Run 'bobp make install' first."
    cmds:
      - '{native-test-command, e.g. uv run pytest {{.CLI_ARGS}} | npm run test -- {{.CLI_ARGS}}}'

  lint:
    desc: Run static checks (style, types, schema validation) without modifying files
    cmds:
      - '{native-lint-command, e.g. uv run ruff check . | npm run lint}'

  format:
    desc: Format project files to repository style
    cmds:
      - '{native-format-command, e.g. uv run ruff format .}'

  security-scan:
    desc: Run all build-time security scans (secrets and dependency audits)
    cmds:
      - task: security-scan-secrets

  security-scan-secrets:
    desc: Scan git history for committed secrets (gitleaks, git-aware)
    preconditions:
      - sh: command -v gitleaks >/dev/null 2>&1
        msg: "gitleaks is not installed. Run 'mise install' first."
    cmds:
      - gitleaks detect --source .

  # --- Build, Run & Cleanup ---

  build:
    desc: Produce the distributable build artifact
    cmds:
      - '{native-build-command}'

  run:
    desc: Run the primary application entry point (pass args via ARGS="..." or -- <args>)
    cmds:
      - '{native-run-command} {{.CLI_ARGS}}'

  clean:
    desc: Remove build outputs and Task caches (keeps local environment)
    cmds:
      - rm -rf build/ dist/ .task/

  distclean:
    desc: Remove build outputs, caches, and the local environment
    deps: [clean]
    cmds:
      - rm -rf '{local-env-dir, e.g. .venv | node_modules}'
```

<!-- RUBRIC-START -->
## Check — TASKFILE

- [ ] **PASS** — `CONTRACT` (Does it implement the standard task surface?): Uses `version: '3'` and defines `default` (aliased `help`), `install`, `install-hooks`, `test`, `clean`, and `distclean` (plus `lint`, `format`, `build`, `run`, `security-scan*` where meaningful), each with a clear `desc:` matching `docs/SDLC.md`.
- [ ] **PASS** — `SHIMS` (Do pinned tools resolve reliably?): Prepends `{{.HOME}}/.local/share/mise/shims` to `env.PATH` so tasks work identically in local shells, agent runs (`bobp make`), and CI without `mise activate`.
- [ ] **PASS** — `NATIVE` (Does it respect language conventions and isolation?): Calls the language's native manifest/local-environment tool (`uv`, `npm`, `go`, `cargo`, etc.), forwards `{{.CLI_ARGS}}` where arguments apply, and never installs system-wide or uses `sudo`.
- [ ] **PASS** — `GUARDS` (Are failures, secrets, and caching handled safely?): Missing tools or local environments fail fast via `preconditions:` with actionable hints; secret scans use git-aware `gitleaks` (never `--no-git`); any checksum-cached tasks list `sources:` and `.task/` is gitignored.
- [ ] **PASS** — `IDEMPOTENT` (Does clean rebuild work repeatably?): `install`, `install-hooks`, and `clean` are safe to run twice; from a clean state, `bobp make install && bobp make test` succeeds.
- [ ] **FAIL** — Any required PASS condition is unmet or unsupported; cite the missing evidence and smallest correction.
<!-- RUBRIC-END -->
