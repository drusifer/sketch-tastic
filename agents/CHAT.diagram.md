# CHAT.md — Conversation Flow

Auto-generated from `agents/CHAT.md` by `bobp chat-diagram`. Do not edit by hand — regenerate with `make chat_diagram` (or it regenerates automatically on every `make chat`).

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant User
    participant All
    participant Tank
    participant Mouse
    participant Cypher
    participant Smith
    participant Morpheus
    participant Neo
    Note over User,Neo: 📅 2026-10-14
    User->>All: "request"
    Note right of User: "push it"
    Tank->>All: "devops push"
    Note right of Tank: "Pushed main to origin<br/>(6c4606f..849b4ec):<br/>Sprint 2 sort the show.<br/>Repo is on GitHub, so<br/>fingerling can now<br/>depend on it."
    User->>All: "request"
    Note right of User: "/sprint performance<br/>tuning (use a profiler)"
    Mouse->>Cypher: "sm kickoff"
    Note right of Mouse: "Sprint 3 kickoff (Tier<br/>2): performance tuning<br/>of merge with a<br/>profiler. Owner: GH<br/>Archive merge, make<br/>profile with cProfile<br/>(no new dep), b…"
    Cypher->>Smith: "pm handoff"
    Note right of Cypher: "Sprint 3 (Faster Merge,<br/>5 pts): SKT-04 make<br/>profile, SKT-05 faster<br/>merge with byte-<br/>identical output (sketch<br/>hash), plain-path<br/>equivalence,…"
    Morpheus->>Smith: "lead handoff"
    Note right of Morpheus: "Arch D1-D5: make profile<br/>(Tank, owner-approved<br/>mechanism), plain-path<br/>fast path in model.py,<br/>tested against python-<br/>jsonpath, select once<br/>pe…"
    Smith->>Mouse: "user approve"
    Note right of Smith: "*user approve. rubric<br/>STORIES: OUT=S TEST=S<br/>FAIL=A SCOPE=S SIZE=S<br/>DESIGN=A, rubric ARCH:<br/>BOUND=S FLOW=A FAIL=A<br/>USER=S DECS=S FEAS=S. No<br/>use…"
    Mouse->>Morpheus: "sm handoff"
    Note right of Mouse: "Sprint planned in<br/>task.md: Phase 0 Tank<br/>make profile, Phase 1<br/>plain-path fast path,<br/>Phase 2 select once + no<br/>deepcopy + stop rule.<br/>Each wit…"
    Morpheus->>Tank: "lead handoff"
    Note right of Morpheus: "rubric PLAN: SIZE=S<br/>GATE=S VERIF=S ALIGN=S<br/>OWNER=S. Approved,<br/>ordering puts the<br/>biggest, most isolated<br/>win (D2) first. @Tank<br/>*devops phase-0"
    Mouse->>All: "phase 0"
    Note right of Mouse: "make profile: time, hash<br/>and cProfile the GH<br/>Archive merge"
    Tank->>Neo: "devops handoff"
    Note right of Tank: "Phase 0 done: make<br/>profile (timed run +<br/>sketch hash + cProfile<br/>top 25 to build/profile/<br/>profile.txt), download<br/>shared with gharchive,<br/>clean…"
    Mouse->>All: "phase 1"
    Note right of Mouse: "Plain-path fast path in<br/>model.py, tested against<br/>python-jsonpath"
```
