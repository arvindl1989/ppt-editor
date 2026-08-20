"""What each archetype needs before it is worth choosing.

The planner used to see two descriptions of every archetype and they
disagreed. One was a prose job from the handoff tables; the other was
the list of keys derived from the geometry, and for a third of the
library those keys said nothing:

    agenda_c_split        title (text), body (text)
    timeline_quarter_axis title (text), body (text), body2 (text)
    comparison_table      title (text), table (text)

An agenda that takes no agenda items. A timeline that takes no events.
So a model reaching for the interesting layout found it could only put
two paragraphs there, and fell back to the handful with real slots --
`three_content`, `kone_numbers`, `timeline`. It was not repeating out of
laziness. It was repeating because those were the only slides it could
fill.

The fix was already written down. `EXTERNAL_25.md` carries a `contract`
column for all twenty-five:

    | 11 | `THREE_CONTENT` | ... | `title:title · items[3]:{heading:heading, text:body}` |

`brandmode.jobs()` matched that column and threw it away. This module
reads it, gives the internal set the same treatment from the prose in
`INTERNAL_25.md`, and turns both into something two other things can
use: a planner that is told what a slide needs before choosing it, and
a test that says where the renderer cannot yet accept it.

A contract is a claim about the DESIGN, not about the code. Where the
two disagree the contract is right and the registry has a gap -- which
is exactly what `gaps()` reports.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field

from deckguard import brandmode as bm

# --------------------------------------------------------------------------
# the shape of a contract
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Slot:
    """One thing an archetype asks the caller for."""

    key: str
    role: str = ""                      # the BRAND_MODE role it is set in
    minimum: int = 1                    # fewest items that still read as designed
    maximum: int = 1                    # most the layout has room for
    fields: tuple = ()                  # for a list: the Slots inside each item
    optional: bool = False

    @property
    def is_list(self) -> bool:
        return self.maximum > 1 or bool(self.fields)

    @property
    def is_picture(self) -> bool:
        return self.role in ("picture", "image_band", "image")

    def describe(self) -> str:
        if not self.is_list:
            # A hint that contradicts the key is worse than none. The
            # handoff sets a cover's title in `stat_value` and a scope
            # line in `eyebrow` -- typography roles, borrowed for their
            # size, saying nothing about the material. Read literally
            # they told a planner a cover title should be "a short
            # figure, e.g. 91%".
            hint = "" if self.key in _SELF_NAMING else _ROLE_HINT.get(self.role, "")
            mark = "?" if self.optional else ""
            return f"{self.key}{mark}{f' ({hint})' if hint else ''}"
        inner = ", ".join(f.key for f in self.fields)
        span = (str(self.minimum) if self.minimum == self.maximum
                else f"{self.minimum}-{self.maximum}")
        return f"{self.key} ({span} × {{{inner}}})"


@dataclass(frozen=True)
class Contract:
    """Everything one archetype needs, and what it is for."""

    archetype: str
    audience: str
    job: str = ""
    slots: tuple = field(default_factory=tuple)

    def slot(self, key: str):
        return next((s for s in self.slots if s.key == key), None)

    @property
    def needs(self) -> tuple:
        """The slots that must be filled for the slide to be worth using.

        Pictures are excluded: they are filled from the library, so a
        photo slide is never disqualified for want of a photograph.
        """
        return tuple(s for s in self.slots if not s.optional and not s.is_picture)

    def describe(self) -> str:
        return " · ".join(s.describe() for s in self.slots if not s.is_picture)


# Keys that say what they hold better than their typography role does.
_SELF_NAMING = {
    "title", "subtitle", "scope", "scope_label", "context", "caption",
    "support", "note", "lead", "intro", "body", "text", "text1", "text2",
    "credits", "next", "owner", "tagline",
}

# What a role means in terms of the MATERIAL it wants, which is what a
# planner is actually matching against. Only the roles that constrain
# content appear; the rest are typography and say nothing about fit.
_ROLE_HINT = {
    "bullets": "a real list, 2-6 short lines",
    "stat_value": "a short figure, e.g. 91%",
    "hero_value": "one figure, 4 characters at most",
    "stat_label": "2-4 words under a figure",
    "number": "01, 02, 03",
    "display": "a few words, set very large",
    "table": "rows of comparable values",
    "eyebrow": "2-5 words, uppercase",
    "attribution": "who said it",
    "quote": "the words as spoken",
}


# --------------------------------------------------------------------------
# reading the external table's own contract column
# --------------------------------------------------------------------------

# `items[3]:{heading:heading, text:body}` and `title:title_narrow`.
_SLOT = re.compile(r"^([a-z_0-9]+)(?:\[(\d+)\])?(?::([a-z_0-9]+))?(?:\s*:?\s*\{(.+)\})?$")


def _parse_slot(text: str, minimums: dict) -> Slot | None:
    text = text.strip().strip("`").strip()
    if not text:
        return None
    # `items[2]:{label:eyebrow, bullets:bullets}` -- split the braces off
    # first so the commas inside them are not read as slot separators.
    brace = ""
    if "{" in text:
        head, _, rest = text.partition("{")
        brace = rest.rstrip("}").strip()
        text = head.rstrip(": ").strip()
    found = _SLOT.match(text)
    if not found:
        return None
    key, count, role, _ = found.groups()
    maximum = int(count) if count else 1
    fields = []
    for piece in brace.split(",") if brace else []:
        piece = piece.strip()
        if not piece:
            continue
        inner_key, _, inner_role = piece.partition(":")
        fields.append(Slot(key=inner_key.strip(), role=(inner_role or "").strip()))
    return Slot(
        key=key,
        role=role or "",
        minimum=min(minimums.get(key, maximum), maximum),
        maximum=maximum,
        fields=tuple(fields),
        optional=key in _OPTIONAL,
    )


def parse(spec: str, minimums: dict | None = None) -> tuple:
    """The handoff's `a:role · b[3]:{c, d}` line, as Slots."""
    out = []
    for piece in (spec or "").split("·"):
        slot = _parse_slot(piece, minimums or {})
        if slot is not None:
            out.append(slot)
    return tuple(out)


# Slots a slide reads as complete without. Everything else is required,
# which is the point: a contract that makes nothing mandatory cannot
# tell a planner that a layout is the wrong one.
_OPTIONAL = {
    "eyebrow", "scope_label", "scope", "footer", "subtitle", "support",
    "context", "note", "lead", "caption", "text2", "body2", "body3",
    "classification", "date", "tagline",
    # figures the engine rasterises for itself. `table` is NOT here: a
    # comparison table's rows are content, and the planner writes them.
    "chart", "diagram",
}

# Where fewer than the as-built count still reads as designed. The
# default is that a layout wants exactly what it was drawn for -- a
# three-column grid with two things in it has a hole where the third
# should be -- so these are the deliberate exceptions, each one a
# layout whose repeat is a sequence rather than a grid.
_MINIMUMS = {
    "kone_numbers": {"stats": 3},        # the handoff itself says three to five
    "statement_b": {"stats": 3},         # "Three to five KONE numbers"
    "timeline": {"items": 3},            # a roadmap with three stops is a roadmap
    "timeline_quarter_axis": {"events": 3},
    "credits": {"names": 4},             # a wall of names, not a fixed grid
    "resource_links": {"tiles": 2},
    "numbered_icon_row_6": {"items": 4},  # a 3x2 grid tolerates one short row
    "icon_columns_5": {"items": 3},
    "quarterly_plan_4col": {"quarters": 2},
    "matrix_2x2": {"quadrants": 4},      # a 2x2 with three quadrants is not a 2x2
}


# Where the handoff's own table names a slot something the built layout
# does not. Corrected here rather than in `EXTERNAL_25.md`, which is
# vendored and gets replaced wholesale when the handoff is reissued.
_KEY_FIXES: dict[str, dict] = {
    # the other two covers call their photograph `image`, and so does
    # the layout this one is bound to
    "cover_f_fullbleed": {"photo": "image"},
}

# Slots the handoff asks for that the archetype no longer draws. The
# only ones so far are its own footer lines: `stamp_chrome` puts the
# date and page number on every body slide, so an archetype-level
# footer was a second one underneath the first, below the floor.
_DROP_KEYS: dict[str, set] = {
    "kone_numbers": {"footer"},
}

# Where the handoff's contract described the layout as it was BUILT and
# the layout has since been rebuilt. Both of these were `body/body2/
# body3` -- the unnamed-slot disease the whole module exists to end --
# and the entry here is what the renderer now reads.
_EXTERNAL_OVERRIDES: dict[str, str] = {
    "quote_a": "title:title · quote:quote · context:body · attribution:attribution",
    "agenda_b_numbered": "title:heading · items[5]:{number:number, label:heading}",
}


@functools.lru_cache(maxsize=1)
def external() -> dict:
    """The external set's contracts, read from its own table."""
    text = (bm.handoff_dir() / "EXTERNAL_25.md").read_text()
    out = {}
    for name, job, spec in bm._JOB_ROW.findall(text):
        key = name.lower()
        spec = _EXTERNAL_OVERRIDES.get(key, spec)
        fixes = _KEY_FIXES.get(key, {})
        dropped = _DROP_KEYS.get(key, set())
        slots = tuple(
            s if s.key not in fixes else Slot(
                key=fixes[s.key], role=s.role, minimum=s.minimum,
                maximum=s.maximum, fields=s.fields, optional=s.optional)
            for s in parse(spec, _MINIMUMS.get(key, {}))
            if s.key not in dropped
        )
        out[key] = Contract(archetype=key, audience="external",
                            job=job.strip(), slots=slots)
    return out


# --------------------------------------------------------------------------
# the internal set, written out from INTERNAL_25.md
# --------------------------------------------------------------------------

# The internal table in `README.md` has a `treatment` column where the
# external one has a `contract`, so there is nothing to parse: these are
# transcribed from the as-built prose in `INTERNAL_25.md`, one line each,
# quoted in the comment so the two can be checked against each other.
_INTERNAL_SPECS: dict[str, str] = {
    # 01 "Three photo panes cut across the top of a white field ...
    #     Eyebrow ... Title 76px ... Tagline bottom-right."
    "cover_b_cut3": "image:picture · title:display · context:body",
    # 02 "Full-height photo right ... blue eyebrow, 48px statement,
    #     then three rows -- 44px blue chip with white pictogram, 19px text."
    "picture_intro": "photo:picture · eyebrow:eyebrow · title:display · points[3]:{icon, text:body}",
    # 03 "Mint column ... 44px title, 16px lead. Right column: five rows,
    #     each a sand block with a 44px blue numeral chip and 24px label."
    "agenda_c_split": "title:title · lead:body · items[5]:{number:number, label:heading}",
    # 04 "72px blue chip, 64px title, 220x6 blue rule."
    "divider_title_only": "title:display",
    # 05 "300px blue numeral. Section label and 56px title at x:620."
    "divider_numbering": "number:display · eyebrow:eyebrow · title:display",
    # 06 "Full-bleed photograph ... white label and 56px white title."
    "image_section_divider": "image:image_band · eyebrow:eyebrow · title:display",
    # 07 "Five cards ... each: 64px chip, 24px heading, 15px body."
    "icon_columns_5": ("eyebrow:eyebrow · title:title · intro:body · "
                       "items[5]:{icon, text:body}"),
    # 08 "3x2 grid. Each cell: 28px blue numeral, 24px heading, 15px body."
    "numbered_icon_row_6": "title:title · items[6]:{number:number, icon, label:heading}",
    # 09 "Four illustration cells ... four stage cells, 28px blue pictogram
    #     with a stage label, 24px heading, 15px body."
    "lifecycle_4stage": ("image:picture · eyebrow:eyebrow · title:title · "
                        "stages[4]:{icon, heading:heading, bullets:bullets}"),
    # 10 "Three sand panels ... a 28px blue numeral and 19px step text."
    "how_it_works_3step": "image:image_band · title:title · steps[3]:{number:number, text:body}",
    # 11 "Four columns. Header: quarter label and pictogram. Body: 22px
    #     heading and a blue-marker bullet list."
    "quarterly_plan_4col": ("eyebrow:eyebrow · title:title · intro:body · "
                            "columns[4]:{text:body} · "
                            "quarters[4]:{label:stat_label, items:bullets}"),
    # 12 "40px title in a 340px column. Pink panel, lead plus three
    #     bullets. Right: four stems -- period label, 16px text."
    "timeline_quarter_axis": ("title:title · lead:body · bullets:bullets · "
                              "events[4]:{period:stat_label, text:body}"),
    # 13 "1000px grid ... four quadrants."
    "matrix_2x2": "title:title · xlabel:eyebrow · ylabel:eyebrow · quadrants[4]:{heading:heading, items:bullets}",
    # 14 "Blue stat band, five 52px white figures with labels. Two columns
    #     beneath: what happens next (bulleted) and credit where it is due."
    "milestone_slide": ("eyebrow:eyebrow · title:title · lede:body · "
                        "stats[5]:{value:stat_value, label:stat_label} · "
                        "scope_label:eyebrow · scope:body · "
                        "next_label:eyebrow · next:bullets · "
                        "credits_label:eyebrow · credits:body · done[3]:{text:body}"),
    # 15 "Sand list panel left, four bullets. Right: a blue owner box,
    #     then three mint function boxes, 20px name and 15px scope."
    "org_functions": "title:title · functions:bullets · diagram:figure",
    # 16 "Five figures, 64px white numeral and a label. Scope line beneath."
    "kone_numbers": ("eyebrow:eyebrow · title:title · scope_label:eyebrow · scope:eyebrow · "
                     "stats[5]:{value:stat_value, label:stat_label}"),
    # 17 "Blue highlight panel holding a 76px figure and caption. Five
    #     bars with a label and value. Three commentary cards."
    "segment_breakdown": ("title:title · highlight_value:hero_value · "
                          "highlight_caption:body · chart:figure · "
                          "categories[3]:{icon, heading:heading, items:bullets}"),
    # 18 "620x300 column chart ... two commentary cards: mint 'what it
    #     shows', pink 'what it does not'." The chart itself is a raster
    #     figure the engine draws, not a slot the planner fills.
    "chart_commentary": ("eyebrow:eyebrow · title:title · chart:figure · "
                         "columns[2]:{heading:heading, bullets:bullets}"),
    # 19 "280px blue figure. 32px caption, 16px support."
    "hero_stat": "eyebrow:eyebrow · value:hero_value · caption:heading · support:body",
    # 20 "56px blue chip, 32px section title, 15px note. Quote 44px,
    #     blue rule, attribution beneath."
    "quote_b": "title:title · context:body · quote:quote · attribution:attribution",
    # 21 "420px blue column carrying context. Quote 40px black on white,
    #     attribution beneath."
    "quote_e": "context:body · quote:quote · attribution:attribution",
    # 22 "Blue pictogram eyebrow, 40px title, 19px lead. Twelve names in
    #     a four-column grid."
    "credits": "eyebrow:eyebrow · title:title · note:body · names[12]:{name:heading}",
    # 23 "56px statement. Three yellow cards: 48px chip, 24px audience,
    #     two blue-marker bullets."
    "statement_links": "statement:display · columns[3]:{heading:heading, links:bullets}",
    # 24 "Four tiles, each a 64px pictogram over a 26px title and 15px
    #     description. Contact line."
    "resource_links": "title:title · tiles[4]:{icon, label:heading} · contact:body",
    # 25 "120px white title, two 19px white lines."
    "outro": "title:display · text1:body · text2:body",
}


@functools.lru_cache(maxsize=1)
def internal() -> dict:
    jobs = bm.jobs().get("internal", {})
    return {
        name: Contract(archetype=name, audience="internal",
                       job=jobs.get(name, ""),
                       slots=parse(spec, _MINIMUMS.get(name, {})))
        for name, spec in _INTERNAL_SPECS.items()
    }


def table(audience: str) -> dict:
    return internal() if audience == "internal" else external()


def for_archetype(name: str, audience: str = "internal"):
    """The contract for an archetype, from its own set or the other one."""
    name = (name or "").lower()
    found = table(audience).get(name)
    if found is not None:
        return found
    other = "external" if audience == "internal" else "internal"
    return table(other).get(name)


# --------------------------------------------------------------------------
# where the renderer cannot yet honour the contract
# --------------------------------------------------------------------------


def _registry_slots(name: str) -> dict:
    """What the live registry will actually read, as {key: (count, fields)}.

    Fields matter as much as the key does: a contract promising
    `quarters[4]:{period, heading}` against a group built as
    `{label, items}` tells the planner to emit two field names nothing
    reads, and the slide comes back with the labels blank.
    """
    from deckguard.registry import _load_archetypes

    spec = _load_archetypes().ARCHETYPES.get(name) or {}
    out: dict = {}
    for region in spec.get("regions") or []:
        if region.get("content"):
            out[region["content"]] = (1, frozenset())
    for group in spec.get("groups") or []:
        if not group.get("content"):
            continue
        fields = {
            "icon" if r.get("role") == "icon" else r.get("content")
            for r in group.get("regions") or []
            if r.get("content") or r.get("role") == "icon"
        }
        out[group["content"]] = (len(group.get("origins") or []) or 1, frozenset(fields))
    return out


def gaps(audience: str | None = None) -> dict:
    """Every slot a contract promises that the renderer cannot accept.

    This is the punch list, and it is generated rather than written
    down, so it shrinks as the registry is fixed and can never claim a
    gap has been closed when it has not.
    """
    from deckguard.registry import _archetype_image_slots, _load_archetypes

    built = set(_load_archetypes().ARCHETYPES)
    pictures = {name: {slot[1]} for name, slot in _archetype_image_slots().items()
                if slot[0] == "single"}
    out: dict = {}
    for name in [audience] if audience else ["internal", "external"]:
        for archetype, contract in table(name).items():
            if archetype not in built:
                continue
            have = _registry_slots(archetype)
            missing = []
            for slot in contract.slots:
                if slot.key not in have:
                    missing.append(f"{slot.describe()} — no such slot")
                    continue
                count, fields = have[slot.key]
                if slot.is_list and count < slot.minimum:
                    missing.append(
                        f"{slot.key} — contract wants {slot.minimum}, "
                        f"the layout holds {count}")
                unread = [f.key for f in slot.fields if f.key not in fields]
                if unread:
                    missing.append(
                        f"{slot.key}.{{{', '.join(unread)}}} — the layout reads "
                        f"{{{', '.join(sorted(fields))}}}")
            # The other direction: a slot the renderer will draw that no
            # contract mentions is a slot no planner will ever fill.
            # Picture slots are exempt -- they are filled from the photo
            # library, so nobody is meant to ask for them.
            for key in have:
                if contract.slot(key) is None and key not in pictures.get(archetype, ()):
                    missing.append(f"{key} — built, but the contract never asks for it")
            if missing:
                out.setdefault(archetype, {})[name] = missing
    return out


def guide(audience: str) -> str:
    """The menu, written as contracts rather than as prose.

    What the planner reads. Every line says what the slide is for AND
    what it needs, so an archetype can be ruled out before it is chosen
    rather than picked and then padded.
    """
    lines = []
    for slide in bm.slides_in(audience):
        name = slide["archetype"]
        contract = for_archetype(name, audience)
        if contract is None:
            lines.append(f"  {name}")
            continue
        job = (contract.job or bm.job_for(name, audience)).rstrip(".")
        lines.append(f"  {name} — {job}.\n      needs: {contract.describe()}")
    return "\n".join(lines)
