# CHAT.md — Conversation Flow

Auto-generated from `agents/CHAT.md` by `bobp chat-diagram`. Do not edit by hand — regenerate with `bobp chat-diagram` (or it regenerates automatically on every `bobp chat`).

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant User
    participant All
    participant Tank
    participant Neo
    participant Mouse
    participant Morpheus
    Note over User,Morpheus: 📅 2026-10-14
    User->>All: "request"
    Note right of User: "push sketch"
    Tank->>All: "devops push"
    Note right of Tank: "Pushed sketch-tastic<br/>main to origin (through<br/>bcabf73: post-Sprint 3<br/>fixes + Sprint 4).<br/>fingerling not touched<br/>(its pin bump to 849b4ec<br/>is s…"
    Note over User,Morpheus: 📅 2026-10-15
    Neo->>User: "swe fix"
    Note right of Neo: "Profile is the only<br/>source of key order:<br/>every skit starts with<br/>every aggregate in<br/>profile order at its<br/>initial state (0, [],<br/>AVG {null,0,0…"
    User->>All: "request"
    Note right of User: "Skit ids from token<br/>values in profile order<br/>(no keys), profile_id<br/>from field specs in<br/>profile order (v0: no<br/>compatibility)."
    Neo->>User: "swe fix"
    Note right of Neo: "Skit id = MD5 of JSON<br/>token values in profile<br/>order (no keys),<br/>profile_id = field specs<br/>in profile order. Golden<br/>ids, README quickstart<br/>(sm…"
    User->>All: "request"
    Note right of User: "push main"
    Tank->>All: "devops push"
    Note right of Tank: "Pushed main to origin<br/>(through 636243e:<br/>profile-order defaults,<br/>profile-ordered skit<br/>ids)."
    Mouse->>User: "handoff"
    Note right of Mouse: "Prepared for a context<br/>clear:<br/>Mouse/Neo/Morpheus state<br/>and task.md updated<br/>(pipeline, profile-order<br/>rules, measurements,<br/>owner rules, backl…"
    Note over User,Morpheus: 📅 2026-11-17
    User->>All: "request"
    Note right of User: "PyPI packaging with bob-<br/>protocol Init, corrected<br/>target is sketch-tastic,<br/>not fingerling."
    Tank->>All: "devops init"
    Note right of Tank: "Initialized Tank for<br/>sketch-tastic PyPI<br/>packaging. Why:<br/>packaging and trusted-<br/>publishing configuration<br/>already exist, reconcile<br/>their curre…"
    Tank->>Morpheus: "handoff"
    Note right of Tank: "Initialization complete<br/>in sketch-tastic.<br/>Existing Hatchling<br/>packaging,<br/>build/smoke/release-<br/>check targets and<br/>trusted-publishing<br/>workflow f…"
    User->>All: "request"
    Note right of User: "pypi publishing please"
    Tank->>All: "devops init"
    Note right of Tank: "Resuming PyPI publishing<br/>as Tank. Why: owner<br/>requested release,<br/>checking existing<br/>workflow, release<br/>version and external<br/>setup."
    Tank->>Tank: "handoff"
    Note right of Tank: "Release 0.2.0 build and<br/>tag-version check pass,<br/>GitHub pypi environment<br/>created. Awaiting owner<br/>pending publisher setup<br/>on PyPI. No tag pus…"
    Tank->>All: "devops resume"
    Note right of Tank: "Owner confirms PyPI<br/>publisher is pending,<br/>resuming authorized<br/>0.2.0 publication. Why:<br/>account setup<br/>prerequisite is<br/>complete."
    Tank->>Tank: "handoff"
    Note right of Tank: "Published sketch-tastic<br/>0.2.0: CI and trusted<br/>publishing succeeded<br/>(run 44212325102), PyPI<br/>wheel and sdist<br/>verified. No approval<br/>button nee…"
    Note over User,Morpheus: 📅 2026-11-18
    User->>All: "request"
    Note right of User: "prep for clear"
    Tank->>All: "devops resume"
    Note right of Tank: "Tank preparing cold-<br/>start handoff. Why:<br/>preserve completed PyPI<br/>release and outstanding<br/>local documentation<br/>changes before context<br/>clear."
    Tank->>Tank: "handoff"
    Note right of Tank: "Ready for context clear:<br/>0.2.0 published and CI<br/>green, Tank state has<br/>release URL, exact<br/>resume steps and<br/>uncommitted-file<br/>inventory. No sp…"
    User->>All: "request"
    Note right of User: "commit docs too please"
    Tank->>All: "devops resume"
    Note right of Tank: "Tank preparing<br/>documentation commit.<br/>Why: owner requested<br/>saving release records<br/>and clear-session<br/>handoff in git."
    Tank->>Tank: "handoff"
    Note right of Tank: "Release docs reviewed<br/>and ready to commit with<br/>saved cold-start state.<br/>Why: preserve successful<br/>0.2.0 publication, no<br/>package changes or te…"
```
