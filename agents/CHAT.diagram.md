# CHAT.md — Conversation Flow

Auto-generated from `agents/CHAT.md` by `bobp chat-diagram`. Do not edit by hand — regenerate with `make chat_diagram` (or it regenerates automatically on every `make chat`).

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant Tank
    participant Cypher
    participant Smith
    participant Morpheus
    participant Mouse
    participant Neo
    participant All
    Note over Tank,All: 📅 2026-10-14
    Tank->>Cypher: "devops sdlc"
    Note right of Tank: "Stage 0 done:<br/>fingerprint-sampler<br/>imported from fingerling<br/>with history (subtree<br/>split, 31 commits), root<br/>build env (pyproject dev<br/>group, M…"
    Cypher->>Smith: "pm handoff"
    Note right of Cypher: "Sprint 1 (Move and<br/>Rename, Tier 2, 5 pts):<br/>SKT-01 sketch-tastic /<br/>sketchtastic / skt,<br/>SKT-02 sketch + skit<br/>vocabulary.<br/>docs/sprints/USER_ST…"
    Morpheus->>Smith: "lead handoff"
    Note right of Morpheus: "Arch D1-D3: git mv<br/>package, pyproject<br/>name/scripts/urls, prog<br/>from argv, then<br/>module/class/key/flag<br/>renames (same hashing).<br/>Phase 1 names o…"
    Smith->>Mouse: "user approve"
    Note right of Smith: "*user approve. rubric<br/>STORIES: OUT=S TEST=S<br/>FAIL=n/a SCOPE=S SIZE=S<br/>DESIGN=A. Arch approved:<br/>help showing the invoked<br/>name (skt vs sketchta…"
    Mouse->>Morpheus: "sm handoff"
    Note right of Mouse: "Sprint 1 planned in<br/>task.md: Phase 1 names<br/>(SKT-01), Phase 2<br/>vocabulary (SKT-02),<br/>close with Tank sdlc-<br/>check. @Morpheus *lead<br/>review sprint…"
    Morpheus->>Neo: "lead handoff"
    Note right of Morpheus: "Plan approved. @Neo *swe<br/>impl phase-1"
    Mouse->>All: "phase 1"
    Note right of Mouse: "Phase 1: new names -<br/>sketch-tastic,<br/>sketchtastic, skt<br/>(SKT-01)"
```
