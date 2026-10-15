# CHAT.md — Conversation Flow

Auto-generated from `agents/CHAT.md` by `bobp chat-diagram`. Do not edit by hand — regenerate with `make chat_diagram` (or it regenerates automatically on every `make chat`).

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant User
    participant All
    participant Neo
    Note over User,Neo: 📅 2026-10-14
    User->>All: "request"
    Note right of User: "Revert the plain-path<br/>shortcut, replace<br/>python-jsonpath with<br/>jsonpath-rfc9535 2.0<br/>(basic strategy).<br/>Standard RFC 9535 only,<br/>no special synt…"
    Neo->>User: "swe fix"
    Note right of Neo: "Done on fix/jsonpath-<br/>rfc9535: plain-path<br/>shortcut removed,<br/>python-jsonpath replaced<br/>by jsonpath-rfc9535<br/>2.0.2 (basic resolver,<br/>no locations…"
    Neo->>User: "swe fix"
    Note right of Neo: "fix/fold-once: Sprint 3<br/>select-once reverted,<br/>merge now folds each<br/>event into the run only<br/>and merges the run into<br/>the sketch once<br/>(Aggrega…"
```
