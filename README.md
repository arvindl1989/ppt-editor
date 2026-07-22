# deckguard

`deckguard` is a Python tool that automates PowerPoint brand compliance for
KONE's Marketing Hub — available as a CLI and as a small hostable web app.
It has three capabilities:

- **`fix`** — auto-correct brand violations in a `.pptx` file
- **`audit`** — scan one deck or a folder of decks and report violations
- **`migrate`** — move an old-template deck onto a new template (**Phase 3,
  not yet implemented**)

## Architecture

- **Deterministic first, AI second.** Everything achievable with rules +
  `python-pptx` — color remap, font swap, logo replace, effects removal,
  size/alignment checks — is pure Python with zero API calls. This is all
  of what's implemented today (Phase 1). A later phase will add an
  Anthropic-API-backed visual audit layer for judgment calls (layout
  consistency, "used sparingly", clear-space) that XML analysis can't
  decide; `deckguard` runs fully today with **no API key required**.
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

Routes: `GET /` (upload form), `POST /audit`, `POST /fix`,
`GET /download/{token}/{filename}`, `GET /health`.

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
| `inspect <deck>` | Full structured inventory: shapes, fills, fonts (raw + normalized), sizes, alignment, images (with perceptual hash), effects, layout/master usage. The discovery tool for growing `brand_rules.yaml` from real decks. |
| `fix <deck>` | Applies deterministic corrections: color remap (fills, gradients, text, lines, theme), font remap (run + theme/master/layout level), logo replacement by image hash, forbidden text-effect removal, forced left-alignment. |
| `audit <deck\|folder>` | Reports violations (slide, element, rule, severity, auto-fixable). Folder mode writes a per-deck report plus a `summary.csv`. |
| `hash-logo <image>` | Prints an image's perceptual hash, for `logo.old_logo_hashes`. |
| `validate-rules [rules.yaml]` | Checks a brand config for syntax and semantic errors (hex format, remap targets in the approved list, logo file exists, etc). |
| `learn <old> <new>` | Compares an off-brand deck against an already-on-brand reference deck and proposes `colors.remap`/`fonts.remap` additions — see below. |
| `migrate <deck> --template <potx>` | Phase 3 stub — prints "not yet implemented". |

Every command takes `--rules path/to/brand_rules.yaml` (defaults to the
packaged KONE config). `fix` and `audit` also take `--out DIR` for where
reports/output land.

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
  old_logo_hashes: []      # populate via `deckguard hash-logo`
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
#    its comments/formatting), then re-run `fix` to apply them
```

Low-confidence proposals are never auto-applied — re-run with
`--min-confidence low` once you've manually confirmed one is correct.
The web app's "Make an old deck look like a reference deck" form does
this in one step: upload both decks, high-confidence differences are
applied automatically, and you get back the transformed deck plus the
updated `brand_rules.yaml` to download (the *server's* config is never
mutated by a web request — proposals are applied to a scratch copy).

This only handles color/font *styling*, not layout or structure — real
deck revisions rarely have 1:1-matching shape names/ids between old and
new versions, so no attempt is made to match or transplant individual
shapes.

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
FastAPI's `TestClient`, no server process needed.

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
