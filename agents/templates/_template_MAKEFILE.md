<!--
Thin Makefile forwarding shim template.
Owned by Tank (DevOps Engineer) — see .agents/skills/tank/SKILL.md and .agents/skills/build-env/SKILL.md.
Instantiate the fenced Makefile block below as `Makefile` at the repository root.
Remove this note, the Markdown wrapper, and the check block when creating the real `Makefile`; checks belong to templates.
-->
# Template: Thin `Makefile` Forwarding Shim

Use this template when bootstrapping a project with `mise.toml` and `Taskfile.yml`. Keep all build, test, lint, and operational recipes in `Taskfile.yml`; `Makefile` exists only so `make <target>` and `bobp make <target>` forward cleanly into Task.

```makefile
# Thin forwarding shim to Taskfile.yml (go-task) for `make` and `bobp make` muscle memory.
# All tasks, dependencies, and caching live in Taskfile.yml.
# Install `task` and the project toolchain via: mise install

# Pick up mise-installed tools even if the caller's shell has not run `mise activate`.
export PATH := $(HOME)/.local/share/mise/shims:$(HOME)/.local/bin:/snap/bin:$(PATH)

TASK := $(shell command -v task 2>/dev/null || command -v go-task 2>/dev/null)

.PHONY: all help _check-task

all: help

# Optional: keep targets directly here ONLY if they must work before `task` is installed
# (for example, `doctor` or `init` calling `./scripts/doctor.sh` or `./scripts/init.sh`).

help: _check-task
	@$(TASK) --list

_check-task:
	@if [ -z "$(TASK)" ]; then \
		echo "Error: 'task' (go-task) is not installed."; \
		echo "Install the toolchain with 'mise install' (https://mise.jdx.dev) or install Task directly (https://taskfile.dev/installation/)."; \
		exit 1; \
	fi

# Prevent the catch-all rule from matching build files themselves.
Makefile Taskfile.yml mise.toml: ;

%: _check-task
	@$(TASK) $@ $(if $(ARGS),-- $(ARGS))
```

<!-- RUBRIC-START -->
## Check — MAKEFILE

- [ ] **PASS** — `THIN` (Does build logic stay out of the Makefile?): All build, test, lint, and ops recipes live in `Taskfile.yml`; the `Makefile` contains only the forwarding shim and (optionally) pre-Task bootstrap scripts that must run before `task` is installed.
- [ ] **PASS** — `PATH` (Do mise-installed tools resolve in non-interactive shells?): Exports `$(HOME)/.local/share/mise/shims` on `PATH` so `bobp make <target>` finds `task` and toolchain binaries without `mise activate`.
- [ ] **PASS** — `GUARD` (Are failure and catch-all edge cases handled safely?): `_check-task` fails fast with an actionable `mise install` hint when `task` is missing, and `Makefile Taskfile.yml mise.toml: ;` prevents `%:` from matching build files.
- [ ] **PASS** — `ARGS` (Do standard invocations work through the shim?): `%:` forwards targets and optional `ARGS="..."` (`$(if $(ARGS),-- $(ARGS))`) to `Taskfile.yml`, and `bobp make help` lists tasks cleanly.
- [ ] **PASS** — `SYNTAX` (Is the real file valid Make syntax?): Template prose and check blocks are excluded from the generated `Makefile`, and recipe lines are indented with real tabs.
- [ ] **FAIL** — Any required PASS condition is unmet or unsupported; cite the missing evidence and smallest correction.
<!-- RUBRIC-END -->
