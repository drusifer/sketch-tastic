# CHAT_SPRINT_2 — Sprint Archive

## Summary

Sprint 2, Sort the Show (Tier 2, 2 pts, 0 fix cycles). Owner: sort lowest first only, KEY = header any case, default COUNT (flips most-frequent-first), --top N dropped. Phase 1 refactored show columns to (header, value, cell) data, output unchanged. Phase 2 added show --sort KEY: '-' first, numbers before text, ties in file order, unknown/ambiguous key exits 2 listing columns; help and README. GH Archive: | tail shows heaviest skit. No release (mainline).

---

## Planning

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
    Note over User,Neo: 📅 2026-10-14
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
```

---

## Phase 1

Columns as data: refactor show to one (header, value, cell) list, table unchanged

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant Neo
    participant Trin
    participant Morpheus
    Note over Neo,Morpheus: 📅 2026-10-14
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 1 impl: show<br/>columns are one (header,<br/>value, cell) list, make<br/>format/lint clean, make<br/>test 223 OK, no test<br/>edits. @Trin *qa uat<br/>phase…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 1 passed: make<br/>test 223 OK, ShowTests<br/>untouched (git diff<br/>tests empty), lint<br/>clean, output byte-<br/>identical per existing<br/>exact-line…"
    Morpheus->>Neo: "lead handoff"
    Note right of Morpheus: "Phase 1 review passed:<br/>D1 as designed, default-<br/>arg lambdas bind per<br/>column correctly, token<br/>None prints '-' (tokens<br/>are never null: absent…"
```

---

## Phase 2

--sort KEY, default COUNT (lowest first), help and README

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant Neo
    participant Trin
    participant Morpheus
    participant Tank
    participant Oracle
    participant Smith
    participant All
    participant Cypher
    participant Mouse
    Note over Neo,Mouse: 📅 2026-10-14
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 2 impl: show<br/>--sort KEY (default<br/>COUNT, lowest first),<br/>exact-then-caseless<br/>lookup, exit 2 with<br/>column list, help epilog<br/>+ README. 7 n…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 2 passed, AC<br/>by test: AC1/4<br/>sorts_by_an_aggregate,<br/>AC2 default_is_count,<br/>AC3 sorts_by_every_fixed<br/>_column (+case), AC5<br/>missing_fir…"
    Morpheus->>Tank: "lead handoff"
    Note right of Morpheus: "Phase 2 review passed:<br/>D2/D3 as designed,<br/>stable sort from file<br/>order gives tie rule for<br/>free, bool excluded from<br/>numbers, _NoColumn<br/>stays…"
    Tank->>Oracle: "devops handoff"
    Note right of Tank: "SDLC check passed: from-<br/>clean distclean/install/<br/>lint/test/secrets/build,<br/>test-all (3.14, 3.15),<br/>smoke green, no<br/>mechanism change, Last<br/>veri…"
    Oracle->>Smith: "ora handoff"
    Note right of Oracle: "Docs groomed. rubric<br/>SDLC: TRUE=S WHOLE=A<br/>CLEAN=A CLASS=S CHECK=A<br/>GAPS=A (footer only).<br/>rubric DECISION: CTX=S<br/>CHOICE=S CONSEQ=S for<br/>sort d…"
    Smith->>All: "user approve"
    Note right of Smith: "*user approve. rubric<br/>UAT: COVER=S STEPS=A<br/>FAIL=S DATA=S EVID=A. GH<br/>Archive via make: show<br/>--sort<br/>'payload_bytes.SUM %' |<br/>tail ends on fa38…"
    Neo->>Cypher: "retro"
    Note right of Neo: "Neo retro: columns-as-<br/>data made sort one line<br/>plus key lookup,<br/>refactor first kept the<br/>diff reviewable. Backlog<br/>items: none"
    Trin->>Cypher: "retro"
    Note right of Trin: "Trin retro: exact<br/>stdout/stderr asserts<br/>for both errors, smoke<br/>caught README order.<br/>Backlog items: test-<br/>internal fingerprint<br/>names still op…"
    Morpheus->>Cypher: "retro"
    Note right of Morpheus: "Morpheus retro: one<br/>ordering rule for every<br/>column, default<br/>included, no special<br/>cases. Backlog items:<br/>none"
    Oracle->>Cypher: "retro"
    Note right of Oracle: "Oracle retro: decision<br/>recorded the same day,<br/>nothing undocumented.<br/>Backlog items: none"
    Mouse->>Cypher: "retro"
    Note right of Mouse: "Mouse retro: 2 phases, 0<br/>fix cycles, owner's mid-<br/>planning change (default<br/>COUNT) landed before any<br/>code. Backlog items:<br/>none"
    Cypher->>Cypher: "retro"
    Note right of Cypher: "Cypher retro: asking the<br/>owner first cut --top N<br/>and flipped the default<br/>before stories were<br/>final. Backlog items:<br/>none new"
    Smith->>Cypher: "retro"
    Note right of Smith: "Smith retro: ranking is<br/>now one flag, | tail<br/>puts the answer next to<br/>the prompt. Backlog<br/>items: none"
    Cypher->>All: "pm launch"
    Note right of Cypher: "*pm launch sprint-2.<br/>Sort the Show: show<br/>--sort KEY (any header,<br/>any case), lowest first,<br/>default COUNT (breaking:<br/>least frequent first),<br/>b…"
```
