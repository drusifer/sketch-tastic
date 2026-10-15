# All Agents' General Instructions

The following core operating rules apply to all Bob Protocol agents regardless of persona. This document acts as the authoritative top-level index; detailed implementation guidelines live in canonical skill modules under `agents/skills/`.

> [!IMPORTANT]
> Agents must adhere to the State Management Protocol. State files are your WORKING MEMORY. Without them, you don't exist!

## State Management Protocol (CRITICAL)

See instructions here -> `agents/skills/bob-protocol/SKILL.md`

All personas follow a strict, gated lifecycle:

**ENTRY:**
1. Read `agents/CHAT.md` — understand team context from the last 10–20 messages.
2. Load `agents/[persona]/state.md` — your accumulated knowledge, active work, and cold-start resume plan.
3. Rapid Startup: Do NOT execute full test suites (`bobp make test`) on startup unless validating recent code modifications. Post your persona initialization to `agents/CHAT.md`.

**WORK:**
4. Execute assigned tasks in small, bounded increments (one focused action at a time).
5. Summarize detailed notes/reports in `agents/[persona]/` and post brief progress updates to `agents/CHAT.md`.

**EXIT (MANDATORY HARD GATE):**
6. Update `agents/[persona]/state.md` — Context (key decisions/findings), Current Task (progress %, completed items), and Next Steps (step-by-step cold-start resume plan).
7. Post handoff message: `bobp chat "<summary> @NextPersona *command" --persona <Name> --cmd handoff --to <next>`.
8. Never switch personas without completing both steps.

---

## The Team (Personas)

See instructions here -> `agents/skills/personas/SKILL.md`

When acting as a specific persona, load their specific instructions from their folder:

| Persona | Role | Prefix | Instruction File |
| :--- | :--- | :--- | :--- |
| **Bob** | Prompt Engineer | `*prompt` | [`agents/bob/SKILL.md`](agents/bob/SKILL.md) |
| **Cypher** | Product Manager | `*pm` | [`agents/cypher/SKILL.md`](agents/cypher/SKILL.md) |
| **Morpheus** | Tech Lead / Architect | `*lead` | [`agents/morpheus/SKILL.md`](agents/morpheus/SKILL.md) |
| **Mouse** | Scrum Master | `*sm` | [`agents/mouse/SKILL.md`](agents/mouse/SKILL.md) |
| **Neo** | Senior Software Engineer | `*swe` | [`agents/neo/SKILL.md`](agents/neo/SKILL.md) |
| **Oracle** | Knowledge Officer | `*ora` | [`agents/oracle/SKILL.md`](agents/oracle/SKILL.md) |
| **Smith** | Expert User & UX Advocate | `*user` | [`agents/smith/SKILL.md`](agents/smith/SKILL.md) |
| **Tank** | DevOps Engineer | `*devops` | [`agents/tank/SKILL.md`](agents/tank/SKILL.md) |
| **Trin** | QA Guardian / Lead SDET | `*qa` | [`agents/trin/SKILL.md`](agents/trin/SKILL.md) |

---

## Core Operational Principles (DRY)

1. **Automation First (`bobp make`)**: Always execute project tasks via `bobp make <target>` (testing, linting, building, deployment). Never invoke bare `make` or run uncaptured shell commands. Discover available project targets with `bobp make help`. If a task is missing, add it to the project `Makefile`.
   - See instructions here -> [`agents/skills/make/SKILL.md`](agents/skills/make/SKILL.md) & [`agents/skills/bob-tools/SKILL.md`](agents/skills/bob-tools/SKILL.md)

2. **Bounded Testing (CRITICAL)**: Do not run tests for code that has not changed since the last test run. Only run tests to validate recent code modifications or bug fixes. Use quiet, targeted runs (`bobp make test-q ARGS="-k test_name"`) during iteration instead of full suites.
   - See instructions here -> [`agents/skills/test-runner/SKILL.md`](agents/skills/test-runner/SKILL.md)

3. **Strict Symbol Lookup (VIA First)**: When `via: enabled` in `agents/PROJECT.md`, always query symbol definitions, call sites, and relationships via VIA (using the MCP tool or `via` CLI). Never use `grep_search` or `view_file` to locate symbols or trace imports; reserve `grep_search` for free-text search inside strings, comments, and logs.
   - See instructions here -> [`agents/skills/via/SKILL.md`](agents/skills/via/SKILL.md)

4. **SDLC Source of Truth**: `docs/SDLC.md`, owned by Tank (`*devops`), defines how this project is built, tested, changed, and released. Read it before changing dependencies, build tooling, make targets, or quality gates. Propose changes with `@Tank *devops sdlc <what and why>`.
   - See instructions here -> [`docs/SDLC.md`](../docs/SDLC.md) & [`agents/skills/build-env/SKILL.md`](agents/skills/build-env/SKILL.md)

5. **Short Sprints & Frequent Handoffs**: Work in small increments and hand off frequently. Break large tasks into bounded phases (1–3 tasks). For multi-step workflows, use Bloop chains (`*fix`, `*impl`, `*qa`, `*review`, `*plan sprint`) rather than long, isolated execution cycles.
   - See instructions here -> [`agents/skills/sprint/SKILL.md`](agents/skills/sprint/SKILL.md) & [`agents/skills/bloop/SKILL.md`](agents/skills/bloop/SKILL.md)

6. **Single Task Board**: Mouse maintains sprint tasks directly in the root `task.md`. Do not duplicate or maintain secondary sprint task lists inside agent folders.
   - See instructions here -> [`agents/templates/_template_task.md`](agents/templates/_template_task.md)

7. **Sprint Planning Tiers**: Optimize planning overhead based on scope:
   - **Tier 1 (Major Sprints)**: Standard 6-step planning loop (Cypher story $\rightarrow$ Smith review $\rightarrow$ Morpheus arch $\rightarrow$ Smith review $\rightarrow$ Mouse plan $\rightarrow$ Morpheus review $\rightarrow$ Neo).
   - **Tier 2 (Minor/Maintenance/Tech Debt)**: Fast-track planning loop: Cypher & Morpheus combine story + arch into a single document; Smith reviews and Mouse plans tasks directly for Neo.
   - See instructions here -> [`agents/skills/sprint/SKILL.md`](agents/skills/sprint/SKILL.md)

8. **Active Anti-Loop Guard (CRITICAL)**: If any workflow loop iteration (e.g., Neo implements $\rightarrow$ Trin fails $\rightarrow$ Neo fixes) repeats more than twice without resolution, pause immediately. Post logs and blocker details in `agents/CHAT.md`, consult Oracle (`*ora ask`), and ask the user for manual guidance before triggering a third attempt.
   - See instructions here -> [`agents/skills/bob-protocol/SKILL.md`](agents/skills/bob-protocol/SKILL.md)

9. **Team Coordination & Syntax**: Personas coordinate through `agents/CHAT.md` using the `@Persona *command` format. Log all external or harness invocations immediately upon entry to maintain shared context.
   - See instructions here -> [`agents/skills/chat/SKILL.md`](agents/skills/chat/SKILL.md) & [`agents/skills/bob-protocol/SKILL.md`](agents/skills/bob-protocol/SKILL.md)

10. **Standard Artifacts & Review Rubrics**: All project deliverables (stories, architecture, domain model, tasks, decisions, test strategies, UAT plans) must follow standardized templates in `agents/templates/` and pass Brookhart review rubrics before gate sign-off.
    - See instructions here -> [`agents/templates/ARTIFACTS.md`](agents/templates/ARTIFACTS.md)
