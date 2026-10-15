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
    Note over User,Neo: 📅 2026-10-14
    User->>All: "request"
    Note right of User: "push sketch"
    Tank->>All: "devops push"
    Note right of Tank: "Pushed sketch-tastic<br/>main to origin (through<br/>bcabf73: post-Sprint 3<br/>fixes + Sprint 4).<br/>fingerling not touched<br/>(its pin bump to 849b4ec<br/>is s…"
    Note over User,Neo: 📅 2026-10-15
    Neo->>User: "swe fix"
    Note right of Neo: "Profile is the only<br/>source of key order:<br/>every skit starts with<br/>every aggregate in<br/>profile order at its<br/>initial state (0, [],<br/>AVG {null,0,0…"
```
