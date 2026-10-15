# CHAT.md — Conversation Flow

Auto-generated from `agents/CHAT.md` by `bobp chat-diagram`. Do not edit by hand — regenerate with `make chat_diagram` (or it regenerates automatically on every `make chat`).

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant User
    participant All
    participant Mouse
    participant Cypher
    participant Smith
    participant Morpheus
    participant Neo
    participant Trin
    participant Tank
    Note over User,Tank: 📅 2026-10-14
    User->>All: "request"
    Note right of User: "/bob-protocol init"
    Mouse->>User: "sm init"
    Note right of Mouse: "Init: cold start<br/>reconciled. No sprint in<br/>flight, Sprint 1 (move<br/>and rename, 5/5) merged<br/>to main, tree clean,<br/>agent links synced.<br/>Waiting o…"
    User->>All: "request"
    Note right of User: "/sprint sort and top n"
    Mouse->>Cypher: "sm kickoff"
    Note right of Mouse: "Sprint 2 kickoff (Tier<br/>2): show --sort KEY.<br/>Owner decided: ascending<br/>only (lowest to highest,<br/>no reverse), KEY =<br/>header name, any case,<br/>--t…"
    Cypher->>Smith: "pm handoff"
    Note right of Cypher: "Sprint 2 (Sort the Show,<br/>Tier 2, 2 pts): STORY-<br/>SKT-03 show --sort KEY,<br/>lowest first, default<br/>KEY=COUNT (owner, mid-<br/>planning: flips most-<br/>fre…"
    Morpheus->>Smith: "lead handoff"
    Note right of Morpheus: "Arch D1-D3: show columns<br/>become (header, value,<br/>cell) data so rows can<br/>sort on raw values,<br/>--sort default COUNT,<br/>stable sort,<br/>None<numbers<…"
    Smith->>Mouse: "user approve"
    Note right of Smith: "*user approve. rubric<br/>STORIES: OUT=S TEST=S<br/>FAIL=S SCOPE=S SIZE=S<br/>DESIGN=A. Arch approved:<br/>one rule (lowest first,<br/>- first) for every<br/>colum…"
    Mouse->>Morpheus: "sm handoff"
    Note right of Mouse: "Sprint planned in<br/>task.md: Phase 1<br/>columns-as-data refactor<br/>(order-neutral, tests<br/>untouched), Phase 2<br/>--sort KEY + default<br/>COUNT + docs (br…"
    Morpheus->>Neo: "lead handoff"
    Note right of Morpheus: "rubric PLAN: SIZE=S<br/>GATE=S VERIF=S ALIGN=S<br/>OWNER=S. Plan approved,<br/>Phase 1 keeps the risky<br/>refactor separate from<br/>the behaviour change.<br/>Pha…"
    Mouse->>All: "phase 1"
    Note right of Mouse: "Columns as data:<br/>refactor show to one<br/>(header, value, cell)<br/>list, table unchanged"
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 1 impl: show<br/>columns are one (header,<br/>value, cell) list, make<br/>format/lint clean, make<br/>test 223 OK, no test<br/>edits. @Trin *qa uat<br/>phase…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 1 passed: make<br/>test 223 OK, ShowTests<br/>untouched (git diff<br/>tests empty), lint<br/>clean, output byte-<br/>identical per existing<br/>exact-line…"
    Morpheus->>Neo: "lead handoff"
    Note right of Morpheus: "Phase 1 review passed:<br/>D1 as designed, default-<br/>arg lambdas bind per<br/>column correctly, token<br/>None prints '-' (tokens<br/>are never null: absent…"
    Mouse->>All: "phase 2"
    Note right of Mouse: "--sort KEY, default<br/>COUNT (lowest first),<br/>help and README"
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 2 impl: show<br/>--sort KEY (default<br/>COUNT, lowest first),<br/>exact-then-caseless<br/>lookup, exit 2 with<br/>column list, help epilog<br/>+ README. 7 n…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 2 passed, AC<br/>by test: AC1/4<br/>sorts_by_an_aggregate,<br/>AC2 default_is_count,<br/>AC3 sorts_by_every_fixed<br/>_column (+case), AC5<br/>missing_fir…"
    Morpheus->>Tank: "lead handoff"
    Note right of Morpheus: "Phase 2 review passed:<br/>D2/D3 as designed,<br/>stable sort from file<br/>order gives tie rule for<br/>free, bool excluded from<br/>numbers, _NoColumn<br/>stays…"
```
