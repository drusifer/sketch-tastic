# BobProtocol Documentation Index

**Last Updated:** 2026-03-22

## Quick Access

Type `*help` for complete command reference with examples.

---

## Primary Documentation

### Getting Started
- **[STARTUP.md](../STARTUP.md)** - LLM startup instructions
- **[README.md](../README.md)** - Project overview and team reference
- **[SHORTHAND_GUIDE.md](../SHORTHAND_GUIDE.md)** - Complete trigger/command reference
- **[HELP.md](bob/HELP.md)** - Quick reference for all 8 personas and commands

### Tools
- **`bobp` CLI** - Agent tooling subcommands (`bobp chat`, `bobp make`, `bobp setup-agent-links`, …); run `bobp --help` for the full list

---

## Persona Documentation

### Active Personas (9)

| Persona | Role | SKILL.md | Prefix |
|---------|------|----------|--------|
| Bob | Prompt Engineering Expert | [bob/SKILL.md](bob/SKILL.md) | `*new` / `*reprompt` / `*learn` |
| Cypher | Product Manager | [cypher/SKILL.md](cypher/SKILL.md) | `*pm` |
| Morpheus | Tech Lead / Architect | [morpheus/SKILL.md](morpheus/SKILL.md) | `*lead` |
| Neo | Senior Software Engineer | [neo/SKILL.md](neo/SKILL.md) | `*swe` |
| Oracle | Knowledge Officer | [oracle/SKILL.md](oracle/SKILL.md) | `*ora` |
| Trin | QA / Guardian | [trin/SKILL.md](trin/SKILL.md) | `*qa` |
| Mouse | Scrum Master | [mouse/SKILL.md](mouse/SKILL.md) | `*sm` |
| Smith | Expert User & UX Advocate | [smith/SKILL.md](smith/SKILL.md) | `*user` |
| Tank | DevOps Engineer | [tank/SKILL.md](tank/SKILL.md) | `*devops` |

---

## Team Communication

- **[CHAT.md](CHAT.md)** - Team communication log (append-only)
- Each persona maintains state in their `<name>/` folder:
  - `state.md` - Working memory: Context, Current Task, and Next Steps sections

---

## Template Files

Located in `agents/templates/`:

- `ARTIFACTS.md` - Artifact inventory, rubric quality standards, and review gates
- `_template_USER_STORIES.md` - Sprint user stories (rubric: STORIES)
- `_template_ARCH.md` - System & sprint architecture (rubric: ARCH)
- `_template_DOMAIN.md` - Domain model & ubiquitous language specification (rubric: DOMAIN)
- `_template_task.md` - Sprint task board (rubric: PLAN)
- `_template_SDLC.md` - Software development lifecycle (rubric: SDLC; variants for python, javascript)
- `_template_LESSON.md` - Engineering lessons learned (rubric: LESSON)
- `_template_DECISION.md` - Architecture decision record / MADR (rubric: DECISION)
- `_template_finding.md` - Research spike & technical finding (rubric: FINDING)
- `_template_TEST_STRATEGY.md` - Quality & UAT strategy (rubric: STRATEGY)
- `_template_UAT_PLAN.md` - Sprint acceptance test plan (rubric: UAT)
- `_template_state.md` - Agent working memory state
- `_template_CHAT.md` - CHAT.md message format
- `_template_tldr.md` - TLDR block formats

---

## Tools

Shipped as `bobp` CLI subcommands, not project-local scripts:

- `bobp chat` - Post messages to CHAT.md
- `bobp make <target>` - Run this project's own `make <target>`, captured to build/build.out and posted to CHAT.md
- `bobp setup-agent-links` - Create `.claude/skills/` symlinks (run once on setup)

---

## Archived Documentation

Files prefixed with `.archive_` are historical and no longer active:
- `.archive_COMMANDS.md` - (Consolidated into HELP.md)
- `.archive_state_management_fix.md` - (Implemented in protocol)

---

## Documentation Standards

### File Naming
- Persona definitions: `[PersonaName]_[ROLE]_AGENT.md`
- State files: `state.md`
- MCP tools: `[toolname]_mcp.md`
- Templates: `_template_*.md`
- Archived: `.archive_*.md`

### Structure
- All persona docs in `agents/[persona]/`
- All MCP tool docs in `agents/tools/`
- Team communication in `agents/CHAT.md`
- Primary references in `agents/bob/`

### Maintenance
- Update `*help` when adding commands
- Update tool docs when changing MCPs
- Archive outdated docs with `.archive_` prefix
- Keep HELP.md, BOB_SYSTEM_PROTOCOL.md, and START_HERE.md in sync

---

## Quick Command Reference

```bash
*help                          # Show complete help
*chat                          # Activate Bob System
*prompt <desc>                 # Create agent (Bob)
*swe impl <task>              # Implement (Neo)
*qa test <scope>              # Test (Trin)
*ora ask <question>           # Query knowledge (Oracle)
*lead plan <epic>             # Plan (Morpheus)
*pm doc <type>                # Create PRD (Cypher)
*sm status                    # Sprint status (Mouse)
```

---

**For Help:** Type `*help` or read `agents/bob/HELP.md`
