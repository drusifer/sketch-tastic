# CHAT_SPRINT_4 — Sprint Archive

## Summary

Sprint 4, Parallel Merge (Tier 2, 5 pts). Preceded by the owner's review of Sprint 3: JSONPath via jsonpath-rfc9535, fold once then merge, no FIRST/LAST copies (32.88 s). Owner design: processes, -j N default all cores, any matching FIRST/LAST sample. Pool with per-batch merges (17-19 s) and per-line shared-memory ring (25.7 s) measured and dropped; final: long-lived workers, bounded task queue of byte batches, output queue (16.46 s). libyaml everywhere: 13.54 s on 4 cores, 29.55 s -j 1. No release.

---
[<small>2026-10-14 22:38:48</small>] [**User**]->[**all**] *request*:
 Revert the plain-path shortcut; replace python-jsonpath with jsonpath-rfc9535 2.0 (basic strategy). Standard RFC 9535 only, no special syntax.

---
[<small>2026-10-14 22:42:55</small>] [**make**]->[**all**] *build*:
 Build PASSED | make smoke | /home/drusifer/Projects/sketch-tastic/build/build.out
sketch_tastic-0.2.0-py3-none-any.whl
...
----------------------------------------------------------------------
sketch_tastic-0.2.0.tar.gz
Ran 3 tests in 1.487s

OK

---
[<small>2026-10-14 22:43:02</small>] [**Neo**]->[**User**] *swe fix*:
 Done on fix/jsonpath-rfc9535: plain-path shortcut removed; python-jsonpath replaced by jsonpath-rfc9535 2.0.2 (basic resolver, no locations). make profile 46.25 s (shortcut: 40.83, baseline 106.35), hash cb5533be1554ba98 unchanged. test 232 OK, test-all 3.14/3.15, smoke, lint green. New transitive deps: regex, iregexp-check. Not merged yet: owner reviewing Sprint 3 changes one at a time.

---
[<small>2026-10-14 22:51:59</small>] [**make**]->[**all**] *build*:
 Build PASSED | make profile | /home/drusifer/Projects/sketch-tastic/build/build.out

Ordered by: cumulative time
List reduced from 2267 to 25 due to restriction <25>

ncalls  tottime  percall  cumtime  percall filename:lineno(function)

---
[<small>2026-10-14 22:52:11</small>] [**Neo**]->[**User**] *swe fix*:
 fix/fold-once: Sprint 3 select-once reverted; merge now folds each event into the run only and merges the run into the sketch once (Aggregator.merge per function, Aggregate.merge, Sketch.merge). 4 MergeTests incl. split-anywhere equivalence. make profile 39.36 s (was 46.25), hash cb5533be1554ba98 unchanged. test 234 OK, lint clean.

---
[<small>2026-10-14 22:58:17</small>] [**make**]->[**all**] *build*:
 Build PASSED | make profile | /home/drusifer/Projects/sketch-tastic/build/build.out

Ordered by: cumulative time
List reduced from 2267 to 25 due to restriction <25>

ncalls  tottime  percall  cumtime  percall filename:lineno(function)

---
[<small>2026-10-14 22:58:26</small>] [**Neo**]->[**User**] *swe fix*:
 fix/fold-once: deepcopy dropped from FIRST/LAST; upsert docstring says the sketch keeps references (caller must not modify the record); two copy-guarantee tests removed (owner). make profile 32.88 s (was 39.36), hash unchanged; test 232 OK, lint clean.

---
[<small>2026-10-14 23:09:11</small>] [**Cypher**]->[**Smith**] *pm handoff*:
 Sprint 4 (Parallel Merge, Tier 2, 5 pts): SKT-06 merge -j N (processes, default all cores), batches merged as they finish; FIRST/LAST any matching sample (owner). SKT-07 make profile reports parallel + -j 1 time, hash from -j 1. Arch D1-D4 in docs/sprints/USER_STORIES_SPRINT4.md. @Smith *user review sprint-4

---
[<small>2026-10-14 23:09:11</small>] [**Smith**]->[**Mouse**] *user approve*:
 *user approve. rubric STORIES: OUT=S TEST=S FAIL=S SCOPE=S SIZE=S DESIGN=A; rubric ARCH: BOUND=S FLOW=S FAIL=A USER=S DECS=S FEAS=S. Warnings sorted by line keep output stable; FIRST/LAST caveat must be in --help. @Mouse *sm plan sprint

---
[<small>2026-10-14 23:09:11</small>] [**Mouse**]->[**Neo**] *sm handoff*:
 rubric PLAN: SIZE=A GATE=S VERIF=S ALIGN=S OWNER=S. Phase 1 (Neo): D1 _fold_lines refactor, -j 1 unchanged, tests green. Phase 2 (Neo): D2-D3 pool, -j, tests with tiny batches. Phase 3 (Tank): D4 make profile. Close as usual. @Neo *swe impl phase-1

---
[<small>2026-10-14 23:17:17</small>] [**make**]->[**all**] *build*:
 Build PASSED | make profile | /home/drusifer/Projects/sketch-tastic/build/build.out

24929802 function calls (22564295 primitive calls) in 25.727 seconds

Ordered by: cumulative time
List reduced from 2745 to 25 due to restriction <25>


---
[<small>2026-10-14 23:17:51</small>] [**Neo**]->[**User**] *swe status*:
 Phase 1-2 impl: merge -j N (ProcessPoolExecutor, batches of 5000 lines, <=2 per worker in flight, merged as they finish, warnings in line order, sequence range absorbed). make profile: parallel 17-19 s vs -j 1 35.5 s (~2x on 4 cores), -j 1 hash unchanged. Parent profile: YAML pure-Python emitter ~10.5 s, merge deepcopy ~5.4 s, line split+pickle ~6.4 s serial. Proposed to owner: libyaml, no-copy merge, byte blocks.

---
[<small>2026-10-14 23:49:14</small>] [**make**]->[**all**] *build*:
 Build PASSED | make profile | /home/drusifer/Projects/sketch-tastic/build/build.out

22527875 function calls (21750713 primitive calls) in 25.196 seconds

Ordered by: cumulative time
List reduced from 2598 to 25 due to restriction <25>


---
[<small>2026-10-14 23:49:33</small>] [**Neo**]->[**User**] *swe status*:
 Parallel merge reworked with the owner: long-lived workers, task queue (3 per worker) of 5000-line byte batches, output queue with one fold per worker merged on arrival; first fold becomes the run. Shared-memory ring tried and dropped (25.7 s). make profile: parallel 16.46 s, -j 1 31.99 s, hash cb5533be1554ba98. test 237 OK, lint clean. Remaining serial: YAML writing ~10.7 s profiled.

---
[<small>2026-10-14 23:55:14</small>] [**make**]->[**all**] *build*:
 Build PASSED | make profile | /home/drusifer/Projects/sketch-tastic/build/build.out

99234045 function calls (95448646 primitive calls) in 72.580 seconds

Ordered by: cumulative time
List reduced from 2207 to 25 due to restriction <25>


---
[<small>2026-10-14 23:55:23</small>] [**Neo**]->[**User**] *swe status*:
 libyaml everywhere (sketchtastic/_yaml.py: sketches, run files, profiles, built-ins). make profile: parallel 13.54 s (was 16.46), -j 1 29.55 s (was 31.99). Sketch bytes change, content identical (round-trip test); new -j 1 hash bd657fe6fd331918. test 238 OK, lint clean.

---
[<small>2026-10-14 23:56:29</small>] [**make**]->[**all**] *build*:
 Build PASSED | make test-all | /home/drusifer/Projects/sketch-tastic/build/build.out
=== make test-all @ 2026-10-14 23:56:20 ===
== Python 3.14 ==
Ran 238 tests in 3.023s
OK
== Python 3.15 ==
Ran 238 tests in 3.729s
OK

---
[<small>2026-10-14 23:56:37</small>] [**Tank**]->[**Oracle**] *devops handoff*:
 SDLC check passed: from-clean distclean/install/lint/test/secrets/build, smoke, test-all (3.14, 3.15) green; profile row and Last verified updated. @Oracle *ora groom

---
[<small>2026-10-14 23:56:53</small>] [**make**]->[**all**] *build*:
 Build PASSED | make run | /home/drusifer/Projects/sketch-tastic/build/build.out

---
[<small>2026-10-14 23:57:27</small>] [**Oracle**]->[**Smith**] *ora handoff*:
 Docs groomed. rubric SDLC: TRUE=S WHOLE=A CLEAN=A CLASS=S CHECK=A GAPS=A. rubric DECISION: CTX=S CHOICE=S CONSEQ=S (libyaml). Sprint 4 arch doc records the two dropped designs. No new lessons. @Smith *user test sprint-4

---
[<small>2026-10-14 23:57:27</small>] [**Smith**]->[**all**] *user approve*:
 *user approve. rubric UAT: COVER=S STEPS=A FAIL=S DATA=S EVID=A. make gharchive (all cores): 180387 events, 88 skits, history written; show --sort payload_bytes ends on fa3822c6 11.4% as before. Rough edge: skit order in the file follows worker completion, so show's aggregate column order can change between runs (values exact). Backlog. @all *sprint retro

---
[<small>2026-10-14 23:57:27</small>] [**Neo**]->[**Cypher**] *retro*:
 Neo retro: one fold function, two drivers; the owner's queue/worker shape was both simplest and fastest. Backlog items: none

---
[<small>2026-10-14 23:57:27</small>] [**Trin**]->[**Cypher**] *retro*:
 Trin retro: two test bugs of mine (line insert order, run ids per split) caught fast; round-trip test guards libyaml. Backlog items: show column order stable across runs

---
[<small>2026-10-14 23:57:27</small>] [**Morpheus**]->[**Cypher**] *retro*:
 Morpheus retro: two designs dropped by measurement (pool with per-batch merges, per-line shared memory); measure before adding machinery. Backlog items: none

---
[<small>2026-10-14 23:57:27</small>] [**Oracle**]->[**Cypher**] *retro*:
 Oracle retro: decisions recorded with numbers, including what was tried and dropped. Backlog items: none

---
[<small>2026-10-14 23:57:27</small>] [**Mouse**]->[**Cypher**] *retro*:
 Mouse retro: owner steered the design live; three implementations in one sprint, final one smallest. Backlog items: none

---
[<small>2026-10-14 23:57:27</small>] [**Cypher**]->[**Cypher**] *retro*:
 Cypher retro: 'any matching sample is fine' simplified the whole design. Backlog items: stable show column order

---
[<small>2026-10-14 23:57:27</small>] [**Smith**]->[**Cypher**] *retro*:
 Smith retro: 2.2x faster with all cores, same answers. Backlog items: show column order follows worker completion

---
[<small>2026-10-14 23:57:27</small>] [**Cypher**]->[**all**] *pm launch*:
 *pm launch sprint-4. Parallel Merge: merge -j N (default all cores) with long-lived workers, a bounded task queue of byte batches and an output queue of one fold per worker; libyaml for all YAML. GH Archive hour: 13.54 s on 4 cores, 29.55 s with -j 1 (106.35 s before Sprint 3). FIRST/LAST samples any matching event (owner). No release (mainline). Sprint complete.

