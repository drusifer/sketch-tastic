# Sprint 5 UAT: Bluesky Image Counts

**Owner:** Trin / Smith · **Scope:** STORY-SKT-08..09 · **Date:** 2026-11-19

## Journeys and acceptance checks

| Journey | Command / evidence | Expected |
|---|---|---|
| Capture bounded public records | `bobp make bluesky-capture ARGS="--seconds 120 --limit 100000 --output data/bluesky.jsonl"` | Stops at time/limit; JSONL plus endpoint/window provenance; no credentials |
| Prepare original dataset | `bobp make bluesky ARGS="prepare data/bluesky.jsonl --output data/bluesky-demo"` | Image/skit counts; sketch, exact profile, summary and representatives |
| Explore enum counts | `bobp make -vvv bluesky ARGS="report data/bluesky-demo --group-by orientation"` | ASCII bars, observed/absent enum values, capture scope |
| Filter multiple properties | `bobp make -vvv bluesky ARGS="report data/bluesky-demo --group-by mime --where reply=reply --where alt=present"` | AND filtering; matching image total equals displayed counts |
| Inspect skit combinations | `bobp make -vvv run ARGS="show data/bluesky-demo/images.sketch.yaml"` | One row per observed token combination |
| Retained test data | `bobp make run ARGS="merge -p data/bluesky-demo/profile.yaml -s data/representatives.sketch.yaml data/bluesky-demo/representatives.jsonl"` | Same number/IDs of skits, one input row per skit; preparation independently asserts set equality |
| Empty/bad input | `bobp make test-bluesky` | Explicit empty output; malformed rows include line numbers; existing output protected |
| Enum and source fidelity | `bobp make test-bluesky` | 1/2/3/4/5/10/11/20 boundaries, direct/quote/gallery, missing/invalid values, original event preserved |

## Results

- 24 demo tests and complete 267-test suite passed; lint passed.
- Public canonical-v2 one-frame smoke captured and prepared one image/skit; ASCII report displayed correctly.
- Live 120-second capture: 4,587 frames, 4,394 accepted creates, 580 image posts,
  821 image rows and 70 skits/representatives. Retained ID-set equality passed.
  The public merge CLI independently read 70 representative rows and produced 70 skits.
- Orientation report: portrait 357, square 57, landscape 349, missing 58 (sum 821).
  AND-filter `reply=reply`, `alt=present`: 20 images, six skits, all JPEG.
  Absent categories remain visible (including quote_gallery and attachment_count=11+).
- Clean conformance: 267 tests each on Python 3.14 and 3.15, lint, three installed-wheel
  smoke tests, wheel/sdist build, secret scan and locked dependency audit passed.
- Capture UTC window: 2026-11-20 02:47:24–02:49:24. Source SHA-256:
  `a8d645e59fbd0851a1a5c7f14a6e1db661151f192c6be859fb0fd6fca5e2b499`.
  Generated evidence remains in ignored `data/bluesky-demo/`; it is removed by `clean`.
- Smith verdict: approved. UAT COVER/STEPS/FAIL/DATA/EVID=PASS. The engineering lesson
  in `docs/LESSONS.md` passes WHEN/WHAT/RULE/CAUSE/PLACE.
- Security: Switch design and implementation passed; locked dependency audit and hook probe passed.
- No browser testing applies: this is an ASCII CLI.

## Limits
The capture is a window of public create events, not a global inventory. Missing enum values
remain visible as not observed. Retained-ID equality establishes observed profile-variant
preservation; no claim of path coverage, replay, or theoretical combination completeness.
