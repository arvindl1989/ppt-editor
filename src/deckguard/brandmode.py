"""The KONE brand mode: role -> type, and the rules that override the box.

`BRAND_MODE.md` in `assets/kone-design/handoff-25/` is the source; this is
that document in the form the renderer consumes. It exists because 223 of
the tool's 293 regions carried no type block at all -- their size, weight
and colour were inferred from a role name at draw time, which is why a
short quote came out at paragraph size in a 657px panel.

Nothing here is inferred from a box size. The four roles that legitimately
change with their container say so, and `resolve` is the only place that
decision is made.
"""

from __future__ import annotations

from typing import Optional

BLACK = "141414"
WHITE = "FFFFFF"
BLUE = "1450F5"

# Fields. Yellow and mint are blocks inside a layout, never a slide field.
# Two sands were in circulation -- `F3EEE6` here and `F3EEEA` in the
# layout tables -- and both shipped, on adjacent slides of the same deck.
# The real KONE deck measures `F3EEEA`, so that is the one.
SAND = "F3EEEA"
LIGHT_BLUE = "D2F5FF"
PINK = "FFCDD7"
MINT = "AAE1C8"
YELLOW = "FFE141"
SECONDARY_FIELDS = frozenset({SAND, LIGHT_BLUE, PINK})
BLOCK_ONLY = frozenset({MINT, YELLOW})

# Chart series only -- never a background.
TINTS = ("1450F5", "4373F7", "7296F9", "A1B9FB", "D0DCFD")

INTER = "Inter"
KONE_INFO = "KONE Information"

# role -> (font, px, weight, leading, tracking, colour, caps)
TYPE_SCALE: dict[str, tuple] = {
    # Inter -- sentence case always, black or white, never blue, never grey.
    # The four display roles come from README's as-built table rather than
    # from BRAND_MODE's role table: README states they are measured from
    # the built decks, and BRAND_MODE's numbers for them (44 for a cover
    # title against a measured 76) read as conservative defaults rather
    # than measurements. Everything else below is BRAND_MODE's.
    "cover_title":       (INTER, 76, 400, 0.98, -0.03, BLACK, False),
    "outro_title":       (INTER, 120, 400, 0.95, -0.04, BLACK, False),
    "display":           (INTER, 44, 400, 1.08, -0.02, BLACK, False),
    "statement":         (INTER, 40, 400, 1.15, -0.015, BLACK, False),
    "title":             (INTER, 32, 400, 1.15, -0.005, BLACK, False),
    "title_narrow":      (INTER, 28, 400, 1.15, -0.005, BLACK, False),
    "title_light":       (INTER, 32, 400, 1.15, -0.005, WHITE, False),
    "cover_title_light": (INTER, 76, 400, 0.98, -0.03, WHITE, False),
    "outro_title_light": (INTER, 120, 400, 0.95, -0.04, WHITE, False),
    "subtitle":          (INTER, 20, 400, 1.4, 0, BLACK, False),
    # The standfirst under a cover headline. Its own role because the
    # engine already ships a `subtitle` -- KONE Information 14, caps --
    # and an engine role wins over a brand one, so a cover's standfirst
    # came out as a line of small caps where the reference sets 20px
    # sentence case.
    "cover_context":     (INTER, 20, 400, 1.4, 0, BLACK, False),
    "cover_context_light": (INTER, 20, 400, 1.4, 0, WHITE, False),
    "heading":           (INTER, 19, 600, 1.25, 0, BLACK, False),
    "on_panel_heading":  (INTER, 19, 600, 1.25, 0, WHITE, False),
    "body":              (INTER, 16, 400, 1.5, 0, BLACK, False),
    "body_narrow":       (INTER, 15, 400, 1.45, 0, BLACK, False),
    "on_panel_body":     (INTER, 16, 400, 1.5, 0, WHITE, False),
    "bullets":           (INTER, 19, 400, 1.45, 0, BLACK, False),
    "caption":           (INTER, 14, 400, 1.4, 0, BLACK, False),
    "quote_lg":          (INTER, 30, 400, 1.3, -0.005, BLACK, False),
    "quote_sm":          (INTER, 24, 400, 1.3, -0.005, BLACK, False),
    "price":             (INTER, 34, 400, 1.1, -0.01, BLACK, False),
    # KONE Information -- ALL CAPS always. Blue, black or white.
    "eyebrow":           (KONE_INFO, 12, 400, 1.2, 0.08, BLUE, True),
    "eyebrow_light":     (KONE_INFO, 12, 400, 1.2, 0.08, WHITE, True),
    "label":             (KONE_INFO, 12, 400, 1.2, 0.06, BLUE, True),
    "stat_label":        (KONE_INFO, 12, 400, 1.2, 0.06, BLACK, True),
    "attribution":       (KONE_INFO, 12, 400, 1.3, 0.06, BLACK, True),
    "axis":              (KONE_INFO, 12, 400, 1.2, 0.06, BLUE, True),
    "footer":            (KONE_INFO, 11, 400, 1.0, 0.05, BLACK, True),
    "classification":    (KONE_INFO, 10, 400, 1.0, 0.05, BLACK, True),
    # KONE numbers -- figure blue, label black, so the blue reads as the
    # number rather than as the pair.
    # Size from README's as-built table; colour stays BRAND_MODE's. The
    # built decks describe both of these as blue ("280px blue figure",
    # "300px blue numeral") while BRAND_MODE's table sets them black and
    # says "black on every secondary field". Colour was not part of the
    # size ruling, and the table is the per-role authority -- flagged.
    "hero_value":        (INTER, 280, 400, 0.86, -0.04, BLACK, False),
    "stat_value":        (INTER, 64, 400, 1.0, -0.02, BLUE, False),
    "stat_value_md":     (INTER, 44, 400, 1.0, -0.02, BLUE, False),
    "number":            (INTER, 28, 400, 1.0, -0.01, BLUE, False),
    # `figure` is the name BRAND_MODE's table gives this, but it cannot
    # be used as a REGION role: `kone_engine` reads `role == "figure"`
    # as an image and draws a picture box, so a divider spec'd that way
    # renders the numeral as an empty placeholder. Region roles and type
    # roles share one namespace at draw time and this is the one word
    # they disagree about. `figure` stays as an alias for anything
    # already asking for it by that name.
    "section_numeral":       (INTER, 300, 400, 0.8, -0.04, BLACK, False),
    "section_numeral_light": (INTER, 300, 400, 0.8, -0.04, WHITE, False),
    "figure":            (INTER, 300, 400, 0.8, -0.04, BLACK, False),

    # A divider's title is not a slide title. BRAND_MODE's table says
    # "every slide title is 32 -- no exceptions", and that rule is about
    # CONTENT slides: both divider entries in the set specs ask for 56
    # (`DIVIDER_NUMBERING` and `IMAGE_SECTION_DIVIDER`), independently,
    # which is two witnesses for a distinct role rather than an
    # exception to `title`. Naming it is what keeps the 32 rule intact.
    "divider_title":       (INTER, 56, 400, 1.0, -0.025, BLACK, False),
    "divider_title_light": (INTER, 56, 400, 1.0, -0.025, WHITE, False),
}

# Role names that encode a rendering rather than an intent. `gal_i64_141414`
# means "Inter 64 black", which is an output, not a decision. Two of these
# are deliberately absent: `gal_i19_141414` reads as bullets OR heading
# depending on the slot, so it must be decided per slot rather than mapped.
RETIRED_ROLES: dict[str, str] = {
    "body_muted": "body",              # "muted" was the grey that got banned
    "gal_i64_141414": "hero_value",
    "gal_i43_141414": "stat_value_md",
    "gal_i15_141414": "body_narrow",
    "gal_i16_141414": "body",
    "gal_i64_FFFFFF": "stat_value",
    "gal_i19_FFFFFF": "on_panel_body",
    "gal_i34_FFFFFF": "title_light",
    "gal_k12_FFFFFF_c": "eyebrow_light",
}

# The roles that legitimately change with their container, and the widths
# they change at. Everything else is fixed regardless of its box.
NARROW_TITLE_MAX = 374
NARROW_BODY_MAX = 300
QUOTE_LARGE_MIN = 600

# Vertical rhythm. A block starts 32px below the block above it; a row of
# OBJECTS starts 69px below a title instead, because an object's top edge
# is hard and needs more air than a line of text does.
TITLE_BAND_BOTTOM = 195
GAP_TEXT = 32
GAP_OBJECTS = 69
CONTENT_START_TEXT = TITLE_BAND_BOTTOM + GAP_TEXT        # 227
CONTENT_START_OBJECTS = TITLE_BAND_BOTTOM + GAP_OBJECTS  # 264
SUBTITLE_BAND_BOTTOM = 232
FLOOR = 629          # nothing but chrome below this
FOOTER_Y = 658

# The tighter band, measured off a real KONE deck ("Life, upgraded in ONE
# week"). Its title sits at y=22 in 32px type and its first content row
# at y=118 -- 109px higher than the rhythm above, which is what lets a
# twelve-card grid breathe on one slide. The airier band stays as the
# spec's own numbers; this is what the layouts are shifted onto.
TIGHT_TITLE_Y = 22
TIGHT_TITLE_H = 82
TIGHT_CONTENT_Y = 118

# Cards. The reference sets its grid in white rounded rectangles on
# sand, each with a soft shadow, a coloured rule under a caps label, and
# a small arrow glyph in the corner. Radius is 13px measured off a 176px
# card (PowerPoint stores it as a fraction of the short side, 0.0717).
CARD_RADIUS_PX = 13
CARD_SHADOW = {"blur": 18, "distance": 3, "direction": 90.0, "alpha": 0.10}
CARD_FILL = WHITE
CARD_RULE_H = 1
CARD_LABEL_Y = 12          # caps label inside the card, above the rule
CARD_RULE_Y = 38           # the coloured rule, full card width
CARD_BODY_Y = 52

# The grid the reference uses: four columns on a 300px pitch, three rows
# on a 193px pitch, 288x176 cards. A card may span two columns and two
# rows; nothing else in the grid moves when it does.
CARD_COL_X = (45, 346, 646, 946)
CARD_ROW_Y = (118, 311, 505)
CARD_W = 288
CARD_H = 176

# Accents a card's rule may take, in the order a grid cycles them. The
# LABEL is never set in these -- at 12px on white, mint and pale blue are
# barely legible, and the reference deck shows it. The rule carries the
# colour; the label stays blue or black.
CARD_ACCENTS = (BLUE, BLACK, MINT, PINK, LIGHT_BLUE)

# Chrome, owned by the layout. An archetype declares what it needs and
# draws nothing.
LOGO_LEFT = (45, 45)
LOGO_RIGHT_EDGE = 1235
FOOTER_DATE_X = 45
FOOTER_PAGE_X = 1167
CLASSIFICATION_Y = 640
NO_FOOTER = frozenset({"cover", "divider", "outro", "fullslide_picture", "blank"})

# Photo protection. Only where type sits ON the photograph -- a cover that
# puts its title on white gets none.
SCRIM_BOTTOM_UP = ((0.45, 0.0), (1.0, 0.72))
SCRIM_LEFT_RIGHT = ((0.0, 0.78), (0.55, 0.0))


def canonical(role: str) -> str:
    """The role a retired name reads back to."""
    return RETIRED_ROLES.get(role, role)


def resolve(
    role: str,
    *,
    width: Optional[float] = None,
    on_dark: bool = False,
) -> Optional[dict]:
    """The type block for a role, or None if the role carries no type.

    `width` is the region's own width and is consulted only for the four
    roles that say they change with it. `on_dark` swaps a role for its
    light twin -- type on blue, black or a scrimmed photograph.
    """
    role = canonical(role)

    if role == "title" and width is not None and width <= NARROW_TITLE_MAX:
        role = "title_narrow"
    elif role == "body" and width is not None and width <= NARROW_BODY_MAX:
        role = "body_narrow"
    elif role in ("quote", "quote_lg", "quote_sm"):
        # The one place a box legitimately changes the type: a quote sizes
        # to its panel rather than to `body`.
        role = "quote_lg" if width is None or width >= QUOTE_LARGE_MIN else "quote_sm"

    if on_dark:
        role = _ON_DARK.get(role, role)

    entry = TYPE_SCALE.get(role)
    if entry is None:
        return None
    font, px, weight, lead, track, colour, caps = entry
    return {
        "kind": "text", "role": role, "font": font, "px": px, "weight": weight,
        "lead": lead, "track": track, "color": colour, "caps": caps, "align": "l",
    }


_ON_DARK = {
    "cover_title": "cover_title_light",
    "outro_title": "outro_title_light",
    "title": "title_light",
    "title_narrow": "title_light",
    "heading": "on_panel_heading",
    "body": "on_panel_body",
    "body_narrow": "on_panel_body",
    "eyebrow": "eyebrow_light",
    "section_numeral": "section_numeral_light",
    "divider_title": "divider_title_light",
}


def content_start(*, has_subtitle: bool = False, objects: bool = False) -> int:
    """Where content begins under the title band.

    Both numbers `LAYOUTS.md` shows come out of one rule, which is why
    neither is the standard on its own.
    """
    if has_subtitle:
        return SUBTITLE_BAND_BOTTOM + GAP_TEXT
    return CONTENT_START_OBJECTS if objects else CONTENT_START_TEXT


# --------------------------------------------------------------------------
# the two curated sets
# --------------------------------------------------------------------------

import json
import re
from functools import lru_cache
from pathlib import Path


def handoff_dir() -> Path:
    return Path(__file__).parent / "assets" / "kone-design" / "handoff-25"


@lru_cache(maxsize=1)
def slide_sets() -> dict:
    """The internal and external 25s, as Design defined them.

    Read from `slide-sets.json` rather than transcribed, so the sets
    cannot drift from the handoff they came from.
    """
    return json.loads((handoff_dir() / "slide-sets.json").read_text())["sets"]


def set_names() -> list[str]:
    return sorted(slide_sets())


def slides_in(audience: str) -> list[dict]:
    """The 25 slides of a set, in deck order, each carrying its group,
    field, footer flag and on-field type colour."""
    entry = slide_sets().get(audience)
    if entry is None:
        raise KeyError(f"no such set: {audience!r} (have {', '.join(set_names())})")
    out = []
    for group in entry["groups"]:
        for slide in group["slides"]:
            out.append({**slide, "group": group["name"],
                        "archetype": slide["archetype"].lower()})
    return sorted(out, key=lambda s: s["n"])


def canonical_archetypes() -> set:
    """Every archetype either set uses -- the library the builder offers."""
    return {s["archetype"] for name in set_names() for s in slides_in(name)}


def shared_archetypes() -> set:
    """The six that serve both sets: built once, field parameterised."""
    sets = [{s["archetype"] for s in slides_in(n)} for n in set_names()]
    return set.intersection(*sets) if sets else set()


# --------------------------------------------------------------------------
# which chrome a slide gets
# --------------------------------------------------------------------------

# An archetype's KIND decides its chrome, not its name. Covers, dividers
# and the outro carry the logo top-left and no footer; everything else
# carries the logo top-right, a date and a page number.
_COVER = ("cover_", "intro")
_DIVIDER = ("divider_", "image_section_divider", "section_divider")
_NO_CHROME = ("outro", "end_logo", "thank_you", "fullslide_picture", "blank")


def slide_kind(archetype: str) -> str:
    name = (archetype or "").lower()
    if name.startswith(_NO_CHROME) or name in _NO_CHROME:
        return "outro" if "outro" in name or "thank" in name else "bare"
    if name.startswith(_COVER):
        return "cover"
    if name.startswith(_DIVIDER) or "divider" in name:
        return "divider"
    return "content"


def wants_footer(archetype: str) -> bool:
    """Footer chrome on every slide except covers, dividers, the outro,
    a full-bleed picture and a blank. Missing from every generated body
    slide until it was moved here -- an archetype was expected to draw
    its own, and none of them did."""
    return slide_kind(archetype) == "content"


def logo_on_left(archetype: str) -> bool:
    return slide_kind(archetype) in ("cover", "divider", "outro")


# --------------------------------------------------------------------------
# what each slide is FOR
# --------------------------------------------------------------------------

# A planner given a bare list of 25 archetype names cannot choose between
# `matrix_2x2` and `segment_breakdown` on merit, because a name is not a
# reason. It falls back to the order it was given, which is why briefs
# came out using the same first handful every time. These are the job
# descriptions the handoff already carries: EXTERNAL_25's own `job`
# column, and the purpose column of README's internal table.
# re.M matters: without it `^` anchors to the start of the whole
# document and matches exactly nothing in a table.
_JOB_ROW = re.compile(
    r"^\|\s*\d+\s*\|\s*`([A-Z_0-9]+)`\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", re.M)


@lru_cache(maxsize=1)
def jobs() -> dict:
    """archetype -> what it is for, per audience."""
    out: dict = {"external": {}, "internal": {}}
    external = (handoff_dir() / "EXTERNAL_25.md").read_text()
    for name, job, _contract in _JOB_ROW.findall(external):
        out["external"].setdefault(name.lower(), job)
    # README's internal table is `| n | ARCHETYPE | purpose | treatment |`
    readme = (handoff_dir() / "README.md").read_text()
    internal_block = readme.split("## Internal 25", 1)[-1].split("## External 25", 1)[0]
    for name, purpose, treatment in _JOB_ROW.findall(internal_block):
        out["internal"].setdefault(name.lower(), f"{purpose}. {treatment}")
    return out


def job_for(archetype: str, audience: str) -> str:
    table = jobs()
    name = (archetype or "").lower()
    return table.get(audience, {}).get(name) or table.get(
        "external" if audience == "internal" else "internal", {}).get(name, "")


def menu(audience: str) -> str:
    """The audience's set as a menu a planner can choose from, rather
    than a running order it should march down."""
    lines = []
    for slide in slides_in(audience):
        job = job_for(slide["archetype"], audience)
        lines.append(f"  {slide['archetype']}" + (f" — {job}" if job else ""))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# what a deck should cover
# --------------------------------------------------------------------------

# Picking individual slides is precise but slow, and a brief alone leaves
# the planner guessing at shape. This is the middle: say what the deck
# should COVER and let it choose the layout for each. Every section names
# the archetypes that serve it, so the planner is choosing within a
# shortlist rather than across fifty.
DECK_SECTIONS: dict[str, dict] = {
    "context": {
        "label": "Why we're here",
        "hint": "The situation, the problem, what prompted this",
        "internal": ["picture_intro", "agenda_c_split"],
        "external": ["statement_a", "title_content"],
    },
    "numbers": {
        "label": "The numbers",
        "hint": "Proof: counts, percentages, scale",
        "internal": ["kone_numbers", "hero_stat", "segment_breakdown"],
        "external": ["kone_numbers", "hero_stat", "statement_b"],
    },
    "one_number": {
        "label": "One number that matters",
        "hint": "A single figure carrying the whole point",
        "internal": ["hero_stat"],
        "external": ["hero_stat"],
    },
    "scope": {
        "label": "Scope — in and out",
        "hint": "What is covered, what is not, and who owns the rest",
        "internal": ["icon_columns_5", "resource_links", "matrix_2x2"],
        "external": ["two_content", "comparison_table", "three_content"],
    },
    "process": {
        "label": "How it works",
        "hint": "A sequence of steps or stages",
        "internal": ["how_it_works_3step", "lifecycle_4stage", "numbered_icon_row_6"],
        "external": ["how_it_works_3step", "three_content"],
    },
    "timeline": {
        "label": "Timeline or phasing",
        "hint": "Dates, quarters, milestones, what happens when",
        "internal": ["timeline_quarter_axis", "quarterly_plan_4col"],
        "external": ["timeline"],
    },
    "ownership": {
        "label": "Who does what",
        "hint": "Roles, owners, which team handles which part",
        "internal": ["org_functions", "numbered_icon_row_6"],
        "external": ["three_content", "value_prop_four_point"],
    },
    "comparison": {
        "label": "Options compared",
        "hint": "This against that — repair or replace, us or them",
        "internal": ["matrix_2x2", "chart_commentary"],
        "external": ["comparison_table", "two_content", "two_pictures_text_b"],
    },
    "voice": {
        "label": "A quote or voice",
        "hint": "Someone's own words, a customer or a team",
        "internal": ["quote_b", "quote_e"],
        "external": ["quote_a"],
    },
    "evidence": {
        "label": "Photography or examples",
        "hint": "Real sites, reference projects, what it looks like",
        "internal": ["picture_intro", "image_section_divider"],
        "external": ["three_pictures_text", "text_picture_a", "text_picture_b"],
    },
    "next": {
        "label": "What happens next",
        "hint": "Actions, owners, dates, the ask",
        "internal": ["statement_links", "milestone_slide", "resource_links"],
        "external": ["timeline", "value_prop_four_point"],
    },
    "credits": {
        "label": "Credit and thanks",
        "hint": "Who did the work",
        "internal": ["credits"],
        "external": ["credits"],
    },
}


def section_names() -> list:
    return list(DECK_SECTIONS)


def sections_brief(chosen: list, audience: str) -> str:
    """The chosen sections written for a planner, each with the
    archetypes that serve it."""
    lines = []
    for key in chosen:
        entry = DECK_SECTIONS.get(key)
        if not entry:
            continue
        suits = [a for a in entry.get(audience, []) if a]
        lines.append(
            f"  {entry['label']} — {entry['hint']}."
            + (f" Archetypes that suit it: {', '.join(suits)}." if suits else "")
        )
    return "\n".join(lines)
