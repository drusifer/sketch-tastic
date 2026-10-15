# CHAT_SPRINT_3 — Sprint Archive

## Summary

Sprint 3, Faster Merge (Tier 2, 5 pts). Owner: tune merge on the GH Archive hour with a profiler via make, stdlib cProfile, best effort KISS. Phase 0 (Tank): make profile (wall time, sketch hash, cProfile top 25); baseline 106.35 s. Phase 1: plain JSONPaths walk dicts (tested against python-jsonpath): 54.48 s. Phase 2: select once per event for sketch and run file; dropping deepcopy broke the copy contract, revised to one JSON-specific copy per event: 40.83 s. Hash unchanged throughout. Lesson on defensive copies. No release.

---

## Planning

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
    Note over User,Morpheus: 📅 2026-10-14
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
```

---

## Phase 0

make profile: time, hash and cProfile the GH Archive merge

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant Tank
    participant Neo
    Note over Tank,Neo: 📅 2026-10-14
    Tank->>Neo: "devops handoff"
    Note right of Tank: "Phase 0 done: make<br/>profile (timed run +<br/>sketch hash + cProfile<br/>top 25 to build/profile/<br/>profile.txt), download<br/>shared with gharchive,<br/>clean…"
```

---

## Phase 1

Plain-path fast path in model.py, tested against python-jsonpath

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant Neo
    participant Trin
    participant Morpheus
    Note over Neo,Morpheus: 📅 2026-10-14
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 1 impl: _PlainPath<br/>walks dicts for $ /<br/>$.a.b, everything else<br/>still python-jsonpath. 3<br/>PlainPathTests (13 paths<br/>x 17 documents vs jso…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 1 passed: AC3<br/>equivalence table incl.<br/>null, lists/strings mid-<br/>path,<br/>true/null/length/keys<br/>names, non-plain paths<br/>unchanged, make…"
    Morpheus->>Neo: "lead handoff"
    Note right of Morpheus: "Phase 1 review passed:<br/>D2 as designed, regex<br/>conservative (no<br/>quoted/digit names),<br/>cache still validates<br/>every non-plain path.<br/>Remaining to…"
```

---

## Phase 2

Select once per event, FIRST/LAST without deepcopy, alias-free dump

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant Neo
    participant Morpheus
    participant Trin
    participant Tank
    participant Oracle
    participant Smith
    participant All
    participant Cypher
    participant Mouse
    Note over Neo,Mouse: 📅 2026-10-14
    Neo->>Morpheus: "swe blocked"
    Note right of Neo: "Phase 2 attempt 1<br/>failed: dropping<br/>deepcopy broke 2 tests<br/>that pin a library<br/>contract (stored samples<br/>must not alias the<br/>caller's record).…"
    Neo->>Trin: "swe handoff"
    Note right of Neo: "Phase 2 impl: Aggregate.<br/>select/fold_values,<br/>Sketch.select +<br/>upsert(selected=), one<br/>selection per event for<br/>sketch and run, JSON-<br/>specific _c…"
    Trin->>Morpheus: "qa handoff"
    Note right of Trin: "UAT phase 2 passed: AC1<br/>106.35 -> 40.83 s<br/>(2.6x), AC2 hash<br/>identical, existing<br/>tests unmodified (copy-<br/>contract tests kept,<br/>that is what for…"
    Morpheus->>Tank: "lead handoff"
    Note right of Morpheus: "Phase 2 review passed:<br/>D3 as designed, D4<br/>revised correctly<br/>(contract kept, copy<br/>moved to select, memo<br/>keeps originals alive so<br/>ids stay un…"
    Tank->>Oracle: "devops handoff"
    Note right of Tank: "SDLC check passed: from-<br/>clean distclean/install/<br/>lint/test/secrets/build,<br/>smoke, test-all (3.14,<br/>3.15) green, profile<br/>target documented, Las…"
    Oracle->>Smith: "ora handoff"
    Note right of Oracle: "Docs groomed. rubric<br/>SDLC: TRUE=S WHOLE=A<br/>CLEAN=A CLASS=S CHECK=A<br/>GAPS=A. rubric DECISION:<br/>CTX=S CHOICE=S CONSEQ=S<br/>(before/after times,<br/>rej…"
    Smith->>All: "user approve"
    Note right of Smith: "*user approve. rubric<br/>UAT: COVER=S STEPS=A<br/>FAIL=A DATA=S EVID=S.<br/>make gharchive: 180387<br/>events, 88 skits, run<br/>file written, show<br/>--sort 'pa…"
    Neo->>Cypher: "retro"
    Note right of Neo: "Neo retro: profiler<br/>pointed straight at<br/>three causes, one wrong<br/>turn (no-copy) caught by<br/>tests in seconds.<br/>Backlog items: copy-free<br/>ownersh…"
    Trin->>Cypher: "retro"
    Note right of Trin: "Trin retro: sketch hash<br/>in make profile made<br/>byte-identical output a<br/>one-line check,<br/>equivalence table vs<br/>python-jsonpath guards<br/>the fast p…"
    Morpheus->>Cypher: "retro"
    Note right of Morpheus: "Morpheus retro: D4 had<br/>to be revised, the copy<br/>contract was in tests,<br/>not in the arch notes.<br/>Stop rule kept the<br/>sprint KISS. Backlog<br/>items:…"
    Oracle->>Cypher: "retro"
    Note right of Oracle: "Oracle retro: decision<br/>has before/after<br/>numbers, lesson recorded<br/>on checking contracts<br/>before removing copies.<br/>Backlog items: none"
    Mouse->>Cypher: "retro"
    Note right of Mouse: "Mouse retro: 3 phases, 1<br/>rejected approach (anti-<br/>loop: one retry,<br/>succeeded). Profile runs<br/>(~5 min each) were the<br/>pacing item. Backlog<br/>item…"
    Cypher->>Cypher: "retro"
    Note right of Cypher: "Cypher retro: owner<br/>answers up front<br/>(target, tool, KISS<br/>goal) made the stop rule<br/>obvious. Backlog items:<br/>history-weight item<br/>closed by D3"
    Smith->>Cypher: "retro"
    Note right of Smith: "Smith retro: same<br/>output, 2.6x faster,<br/>nothing to relearn.<br/>Backlog items: none"
    Cypher->>All: "pm launch"
    Note right of Cypher: "*pm launch sprint-3.<br/>Faster Merge: make<br/>profile (cProfile, wall<br/>time, sketch hash),<br/>plain-path fast path,<br/>select once per event<br/>for sketch…"
```
