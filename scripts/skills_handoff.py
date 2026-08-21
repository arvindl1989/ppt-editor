"""Package the tool's DECK-MAKING APPROACH for Claude Skills.

Different ask from `design_handoff.py`, which asks a designer what the
slides should say. This one asks: the machinery that turns a brief into
a deck has grown two of several things it should have one of, and the
seams show. Where should it be cut?

Run:  python scripts/skills_handoff.py [outdir]
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from deckguard import brandmode as bm

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# the audit that the whole handoff hangs on
# --------------------------------------------------------------------------


def type_audit() -> dict:
    """Every region, and whether its type comes from the brand or is
    baked into the archetype."""
    from deckguard.registry import _load_archetypes

    archetypes = _load_archetypes()
    rows, baked, role_based = [], 0, 0
    for name, spec in sorted(archetypes.ARCHETYPES.items()):
        if not isinstance(spec, dict):
            continue
        regions = [(r, None) for r in spec.get("regions") or []]
        for group in spec.get("groups") or []:
            regions += [(r, group.get("content")) for r in group.get("regions") or []]
        for region, group in regions:
            key = region.get("content")
            if not key:
                continue
            block = region.get("dg")
            if not block:
                role_based += 1
                continue
            baked += 1
            brand = bm.TYPE_SCALE.get(key)
            disagrees = bool(brand) and (
                abs(brand[1] - (block.get("px") or 0)) > 2
                or brand[0] != block.get("font")
                or brand[6] != block.get("caps"))
            rows.append({
                "archetype": name,
                "slot": (f"{group}.{key}" if group else key),
                "baked": {"px": block.get("px"), "font": block.get("font"),
                          "caps": block.get("caps"), "color": block.get("color")},
                "brand_for_that_slot_name": (
                    {"px": brand[1], "font": brand[0], "caps": brand[6]}
                    if brand else None),
                "disagrees": disagrees,
            })
    return {
        "generated": date.today().isoformat(),
        "regions_with_baked_type": baked,
        "regions_resolved_through_a_role": role_based,
        "percent_bypassing_brand_mode": round(baked * 100 / (baked + role_based)),
        "disagreements": sum(1 for r in rows if r["disagrees"]),
        "rows": rows,
    }


def divider_evidence() -> dict:
    """The slide the report came in about, measured."""
    from deckguard import contracts as C
    from deckguard.registry import _load_archetypes

    spec = _load_archetypes().ARCHETYPES["divider_numbering"]
    contract = C.for_archetype("divider_numbering", "internal")
    return {
        "spec_says": ("INTERNAL_25.md 05: 300px blue numeral at left:38 top:150. "
                      "Section label and 56px title at x:620."),
        "contract_says": contract.describe() if contract else "",
        "renders_as": [
            {"slot": r.get("content"), "box": [round(v) for v in r["box"]],
             "type": r.get("dg")}
            for r in spec["regions"]
        ],
    }


def measure(page: Path) -> dict:
    """Read the ink off a render.

    Declared type sizes are a claim; this is what the slide actually
    puts on the page. Every number in DIVIDER.md that describes what a
    reader sees comes from here, not from the spec.
    """
    try:
        from PIL import Image
    except ImportError:
        return {}
    if not page.is_file():
        return {}

    im = Image.open(page).convert("RGB")
    width, height = im.size
    px = im.load()
    field = px[5, 5]

    def inked(x: int, y: int) -> bool:
        r, g, b = px[x, y]
        return (abs(r - field[0]) + abs(g - field[1])
                + abs(b - field[2])) > 60

    # The right-hand column starts after the numeral's box. Scanning the
    # two columns separately is what separates the eyebrow from the
    # title -- they are 26px apart and would merge in a full-width scan.
    def band(x0: int, x1: int) -> list:
        runs, start = [], None
        for y in range(120, height - 5):
            hit = any(inked(x, y) for x in range(x0, x1))
            if hit and start is None:
                start = y
            if not hit and start is not None:
                xs = [x for x in range(x0, x1)
                      for yy in range(start, y) if inked(x, yy)]
                runs.append({"top": start, "bottom": y - 1, "ink_height": y - start,
                             "left": min(xs), "right": max(xs)})
                start = None
        return runs

    return {"canvas": [width, height], "field": "#%02X%02X%02X" % field,
            "numeral_column": band(0, 440), "text_column": band(440, width - 12)}


def pipeline() -> dict:
    """Where a deck's decisions are actually made, in order."""
    return {
        "1_input": {
            "where": "deckguard/web.py :: generate",
            "reads": ["brief", "stop (the deviation meter)", "sections", "picks",
                      "an uploaded .pptx"],
        },
        "2_plan": {
            "where": "deckguard/assemble.py :: plan / _from_brief",
            "does": ("Builds the instruction, filters the menu to the meter's "
                     "stop, and calls the model once. The model chooses the "
                     "archetypes AND writes the copy in the same pass."),
            "known_weakness": ("One call does two jobs. Structure gets decided "
                               "as a side effect of writing copy, which is the "
                               "mechanical cause of layout repetition."),
        },
        "3_build": {
            "where": "deckguard/layouts.py :: build_deck / render",
            "does": ("Prepends the four-pane cut cover, draws each archetype "
                     "onto its own master layout, stamps chrome, keeps the "
                     "master's Thank you."),
        },
        "4_check": {
            "where": "deckguard/assemble.py :: preflight",
            "checks": ["type outside black/white/KONE Blue",
                       "a dash standing in for a bullet",
                       "content below the floor at y=629",
                       "overlapping text",
                       "more than one logo"],
        },
    }


# --------------------------------------------------------------------------
# renders
# --------------------------------------------------------------------------


def render_dividers(out_dir: Path) -> int:
    """The divider at each field colour, plus a whole worked deck."""
    for tool in ("soffice", "pdftoppm"):
        if shutil.which(tool) is None:
            print(f"  (skipping renders: {tool} not on PATH)")
            return 0

    from deckguard import assemble

    out_dir.mkdir(parents=True, exist_ok=True)
    slides = [
        {"archetype": "divider_numbering", "number": f"0{n}",
         "eyebrow": label, "title": title, "colour": colour}
        for n, (label, title, colour) in enumerate(
            [("Scope", "What you set up", "blue"),
             ("Boundaries", "What sits outside scope", "pink"),
             ("Timing", "Dates and owners", "light-blue"),
             ("Practicalities", "How assets reach you", "mint")], start=1)
    ]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        deck = work / "dividers.pptx"
        assemble.build({"title": "Dividers", "date": "21 August 2026",
                        "audience": "internal", "slides": slides}, str(deck))
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
                        "--outdir", str(work), str(deck)],
                       check=True, capture_output=True, timeout=900)
        subprocess.run(["pdftoppm", "-jpeg", "-jpegopt", "quality=92", "-r", "96",
                        str(work / "dividers.pdf"), str(work / "d")],
                       check=True, capture_output=True, timeout=900)
        pages = sorted(work.glob("d-*.jpg"))
        for index, page in enumerate(pages[1:-1], start=1):
            shutil.copyfile(page, out_dir / f"divider-{index}.jpg")
        shutil.copyfile(deck, out_dir / "dividers.pptx")
        return len(pages) - 2


# --------------------------------------------------------------------------
# the documents
# --------------------------------------------------------------------------


README = """# deckguard — how it makes a deck, and where that is wrong

## The ask

The report was "the fonts and everything on the divider slide looks
whack". It is true, and the cause is not the divider. **The tool has two
type systems and the wrong one wins.**

Read `TYPE_SYSTEM.md` first; it is the whole handoff. `DIVIDER.md` is the
worked example. `PIPELINE.md` says where a deck's decisions get made, so
a fix can be put in the right place.

    TYPE_SYSTEM.md     two type systems, and which one wins
    DIVIDER.md         the reported slide, measured against its own spec
    PIPELINE.md        where each decision is made, in order
    OPEN_QUESTIONS.md  what I could not decide alone
    type-audit.json    every baked region, machine-readable
    contracts.json     what each archetype needs
    meter.json         the deviation meter's tiers
    renders/           the divider on all four fields, and the .pptx

## What the tool is

One page, one button. A brief, a set of picked slides, an uploaded
.pptx, or any combination, becomes a finished KONE deck plus an editable
list of what it built. Slides are drawn with python-pptx onto KONE's own
master. There are 39 built archetypes across two curated sets of 25.

Three layers were added recently and they work:

- **`brandmode.py`** — the brand as data. 42 type roles, the colour
  palette, the vertical rhythm, which slides take a footer.
- **`contracts.py`** — what each archetype NEEDS before it is worth
  choosing, with cardinality. `gaps()` holds the contracts and the
  renderer to each other in both directions and is currently at zero.
- **`meter.py`** — one control, four stops, filtering which layouts are
  eligible. The filter is the enforcement: the planner cannot choose a
  layout it was never shown.

The problem is underneath all three.
"""


# The counts are substituted from `type_audit()` at generation time, so the
# prose and `type-audit.json` cannot drift apart. Plain `.replace`, not
# `.format`: the document is full of literal braces and percent signs.
TYPE_SYSTEM = """# Two type systems, and the wrong one wins

## The measurement

    [[baked]] regions carry a BAKED type block
    [[role_based]] regions resolve through a brand role
    [[percent]]% of the library bypasses BRAND_MODE entirely
    [[disagreements]] of the [[baked]] disagree with the brand for a slot of that name

A region either says

    {"role": "title", "box": [...]}                       <- resolved

or

    {"role": "dg_text", "box": [...],
     "dg": {"px": 46, "font": "Inter", "caps": false}}    <- baked

The second form came from porting an HTML archetype gallery: the parser
read the RENDERED type off each element and wrote it down. That was the
right thing to do at the time -- it is how the layouts got built at all
-- but it means those [[baked]] regions are immune to the brand. Change
`TYPE_SCALE` and they do not move. Add a role and they cannot use it.

## Why it shows on the divider first

`divider_numbering` is baked in all three of its slots, and all three
are wrong:

| slot | baked | the brand says | the spec says |
| --- | --- | --- | --- |
| `number` | 190px Inter | — | 300px |
| `eyebrow` | 13px Inter, sentence case | 12px KONE Information, CAPS | "section label" |
| `title` | 46px Inter | 32px Inter | 56px |

The eyebrow is the one that reads as broken: it is body copy where the
brand wants a small-caps label, so a section marker looks like a stray
sentence above the title.

## The subtlety that makes this non-trivial

A slot's NAME does not determine its role. `number` on a divider is a
300px display numeral; `number` in `numbered_icon_row_6` is a 28px blue
figure. Both are called `number`. So "look the slot name up in
TYPE_SCALE" is wrong, and that is presumably why the baked blocks were
kept.

The pair `(archetype, slot)` does determine it. That is exactly what
`contracts.py` already knows -- the external contracts name a role per
slot:

    DIVIDER_NUMBERING | number:display · eyebrow:body · title:display

Note that this line is also wrong: `eyebrow:body` is what put body copy
in the eyebrow. The handoff table has the same bug the renderer has.

## What I think should happen, and want challenged

1. **The contract names the role; the region stops carrying type.**
   Delete every `dg` block and resolve `(archetype, slot) -> role ->
   TYPE_SCALE` at draw time. One system.
2. **The contracts need a display tier.** `display` is 44px in the
   scale; the divider wants 300px for its numeral and 56px for its
   title. Either add roles (`divider_numeral`, `divider_title`) or let a
   contract override a size, which reopens the same hole.
3. **The 25 disagreements are a migration, not a rewrite.** They are
   listed in `type-audit.json` with both values, so each can be decided
   rather than guessed.

The risk is real: [[baked]] regions were measured off renders that
looked right. Resolving them through the brand will change
[[disagreements]] slides, and some of those changes will be worse before
they are better. A staged migration with the renders in front of you is
the only honest way to do it.
"""


PIPELINE = """# Where a deck's decisions are made

In order, with the file that owns each.

## 1 · Input — `web.py :: generate`

Reads the brief, the meter's stop, the ticked sections, any picked
slides, and an uploaded .pptx. The stop decides the audience; there is
no separate audience control.

## 2 · Plan — `assemble.py :: plan` / `_from_brief`

Builds the instruction and calls the model ONCE. The menu is filtered to
the meter's stop, and every entry carries what the archetype needs:

    three_content — Three equal text columns. Three pillars, three phases.
        needs: title · items (3 × {heading, text})

**The known weakness.** That single call chooses the archetypes AND
writes the copy. Structure therefore gets decided as a side effect of
writing, and whatever the model has just written for is the cheapest
next choice — which is the mechanical cause of a deck reusing one
layout. The intended fix is two passes: extract typed material from the
brief with no layouts mentioned, then match material to contracts in
code and let the model only write copy. Neither pass is built.

## 3 · Build — `layouts.py :: build_deck` / `render`

Prepends the four-pane cut cover unless the spec names one, draws each
archetype onto its own master layout, stamps chrome, keeps the master's
"Thank you".

`render` is where the two type systems meet: a region with a `dg` block
is drawn from that block; a region with a role goes through the engine's
`ROLE_STYLE`, which `brandmode` now fully populates.

## 4 · Check — `assemble.py :: preflight`

Reads the built .pptx back and reports: type outside black/white/KONE
Blue, a dash standing in for a bullet, content below the floor at y=629,
overlapping text, more than one logo. It reports rather than blocks —
the file is always returned.

Preflight is the only thing in the pipeline that has caught its own
author, twice. It is worth strengthening rather than replacing.
"""


OPEN_QUESTIONS = """# What I could not decide alone

## 1. Do the baked type blocks go, or get blessed?

[[baked]] regions, [[percent]]% of the library. Removing them makes the brand
the single authority and changes [[disagreements]] slides. Keeping them
means `BRAND_MODE.md` is advisory for a third of the deck, which makes
the contract layer a half-truth.

## 2. How should a display size be expressed?

The divider wants a 300px numeral and a 56px title. `TYPE_SCALE` has
`display` at 44px. Options: more roles (`divider_numeral`,
`divider_title`, and what else?), a size override on the contract, or a
per-archetype scale factor. The first is verbose, the second reopens the
hole, the third is magic.

## 3. `eyebrow:body` in the handoff's own contract table

`EXTERNAL_25.md` types the divider's section label as `body`. That is
what put sentence-case body copy where a small-caps label belongs. Is
the table wrong, or is a divider's label genuinely not an eyebrow?

## 4. Is one model call defensible?

Splitting extraction from selection is the plan, and it doubles the
calls. With prompt caching the static guide is ~97% of the input and
identical every time, so the cost is close to flat — but it is two
places to go wrong instead of one. Worth it?

## 5. What should preflight refuse?

Today it reports everything and returns the file. Should anything be
fatal — type in an unapproved colour, say — or is a deck you can see the
faults in always better than no deck?
"""


DIVIDER_HEAD = """# The reported slide, measured

`renders/divider-2.jpg` is the slide the report came in about. What
follows is measured off that image, not read off the spec.

## What a reader sees

| | ink | declared | the spec asks for |
| --- | --- | --- | --- |
| numeral `02` | 210 x 142px, black | 190px Inter | **300px, KONE Blue** |
| eyebrow `Boundaries` | 11px x-height, sentence case | 13px Inter | a section label, uppercase |
| title | 45px cap height | 46px Inter | **56px** |

Four separate faults, and only one of them is a font size:

1. **The numeral is black.** The spec says KONE Blue and the contract
   calls it a display figure. Rendered in the same ink as the title, at
   142px of cap height against the title's 45px, it does not read as a
   section index -- it reads as a large dark shape the eye has to get
   past.
2. **The eyebrow is body copy.** 11px of x-height in sentence case is
   the same treatment a paragraph gets. The brand's label role is 12px
   KONE Information in caps. This is the one that reads as "whack": a
   section marker looking like a stray sentence.
3. **Nothing separates the eyebrow from the title.** 26px between the
   eyebrow's baseline and the title's cap, on a slide with 460px of
   empty field below them. The pair reads as one lump.
4. **The block rides high.** The ink spans y=258..400 on a 720px
   canvas; its centre is at 329 against a canvas centre of 360. Not
   enough to look deliberate, enough to look unplaced.

The numeral is NOT clipped, which is worth saying because it looks like
it might be -- its ink stops at y=400 inside a box that runs to y=510.
The flat edge under the `2` is the glyph.

## Where each number comes from

"""

def fill(document: str, audit: dict) -> str:
    """Substitute the live audit into a document's `[[name]]` slots.

    An unfilled slot is a typo in a token name and would ship as
    literal `[[baked]]` in prose someone is meant to act on, so it
    fails here instead.
    """
    for token, value in (
            ("baked", audit["regions_with_baked_type"]),
            ("role_based", audit["regions_resolved_through_a_role"]),
            ("percent", audit["percent_bypassing_brand_mode"]),
            ("disagreements", audit["disagreements"])):
        document = document.replace(f"[[{token}]]", str(value))
    if "[[" in document:
        raise ValueError(f"unfilled slot: {document[document.index('[['):][:40]}")
    return document


def main(argv: list) -> int:
    out = Path(argv[1]) if len(argv) > 1 else (
        ROOT / f"skills-handoff-{date.today().isoformat()}")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    audit = type_audit()
    (out / "README.md").write_text(fill(README, audit), encoding="utf-8")
    (out / "TYPE_SYSTEM.md").write_text(fill(TYPE_SYSTEM, audit), encoding="utf-8")
    (out / "PIPELINE.md").write_text(fill(PIPELINE, audit), encoding="utf-8")
    (out / "OPEN_QUESTIONS.md").write_text(fill(OPEN_QUESTIONS, audit),
                                           encoding="utf-8")

    (out / "type-audit.json").write_text(json.dumps(audit, indent=2))
    (out / "pipeline.json").write_text(json.dumps(pipeline(), indent=2))

    for name in ("meter.json",):
        source = ROOT / "src" / "deckguard" / "assets" / "kone-design" / name
        if source.is_file():
            shutil.copyfile(source, out / name)
    handoff = ROOT / "src" / "deckguard" / "assets" / "kone-design" / "handoff-25"
    if handoff.is_dir():
        shutil.copytree(handoff, out / "brand", dirs_exist_ok=True)

    try:
        from scripts.design_handoff import contracts_json  # noqa: F401
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "dh", ROOT / "scripts" / "design_handoff.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["dh"] = module
        spec.loader.exec_module(module)
        (out / "contracts.json").write_text(
            json.dumps(module.contracts_json(), indent=2, ensure_ascii=False))

    shots = render_dividers(out / "renders")

    # After the renders, because the document is measured off one of them.
    evidence = divider_evidence()
    evidence["measured_from_the_render"] = measure(out / "renders" / "divider-2.jpg")
    (out / "DIVIDER.md").write_text(
        DIVIDER_HEAD + "```json\n"
        + json.dumps(evidence, indent=2, ensure_ascii=False) + "\n```\n",
        encoding="utf-8")

    summary = {
        "generated": date.today().isoformat(),
        "regions_with_baked_type": audit["regions_with_baked_type"],
        "percent_bypassing_brand_mode": audit["percent_bypassing_brand_mode"],
        "disagreements": audit["disagreements"],
        "divider_renders": shots,
    }
    (out / "state.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    archive = shutil.make_archive(str(out), "zip", root_dir=out.parent,
                                  base_dir=out.name)
    print(f"\n{out}\n{archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
