# deckguard

`deckguard` is a Python tool that automates PowerPoint brand compliance for
KONE's Marketing Hub — available as a CLI and as a small hostable web app.
It both **corrects** existing decks and **creates** new ones, always
against the same `brand_rules.yaml` and the same org master template:

- **`create`** — generate a brand-new, on-brand deck from a YAML content
  outline (or append on-brand slides to an existing deck), built directly
  on the org template's own approved layouts
- **`redesign`** — the AI-assisted counterpart to `create`: upload any
  deck and have Claude judge which slide kind each slide's content
  should become, then build it through the exact same deterministic,
  brand-guaranteed pipeline `create` uses (needs `ANTHROPIC_API_KEY`)
- **`fix`** — auto-correct brand violations in a `.pptx` file
- **`audit`** — scan one deck or a folder of decks and report violations
- **`retemplate`** — rebuild an old deck's slides onto the org template's
  own layouts, carrying over title/body text and images
- **`migrate`** — replace just a deck's cover/outro with the org template's
- **`learn`** — derive brand-rule color/font remaps from an old/new deck pair

## Architecture

- **Deterministic first, AI second.** Everything achievable with rules +
  `python-pptx` — color remap, font swap, logo replace, effects removal,
  size/alignment checks, and every layout an on-brand deck gets built or
  rebuilt onto — is pure Python with zero API calls, and stays that way
  regardless of whether AI is available. `redesign` is the one command
  that spends an API call, and only for the one judgment call XML
  analysis can't make on its own — "what kind of slide is this" — never
  for color, font, or layout-approval decisions (see "AI-assisted
  redesign" below). It runs nowhere near the deterministic engine's own
  guarantees: its output is just another `create`-shaped outline, built
  through the identical brand-compliant pipeline. Every other command —
  `create`, `fix`, `audit`, `retemplate`, `migrate`, `learn`, `inspect`,
  `hash-logo`, `validate-rules`, and the web app minus its one opt-in
  route — still runs with **no API key required**, same as always. A
  still-unbuilt, broader visual-judgment layer (logo clear-space,
  "used sparingly" checks against a rendered image rather than extracted
  text) remains future work — that's a materially different, harder
  problem than the content-to-layout mapping `redesign` solves.
- **Config-driven.** All brand knowledge lives in `brand_rules.yaml`
  (shipped as the default config, both at the repo root and packaged
  inside `deckguard`). No brand values are hardcoded — point `--rules` at
  a different file to run the same tool for a different brand.
- **Never destructive.** `fix` always writes to a new `<name>_fixed.pptx`
  file, alongside a machine-readable JSON change log and a human-readable
  Markdown summary. The input file is never opened for writing. Every
  mutating command supports `--dry-run`.
- **Graceful degradation.** SmartArt, embedded charts, OLE objects, and
  anything the deterministic engine can't safely fix is left untouched
  and flagged as "manual review required" rather than risking XML
  surgery it can't be sure of.
- **Generation reuses correction, not the other way around.** `create`
  (see below) doesn't duplicate any brand logic: it picks a layout using
  the exact same content-fit matcher `retemplate` uses to rebuild old
  slides, and finishes every composed deck by running it through the
  same `fix_deck` engine `fix` uses. A new capability, zero new rules.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Requires Python 3.11+. This installs the `deckguard` console script, the
`deckguard.web` FastAPI app, and their shared dependencies (`python-pptx`,
`Pillow`, `imagehash`, `PyYAML`, `click`, `rich`, `fastapi`, `uvicorn`).

> **LibreOffice (Phase 2 only):** the upcoming AI visual-audit layer
> renders slides to PNG via `soffice --headless --convert-to png`. It
> isn't required for anything in this repo today — `fix`, `audit`,
> `inspect`, `hash-logo`, `validate-rules`, and the web app are all
> pure-Python and work without it.

## Web app

A minimal browser UI over the same engine the CLI uses — upload a
`.pptx`, audit or fix it, download the results. No new brand logic lives
here; `deckguard/web.py` just calls the same `inventory` /
`rules_engine` / `fixer` functions the CLI does, so the two can never
disagree about what counts as a violation or a fix.

```bash
uvicorn deckguard.web:app --reload
# -> http://127.0.0.1:8000
```

Routes: `GET /` (upload + compose + redesign forms), `POST /audit`,
`POST /fix`, `POST /create` (compose a new deck from a pasted YAML
outline, optionally appending onto an uploaded existing deck),
`POST /redesign` (AI-assisted redesign of an uploaded deck — only
active when the server has `ANTHROPIC_API_KEY` set; see "AI-assisted
redesign" above), `POST /learn`, `GET /download/{token}/{filename}`,
`GET /health`.

Set `DECKGUARD_WEB_PASSWORD` to require an HTTP Basic Auth password
before anything is reachable (username is ignored) — unset by default,
which is fine for local use but **should be set once this is hosted
anywhere with a public URL**, since it processes decks you upload.
Uploads and results live under `DECKGUARD_WEB_STORAGE` (defaults to
`/tmp/deckguard-web`) and are cleaned up after ~2 hours.

### Hosting on Railway

The repo ships `Procfile` and `railway.json` for this:

1. In Railway, **New Project → Deploy from GitHub repo**, pick this repo.
2. Railway's Nixpacks builder detects `pyproject.toml` and runs
   `pip install .`, then starts `uvicorn deckguard.web:app --host 0.0.0.0
   --port $PORT` per `railway.json`/`Procfile` — no extra config needed.
3. Under the service's **Variables**, set `DECKGUARD_WEB_PASSWORD` to
   something before sharing the URL around.
4. Railway assigns a public URL under **Settings → Networking → Generate
   Domain**.

Any other Python host that runs a `Procfile`-style start command (or
just `uvicorn deckguard.web:app --host 0.0.0.0 --port $PORT`) works the
same way — nothing here is Railway-specific beyond those two config
files.

## Quickstart

```bash
# Generate a brand-new deck from a YAML content outline
deckguard create outline.yaml --out deck.pptx

# ...or append its slides onto a copy of an existing deck instead
deckguard create outline.yaml --out deck.pptx --append existing.pptx

# Sanity-check the brand config
deckguard validate-rules

# See everything deckguard can find in a deck
deckguard inspect mydeck.pptx --format md

# Audit a deck (or a folder of decks) against the brand rules
deckguard audit mydeck.pptx
deckguard audit ./decks/ --out ./reports --format json

# Preview fixes without writing a file
deckguard fix mydeck.pptx --dry-run

# Apply fixes -> mydeck_fixed.pptx + a JSON/Markdown change log
deckguard fix mydeck.pptx --out ./fixed

# Get a perceptual hash to add to logo.old_logo_hashes
deckguard hash-logo old_logo_export.png
```

`audit` exits non-zero when any violation's severity is in the config's
`audit.fail_on` list (`critical` by default) — wire it into CI to gate
merges on brand compliance.

## Commands

| Command | Purpose |
|---|---|
| `create <outline.yaml> --out <deck.pptx>` | Generates a new deck straight onto the org template's own layouts from a YAML content outline — see "Composing a new deck" below. `--append <deck.pptx>` appends onto a copy of an existing deck instead of starting fresh. |
| `redesign [deck] --out <deck.pptx> [--brief TEXT] [--mode rewrite\|brand] [--review]` | Two modes, see "AI-assisted redesign" below. `--mode rewrite` (default): AI-assisted counterpart to `create`, from any starting point — redesigns an existing deck's content, fills its blank slides from `--brief`, or (with no deck at all) builds one from just a brief. Needs `ANTHROPIC_API_KEY`. `--mode brand`: fully deterministic, no API key — carries `deck`'s own text/images over verbatim onto approved layouts (picked for variety) and swaps its cover/closing slide onto the current brand look. `--mode brand --review` adds one small, optional AI call that rebuilds a skipped divider/transition-style slide (e.g. "Appendix") onto the org template's own Section Divider layout — needs `ANTHROPIC_API_KEY` just for that one call. |
| `inspect <deck>` | Full structured inventory: shapes, fills, fonts (raw + normalized), sizes, alignment, images (with perceptual hash), effects, layout/master usage. The discovery tool for growing `brand_rules.yaml` from real decks. |
| `fix <deck>` | Applies deterministic corrections: color remap (fills, gradients, text, lines, theme), font remap (run + theme/master/layout level), logo replacement by image hash, forbidden text-effect removal, forced left-alignment. |
| `audit <deck\|folder>` | Reports violations (slide, element, rule, severity, auto-fixable). Folder mode writes a per-deck report plus a `summary.csv`. |
| `hash-logo <image>` | Prints an image's perceptual hash, for `logo.old_logo_hashes`. |
| `validate-rules [rules.yaml]` | Checks a brand config for syntax and semantic errors (hex format, remap targets in the approved list, logo file exists, etc). |
| `learn <old> <new>` | Compares an off-brand deck against an already-on-brand reference deck and proposes `colors.remap`/`fonts.remap` additions — see below. |
| `migrate <deck> --template <potx>` | Replaces just the cover/outro slide with the org template's own. |
| `retemplate <deck> --template <potx>` | Rebuilds every eligible slide's structure onto an org-template layout, carrying over text/images — see below. |

Every command takes `--rules path/to/brand_rules.yaml` (defaults to the
packaged KONE config). `fix`, `audit`, and `create` also take `--out
DIR`/`--out FILE` for where reports/output land.

## Composing a new deck from an outline

`deckguard create` builds a deck straight onto the org template's own
approved layouts from a YAML content outline — no separate `fix` pass is
needed afterward, since every slide's color and font come from the
template's theme by construction (the same `fix_deck` engine `deckguard
fix` uses runs once, automatically, before the file is saved, to resolve
any inherited-but-unresolved text color — see `compose.py`'s module
docstring for why that step exists).

```yaml
# outline.yaml
slides:
  - kind: cover
    title: "Q3 Modernization Review"
    subtitle: "People Flow, reimagined"
    variant: B                        # Cover A-F

  - kind: agenda
    title: "Agenda"
    bullets: ["Where we are", "What changed", "What's next"]

  - kind: section                     # chapter divider
    title: "Where we are"
    variant: plain                    # plain | numbered | A | B | C | D

  - kind: content                     # 1-3 columns, picks the tightest layout
    title: "Three priorities"
    columns:
      - ["Reliability", {level: 1, text: "99.98% uptime"}]
      - ["Speed"]
      - ["Scale"]

  - kind: stat                        # KONE-numbers-style callouts
    title: "KONE numbers"
    stats:
      - {number: "1.1M", label: "elevators & escalators maintained"}
      - {number: "60,000", label: "employees worldwide"}

  - kind: timeline                    # milestone-by-milestone roadmap
    title: "Roadmap"
    milestones:
      - {label: "Q3 2026", text: "Predictive maintenance GA"}
      - {label: "Q4 2026", text: "Full fleet rollout"}

  - kind: quote
    title: "Customer voice"
    quote_text: "KONE's predictive maintenance cut our downtime in half."
    quote_author: "Facilities Director, EU retail chain"
    variant: A                        # Quote A-E

  - kind: statement                   # one big centered message
    title: "A single, unmissable point"

  - kind: end
    title: "Thank you"

  - kind: blank                       # logo/footer only, for manual edits
  - kind: content
    layout: "Two content A"           # escape hatch: force an exact layout
    columns: [["Left"], ["Right"]]
```

```bash
deckguard create outline.yaml --out deck.pptx
# -> wrote: deck.pptx
#    11 slide(s) using layouts: Agenda A, Blank, Cover B, Outro, ...
```

`content`/`stat`/`timeline` slides don't name a layout directly — the
number of columns/stats/milestones supplied picks the tightest-fitting
layout automatically, via the identical `match_layout` algorithm
`retemplate` uses to rebuild legacy slides (see Architecture above).
`cover`/`quote`/`section` take an optional `variant` letter; anything can
be overridden with an explicit `layout: "<name>"`.

Pass `--append existing.pptx` to add the outline's slides onto a copy of
an existing deck instead of starting fresh — that deck's own pre-existing
slides, theme, and master are left completely untouched; only the new
slides are ever touched or reported on.

Two things `create` deliberately does not attempt:

- **All-caps content isn't rewritten.** A quarter label like `"Q3 2026"`
  or a unit-suffixed number like `"1.1M"` reads as ALL CAPS to the
  `all_caps` rule (any text with an uppercase letter and no lowercase one
  — the same heuristic that already flags a hand-typed deck's real
  ALL-CAPS headings). `fix_deck` never auto-rewrites case for anyone, by
  design, so these surface in `manual_review` rather than being silently
  mangled.
- **Per-slide date/footer/page-number chrome isn't restored.** Composed
  slides get the logo/tagline (inherited straight from the layout — see
  `compose.py`'s module docstring) but not a per-slide date/footer/page
  number placeholder, the same as a slide added via python-pptx's own
  `add_slide()`. A known gap, not a silent corruption.

## AI-assisted redesign

`deckguard redesign` has two modes. `--mode rewrite` (the default,
described in this whole section) is the judgment layer `create` can't
provide on its own, and it works from any starting point — the goal is
that a brand new deck, a mostly-empty one, and a completely off-brand
one all land on the org template the way a human designer would build
them, through one command. `--mode brand` is a different, fully
deterministic animal — see "`--mode brand`: same command, no AI, no
wording changes" near the end of this section if what you want is your
deck's existing wording carried over exactly as written, just re-laid-
out onto approved layouts and brought onto brand colors/fonts.

```bash
export ANTHROPIC_API_KEY=sk-...

# 1. Redesign an existing, possibly off-brand deck
deckguard redesign old_deck.pptx --out redesigned.pptx

# 2. A deck that's mostly empty -- redesign its real content AND
#    author its blank slides from a brief, as one coherent whole
deckguard redesign half_empty.pptx --out filled.pptx \
  --brief "Q3 update on the predictive-maintenance rollout"

# 3. No deck at all -- build one from nothing, like asking a designer
#    for a deck on a topic
deckguard redesign --out from_scratch.pptx \
  --brief "A short deck on predictive maintenance for facilities managers" \
  --slides 8

# -> wrote: redesigned.pptx
#    9 slide(s) using layouts: Cover B, Section divider (just title), ...
#    (a table with the skipped-slides list, if any)
#    tokens: 8420 in / 3110 out — est. cost $0.120 (claude-opus-5)
```

**What's deterministic and what's AI-judged is a hard line, not a
blur, in every one of those three modes.** Content extraction reuses
`retemplate.py`'s own shape-safety rules (a table, chart, embedded
object, media, or grouped shape is never sent to the model, brief or
no brief — skipped and reported, same as `retemplate`), but applies
`redesign`'s own, more permissive text/image caps on top — see below
for why those caps are shaped differently from `retemplate`'s. The
model makes exactly two kinds of judgment call, kept explicitly
separate in its instructions:

- For a slide **with real source content**: which `kind`
  (cover/agenda/section/content/quote/statement/stat/timeline/end/
  blank) it should become — and nothing about the wording itself.
  Content is carried over **verbatim**: no rewording, no condensing,
  no inventing facts, numbers, or claims not already on that slide. If
  a source slide has more text than any single layout can hold, the
  model splits it across multiple output slides (all tagged with that
  same source slide) rather than dropping or paraphrasing anything —
  see "Dense, hand-built slides are split, not condensed or skipped"
  below.
- For a **blank slide, or a bare brief with no slide behind it at
  all**: the opposite rule — there's nothing to preserve, so the model
  is instructed to write real, specific content grounded in the brief
  (never vague filler, never a fabricated number where the brief didn't
  give one).

A blank slide is genuinely blank (no title, text, or images at all) —
distinguishable by `retemplate.EMPTY_SLIDE_REASON` from every other
skip reason, which stays a hard skip regardless of a brief.

**Dense, hand-built slides are split, not condensed or skipped, no
matter how many text boxes they were built from.** `retemplate` caps a
slide at 3 separate text boxes because it carries content over
*verbatim* onto exactly ONE new slide — a real ceiling, since no
layout offers more than 3 body placeholders. `redesign` also carries
content over verbatim (on explicit direction: it never rewords or
condenses a source slide's own text, full stop), but isn't confined to
one output slide for it — a slide with more text than any layout holds
gets split across as many output slides as it takes (typically 2-3),
all sharing that slide's `source_slide_index`, rather than losing or
paraphrasing anything. What redesign caps instead is total text
*volume* (`REDESIGN_MAX_TEXT_CHARS`, generously) — a sanity ceiling
against a pathological/corrupted file (an unbounded split is still a
real cost), not a second-guess of an ordinary dense slide. The rules
that DO stay hard skips regardless — a table, chart, embedded object,
media, or grouped shape — are exactly the ones no amount of relayout
can safely reinterpret; a brief never overrides them.

**Images are carried over, not just text.** The model is never shown
the actual pixels — its outline schema doesn't have an `images`
field, only an `image_count` — so which images survive is decided
deterministically, not by the model: each output slide gets its own
source slide's images (up to `REDESIGN_IMAGES_PER_SLIDE`, capped to
what the org template's picture-carrying layouts actually support)
attached back in after the model call, keyed by `source_slide_index`.
This closes a real gap: earlier versions dropped every image from
every redesigned slide silently, since nothing downstream had a path
to carry raw image bytes into a layout's picture placeholder at all —
`compose.py`'s content-layout candidates now include the org
template's picture-carrying layouts (e.g. "Two pictures and text B"),
and `SlideSpec.images` accepts raw bytes as well as file paths.

Either way, the model's output is validated against a JSON schema
shaped exactly like `create`'s own outline format (see
`compose.outline_from_list`), so a human-written YAML outline, a
redesigned deck, and a from-scratch AI-authored one are
indistinguishable from that point on — all three run through the
identical `build_deck` — same layout selection, same final `fix_deck`
brand-compliance pass. Nothing about color, font, or layout-approval
judgment is ever delegated to the model, in any mode.

Options: `--brief` (topic/description — required if you omit DECK,
also fills any blank slides in a DECK you do give it), `--slides`
(target total slide count; omit it and Claude judges an appropriate
length from the brief's scope), `--model` (default `claude-opus-5`;
pass `claude-sonnet-5` for a cheaper run), `--effort`
(`low`/`medium`/`high`/`xhigh`/`max`, default `high`), `--notes`
(free-text steering appended to the model's instructions, e.g.
`--notes "prefer stat slides for anything with a percentage"` — the
way to tune behavior without touching code), and the same
`--template`/`--rules` options `create` takes.

**Cost.** Each run prints the API's real `usage` token counts and a
rough estimate (`Usage.estimated_cost_usd` in `redesign.py`, using the
per-model pricing cached there — verify against
platform.claude.com/docs/en/pricing before trusting it for billing). A
whole-deck redesign is one batched API call, not one per slide, so a
50-slide deck typically lands well under $2 even at `claude-opus-5`
pricing; a handful of slides for iterating on `--notes` costs a small
fraction of that. `anthropic` is a base dependency (see
`requirements.txt`), but nothing about `redesign` runs, and no key is
ever required, unless you explicitly set `ANTHROPIC_API_KEY` — every
other command in this tool remains fully API-key-free.

**On the hosted web app**, the "Redesign a deck" form's AI rewrite
option only appears/works when the server itself has
`ANTHROPIC_API_KEY` set — it's the one path in `web.py` that spends
real money per request, so it's opt-in per deployment rather than on
by default, and it never accepts a client-supplied key. Brand mode
(below) needs no key and is always available, key or no key. **If you
enable AI rewrite on a public deployment, also set
`DECKGUARD_WEB_PASSWORD`** — an open, unauthenticated route that spends
API budget per request would let anyone run up your bill.

### `--mode brand`: same command, no AI, no wording changes

```bash
# No ANTHROPIC_API_KEY needed at all
deckguard redesign old_deck.pptx --out rebranded.pptx --mode brand

# -> wrote: rebranded.pptx
#    4 slide(s) using layouts: Cover B, Text and picture A, Two content B, Outro
#    (a table with the skipped-slides list, if any)
#    mode: brand — fully deterministic, no API call made
```

This is what to reach for when a deck's *wording* is already fine and
the only real problem is that it isn't built on approved layouts,
colors, or fonts — the same category of fix `retemplate` + `fix`
already cover separately, done here as one pass with two things
neither of those alone does:

- **A confidently-detected cover/closing slide is swapped onto the
  current brand `Cover B`/`Outro` layout**, not just recolored in
  place — its own image (if it has one) carries into that layout's own
  picture placeholder, a normal, independently editable placeholder in
  the output file, so replacing the picture afterward in PowerPoint
  works exactly like it would on any other placeholder picture. Only
  ever applied to slide 1 / the last slide, and only when it's
  genuinely sparse (a title and at most one short supporting line) —
  busier slides are real content and are never guessed at.
- **Layout choice is picked for visual variety**, not just the single
  tightest fit `retemplate` alone would always pick — `match_layout`'s
  `usage_counts` tie-break spreads similarly-shaped slides across the
  equally-good candidate layouts instead of stamping one layout out
  slide after slide. It only ever breaks a TIE between equally good
  fits; it can never push a slide onto a layout that fits it worse.

Every eligible slide's title/body text/images are carried over
**verbatim** — the exact same eligibility rules `retemplate` already
uses (a slide's text has to fit within the real per-placeholder cap a
layout offers, since nothing here condenses; a table, chart, embedded
object, media, or grouped shape is still a hard skip). This is
deliberately much stricter than `--mode rewrite`'s eligibility, which
tolerates far more text because it's allowed to condense it — brand
mode never does, so a dense hand-built slide that `--mode rewrite`
would happily condense stays a hard skip here, reported the same way.
Color/font brand compliance is finished by running the same `fix_deck`
engine `deckguard fix` uses over the whole result before returning.

### `--review`: one small, optional AI call on top of `--mode brand`

```bash
export ANTHROPIC_API_KEY=sk-...   # only --review needs this; --mode brand alone doesn't

deckguard redesign old_deck.pptx --out rebranded.pptx --mode brand --review
```

Brand mode's own skip list can include a real, common case it has no
deterministic way to handle: a short divider/transition page (an
"Appendix", "Q&A", or "Thank You" break between sections) that happens
to be built with more decoration or shape complexity than retemplate's
own verbatim-carryover rules allow — correctly left alone, since
nothing in that hard-skip list is something a heuristic should guess
its way around.

`--review` adds exactly two narrowly-scoped judgment calls for this,
both looking only at slides `--mode brand` already left untouched
(never a rebuilt slide):

1. **Divider detection, the one thing it's allowed to actually fix.**
   "Does this read as a short divider page, and if so what should its
   title say" — for anything answered yes, it rebuilds that ONE slide
   onto the org template's own Section Divider layout with that title,
   taken verbatim from the slide's own text (never invented). Nothing
   else about the deck changes.
2. **Two more categories, flagged but never auto-applied:** unreplaced
   placeholder/template copy (e.g. "Lorem ipsum", "[bracketed
   placeholder]", "PRODUCT NAME") and a confidentiality/proprietary
   notice worded differently than plain "Confidential" (which a
   separate deterministic pass already removes on its own). These come
   back as plain-text findings (`RedesignResult.review_notes`, printed
   by the CLI) for a human to act on, not silently applied.

Nothing beyond those two categories is in scope — this is deliberately
not a second `--mode rewrite`, and the model is shown a text preview,
not a rendering, so its judgment is necessarily limited to what the
text itself reveals.

## Config reference (`brand_rules.yaml`)

```yaml
brand:
  name: "KONE"

colors:
  approved: ["#1450F5", "#FFFFFF", ...]   # the full approved palette
  remap:                                   # legacy hex -> correct hex
    "#005EB8": "#1450F5"                   # old KONE Blue -> new KONE Blue
  tolerance: 0                             # RGB distance for "near-miss" (minor) flags

fonts:
  approved: ["Inter", "Inter Semi Bold", "KONE Information"]
  remap: {"Calibri": "Inter", "Arial": "Inter", "Segoe UI": "Inter"}
  min_body_size_pt: 12
  min_title_size_pt: 24

typography_rules:
  alignment: {default: "left", exceptions: [...]}
  all_caps: {forbidden_fonts: [...], allowed_words: ["KONE"], required_fonts: [...]}
  text_colors: {"Inter": ["#141414", "#FFFFFF"], ...}   # list order matters: first = preferred
  text_effects: {forbidden: ["shadow", "glow", "reflection", "outline", "3d"]}
  role_restrictions:
    "KONE Information": {max_size_pt: 18, forbidden_roles: [...], allowed_roles: [...]}

logo:
  new_logo_path: "assets/kone_logo.png"
  old_logo_hashes: []      # populate via `deckguard hash-logo`, for an old logo that's a raster image
  old_logo_region_in: null # [left, top, width, height] in inches -- see below, for a non-raster old logo
  min_clear_space_px: 20   # Phase 2 (AI audit) — not checked by the XML engine

layout:
  slide_size: "16:9"
  forbidden_elements: ["wordart", "3d_effects"]

audit:
  fail_on: ["critical"]    # severities that make `audit` exit non-zero
```

`colors.approved`/`fonts.approved` are matched theme-aware and
normalization-aware:

- **Colors** exist as literal `srgbClr` values *and* as theme color
  references with a tint/shade (`lumMod`/`lumOff`) modifier layered on
  top. `deckguard` resolves theme+tint combinations to their effective
  RGB for matching, and — since a legacy theme color's tints are all
  derived from the same base — `fix` corrects the *theme* slot once
  rather than every shape that references it.
- **Fonts** are matched case-insensitively with hyphens/spaces
  stripped, and a bold `Inter` run is treated as `Inter Semi Bold`, so
  `"Inter Semi Bold"`, `"Inter-SemiBold"`, `"InterSemiBold"`, and
  `"Inter"` + bold all resolve to the same approved family. The theme's
  `fontScheme` (major/minor Latin typeface) is corrected the same way
  theme colors are, fixing every placeholder that inherits the default.

**`logo.old_logo_region_in`** exists for an old logo `old_logo_hashes`
can never match: one that isn't a raster image at all, e.g. a wordmark
drawn as vector shapes directly on a slide master (confirmed against a
real legacy deck — a group of freeform paths, not a picture). Set it to
`[left, top, width, height]` in inches and every top-level shape on a
slide master fully inside that box is deleted and replaced with
`new_logo_path`, sized to fit. To find the right numbers for your own
deck: open it in PowerPoint, click the logo mark on the slide master
(View → Slide Master), and read its position/size in inches from the
Format Shape pane (or the ruler) — pad each side by a few tenths of an
inch. Unset (`null`, the default) means this never runs: unlike a hash
match (which identifies *what* the old logo looks like before touching
anything), a region only identifies *where* something is, so deleting
shapes by position alone is only safe once a human has confirmed the
region against their own deck's master.

## Severity mapping

- **critical** — old logo present, old KONE Blue `#005EB8` (or a theme
  tint derived from it), a non-approved font used in a heading
- **major** — any other non-approved/off-brand color, an approved font
  used in a color its `text_colors` list doesn't allow, forbidden
  ALL CAPS usage, `KONE Information` used at heading/body sizes, forbidden
  text effects
- **minor** — alignment violations, sub-minimum text sizes, near-miss
  colors within `colors.tolerance`

Not every `major`/`critical` finding is auto-fixable — e.g. ALL CAPS
case is flagged but never rewritten (a case transform is a content edit
that can silently mangle acronyms), and an unapproved color with no
configured remap target has no deterministic "correct" replacement to
apply. Those always land in `manual_review`, never in `changes`.

## Learning brand rules from an example deck

`deckguard learn <old.pptx> <new.pptx>` compares an off-brand deck
against an already-on-brand reference deck and proposes
`colors.remap`/`fonts.remap` additions — the same workflow used by hand
throughout this project's development, now a repeatable feature. It
reasons only about *usage*, not shape identity or layout: a color/font
that disappears from the old deck while a new one appears at a similar
count is proposed as its replacement, scored by how closely those counts
correlate.

```bash
deckguard learn legacy_deck.pptx reference_deck.pptx
# -> proposal table: role, old hex, new hex, counts, confidence (high/low)

deckguard learn legacy_deck.pptx reference_deck.pptx --apply
# -> writes high-confidence proposals into brand_rules.yaml (preserving
#    its comments/formatting)

deckguard learn legacy_deck.pptx reference_deck.pptx --transform out.pptx
# -> ALSO rebuilds legacy_deck.pptx itself: same engine `redesign --mode
#    brand` uses, so it lands on the org template's own approved layouts
#    (cover/content/end alike), its own wording and images carried over
#    verbatim, with the just-learned colors/fonts applied on top. Add
#    --review for the one small AI pass (needs ANTHROPIC_API_KEY) that
#    also catches a leftover divider slide or placeholder/confidentiality
#    text -- same --review as `redesign --mode brand`.
```

Low-confidence proposals are never auto-applied to `--apply`/the config
file — re-run with `--min-confidence low` once you've manually confirmed
one is correct (this also affects which proposals `--transform` uses).
The web app's "Learn from a reference" form does the full pipeline in
one step: upload both decks and you get back the old deck rebuilt onto
the org's approved layouts with the learned colors/fonts applied, plus
the updated `brand_rules.yaml` to download (the *server's* config is
never mutated by a web request — proposals are applied to a scratch
copy). AI review runs automatically there whenever the server has an
`ANTHROPIC_API_KEY` configured.

The *proposal* step (plain `learn`, no `--transform`) only ever reasons
about color/font *usage counts* — it doesn't try to match individual
shapes between the old and new deck. `--transform`'s layout rebuild
comes from the same deterministic `retemplate`/`redesign --mode brand`
matching every other command in this project uses, not from anything
learned by comparing the two input decks' structure.

## Worked example

```bash
$ deckguard audit legacy_deck.pptx
                              legacy_deck.pptx
┏━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃ Slide ┃ Severity ┃ Rule         ┃ Shape   ┃ Message                 ┃ Fix? ┃
┡━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━┩
│ 1     │ critical │ legacy_color │ Title 1 │ legacy color #005EB8   │ yes  │
│       │          │              │         │ should be remapped to  │      │
│       │          │              │         │ #1450F5                │      │
│ 1     │ critical │ unapproved_… │ Title 1 │ font 'Calibri' is not  │ yes  │
│       │          │              │         │ approved (heading)     │      │
└───────┴──────────┴──────────────┴─────────┴─────────────────────────┴──────┘

$ deckguard fix legacy_deck.pptx --out ./fixed
wrote: fixed/legacy_deck_fixed.pptx
5 changes applied, 1 need manual review

$ deckguard audit fixed/legacy_deck_fixed.pptx
# 2 critical violations resolved; slide-size mismatch remains (not
# auto-fixed — resizing/repositioning content is out of Phase 1 scope).
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

The test suite (`tests/`) builds every fixture `.pptx` in-memory with
`python-pptx` (see `tests/helpers.py`) rather than shipping binary
fixture files, covering: font-name-variant matching, theme-color/tint
remap, effects add/detect/remove, logo phash matching + replacement,
severity mapping per rule, the non-destructive guarantee (source file
byte-for-byte unchanged after `fix`), `--dry-run` correctness, and
(`test_web.py`) the web app's upload/audit/fix/download flow, error
handling, download path-traversal guarding, and the password gate — via
FastAPI's `TestClient`, no server process needed. `test_redesign.py`
covers `redesign` the same way every other test does — no real network
or API calls — by injecting a fake Anthropic-shaped client (any object
exposing `.messages.stream(...)`) so the extraction/prompt/parsing
logic is fully exercised offline.

## Known Phase 1 limitations

- A text run with no explicit font override (inheriting from its
  placeholder/layout/master) is not checked against `fonts.approved`
  per-run — only the theme's default font is corrected. Resolving the
  full placeholder → layout → master → theme inheritance chain per run
  is deferred rather than guessed at.
- `layout.forbidden_elements` detects WordArt-style text warps
  deterministically; `min_clear_space_px` (logo clear space) and layout
  "consistency" are visual-judgment checks reserved for the Phase 2 AI
  audit layer.
- Chart data, SmartArt, OLE objects, and deeply nested/complex groups are
  detected and left untouched rather than risked.
