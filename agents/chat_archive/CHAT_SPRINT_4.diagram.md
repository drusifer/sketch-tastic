# CHAT_SPRINT_4 — Sprint Archive

## Summary

Sprint 4, Parallel Merge (Tier 2, 5 pts). Preceded by the owner's review of Sprint 3: JSONPath via jsonpath-rfc9535, fold once then merge, no FIRST/LAST copies (32.88 s). Owner design: processes, -j N default all cores, any matching FIRST/LAST sample. Pool with per-batch merges (17-19 s) and per-line shared-memory ring (25.7 s) measured and dropped; final: long-lived workers, bounded task queue of byte batches, output queue (16.46 s). libyaml everywhere: 13.54 s on 4 cores, 29.55 s -j 1. No release.

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant User
    participant All
    participant Neo
    participant Cypher
    participant Smith
    participant Mouse
    participant Tank
    participant Oracle
    participant Trin
    participant Morpheus
    Note over User,Morpheus: 📅 2026-10-14
    User->>All: "request"
    Note right of User: "Revert the plain-path<br/>shortcut, replace<br/>python-jsonpath with<br/>jsonpath-rfc9535 2.0<br/>(basic strategy).<br/>Standard RFC 9535 only,<br/>no special synt…"
    Neo->>User: "swe fix"
    Note right of Neo: "Done on fix/jsonpath-<br/>rfc9535: plain-path<br/>shortcut removed,<br/>python-jsonpath replaced<br/>by jsonpath-rfc9535<br/>2.0.2 (basic resolver,<br/>no locations…"
    Neo->>User: "swe fix"
    Note right of Neo: "fix/fold-once: Sprint 3<br/>select-once reverted,<br/>merge now folds each<br/>event into the run only<br/>and merges the run into<br/>the sketch once<br/>(Aggrega…"
    Neo->>User: "swe fix"
    Note right of Neo: "fix/fold-once: deepcopy<br/>dropped from FIRST/LAST,<br/>upsert docstring says<br/>the sketch keeps<br/>references (caller must<br/>not modify the record),<br/>two…"
    Cypher->>Smith: "pm handoff"
    Note right of Cypher: "Sprint 4 (Parallel<br/>Merge, Tier 2, 5 pts):<br/>SKT-06 merge -j N<br/>(processes, default all<br/>cores), batches merged<br/>as they finish,<br/>FIRST/LAST any m…"
    Smith->>Mouse: "user approve"
    Note right of Smith: "*user approve. rubric<br/>STORIES: OUT=S TEST=S<br/>FAIL=S SCOPE=S SIZE=S<br/>DESIGN=A, rubric ARCH:<br/>BOUND=S FLOW=S FAIL=A<br/>USER=S DECS=S FEAS=S.<br/>Warnin…"
    Mouse->>Neo: "sm handoff"
    Note right of Mouse: "rubric PLAN: SIZE=A<br/>GATE=S VERIF=S ALIGN=S<br/>OWNER=S. Phase 1 (Neo):<br/>D1 _fold_lines refactor,<br/>-j 1 unchanged, tests<br/>green. Phase 2 (Neo):<br/>D2-…"
    Neo->>User: "swe status"
    Note right of Neo: "Phase 1-2 impl: merge -j<br/>N (ProcessPoolExecutor,<br/>batches of 5000 lines,<br/><=2 per worker in<br/>flight, merged as they<br/>finish, warnings in line<br/>o…"
    Neo->>User: "swe status"
    Note right of Neo: "Parallel merge reworked<br/>with the owner: long-<br/>lived workers, task<br/>queue (3 per worker) of<br/>5000-line byte batches,<br/>output queue with one<br/>fold…"
    Neo->>User: "swe status"
    Note right of Neo: "libyaml everywhere<br/>(sketchtastic/_yaml.py:<br/>sketches, run files,<br/>profiles, built-ins).<br/>make profile: parallel<br/>13.54 s (was 16.46), -j<br/>1 29.5…"
    Tank->>Oracle: "devops handoff"
    Note right of Tank: "SDLC check passed: from-<br/>clean distclean/install/<br/>lint/test/secrets/build,<br/>smoke, test-all (3.14,<br/>3.15) green, profile row<br/>and Last verified…"
    Oracle->>Smith: "ora handoff"
    Note right of Oracle: "Docs groomed. rubric<br/>SDLC: TRUE=S WHOLE=A<br/>CLEAN=A CLASS=S CHECK=A<br/>GAPS=A. rubric DECISION:<br/>CTX=S CHOICE=S CONSEQ=S<br/>(libyaml). Sprint 4<br/>arch…"
    Smith->>All: "user approve"
    Note right of Smith: "*user approve. rubric<br/>UAT: COVER=S STEPS=A<br/>FAIL=S DATA=S EVID=A.<br/>make gharchive (all<br/>cores): 180387 events,<br/>88 skits, history<br/>written, show…"
    Neo->>Cypher: "retro"
    Note right of Neo: "Neo retro: one fold<br/>function, two drivers,<br/>the owner's queue/worker<br/>shape was both simplest<br/>and fastest. Backlog<br/>items: none"
    Trin->>Cypher: "retro"
    Note right of Trin: "Trin retro: two test<br/>bugs of mine (line<br/>insert order, run ids<br/>per split) caught fast,<br/>round-trip test guards<br/>libyaml. Backlog items:<br/>show c…"
    Morpheus->>Cypher: "retro"
    Note right of Morpheus: "Morpheus retro: two<br/>designs dropped by<br/>measurement (pool with<br/>per-batch merges, per-<br/>line shared memory),<br/>measure before adding<br/>machinery. B…"
    Oracle->>Cypher: "retro"
    Note right of Oracle: "Oracle retro: decisions<br/>recorded with numbers,<br/>including what was tried<br/>and dropped. Backlog<br/>items: none"
    Mouse->>Cypher: "retro"
    Note right of Mouse: "Mouse retro: owner<br/>steered the design live,<br/>three implementations in<br/>one sprint, final one<br/>smallest. Backlog items:<br/>none"
    Cypher->>Cypher: "retro"
    Note right of Cypher: "Cypher retro: 'any<br/>matching sample is fine'<br/>simplified the whole<br/>design. Backlog items:<br/>stable show column order"
    Smith->>Cypher: "retro"
    Note right of Smith: "Smith retro: 2.2x faster<br/>with all cores, same<br/>answers. Backlog items:<br/>show column order<br/>follows worker<br/>completion"
    Cypher->>All: "pm launch"
    Note right of Cypher: "*pm launch sprint-4.<br/>Parallel Merge: merge -j<br/>N (default all cores)<br/>with long-lived workers,<br/>a bounded task queue of<br/>byte batches and an ou…"
```
