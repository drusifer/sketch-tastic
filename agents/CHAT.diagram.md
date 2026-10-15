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
    participant Trin
    Note over Tank,Trin: 📅 2026-10-14
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
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 1 done, tests<br/>first: src/sketchtastic<br/>(git mv), dist sketch-<br/>tastic, scripts<br/>sketchtastic + skt, prog<br/>from argv, --version<br/>'sketch-tas…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 1 pass: AC1<br/>wheel<br/>sketch_tastic-0.2.0, skt<br/>+ sketchtastic installed<br/>(smoke), python -m<br/>works, AC2 version text,<br/>help shows invoke…"
    Morpheus->>Neo: "lead handoff"
    Note right of Morpheus: "Phase 1 approved: D1 as<br/>designed, git mv keeps<br/>blame. @Neo *swe impl<br/>phase-2"
    Mouse->>All: "phase 2"
    Note right of Mouse: "Phase 2: sketch and skit<br/>vocabulary (SKT-02)"
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 2 done, tests<br/>first: sketch.py/Sketch/<br/>Skit/SketchError/skit_id<br/>/SKETCH_VERSION, file<br/>key skits, run header<br/>sketch, -s/--sketch<br/>SKETCH,…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 2 pass: AC1<br/>--sketch (no --set),<br/>history<br/><sketch>.history, AC2<br/>summary 'skits: ...<br/>total in sketch',<br/>'cannot use sketch<br/>file', 'n…"
    Morpheus->>Tank: "lead handoff"
    Note right of Morpheus: "Phase 2 approved: D2<br/>complete, grep shows<br/>'fingerprint' only as a<br/>verb. All phases<br/>reviewed. @Tank *devops<br/>sdlc-check"
```
