# CHAT_SPRINT_1 — Sprint Archive

## Summary

Sprint 1, Move and Rename (Tier 2, 5 pts, 0 fix cycles). Stage 0 (Tank): fingerprint-sampler imported from fingerling with history via subtree split; root build env, Makefile, uv.lock, hooks, manual CI, docs/SDLC.md. SKT-01: distribution sketch-tastic, import sketchtastic, commands sketchtastic and skt. SKT-02: the set is a sketch, one fingerprint a skit (Sketch, Skit, --sketch, skits:). No release (mainline).

---

## Planning

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
    Note over Tank,Neo: 📅 2026-10-14
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
```

---

## Phase 1

Phase 1: new names - sketch-tastic, sketchtastic, skt (SKT-01)

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant Neo
    participant Trin
    participant Morpheus
    Note over Neo,Morpheus: 📅 2026-10-14
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 1 done, tests<br/>first: src/sketchtastic<br/>(git mv), dist sketch-<br/>tastic, scripts<br/>sketchtastic + skt, prog<br/>from argv, --version<br/>'sketch-tas…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 1 pass: AC1<br/>wheel<br/>sketch_tastic-0.2.0, skt<br/>+ sketchtastic installed<br/>(smoke), python -m<br/>works, AC2 version text,<br/>help shows invoke…"
    Morpheus->>Neo: "lead handoff"
    Note right of Morpheus: "Phase 1 approved: D1 as<br/>designed, git mv keeps<br/>blame. @Neo *swe impl<br/>phase-2"
```

---

## Phase 2

Phase 2: sketch and skit vocabulary (SKT-02)

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant Neo
    participant Trin
    participant Morpheus
    participant Tank
    Note over Neo,Tank: 📅 2026-10-14
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 2 done, tests<br/>first: sketch.py/Sketch/<br/>Skit/SketchError/skit_id<br/>/SKETCH_VERSION, file<br/>key skits, run header<br/>sketch, -s/--sketch<br/>SKETCH,…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 2 pass: AC1<br/>--sketch (no --set),<br/>history<br/><sketch>.history, AC2<br/>summary 'skits: ...<br/>total in sketch',<br/>'cannot use sketch<br/>file', 'n…"
    Morpheus->>Tank: "lead handoff"
    Note right of Morpheus: "Phase 2 approved: D2<br/>complete, grep shows<br/>'fingerprint' only as a<br/>verb. All phases<br/>reviewed. @Tank *devops<br/>sdlc-check"
```

---

## Close

Close: Tank SDLC check, Oracle groom, Smith user test, retro, launch

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant Tank
    participant Oracle
    participant Smith
    participant All
    participant Neo
    participant Cypher
    participant Trin
    participant Morpheus
    participant Mouse
    Note over Tank,Mouse: 📅 2026-10-14
    Tank->>Oracle: "devops handoff"
    Note right of Tank: "SDLC check passed: from-<br/>clean distclean/install/<br/>lint/test/secrets/build,<br/>test-all 3.14+3.15,<br/>smoke (sketchtastic +<br/>skt from the wheel),<br/>loc…"
    Oracle->>Smith: "ora handoff"
    Note right of Oracle: "Docs groomed. rubric<br/>SDLC: TRUE=S WHOLE=A<br/>CLEAN=A CLASS=S CHECK=A<br/>GAPS=A (new<br/>docs/SDLC.md, ported<br/>from fingerling).<br/>DECISIONS records the…"
    Smith->>All: "user approve"
    Note right of Smith: "*user approve. GH<br/>Archive via make:<br/>'skits: 88 new ... total<br/>in sketch',<br/>gh.sketch.yaml with<br/>skits:, history gh.sketc<br/>h.history/261015-0001.…"
    Neo->>Cypher: "retro"
    Note right of Neo: "Neo retro: mechanical<br/>rename went fine with<br/>whole-word seds plus a<br/>phrase map, one overlap<br/>garbled a description<br/>and was caught in review<br/>o…"
    Trin->>Cypher: "retro"
    Note right of Trin: "Trin retro: 218 -> 223<br/>tests, skit_id pinned to<br/>a pre-move value guards<br/>identity. Backlog items:<br/>none"
    Morpheus->>Cypher: "retro"
    Note right of Morpheus: "Morpheus retro: names<br/>only, no mechanism<br/>change, subtree split<br/>kept blame. Backlog<br/>items: none"
    Oracle->>Cypher: "retro"
    Note right of Oracle: "Oracle retro:<br/>fingerling's<br/>DECISIONS/LESSONS stay<br/>there, linked. Backlog<br/>items: none"
    Mouse->>Cypher: "retro"
    Note right of Mouse: "Mouse retro: Stage 0 + 2<br/>phases, 5/5 pts, 0 fix<br/>cycles. Next: fingerling<br/>switches to depend on<br/>this repo once it is<br/>pushed. Backlog items:…"
    Smith->>Cypher: "retro"
    Note right of Smith: "Smith retro: one<br/>vocabulary, two command<br/>names, consistent<br/>output. Backlog items:<br/>none"
    Cypher->>Cypher: "retro"
    Note right of Cypher: "Cypher retro: owner<br/>choices up front made<br/>the stories exact.<br/>Backlog items: test-<br/>internal renames"
    Cypher->>All: "pm launch"
    Note right of Cypher: "*pm launch sprint-1.<br/>sketch-tastic: the<br/>fingerprint tool moved<br/>here with its history<br/>and is now sketch-tastic<br/>/ sketchtastic / skt,<br/>you mer…"
```
