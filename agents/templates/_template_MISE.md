<!--
mise.toml project toolchain template.
Owned by Tank (DevOps Engineer) — see .agents/skills/tank/SKILL.md and .agents/skills/build-env/SKILL.md.
Instantiate the fenced TOML block below as `mise.toml` at the repository root.
Replace `{placeholders}`, uncomment only the tools this repository actually uses, and remove this note, the Markdown wrapper, and the check block when creating the real `mise.toml`.
-->
# Template: `mise.toml` (Project Toolchain)

Declares pinned runtimes and CLI tools installed via `mise install` so local development and CI run identical versions without system-wide installs or `sudo`.

```toml
# Project toolchain for {Project}. Run `mise install` to install pinned runtimes and CLI tools.
# Install any OS-managed tools not managed by mise (e.g. {gcloud, ansible-playbook, or "None"})
# separately per docs/SDLC.md.

[tools]
task = "3"
gitleaks = "8"
# Language runtimes & package managers (uncomment and pin what this project uses):
# python = "3.13"
# uv = "0.7"
# node = "22"
# go = "1.24"
# Infrastructure / ops CLIs (uncomment and pin what this project uses):
# terraform = "1"
# packer = "1"
```

<!-- RUBRIC-START -->
## Check — MISE

- [ ] **PASS** — `PINS` (Are required tools explicitly pinned?): Declares `task` and `gitleaks` plus every project runtime and CLI tool that `mise` can manage, each with an explicit version pin (no unpinned `latest` unless justified in `docs/SDLC.md`).
- [ ] **PASS** — `PARITY` (Do pins agree across the repo?): Every runtime and tool version in `mise.toml` matches `docs/SDLC.md` and the language manifest (`requires-python`, `engines.node`, `go.mod`, etc.).
- [ ] **PASS** — `SCOPE` (Only real dependencies, zero secrets?): Contains only tools this project actually uses, with no commented-out boilerplate left over, no secrets/tokens, and no machine-local paths.
- [ ] **PASS** — `EXTERNAL` (Are non-mise prerequisites documented?): Any tool `mise` cannot install (OS packages, cloud SDKs) is noted in comments and in `docs/SDLC.md` Setup prerequisites.
- [ ] **PASS** — `CLEAN` (Does clean install work?): On a clean checkout, `mise install` succeeds without `sudo` and makes `task` and `gitleaks` available via `mise` shims.
- [ ] **FAIL** — Any required PASS condition is unmet or unsupported; cite the missing evidence and smallest correction.
<!-- RUBRIC-END -->
