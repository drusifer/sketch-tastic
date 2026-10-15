# CHAT.md — Conversation Flow

Auto-generated from `agents/CHAT.md` by `bobp chat-diagram`. Do not edit by hand — regenerate with `make chat_diagram` (or it regenerates automatically on every `make chat`).

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant User
    participant All
    participant Tank
    participant Neo
    participant Mouse
    Note over User,Mouse: 📅 2026-10-14
    User->>All: "request"
    Note right of User: "push sketch"
    Tank->>All: "devops push"
    Note right of Tank: "Pushed sketch-tastic<br/>main to origin (through<br/>bcabf73: post-Sprint 3<br/>fixes + Sprint 4).<br/>fingerling not touched<br/>(its pin bump to 849b4ec<br/>is s…"
    Note over User,Mouse: 📅 2026-10-15
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
```
