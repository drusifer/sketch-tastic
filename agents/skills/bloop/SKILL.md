---
name: bloop
description: Top-level workflow loops (Bob Loops) that chain multiple personas autonomously. Use *fix, *review, *impl, *qa, or *plan sprint instead of manually invoking each persona in sequence.
triggers: ["*fix", "*review", "*impl", "*qa", "*plan sprint", "*deploy"]
requires: ["bob-protocol", "chat", "make"]
---

Top-level loop commands (Bloop) that run multi-persona chains autonomously without the user needing to invoke each step.

TLDR:
    Use Bloop commands when you want a full workflow, not a single-persona response.
    Each loop runs its persona chain to completion — saving state and posting handoffs at every step.
    For direct single-persona control, use `*chat @persona *command` instead.
    Context budget rule: after each phase, if context > 60% recommend `/clear` before continuing.
    Protocol rule: do NOT re-invoke bob-protocol or sub-skills already loaded in this session.

# Bloop — Bob Loop Multi-Persona Workflow Commands

## Overview

Bloop commands trigger an **autonomous chain** of personas. Each persona completes its role, saves state, hands off to the next, and the chain continues until the loop is done or a gate requires input.

**Rule:** Every persona in a loop MUST save state and post a handoff message before switching — see bob-protocol State Management.

---

## Bloop Commands

### `*fix <thing>`
**Fix loop** — investigate, fix, test, and review a bug or broken behavior.

```
Chain: Neo → Trin → Morpheus
```

| Step | Persona | Action |
|------|---------|--------|
| 1 | Neo | Investigate and fix: `*swe fix <thing>` |
| 2 | Trin | Verify fix, run tests: `*qa uat <thing>` |
| 3 | Morpheus | Code review: `*lead review <thing>` |

- If Trin's tests fail → back to Neo (`*swe fix`)
- If Morpheus review fails → back to Neo (`*swe fix`)
- Anti-loop: if Neo fails twice → Oracle consult required before retry

**Example:** `*fix auth token expiry bug`

---

### `*impl <phase>`
**Implementation loop** — implement, test, and review a feature or sprint phase.

```
Chain: Neo → Trin → Morpheus → [Tank if deploy in scope] → [Smith if UX/dev-facing behavior changed] → [context check]
```

| Step | Persona | Action |
|------|---------|--------|
| 0 | (bloop) | If `<phase>` is "next phase": read `agents/mouse/state.md` (Current Task section) and echo "Resolved: next phase = Phase N. Proceeding." before starting chain |
| 1 | Neo | TDD implementation: `*swe impl <phase>` |
| 2 | Trin | UAT — run tests, verify acceptance criteria: `*qa uat <phase>` (unit + integration only; E2E requires a separate `@Trin *qa e2e` invocation) |
| 3 | Morpheus | Code review — quality and architecture: `*lead review <phase>` |
| 3a | Tank | **DevOps gate** (if phase touches env vars, deployment, CI, or infra): `*devops review <phase>`. Tank approves or flags infra concerns before deploy. Skip if phase is app-only. |
| 3b | Smith | **UX gate** (if the phase changes behavior a developer/end-user directly observes or interacts with — CLI output, hook responses, error messages, onboarding flow, etc. — not purely internal refactors): `*user test <phase>` against the real running behavior, not just a spec review. Skip if the phase is internal-only (e.g. a pure data-layer/config-engine phase with no observable surface yet). If `task.md` or any prior planning artifact says "Smith re-engages" for a specific phase, that phase's Smith step is **required, not optional**, regardless of this default heuristic. |
| 4 | (bloop) | **Context check**: report current context %. If > 60%, post "Context at X% — recommend `/clear` before next phase." and stop. |

- If Trin UAT fails → back to Neo for that phase only
- If Morpheus review fails → back to Neo for that phase only
- If Tank review flags infra issues → back to Neo/Morpheus to resolve before Tank re-reviews
- If Smith's UX test flags issues → back to Neo for that phase only
- Do NOT restart the full sprint; fix the failing phase only

> **Lesson (Sprint 1, Project Scalene):** a sprint plan wrote "Smith re-engages post-Phase 2 for `*user test`" in `task.md`, but the `*impl` chain at the time had no Smith step at all — so it silently never happened, and the sprint closed without any UX testing against real hook behavior. If a plan promises a persona re-engagement, it must correspond to an actual step above, not just prose in `task.md`.

**Example:** `*impl phase-2`

---

### `*qa <thing>`
**QA loop** — test and review without reimplementation.

```
Chain: Trin → Morpheus
```

| Step | Persona | Action |
|------|---------|--------|
| 1 | Trin | Test and verify: `*qa test <thing>` |
| 2 | Morpheus | Review results: `*lead review <thing>` |

**Example:** `*qa the new export command`

---

### `*review <thing>`
**Review loop** — architecture and quality review of existing code or a deliverable.

```
Chain: Morpheus → Trin (optional)
```

| Step | Persona | Action |
|------|---------|--------|
| 1 | Morpheus | Architecture review: `*lead review <thing>` |
| 2 | Trin | Quality review (if Morpheus flags issues): `*qa review <thing>` |

**Example:** `*review the new API design`

---

### `*plan sprint`
**Sprint planning loop** — full planning sequence from stories through phase breakdown.

```
Chain: [SDLC gate] → Cypher → [Smith gate] → Morpheus → [Smith gate] → Mouse → Morpheus review → [Tank if deploy or build-env in scope]
```

| Step | Persona | Action | Gate |
|------|---------|--------|------|
| 0 | (starter) | **SDLC gate**: confirm `docs/SDLC.md` exists. Missing → `@Tank *devops sdlc` and stop until Tank confirms it is written. | Blocker |
| 1 | Cypher | Write stories + acceptance criteria: `*pm plan sprint` | Smith review |
| 1a | Smith | `*user review <stories>` → `*user approve` or `*user reject` | Must approve |
| 2 | Morpheus | Architecture decisions: `*lead arch sprint` | Smith review |
| 2a | Smith | `*user feedback <arch>` → `*user approve` or `*user reject` | Must approve |
| 3 | Mouse | Break into short phases (1-3 tasks each): `*sm plan sprint` | Morpheus review |
| 3a | Morpheus | Review sprint plan vs. architecture: `*lead review sprint plan` | |
| 3b | Tank | **DevOps planning gate** (if sprint includes deployment, env, infra, or build-environment work — a new language, package manager, runtime version, or dependency mechanism): `*devops infra <sprint>` — Tank reviews sprint for infra impact, adds deployment tasks (sequenced last) and build-environment tasks (sequenced as Phase 0, before Neo) to the plan, and confirms pipeline readiness. Skip if neither applies. | |

**Gates are hard stops** — Smith must explicitly `*user approve` before the chain continues. Step 0 is a hard stop too: no stories are written until `docs/SDLC.md` exists. Tank's 3b step is required (not optional) whenever Cypher's stories include env var changes, new services, or deployment work, or Morpheus's architecture changes the build environment. Sprint close adds Tank's `*devops sdlc-check` before Oracle's groom (see the `sprint` skill, Step 6a).

**Example:** `*plan sprint`

---

### `*deploy <env>`
**Deploy loop** — ship a tested, reviewed build to a named environment.

```
Chain: Tank → Trin (smoke) → report
```

| Step | Persona | Action |
|------|---------|--------|
| 1 | Tank | Deploy to `<env>`: `*devops deploy <env>` — push to target branch, trigger deploy, monitor build |
| 2 | Trin | Post-deploy smoke test: `*qa verify deploy` — validate critical paths are live (login, form, admin dashboard) |
| 3 | (bloop) | Report: pass → "Deploy to `<env>` confirmed live." / fail → Tank rolls back, Trin reports failure |

**Precondition:** `*deploy` should only run after `*impl` has passed all gates (Trin UAT + Morpheus review + Tank devops review).

**Example:** `*deploy prod`

---

## When to Use Bloop vs. Direct Invocation

| Situation | Use |
|-----------|-----|
| Fix a bug end-to-end | `*fix <bug>` |
| Implement a feature with tests and review | `*impl <feature>` |
| Just run tests and review | `*qa <thing>` |
| Architect review only | `*review <thing>` |
| Full sprint planning | `*plan sprint` |
| Ship a build to an environment | `*deploy <env>` |
| Talk directly to one persona | `*chat @neo *swe fix X` |
| Single-step with full control | `*chat @trin *qa test all` |
| DevOps task only | `*chat @tank *devops <command>` |

---

## Loop Handoff Format

Every persona in a loop posts a handoff before switching:

```bash
bobp chat "<summary> @NextPersona *command" --persona <Name> --cmd "<prefix> handoff" --to <next>
```

The next persona reads CHAT.md on entry — if the handoff isn't there, they start blind.

---

## Loop Optimization & Anti-Loop Rules

To minimize token usage and prevent coordination overhead:
1. **Pre-Handoff Self-Validation**: Neo must run local checks (e.g. static analysis, syntax lints, or quick targeted tests) before handing off code to Trin (`*qa verify` / `*qa uat`). Trivial typos, syntax errors, or lint warnings should be resolved before switching personas.
2. **Consolidation for Minor Changes**: For trivial features or bug fixes (e.g. document typos, adding a canned query JSON, or configuration tweaks), do not trigger a full multi-persona loop. Combine implementation, verification, and state update into a **single-step execution** by a single persona to avoid state-saving overhead.
3. **Active Anti-Loop Guard**: If any loop iteration (e.g. Neo fix → Trin test fail → Neo fix) repeats **more than twice** for the same issue without resolution, the loop must be paused. The active agent must post logs, describe the blocker to the user, and request manual intervention rather than attempting a third cycle.
4. **Fast-Track Sprint Planning**: If a sprint plan consists only of small maintenance items, bypass the full 6-step planning chain. Cypher and Morpheus should compile stories and architecture details into a single document for unified approval by Smith, reducing the transition count.
5. **No Protocol Re-Load**: Do NOT invoke `bob-protocol` at bloop entry. The protocol is already active when bloop is triggered. Re-loading it wastes ~6k tokens per invocation.
6. **No Sub-Skill Re-Invocation**: Do not call `Skill(make, ...)` or `Skill(chat, ...)` more than once per session. Each call reloads the full SKILL.md body unnecessarily. After the first load, run `bobp make <target>` and `bobp chat "..." --persona ... --cmd ... --to ...` via the Bash tool directly — always through `bobp`, never bypassing it. **This has actually been violated** (Sprint 1, Project Scalene: `Skill(make)` was called for `setup`, then called again later in the same session for `test` — the second call should have been a plain `Bash("bobp make test")`). Before calling `Skill(make)` or `Skill(chat)`, check whether you already loaded it earlier in this same session — if so, use Bash directly instead.
7. **Context Budget Between Phases**: After each bloop phase completes, check the context percentage. If > 60%, explicitly warn the user and recommend `/clear` before the next phase. Ensure all state files are written before clearing.

