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
    participant Trin
    Note over User,Trin: 📅 2026-10-14
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
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 1 impl: _PlainPath<br/>walks dicts for $ /<br/>$.a.b, everything else<br/>still python-jsonpath. 3<br/>PlainPathTests (13 paths<br/>x 17 documents vs jso…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 1 passed: AC3<br/>equivalence table incl.<br/>null, lists/strings mid-<br/>path,<br/>true/null/length/keys<br/>names, non-plain paths<br/>unchanged, make…"
    Morpheus->>Neo: "lead handoff"
    Note right of Morpheus: "Phase 1 review passed:<br/>D2 as designed, regex<br/>conservative (no<br/>quoted/digit names),<br/>cache still validates<br/>every non-plain path.<br/>Remaining to…"
    Mouse->>All: "phase 2"
    Note right of Mouse: "Select once per event,<br/>FIRST/LAST without<br/>deepcopy, alias-free<br/>dump"
    Neo->>Morpheus: "swe blocked"
    Note right of Neo: "Phase 2 attempt 1<br/>failed: dropping<br/>deepcopy broke 2 tests<br/>that pin a library<br/>contract (stored samples<br/>must not alias the<br/>caller's record).…"
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 2 impl: Aggregate.<br/>select/fold_values,<br/>Sketch.select +<br/>upsert(selected=), one<br/>selection per event for<br/>sketch and run, JSON-<br/>specific _c…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 2 passed: AC1<br/>106.35 -> 40.83 s<br/>(2.6x), AC2 hash<br/>identical, existing<br/>tests unmodified (copy-<br/>contract tests kept,<br/>that is what for…"
    Morpheus->>Tank: "lead handoff"
    Note right of Morpheus: "Phase 2 review passed:<br/>D3 as designed, D4<br/>revised correctly<br/>(contract kept, copy<br/>moved to select, memo<br/>keeps originals alive so<br/>ids stay un…"
```
