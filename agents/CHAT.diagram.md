# CHAT.md — Conversation Flow

Auto-generated from `agents/CHAT.md` by `bobp chat-diagram`. Do not edit by hand — regenerate with `bobp chat-diagram` (or it regenerates automatically on every `bobp chat`).

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant Neo
    participant All
    participant Trin
    participant Morpheus
    Note over Neo,Morpheus: 📅 2026-11-20
    Neo->>All: "init"
    Note right of Neo: "Neo initialized: owner<br/>requests aggregates.<br/>Why: skits should<br/>summarize actual<br/>observations as well as<br/>kinds. Add profile-<br/>native image coun…"
    Neo->>Trin: "handoff"
    Note right of Neo: "Aggregate implementation<br/>verified:282 tests/lint<br/>pass, original profileID<br/>and860 kinds retained<br/>after full-capture<br/>rebuild. Why: report<br/>per…"
    Trin->>Morpheus: "handoff"
    Note right of Trin: "QA/review approved typed<br/>aggregate paths and safe<br/>numeric/date display,<br/>live report verified.<br/>Why: image counting<br/>follows profile guards<br/>an…"
```
