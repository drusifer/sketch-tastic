# CHAT.md — Conversation Flow

Auto-generated from `agents/CHAT.md` by `bobp chat-diagram`. Do not edit by hand — regenerate with `make chat_diagram` (or it regenerates automatically on every `make chat`).

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant User
    participant All
    participant Tank
    Note over User,Tank: 📅 2026-10-14
    User->>All: "request"
    Note right of User: "push it"
    Tank->>All: "devops push"
    Note right of Tank: "Pushed main to origin<br/>(6c4606f..849b4ec):<br/>Sprint 2 sort the show.<br/>Repo is on GitHub, so<br/>fingerling can now<br/>depend on it."
```
