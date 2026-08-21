# Validation: two gates

A build spec for catching the defects in `DECK_REVIEW.md` before a deck is
returned. Written to be handed to Claude Code as-is.

The principle: **assertions first, rendering second.** 13 of the 14 defects
found in `deck (12).pptx` are catchable with zero model tokens and a
deterministic failure. Rendering is for the small set that assertions cannot
express. Building the render gate first is paying vision prices for a `len()`.

---

## Severity, and the question it must not presuppose

Open question 5 — *what should preflight refuse* — is unresolved. Do not resolve
it in code. Build the mechanism and leave the policy configurable:

| Severity | Behaviour |
| --- | --- |
| `report` | Recorded in the build report. Deck is returned. **Default for every new check.** |
| `refuse` | The plan is rejected and retried once, with the failing check and its evidence given back to the planner. |
| `block` | Deck is not returned at all. |

Every check below ships at `report`. Promotion to `refuse` is a config change,
one check at a time, with the golden-deck test (below) proving each promotion
does what it claims. This way the architecture does not assume an answer to a
question the team has not settled.

---

## Gate 1 — assertions

Free, deterministic, testable. Two phases.

### 1a · Pre-build — on the plan, before any XML is drawn

Cheapest possible failure point: nothing has been rendered yet.

| Check | Rule | Catches |
| --- | --- | --- |
| `copy_fits` | Every slot's string length ≤ the contract's `fits_chars`. **Over-length is a refusal, never a truncation.** | The cover title truncated mid-word at 69 chars against a 16-char slot |
| `no_source_echo` | No slot's text may be a ≥40-character prefix or substring of the raw input brief. | "I would like to share our plan…" lifted verbatim from the email |
| `cardinality` | If source material for a slot is a list of N items, the target region's `count` range must contain N. Never join a list into one paragraph. | Five owners collapsed into one text box |
| `slot_completeness` | Every `required: true` slot in the contract has content. | Empty picture placeholder on the outro |
| `archetype_variety` | No archetype used more than twice in a deck of ≥10 slides, and no two consecutive content slides share an archetype. | The one-model-call layout-reuse problem |

`copy_fits` and `no_source_echo` are the two highest-value checks in this
document. Between them they would have prevented the worst slide in the deck.

### 1b · Post-build — read the `.pptx` back

| Check | Rule | Catches |
| --- | --- | --- |
| `type_colour` | Runs are `141414`, `FFFFFF`, or `1450F5` **only when the font is KONE Information**. Inter is never blue and never grey. | Owner names in blue Inter |
| `no_bold_flag` | `b="1"` never appears on any Inter or Inter SemiBold run. | Bold flag stacked on Inter SemiBold |
| `font_role` | Every run's `latin typeface` ∈ {Inter, Inter SemiBold, KONE Information}. Every KONE Information run is uppercase. Every Inter run is not. | Casing rule, both directions |
| `type_resolves` | **No region carries a `dg` block.** | The whole of README §3; this is the step-1 acceptance criterion wired as a test |
| `chrome` | Footer present iff `wants_footer(archetype)`. Page number string equals the slide index. The only date string anywhere in the package equals the deck date. | Page "11" on slide 12; "23 July 2026"; a footer on the outro |
| `mask_integrity` | A cut-cover archetype emits ≥3 background-coloured rectangles over exactly **one** picture frame. | The cover that was a photo band, not a cut |
| `overlap` | No two text frames intersect geometrically. | The eyebrow box overlapping the title box on slide 4 |
| `floor` | No non-chrome ink below y=629px (472pt). | — |
| `logo_count` | Exactly one logo image per slide; on the correct side for the archetype's kind. | — |
| `bullets` | No text line begins with `-`, `–` or `—`. An indented line must carry a real list marker. | Three indented sentences with no marker |
| `content_edge` | Report any content region whose right edge falls short of x=1235px when its archetype declares a full-width column. | Agenda labels stopping at 904pt |
| `notes_present` | A `notesSlide` part exists for every slide. | No speaker notes in the entire package |

---

## Gate 2 — render and look

Only for what assertions cannot express. Build this **after** gate 1 is green.

### 2a · Font provisioning and a self-test — do this first

LibreOffice substitutes Inter and KONE Information unless both are installed in
the container. Without this step every render review reports type faults that do
not exist in the real PowerPoint output — false positives about precisely the
thing being fixed.

1. Install Inter (400, 600) and `KONE_Information.ttf` into the render image.
2. Commit one reference slide as a PNG.
3. `render_selftest` re-renders it on every boot and compares against the
   reference within a perceptual tolerance.
4. **If the self-test fails, gate 2 is disabled, not trusted.** A render gate
   that cannot prove its own fonts must not be allowed to report type findings.

### 2b · The renderer

`soffice --headless --convert-to pdf`, then rasterise the PDF per page. PDF then
raster is sturdier than direct-to-PNG for multi-slide files.

Cache key: `hash(slide shape XML + archetype version + render pipeline version)`.
An unchanged slide is never re-rendered.

Sampling: render every slide on a release build. On an interactive build, render
only slides that are photo-bearing, newly migrated, or already flagged by gate 1.

### 2c · Ask closed questions, not "how does this look"

The vision call must return structured verdicts, so results are diffable across
builds and testable. Per slide, ask only what a shape tree cannot answer:

1. Is any text clipped by a shape edge or by the canvas edge?
2. Does white type sit over a light region of the photograph?
3. Does the photo crop cut a face, or run the horizon through the type?
4. Is any region more than ~70% empty while an adjacent region wraps past four
   lines?

Return `{slide, check, verdict, note}` as JSON. Never free prose.

Note the division of labour, and respect it: at ~1.2k tokens for a 1280×720
slide the model can judge composition but cannot reliably tell 46px from 56px or
spot a missing small-caps. Gate 2 is strong exactly where gate 1 is weak, and
weak exactly where gate 1 is strong. **Gate 2 reports only. It never refuses.**

---

## The golden-deck regression test

`deck (12).pptx` is the fixture. Commit it as `tests/fixtures/before.pptx` with
the 14 findings in `DECK_REVIEW.md` as the expected result.

```
test_golden_deck_before():
    findings = preflight(load("tests/fixtures/before.pptx"))
    assert covers(findings, EXPECTED_14) >= 13
```

Gate 1 must catch at least 13 of the 14 without rendering anything. The
fourteenth — numbering a parallel list — needs judgement; leave it out of the
assertion set and let gate 2 or a human find it.

This gives the work a checkable definition of done, using an artifact that
already exists.

---

## Order of work

1. Severity mechanism, all checks at `report`.
2. Gate 1a — `copy_fits` and `no_source_echo` first; they are the highest-value
   checks in this document.
3. Gate 1b — the rest of the assertions.
4. The golden-deck test. Do not proceed until it passes.
5. Promote checks to `refuse` one at a time, each with a test.
6. Gate 2a — fonts and the self-test.
7. Gate 2b/2c — renderer, cache, closed-question review.

## Do not

- Do not build gate 2 first.
- Do not let gate 2 refuse a deck.
- Do not truncate to fit a slot, ever. Over-length copy is information: it means
  the copy was not written for that slot.
- Do not trust a render finding while `render_selftest` is failing.
- Do not decide open question 5 in code. Build the mechanism; leave the policy
  in config.
