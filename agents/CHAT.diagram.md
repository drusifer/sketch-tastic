# CHAT.md — Conversation Flow

Auto-generated from `agents/CHAT.md` by `bobp chat-diagram`. Do not edit by hand — regenerate with `bobp chat-diagram` (or it regenerates automatically on every `bobp chat`).

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant User
    participant All
    participant Neo
    participant Trin
    participant Morpheus
    Note over User,Morpheus: 📅 2026-11-21
    User->>All: "request"
    Note right of User: "*nit add Boolean type<br/>support (distinct from<br/>enum)"
    Neo->>All: "swe init"
    Note right of Neo: "Neo taking single-change<br/>nit on fix/boolean-<br/>field-type: detect<br/>Boolean fields (distinct<br/>from Enum and Numeric)<br/>in analysis.py and<br/>dashboard…"
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Boolean field type nit<br/>complete: analysis.py<br/>and dashboard.py now<br/>distinguish Boolean<br/>(with true_pct and<br/>false<true min/max) from<br/>Numeric a…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "QA verified boolean-<br/>field-type: IS_PRESENT<br/>TRUE/FALSE, DEFAULT<br/>True/False+NULL,<br/>constant FALSE, and<br/>mixed enum edge cases<br/>all pass (299 tes…"
    Morpheus->>All: "lead approve"
    Note right of Morpheus: "Code review approved for<br/>fix/boolean-field-type:<br/>clean 3-way field_type<br/>(boolean/numeric/enum)<br/>parity between Python<br/>and JS, zero security…"
```
