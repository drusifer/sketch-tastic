# CHAT.md — Conversation Flow

Auto-generated from `agents/CHAT.md` by `bobp chat-diagram`. Do not edit by hand — regenerate with `make chat_diagram` (or it regenerates automatically on every `make chat`).

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant User
    participant All
    participant Neo
    participant Cypher
    participant Smith
    participant Mouse
    Note over User,Mouse: 📅 2026-10-14
    User->>All: "request"
    Note right of User: "Revert the plain-path<br/>shortcut, replace<br/>python-jsonpath with<br/>jsonpath-rfc9535 2.0<br/>(basic strategy).<br/>Standard RFC 9535 only,<br/>no special synt…"
    Neo->>User: "swe fix"
    Note right of Neo: "Done on fix/jsonpath-<br/>rfc9535: plain-path<br/>shortcut removed,<br/>python-jsonpath replaced<br/>by jsonpath-rfc9535<br/>2.0.2 (basic resolver,<br/>no locations…"
    Neo->>User: "swe fix"
    Note right of Neo: "fix/fold-once: Sprint 3<br/>select-once reverted,<br/>merge now folds each<br/>event into the run only<br/>and merges the run into<br/>the sketch once<br/>(Aggrega…"
    Neo->>User: "swe fix"
    Note right of Neo: "fix/fold-once: deepcopy<br/>dropped from FIRST/LAST,<br/>upsert docstring says<br/>the sketch keeps<br/>references (caller must<br/>not modify the record),<br/>two…"
    Cypher->>Smith: "pm handoff"
    Note right of Cypher: "Sprint 4 (Parallel<br/>Merge, Tier 2, 5 pts):<br/>SKT-06 merge -j N<br/>(processes, default all<br/>cores), batches merged<br/>as they finish,<br/>FIRST/LAST any m…"
    Smith->>Mouse: "user approve"
    Note right of Smith: "*user approve. rubric<br/>STORIES: OUT=S TEST=S<br/>FAIL=S SCOPE=S SIZE=S<br/>DESIGN=A, rubric ARCH:<br/>BOUND=S FLOW=S FAIL=A<br/>USER=S DECS=S FEAS=S.<br/>Warnin…"
    Mouse->>Neo: "sm handoff"
    Note right of Mouse: "rubric PLAN: SIZE=A<br/>GATE=S VERIF=S ALIGN=S<br/>OWNER=S. Phase 1 (Neo):<br/>D1 _fold_lines refactor,<br/>-j 1 unchanged, tests<br/>green. Phase 2 (Neo):<br/>D2-…"
    Neo->>User: "swe status"
    Note right of Neo: "Phase 1-2 impl: merge -j<br/>N (ProcessPoolExecutor,<br/>batches of 5000 lines,<br/><=2 per worker in<br/>flight, merged as they<br/>finish, warnings in line<br/>o…"
```
