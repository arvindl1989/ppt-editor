"""The master template's own geometry, read as data.

Every archetype in this tool used to be ported by hand -- read the
reference, eyeball the boxes, type a region dict, repeat. That got us 22
of the 61 archetypes the brand actually documents, and the 39 missing
ones were not hard, just numerous.

They do not have to be typed at all. `LAYOUTS.md` already lists the px
geometry of all 62 master layouts in a rigidly regular form::

    ### Title and content A
    `slideLayout16`

    - **Title** — 45, 91, 917 × 104
    - **Text/body** — 45, 227, 917 × 402
    - **Footer** — 215, 658, 747 × 19
    - **Logo** — 1153, 45, 81 × 31 · image

and `ARCHETYPES.md` binds each canonical `UPPER_SNAKE` archetype name to
one of those layouts. Between them that is 51 of the 61 archetypes,
specified, in files we already ship. This module reads both and emits
engine archetype dicts, so adding the rest of the vocabulary is a
parsing problem rather than a typing one.

Two measurements justify trusting the files this much. Every one of the
321 geometry lines in `LAYOUTS.md` parses -- there is no ragged tail to
hand-correct. And 316 of those 321 boxes are present at exactly that
pixel in the master .pptx itself; the five that differ are two logo
rectangles off by a pixel and three shapes on the user-guide layout.
`LAYOUTS.md` is not a description of the master, it *is* the master.

What this module deliberately does NOT do:

- It never emits chrome. Logo, tagline, date and page number are the
  layout's job, not the archetype's -- an archetype that draws its own
  logo produces two of them the moment the master's frames are
  repaired. `CHROME_ROLES` is dropped on the floor during parsing.
- It never overwrites a hand-built archetype. `install()` skips any
  name (or alias) that the engine or the gallery port already
  implements, because those were tuned against a real rendering and
  this module is working from a coarser description. Generated geometry
  is the fallback, not the authority.

The role vocabulary in `LAYOUTS.md` is coarse on purpose -- `Text/body`
covers 109 of the 321 boxes and stands for eyebrows, bullet lists,
captions and stat columns alike. `_bind_roles` recovers the structure
that the flat list loses, mainly by noticing that equal-sized boxes at
one y with evenly spaced x are not three regions but one repeating
group of three.
"""

from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

_INTERACTIVE_SKILL_DIR = "~/.claude/skills/kone-design"
_VENDORED_SKILL_DIR = Path(__file__).with_name("assets") / "kone-design"

# Roles the LAYOUT owns. An archetype must never place these itself.
CHROME_ROLES = frozenset({"Logo", "Tagline", "Footer", "Date", "Page number"})

# `- **Title** — 45, 91, 917 × 104 · black`
_BOX_RE = re.compile(
    r"^- \*\*(?P<role>.+?)\*\* — (?P<x>-?\d+), (?P<y>-?\d+), (?P<w>\d+) × (?P<h>\d+)(?P<mods>.*)$",
    re.M,
)
_LAYOUT_KEY_RE = re.compile(r"`(slideLayout\d+)`")

# `| `TITLE_CONTENT` | The workhorse... | `slideLayout16` | built · 04 |`
_ARCH_ROW_RE = re.compile(
    r"^\| `(?P<name>[A-Z][A-Z0-9_]+)` \| (?P<purpose>.*?) \| (?P<master>.*?) \| (?P<status>[^|]+) \|$",
    re.M,
)
_ALIAS_RE = re.compile(r"Alias: `([a-z0-9_]+)`")
_GRADE_RE = re.compile(r"^## Grade ([A-D])", re.M)
_TWIN_RE = re.compile(r"Twin of `([A-Z][A-Z0-9_]+)`")


@dataclass(frozen=True)
class Box:
    """One positioned shape on the 1280x720 grid."""

    role: str
    x: int
    y: int
    w: int
    h: int
    mods: tuple[str, ...] = ()

    @property
    def is_chrome(self) -> bool:
        return self.role in CHROME_ROLES

    @property
    def is_decoration(self) -> bool:
        """`Rectangle 9`, `Fast overskrift` -- shapes the master names
        after itself rather than after a role. Nothing can be bound to
        them, so they are not archetype content."""
        return bool(re.match(r"^(Rectangle|Picture Placeholder|Fast) ", self.role))

    @property
    def on_dark(self) -> bool:
        return "white" in self.mods


@dataclass(frozen=True)
class Layout:
    """A master layout: `slideLayout16`, its title, and its boxes."""

    key: str
    name: str
    boxes: tuple[Box, ...]

    def content_boxes(self) -> list[Box]:
        return [b for b in self.boxes if not b.is_chrome and not b.is_decoration]


@dataclass(frozen=True)
class Archetype:
    """One row of `ARCHETYPES.md`."""

    name: str
    grade: str
    purpose: str
    master: Optional[str]
    aliases: tuple[str, ...]
    status: str
    twin_of: Optional[str] = None

    @property
    def is_built(self) -> bool:
        return self.status.startswith("built")

    @property
    def is_twin(self) -> bool:
        return self.status.startswith("twin")

    @property
    def engine_key(self) -> str:
        return self.name.lower()


def _is_graded(spec: Path) -> bool:
    """Does this directory hold the CURRENT spec?

    An installed kone-design skill may predate the rework and still
    carry an `ARCHETYPES.md` that lists the old gallery vocabulary with
    no grades -- parsing that yields zero archetypes and silently
    disables this whole module. Both files must be present and
    `ARCHETYPES.md` must be the graded one, or we fall back.
    """
    layouts, archetypes = spec / "LAYOUTS.md", spec / "ARCHETYPES.md"
    if not (layouts.is_file() and archetypes.is_file()):
        return False
    return bool(_GRADE_RE.search(archetypes.read_text()))


@lru_cache(maxsize=1)
def spec_dir() -> Path:
    """Where `LAYOUTS.md` / `ARCHETYPES.md` live -- same three-step
    resolution as `skill_bridge._skill_dir`, for the same reason: a
    deployed deckguard has no `~/.claude/skills/` at all. The vendored
    copy is the last candidate AND the fallback, so a stale installed
    skill degrades to the bundled spec rather than to nothing."""
    candidates = []
    env = os.environ.get("KONE_DESIGN_DIR")
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path(_INTERACTIVE_SKILL_DIR).expanduser())
    candidates.append(_VENDORED_SKILL_DIR)

    for base in candidates:
        spec = base / "templates" / "kone-deck"
        if _is_graded(spec):
            return spec
    return _VENDORED_SKILL_DIR / "templates" / "kone-deck"


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------


def _mods(raw: str) -> tuple[str, ...]:
    return tuple(p.strip() for p in raw.split("·") if p.strip())


def parse_layouts(text: str) -> dict[str, Layout]:
    """`LAYOUTS.md` -> {slideLayoutN: Layout}. Sections without a
    `slideLayoutN` marker (the grid preamble, the grades table) are
    prose, not geometry, and are skipped."""
    out: dict[str, Layout] = {}
    for section in re.split(r"^### ", text, flags=re.M)[1:]:
        key_match = _LAYOUT_KEY_RE.search(section)
        if not key_match:
            continue
        boxes = tuple(
            Box(m.group("role").strip(), int(m.group("x")), int(m.group("y")),
                int(m.group("w")), int(m.group("h")), _mods(m.group("mods")))
            for m in _BOX_RE.finditer(section)
        )
        name = section.splitlines()[0].strip()
        out[key_match.group(1)] = Layout(key_match.group(1), name, boxes)
    return out


def parse_archetypes(text: str) -> dict[str, Archetype]:
    """`ARCHETYPES.md` -> {NAME: Archetype}, carrying the grade down
    from whichever `## Grade X` heading the row sits under."""
    out: dict[str, Archetype] = {}
    parts = _GRADE_RE.split(text)
    for i in range(1, len(parts), 2):
        grade, body = parts[i], parts[i + 1]
        for m in _ARCH_ROW_RE.finditer(body):
            purpose = m.group("purpose")
            master = _LAYOUT_KEY_RE.search(m.group("master"))
            twin = _TWIN_RE.search(purpose)
            out[m.group("name")] = Archetype(
                name=m.group("name"),
                grade=grade,
                purpose=purpose,
                master=master.group(1) if master else None,
                aliases=tuple(_ALIAS_RE.findall(purpose)),
                status=m.group("status").strip(),
                twin_of=twin.group(1) if twin else None,
            )
    return out


def load_spec() -> tuple[dict[str, Layout], dict[str, Archetype]]:
    base = spec_dir()
    return (
        parse_layouts((base / "LAYOUTS.md").read_text()),
        parse_archetypes((base / "ARCHETYPES.md").read_text()),
    )


# --------------------------------------------------------------------------
# role binding
# --------------------------------------------------------------------------

# LAYOUTS.md role -> (engine role, content key stem). `Title` and
# `Text/body` are resolved positionally in `_bind_roles`, since the same
# label covers a headline and a caption.
_PICTURE_ROLES = frozenset({"Picture"})
_TITLE_ROLES = frozenset({"Title"})
_BODY_ROLES = frozenset({"Text/body"})
_PANEL_ROLES = frozenset({"Background"})

# Below this height a `Title` box is a line, not a headline -- the
# master uses the same placeholder type for the 36px subtitle on
# slideLayout18 as for the 104px headline above it.
_SUBTITLE_MAX_H = 60

# A modifier means different things either side of the role: on a
# `Background` box it is the FILL (`pink`, `#D2F5FF`); on a text box it
# is the INK (`white` text on the blue panel of Quote A). Both readings
# are unambiguous given the role, so they share the field.
_PANEL_FILL = {
    "white": "FFFFFF",
    "sand": "F3EEEA",
    "pink": "FFCDD7",
    "yellow": "FFE141",
    "mint": "AAE1C8",
    "blue": "1450F5",
}
# Quote A's panel carries no modifier at all -- an unqualified panel is
# KONE Blue, which is why its body text is separately marked `white`.
_DEFAULT_PANEL_FILL = "1450F5"


def _key(stem: str, n: int) -> str:
    return stem if n == 0 else f"{stem}{n + 1}"


def _columns(boxes: list[Box]) -> tuple[list[list[Box]], list[Box]]:
    """Split boxes into repeating column groups and singletons.

    Three 374x403 boxes at y=227 sitting at x=45/453/861 are not three
    regions, they are one group rendered three times -- and only the
    group form lets the engine expand it over a content list of
    whatever length the caller supplies. Boxes are a column set when
    they share role, y, w and h and there are at least two of them;
    sets that share the same x origins (the photo row and the caption
    row of `Three pictures and text`) are then merged into one group so
    each column carries both its picture and its text.
    """
    rows: dict[tuple, list[Box]] = {}
    for b in boxes:
        rows.setdefault((b.role, b.y, b.w, b.h), []).append(b)

    column_rows = [sorted(v, key=lambda b: b.x) for v in rows.values() if len(v) > 1]
    singles = [v[0] for v in rows.values() if len(v) == 1]

    merged: dict[tuple, list[list[Box]]] = {}
    for row in column_rows:
        merged.setdefault(tuple(b.x for b in row), []).append(row)

    groups: list[list[Box]] = []
    for row_set in merged.values():
        row_set.sort(key=lambda r: r[0].y)
        groups.append([b for row in row_set for b in row])
    return groups, singles


def _engine_role(box: Box, kind: str, ordinal: int) -> str:
    if kind == "title":
        if box.h <= _SUBTITLE_MAX_H or ordinal > 0:
            return "heading"
        return "title_light" if box.on_dark else "title"
    if kind == "body":
        return "on_panel_body" if box.on_dark else "body"
    return kind


def _bind_roles(layout: Layout) -> dict:
    """A `Layout` -> an engine archetype dict.

    Chrome is dropped (the layout owns it). Remaining boxes are read in
    reading order, so the first `Title` is the headline and a later,
    shorter one is the line beneath it. Repeating columns become a
    `groups` entry; everything else becomes a flat region.
    """
    content = layout.content_boxes()
    groups_boxes, singles = _columns(content)

    regions: list[dict] = []
    counters: dict[str, int] = {}

    def add(box: Box, kind: str, stem: str) -> None:
        n = counters.get(stem, 0)
        counters[stem] = n + 1
        regions.append({
            "role": _engine_role(box, kind, n),
            "box": [box.x, box.y, box.w, box.h],
            "content": _key(stem, n),
        })

    # Colour panels are carried outside `regions` and painted by
    # `render` before the engine draws anything -- the engine's own
    # `panel` role is hardcoded to KONE Blue, and these come in five
    # colours. Keeping them out of `regions` also keeps the archetype
    # dict something the unmodified engine can still render.
    panels = [
        {
            "box": [b.x, b.y, b.w, b.h],
            "fill": next((_PANEL_FILL.get(m, m.lstrip("#")) for m in b.mods),
                         _DEFAULT_PANEL_FILL),
        }
        for b in sorted(singles, key=lambda b: (b.y, b.x))
        if b.role in _PANEL_ROLES
    ]

    for box in sorted(singles, key=lambda b: (b.y, b.x)):
        if box.role in _TITLE_ROLES:
            add(box, "title", "title")
        elif box.role in _BODY_ROLES:
            add(box, "body", "body")
        elif box.role in _PICTURE_ROLES:
            add(box, "picture", "image")

    groups: list[dict] = []
    for column_boxes in groups_boxes:
        origins = sorted({b.x for b in column_boxes})
        top = min(b.y for b in column_boxes)
        first_column = sorted((b for b in column_boxes if b.x == origins[0]),
                              key=lambda b: b.y)
        sub: list[dict] = []
        seen: dict[str, int] = {}
        for box in first_column:
            if box.role in _PICTURE_ROLES:
                kind, stem = "picture", "image"
            elif box.role in _TITLE_ROLES:
                kind, stem = "title", "heading"
            else:
                kind, stem = "body", "text"
            n = seen.get(stem, 0)
            seen[stem] = n + 1
            sub.append({
                "role": _engine_role(box, kind, n),
                "box": [0, box.y - top, box.w, box.h],
                "content": _key(stem, n),
            })
        groups.append({
            "content": "items",
            "origins": [[x, top] for x in origins],
            "regions": sub,
        })

    spec: dict = {"regions": regions}
    if groups:
        spec["groups"] = groups
    if panels:
        spec["panels"] = panels
    scrims = _implied_scrims(regions)
    if scrims:
        spec["scrims"] = scrims
    return spec


# Roles the engine draws in white. A layout that puts one of these over a
# photograph has reversed type out of a photograph, whatever else it does.
_LIGHT_ROLES = frozenset({"title_light", "on_panel_body", "eyebrow_light"})

# Every role the engine renders as a photograph. `image_band` is not a
# synonym nobody uses -- it is what `image_section_divider` calls its
# full-bleed picture, and matching only on "picture" meant that
# archetype, whose whole design is white type over a photograph, was the
# one full-bleed layout that never got a scrim.
_PICTURE_REGION_ROLES = frozenset({"picture", "image_band"})


def _is_light_role(role) -> bool:
    """Whether a region's ink is white, whichever path produced it.

    Bound layouts name the role (`title_light`); gallery ports carry the
    colour in the name itself (`gal_i64_FFFFFF`). Both reverse out of the
    picture underneath and both need protecting.
    """
    role = str(role or "")
    return role in _LIGHT_ROLES or role.upper().endswith("_FFFFFF")


def _implied_scrims(regions: list[dict]) -> list[dict]:
    """A picture carrying white type needs a scrim, and no layout says so.

    `LAYOUTS.md` marks the type white and leaves the protection to the
    designer, so the derived archetypes shipped without any: the
    full-bleed cover put a white headline straight onto a sunlit
    treeline. Any picture region a light-ink box sits on gets one.
    """
    pictures = [r for r in regions if r.get("role") in _PICTURE_REGION_ROLES]
    if not pictures:
        return []
    light = [r for r in regions if _is_light_role(r.get("role"))]
    scrims = []
    for picture in pictures:
        px, py, pw, ph = picture["box"]
        over = [
            r for r in light
            if r["box"][1] < py + ph and r["box"][1] + r["box"][3] > py
            and r["box"][0] < px + pw and r["box"][0] + r["box"][2] > px
        ]
        if over:
            scrims.append({"box": [px, py, pw, ph], "content": picture.get("content")})
    return scrims


# Sensible generic pictograms for an archetype whose caller named none.
# Checked against the sprite at use time, so a renamed icon degrades to
# the ones that do exist rather than drawing nothing.
_DEFAULT_ICONS = ("cloud", "people", "clock", "wrench", "calendar", "elevator")


def pictograms() -> list[str]:
    """The rasterised marks, kept only as a fallback.

    Superseded by `deckguard.icons`, which draws the real KONE
    pictograms as native editable shapes. This survives for the case
    where the icon sprite is not installed.
    """
    base = spec_dir().parent.parent / "icons"
    return [str(p) for p in sorted(base.glob("*.png"))]


def _icon_names_for(spec: dict, content: dict, slots: int) -> list[str]:
    """Which pictogram goes in each icon slot.

    A caller names one per item (`{"icon": "elevator", ...}`) and gets
    it; anything unnamed falls back to the generic rotation. With 609
    icons in the sprite an author can finally be specific, but nothing
    breaks if they are not.
    """
    from deckguard import icons as icon_mod

    available = icon_mod.load_icons()
    named: list[str] = []
    for group in spec.get("groups", []):
        if not any(r.get("role") == "icon" for r in group["regions"]):
            continue
        for item in (content.get(group["content"]) or [])[:len(group["origins"])]:
            named.append((item or {}).get("icon") if isinstance(item, dict) else None)

    fallback = [n for n in _DEFAULT_ICONS if n in available] or sorted(available)[:1]
    chosen: list[str] = []
    for index in range(slots):
        want = named[index] if index < len(named) else None
        chosen.append(want if want in available else fallback[index % len(fallback)])
    return chosen


def _icon_slots(spec: dict, content: Optional[dict] = None) -> int:
    """How many icons this slide actually needs.

    Counted against the content, not the geometry. An archetype that
    serves both a plain and a grid form declares the grid's origins
    either way, so counting those drew a full set of icons onto the
    plain form -- four of them, two straddling the body paragraph.
    """
    n = sum(1 for r in spec.get("regions", []) if r.get("role") == "icon")
    for group in spec.get("groups", []):
        per = sum(1 for r in group["regions"] if r.get("role") == "icon")
        if not per:
            continue
        supplied = len(group["origins"]) if content is None else len(
            (content.get(group["content"]) or [])[:len(group["origins"])]
        )
        n += per * supplied
    return n


def render(slide, name: str, content: dict, archetypes_module) -> None:
    """Draw an archetype onto `slide`.

    Colour panels are painted first, then the engine draws the text and
    pictures on top. The order is the whole point: an earlier version
    of the gallery port delegated first and painted its background
    afterwards, which turned a white content field into a solid blue
    slide.

    Archetypes carrying gallery `chrome` (the cut covers, the dividers,
    the outro) go through `archetypes.render`, because `gallery.install`
    wraps that function to draw the chrome and calling the engine
    directly would silently drop the cut effect and the divider
    artwork.

    Everything else goes straight to `render_archetype`, for two
    reasons that only show up on real decks. `archetypes.render`
    force-feeds its own sample chart art into `chart`/`diagram` slots
    even when the caller supplied content -- which is how a deck about
    elevators acquired a pie chart nobody asked for -- so the figures
    are applied with `setdefault` here instead. And it passes the
    engine's placeholder icon chips; real pictograms are passed
    instead, cycled to cover archetypes that want more than the three
    that exist.
    """
    from pptx.enum.shapes import MSO_SHAPE

    engine = archetypes_module.E
    spec = archetypes_module.ARCHETYPES.get(name, {})

    if spec.get("chrome"):
        archetypes_module.render(slide, name, content)
        # The gallery's ports were extracted from a reference deck that
        # carried no scrims, and the full-bleed cover is the one layout
        # the brand explicitly says needs one -- its headline landed
        # white on a sunlit treeline. `_seat_above_picture` puts the
        # gradient under the type the engine has already drawn.
        for scrim in spec.get("scrims") or _implied_scrims(spec.get("regions", [])):
            if scrim.get("content") in (None, "") or content.get(scrim.get("content")):
                _draw_scrim(slide, engine, scrim["box"], scrim.get("opacity", 78),
                            _reversed_bands(spec, content, scrim["box"]))
        return

    for panel in spec.get("panels", []):
        x, y, w, h = panel["box"]
        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, engine.X(x), engine.X(y), engine.X(w), engine.X(h)
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = engine._hex(panel["fill"])
        shape.line.fill.background()
        shape.shadow.inherit = False

    # Hairlines. Thin enough that a stroked line renders differently
    # across viewers, so they are 1px filled rectangles like every other
    # rule the master draws.
    for rule in spec.get("rules", []):
        x, y, w, h = rule["box"]
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, engine.X(x), engine.X(y), engine.X(w), engine.X(max(h, 1))
        )
        line.name = "Hairline"
        line.fill.solid()
        line.fill.fore_color.rgb = engine._hex(rule.get("fill", "D0D0D0"))
        line.line.fill.background()
        line.shadow.inherit = False

    filled = dict(content)

    # Regions the reference describes more precisely than ROLE_STYLE can
    # express are drawn here and withheld from the engine.
    engine_spec = {k: v for k, v in spec.items() if k not in ("regions", "groups")}
    engine_spec["regions"] = [
        r for r in spec.get("regions", [])
        if "dg" not in r and not _is_unsupplied_figure(r, filled, name, archetypes_module)
    ]
    engine_spec["groups"] = [
        {**g, "regions": [r for r in g["regions"] if "dg" not in r]}
        for g in spec.get("groups", [])
    ]

    # Icons are drawn here as native shapes, so they are withheld from
    # the engine along with the `dg` regions -- otherwise it draws its
    # blue placeholder chip in the same box.
    from deckguard import icons as icon_mod

    slots = _icon_slots(spec, filled)
    native = bool(icon_mod.load_icons()) and slots
    if native:
        engine_spec["regions"] = [r for r in engine_spec["regions"] if r.get("role") != "icon"]
        engine_spec["groups"] = [
            {**g, "regions": [r for r in g["regions"] if r.get("role") != "icon"]}
            for g in engine_spec["groups"]
        ]
        icons = None
    else:
        marks = pictograms()
        icons = [marks[i % len(marks)] for i in range(slots)] if marks and slots else None

    engine.render_archetype(
        slide, engine_spec, filled, icons=icons,
        bg=getattr(archetypes_module, "BG", {}).get(name),
    )

    if native:
        chosen = _icon_names_for(spec, filled, slots)
        index = 0
        for region in spec.get("regions", []):
            if region.get("role") == "icon":
                icon_mod.add_icon(slide, chosen[index], region["box"])
                index += 1
        for group in spec.get("groups", []):
            items = filled.get(group["content"]) or []
            for (ox, oy), _item in zip(group["origins"], items):
                for region in group["regions"]:
                    if region.get("role") != "icon":
                        continue
                    rx, ry, rw, rh = region["box"]
                    icon_mod.add_icon(slide, chosen[index], [ox + rx, oy + ry, rw, rh])
                    index += 1

    # AFTER the engine, never before. `render_archetype` starts by
    # painting a full-slide background rectangle, so anything drawn
    # first is buried by it -- both numbered dividers came out as an
    # empty sand rectangle with the number, title and label underneath.
    field = _field_for(spec, filled)
    if field:
        _paint_field(slide, engine, field[0])
    else:
        _paint_layout_background(slide, engine, spec)
    # Derived here as well as at build time: the gallery's own ports win
    # over the bound layouts for several archetypes, and they were
    # extracted from a reference deck that carried no scrims at all.
    for scrim in spec.get("scrims") or _implied_scrims(spec.get("regions", [])):
        if scrim.get("content") in (None, "") or filled.get(scrim.get("content")):
            _draw_scrim(slide, engine, scrim["box"], scrim.get("opacity", 78),
                        _reversed_bands(spec, filled, scrim["box"]))
    ink = field[1] if field else None
    for region in spec.get("regions", []):
        if "dg" in region:
            _draw(slide, engine, region, filled.get(region.get("content")), ink)
    for group in spec.get("groups", []):
        items = filled.get(group["content"]) or []
        for (ox, oy), item in zip(group["origins"], items):
            for region in group["regions"]:
                if "dg" not in region:
                    continue
                rx, ry, rw, rh = region["box"]
                shifted = {**region, "box": [ox + rx, oy + ry, rw, rh]}
                _draw(slide, engine, shifted, (item or {}).get(region.get("content")), ink)


# The brand's secondary palette, with the ink each field takes. The
# rule is the brand's own: a blue field takes white type, a secondary
# field takes black.
BRAND_FIELDS = {
    "blue": ("1450F5", "FFFFFF"),
    "light-blue": ("D2F5FF", "141414"),
    "pink": ("FFCDD7", "141414"),
    "yellow": ("FFE141", "141414"),
    "mint": ("AAE1C8", "141414"),
    "sand": ("F3EEEA", "141414"),
}
DEFAULT_FIELD = "blue"


def _field_for(spec: dict, content: dict):
    """(fill, ink) when this archetype paints a whole-slide colour field.

    Only archetypes that declare `field` -- dividers -- take one. The
    caller names a colour per slide; a divider is the one place the
    secondary palette is meant to carry a whole slide, and leaving them
    all the same makes a deck monotonous.
    """
    if not spec.get("field"):
        return None
    name = str(content.get("colour") or content.get("color") or DEFAULT_FIELD).lower()
    return BRAND_FIELDS.get(name, BRAND_FIELDS[DEFAULT_FIELD])


def _is_unsupplied_figure(region: dict, content: dict, name: str, archetypes_module) -> bool:
    """A chart or diagram slot the author gave nothing for.

    The engine keeps a `FIGURES` map of sample artwork and stamps it onto
    every slide of certain archetypes whether or not anyone asked --
    `segment_breakdown` gets a donut reading 53% against satisfaction
    bands of 9-10, 7-8, 5-6 and "Don't know". On a deck built from a
    brief that is not decoration, it is INVENTED DATA wearing the
    company's own chart styling, and it went out in a half-year business
    review.

    A slot with nothing in it is dropped instead. An empty column is
    obvious and harmless; a fabricated statistic is neither.
    """
    figures = getattr(archetypes_module, "FIGURES", {}).get(name) or {}
    key = region.get("content")
    if key not in figures:
        return False
    return not content.get(key)


def _paint_layout_background(slide, engine, spec: dict) -> None:
    """Make the layout's background explicit on the slide.

    Four KONE layouts set their background by THEME REFERENCE rather
    than by colour -- `<p:bgRef><a:schemeClr val="bg2"/>` -- and
    renderers disagree about what that resolves to. PowerPoint follows
    the master's clrMap to sand; LibreOffice produces KONE Blue. Same
    file, two different decks.

    Writing the resolved colour onto the slide removes the question. It
    is a no-op where the archetype paints its own background, and where
    the layout states a literal colour it simply restates it.
    """
    if spec.get("background") or spec.get("panels"):
        return
    from pptx.enum.shapes import MSO_SHAPE

    from deckguard.logo import _page_background_hex

    layout = slide.slide_layout
    if _page_background_hex(layout.element) is not None:
        return                      # already a literal colour, unambiguous
    resolved = _page_background_hex(layout.element, layout)
    if not resolved:
        return
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, engine.X(0), engine.X(0),
                                   engine.X(1280), engine.X(720))
    shape.name = "Layout background"
    shape.fill.solid()
    shape.fill.fore_color.rgb = engine._hex(resolved)
    shape.line.fill.background()
    shape.shadow.inherit = False
    style = shape._element.find(
        "{http://schemas.openxmlformats.org/presentationml/2006/main}style")
    if style is not None:
        shape._element.remove(style)
    # behind everything the engine just drew
    spTree = shape._element.getparent()
    spTree.remove(shape._element)
    spTree.insert(2, shape._element)


def _reversed_bands(spec: dict, content: dict, scrim_box) -> list:
    """The (top, bottom) of every white text block sitting on the scrim.

    Only blocks the slide actually fills count -- an archetype that
    declares an eyebrow the author left empty must not have the picture
    darkened where nothing is written.
    """
    _, sy, _, sh = scrim_box
    bands = []
    for region in spec.get("regions", []):
        style = region.get("dg")
        if style is not None:
            if str(style.get("color", "")).upper() not in ("FFFFFF", "FFF"):
                continue
        elif not _is_light_role(region.get("role")):
            # drawn by the engine; only its light roles are reversed out
            continue
        value = content.get(region.get("content"))
        if not value:
            continue
        x, y, w, h = region["box"]
        if y + h <= sy or y >= sy + sh:
            continue
        bands.append((y, y + _typeset_height(region, value)))
    return bands


def _typeset_height(region: dict, value) -> float:
    """Roughly how far down its box a block of text actually reaches.

    Protecting the whole BOX is what turned the full-bleed cover into a
    uniformly dark photograph: the cover's title frame is 448px tall for
    three lines of type, so the scrim covered the middle of the picture
    end to end. Three lines is what needs protecting, not the frame they
    were given.
    """
    _, _, width, height = region["box"]
    style = region.get("dg") or {}
    px = style.get("px")
    if not px:
        match = re.search(r"_i(\d+)_", str(region.get("role") or ""))
        px = int(match.group(1)) if match else 0
    if not px:
        return height

    text = " ".join(str(v) for v in value) if isinstance(value, (list, tuple)) else str(value)
    per_line = max(1, int(width / (px * 0.52)))
    lines = max(1, -(-len(text) // per_line))
    return min(height, lines * px * 1.3)


def _scrim_ramp(box, protect, opacity: int, feather: float = 0.10):
    """Gradient stops that are dark exactly where white type sits.

    A fixed dark-at-both-edges ramp is a guess, and on TEXT_PICTURE_G it
    guessed wrong: the headline starts 60% of the way down its banner,
    where a ramp that clears at the midpoint has recovered barely a
    sixth of its opacity, and the first line read white-on-sunlit-
    pavement. The bands that need protecting are not a mystery -- they
    are the archetype's own reversed-out text boxes -- so the ramp is
    built from them instead of guessed at.

    Returns `(position, alpha)` pairs sampled across the box, each band
    at full opacity with a soft edge so the picture is never cut by a
    visible line.
    """
    _, y, _, h = box
    if not h:
        return [(0, opacity), (100000, opacity)]

    bands = []
    for bx in protect:
        top = max(0.0, min(1.0, (bx[0] - y) / h))
        bottom = max(0.0, min(1.0, (bx[1] - y) / h))
        if bottom > top:
            bands.append((top, bottom))
    if not bands:
        # nothing reversed out over this picture: the brand's plain
        # edge-darkening, which still seats a photo on a white slide
        bands = [(0.0, 0.06), (0.94, 1.0)]

    def cover(position: float) -> float:
        best = 0.0
        for top, bottom in bands:
            if top <= position <= bottom:
                best = 1.0
            elif position < top:
                best = max(best, 1.0 - min(1.0, (top - position) / feather))
            else:
                best = max(best, 1.0 - min(1.0, (position - bottom) / feather))
        return best

    steps = 20
    return [
        (int(round(i / steps * 100000)), int(round(opacity * cover(i / steps))))
        for i in range(steps + 1)
    ]


def _draw_scrim(slide, engine, box, opacity: int = 78, protect=()) -> None:
    """A gradient over a photo so white type stays readable on it.

    The brand specifies this for `COVER_F_FULLBLEED` and never says how,
    and every archetype that reverses type out of a photograph needs the
    same thing: a banner title came out white-on-pale-escalator and was
    close to invisible.

    Dark behind the reversed-out type and clear elsewhere, so it protects
    the eyebrow and the headline without greying out the subject of the
    picture -- which a flat overlay does, and which is why the spec calls
    for a gradient rather than a tint.
    """
    from lxml import etree
    from pptx.enum.shapes import MSO_SHAPE

    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    x, y, w, h = box
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, engine.X(x), engine.X(y), engine.X(w), engine.X(h)
    )
    shape.name = "Photo protection"
    shape.line.fill.background()
    shape.shadow.inherit = False
    style = shape._element.find(
        "{http://schemas.openxmlformats.org/presentationml/2006/main}style")
    if style is not None:
        shape._element.remove(style)

    spPr = shape._element.spPr
    for tag in ("solidFill", "noFill", "gradFill"):
        existing = spPr.find(f"{{{A}}}{tag}")
        if existing is not None:
            spPr.remove(existing)

    grad = etree.SubElement(spPr, f"{{{A}}}gradFill")
    grad.set("rotWithShape", "1")
    stops = etree.SubElement(grad, f"{{{A}}}gsLst")
    for position, alpha in _scrim_ramp(box, protect, opacity):
        stop = etree.SubElement(stops, f"{{{A}}}gs")
        stop.set("pos", str(position))
        colour = etree.SubElement(stop, f"{{{A}}}srgbClr")
        colour.set("val", "141414")
        etree.SubElement(colour, f"{{{A}}}alpha").set("val", str(alpha * 1000))
    lin = etree.SubElement(grad, f"{{{A}}}lin")
    lin.set("ang", "5400000")   # top to bottom
    lin.set("scaled", "0")

    # The gradient must sit directly on the photo and UNDER the type.
    # Appending is only correct when the caller draws the text
    # afterwards; the gallery's ports have the engine draw theirs inside
    # `render_archetype`, so an appended scrim greyed out the headline it
    # was meant to protect. Seating it immediately above the picture is
    # right for both paths.
    _seat_above_picture(shape, box, slide)
    return shape


def _seat_above_picture(shape, box, slide=None) -> None:
    """Move `shape` to just after the picture it is protecting.

    The FIRST substantial one, not the last: a cover carries the logo
    and the tagline as pictures too, and they are added after the type.
    Seating the scrim above those put it over the headline and dimmed
    the very words it exists to make readable.
    """
    from lxml import etree

    tree = shape._element.getparent()
    if tree is None or slide is None:
        return
    left, top, width, height = box
    area = max(1.0, width * height)

    for candidate in slide.shapes:
        if etree.QName(candidate._element).localname != "pic":
            continue
        # Resolved geometry, not the raw `xfrm`: a picture PLACEHOLDER
        # inherits its position from the layout and carries no `xfrm` of
        # its own, so reading the element directly found nothing and the
        # scrim stayed appended -- on top of the headline.
        try:
            px, py = candidate.left / 9525.0, candidate.top / 9525.0
            pw, ph = candidate.width / 9525.0, candidate.height / 9525.0
        except Exception:  # noqa: BLE001 -- a picture without geometry
            continue
        if pw * ph < area * 0.5:      # chrome, not the photograph
            continue
        if px < left + width and px + pw > left and py < top + height and py + ph > top:
            # lxml's own index, never a dict keyed on `id()`: lxml builds
            # a fresh Python proxy on each element access and lets the
            # old one be collected, so those ids are neither stable nor
            # unique. A recycled id matched the wrong element and seated
            # the scrim one shape too late -- over the type.
            try:
                index = tree.index(candidate._element)
            except ValueError:  # pragma: no cover -- not in this tree
                continue
            tree.remove(shape._element)
            tree.insert(index + 1, shape._element)
            return


def _paint_field(slide, engine, fill: str) -> None:
    """Flood the slide with one of the brand's secondary colours.

    The field has to REPLACE the engine's own background rectangle, not
    sit under it. `render_archetype` opens by painting the archetype's
    default fill across the slide, so a field inserted at the bottom of
    the shape tree is covered by sand and only the ink colour survives --
    which is how a blue divider came out as white type on sand, all but
    invisible.
    """
    from pptx.enum.shapes import MSO_SHAPE

    for existing in _full_slide_fills(slide, engine):
        existing.getparent().remove(existing)

    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, engine.X(0), engine.X(0),
                                   engine.X(1280), engine.X(720))
    shape.name = "Colour field"
    shape.fill.solid()
    shape.fill.fore_color.rgb = engine._hex(fill)
    shape.line.fill.background()
    shape.shadow.inherit = False
    style = shape._element.find(
        "{http://schemas.openxmlformats.org/presentationml/2006/main}style")
    if style is not None:
        shape._element.remove(style)
    spTree = shape._element.getparent()
    spTree.remove(shape._element)
    spTree.insert(2, shape._element)


def _full_slide_fills(slide, engine):
    """The plain filled rectangles that cover the whole slide.

    Matched on geometry and fill rather than on name: the engine names
    its background `Rectangle 1`, but that name is not reserved and a
    port could reasonably produce another.
    """
    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    width, height = engine.X(1280), engine.X(720)
    found = []
    for shape in slide.shapes:
        if not shape.has_text_frame or shape.text_frame.text.strip():
            continue
        geom = shape._element.find(f".//{{{A}}}prstGeom")
        if geom is None or geom.get("prst") != "rect":
            continue
        if (shape.left, shape.top) != (0, 0):
            continue
        if abs(shape.width - width) > 1000 or abs(shape.height - height) > 1000:
            continue
        if shape._element.find(f".//{{{A}}}solidFill") is None:
            continue
        found.append(shape._element)
    return found


def _draw(slide, engine, region: dict, value, ink: Optional[str] = None) -> None:
    """Draw one reference-specified block."""
    if value in (None, "", []):
        return
    style = region["dg"]
    if ink:
        style = {**style, "color": ink}
    if style["kind"] == "bullets":
        _draw_bullets(slide, engine, region["box"], value, style, ink)
    elif style["kind"] == "tick":
        _draw_tick(slide, engine, region["box"], value, style)
    else:
        if style.get("zero_is_black") and _reads_as_zero(value):
            # The brand's own instruction: the number that is deliberately
            # zero -- no disruption, no downtime, no escalations -- is the
            # strongest claim on the slide, and reads as a different KIND
            # of claim when it is not in the same blue as the rest.
            style = {**style, "color": "141414"}
        _draw_text(slide, engine, region["box"], value, style)


def _reads_as_zero(value) -> bool:
    return str(value).strip().strip("+%") in ("0", "0.0", "zero", "Zero", "none", "None")


def _draw_tick(slide, engine, box, value, style) -> None:
    """A blue disc with a white check, and its label beside it.

    The only symbol the milestone slide allows, and a glyph rather than
    an emoji -- the brand forbids emoji outright and a coloured emoji
    tick would also ignore the palette.
    """
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

    x, y, w, h = box
    size = style.get("badge", 20)
    disc = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, engine.X(x), engine.X(y), engine.X(size), engine.X(size)
    )
    disc.name = "Tick"
    disc.fill.solid()
    disc.fill.fore_color.rgb = engine._hex(style.get("badge_fill", "1450F5"))
    disc.line.fill.background()
    disc.shadow.inherit = False

    frame = disc.text_frame
    for margin in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(frame, margin, 0)
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    paragraph = frame.paragraphs[0]
    paragraph.alignment = PP_ALIGN.CENTER
    engine._run(paragraph, "\u2713", "Inter", size * 0.6, engine._hex("FFFFFF"))

    gap = style.get("gap", 12)
    _draw_text(slide, engine, [x + size + gap, y, w - size - gap, h], value,
               {**style, "kind": "text"})


def _draw_text(slide, engine, box, value, style) -> None:
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

    frame = engine._tf(slide, box, MSO_ANCHOR.TOP)
    paragraph = frame.paragraphs[0]
    engine._run(
        paragraph, value, style.get("font", "Inter"), style["px"],
        engine._hex(style.get("color", "141414")), caps=style.get("caps", False),
    )
    if style.get("align") == "r":
        paragraph.alignment = PP_ALIGN.RIGHT


def _draw_bullets(slide, engine, box, items, style, ink: Optional[str] = None) -> None:
    """A real list, not a typed dash.

    The brand rule is explicit and the engine breaks it: `_dash_bullets`
    writes an em dash followed by two spaces, which is a character in a
    paragraph, not a list marker. It does not indent, does not hang, does
    not survive editing in PowerPoint's outline view, and cannot nest.

    This writes `buChar` paragraph formatting instead -- marker in KONE
    Blue, text in black, one nested level as the spec allows. A nested
    item is any list entry given as `{"text": ..., "sub": [...]}`.
    """
    from lxml import etree
    from pptx.enum.text import MSO_ANCHOR
    from pptx.util import Pt

    A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

    def mark(paragraph, level: int, px: float) -> None:
        pPr = paragraph._pPr if paragraph._pPr is not None else paragraph._p.get_or_add_pPr()
        pPr.set("lvl", str(level))
        pPr.set("indent", str(-int(px * 0.75 * 12700)))
        pPr.set("marL", str(int((level + 1) * px * 0.9 * 0.75 * 12700)))
        colour = etree.SubElement(pPr, f"{{{A_NS}}}buClr")
        srgb = etree.SubElement(colour, f"{{{A_NS}}}srgbClr")
        # a blue marker vanishes on a blue field
        srgb.set("val", ink or "1450F5")
        etree.SubElement(pPr, f"{{{A_NS}}}buSzPct").set("val", "100000")
        etree.SubElement(pPr, f"{{{A_NS}}}buFont").set("typeface", "Arial")
        etree.SubElement(pPr, f"{{{A_NS}}}buChar").set("char", "•" if level == 0 else "◦")

    frame = engine._tf(slide, box, MSO_ANCHOR.TOP)
    first = True
    for item in items if isinstance(items, (list, tuple)) else [items]:
        text = item.get("text") if isinstance(item, dict) else item
        children = item.get("sub", []) if isinstance(item, dict) else []
        for level, line, px in [(0, text, style["px"])] + [
            (1, child, style["nested_px"]) for child in children
        ]:
            paragraph = frame.paragraphs[0] if first else frame.add_paragraph()
            first = False
            paragraph.space_after = Pt(px * style.get("lead", 0.35))
            engine._run(paragraph, line, "Inter", px, engine._hex(ink or "141414"))
            mark(paragraph, level, px)


# --------------------------------------------------------------------------
# building and installing
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# refinements from the rendered reference
# --------------------------------------------------------------------------
#
# `LAYOUTS.md` is a placeholder map, not a design. It carries four
# content roles, and 109 of its 321 boxes are the single label
# `Text/body` -- so binding it alone produces a headline over an
# undifferentiated paragraph where the design has an eyebrow, a real
# bulleted list with KONE Blue markers, and a nested level. Measured:
# the reference slides average 18.6 elements, generated archetypes 3.6.
#
# The design lives in the `.dc.html` files. These entries transcribe it
# for the archetypes that carry the most decks, and overlay the
# generated geometry. Each `dg` block is drawn by `render` rather than
# by the engine, whose ROLE_STYLE has no 34px title and no real bullet
# support. Everything here is read off the reference markup -- box,
# size and colour -- not invented.
#
# This is deliberately partial. Extending it is how the rest of the
# vocabulary gets its fidelity back; a fidelity harness should drive
# which archetype is worth doing next.

def _text(x, y, w, h, key, px, *, font="Inter", color="141414", caps=False, align="l"):
    return {"role": "dg_text", "box": [x, y, w, h], "content": key,
            "dg": {"kind": "text", "px": px, "font": font, "color": color,
                   "caps": caps, "align": align}}


def _bullets(x, y, w, h, key, px, nested_px=None, lead=0.35):
    return {"role": "dg_bullets", "box": [x, y, w, h], "content": key,
            "dg": {"kind": "bullets", "px": px, "nested_px": nested_px or px - 2,
                   "lead": lead}}


_REFINEMENTS: dict[str, dict] = {
    # KoneDeck slide 4 -- eyebrow, 34px title, disc bullets with a
    # nested circle level. The workhorse of every deck.
    "title_content": {"regions": [
        _text(45, 47, 917, 22, "eyebrow", 12, font="KONE Information", color="1450F5", caps=True),
        _text(45, 91, 917, 104, "title", 34),
        _bullets(45, 227, 917, 402, "bullets", 19, nested_px=17),
    ]},
    # ArchetypeLibraryB slide 07
    "title_subtitle_content_a": {"regions": [
        _text(45, 91, 917, 68, "title", 30),
        _text(45, 159, 917, 36, "subtitle", 17),
        _bullets(45, 227, 917, 402, "bullets", 18),
    ]},
    # KoneDeck slide 6 -- two bulleted columns, each with its own label
    "two_content": {
        "regions": [_text(45, 91, 1189, 104, "title", 34)],
        "groups": [{"content": "items", "origins": [[45, 227], [657, 227]], "regions": [
            _text(0, 0, 578, 22, "label", 12, font="KONE Information", color="1450F5", caps=True),
            _bullets(0, 30, 578, 372, "bullets", 17),
        ]}],
    },
    # ArchetypeLibraryB slide 09 -- the title is in the DESIGN but not
    # in the master layout, so binding LAYOUTS.md alone loses it and the
    # slide comes out headless.
    "three_content": {
        "regions": [_text(45, 91, 1189, 45, "title", 32)],
        "groups": [{"content": "items", "origins": [[45, 227], [453, 227], [861, 227]],
                    "regions": [
                        _text(0, 0, 374, 30, "heading", 20),
                        _text(0, 40, 374, 363, "text", 16),
                    ]}],
    },
    # ArchetypeLibraryB slide 08 -- narrow title column, wide bullets
    "two_content_narrow_title": {"regions": [
        _text(45, 91, 374, 104, "title", 28),
        _text(45, 227, 374, 402, "body", 16),
        _bullets(453, 227, 781, 402, "bullets", 18),
    ]},
    # KoneDeck slide 3. The gallery port of this bound the title into
    # the RIGHT-hand box and emitted no number at all -- which is the
    # one thing a numbered divider is for. The reference puts the
    # section label and title left, and a 420px numeral right.
    # Agenda A. The gallery port emitted four separate one-line text
    # boxes, so an agenda could only ever have exactly four items and
    # they were not a list -- no markers, no hanging indent, nothing
    # PowerPoint's outline view could edit. One bulleted box instead,
    # on the master's own 578x448 body area, with the full-height photo
    # the layout already declares.
    "agenda_a_table": {
        "regions": [
            {"role": "picture", "box": [759, 0, 521, 720], "content": "photo"},
            _text(45, 39, 578, 36, "eyebrow", 14,
                  font="KONE Information", color="1450F5", caps=True),
            _text(45, 91, 578, 60, "title", 40),
            # an agenda is four or five short lines in a 448px column;
            # at body size they huddle in the top corner and leave the
            # rest of the slide empty. Bigger type, and air between the
            # items, so the list occupies the space it is given.
            _bullets(45, 195, 578, 434, "items", 24, lead=1.15),
        ],
    },

    # Corrected against a real deck, which uses this layout five times.
    # The gallery port and the HTML reference both put the title left
    # and the numeral right; the master's own boxes -- and every real
    # slide -- do the opposite. `Text/body` at 45 carries the number,
    # `Title` at 453 carries the words.
    #
    # Colour is chosen per slide rather than fixed. The layout's own
    # background resolves to sand, which reads as washed out against
    # the rest of the deck; a divider is the one place the brand's
    # secondary palette is meant to carry a whole slide. `colour` in
    # the content picks one, and the ink follows the brand rule --
    # blue field takes white type, a secondary field takes black.
    "divider_numbering": {"field": True, "regions": [
        _text(45, 91, 374, 300, "number", 190),
        _text(453, 91, 578, 120, "eyebrow", 13),
        _text(453, 130, 578, 400, "title", 46),
    ]},

    # The next two come from REAL decks rather than the HTML reference,
    # because real decks disagree with it about what these layouts are
    # for. Across two on-brand KONE decks, `Text and picture A` is used
    # 18 times and `Text and picture G` 8 -- more than every other
    # layout combined -- and both carry a pattern the archetypes had no
    # form for: a grid of icon-plus-short-text cells. Slides using them
    # average 7-10 text blocks against the 3 regions bound from the
    # placeholder map.
    #
    # Both keep their plain form too. The engine skips a region whose
    # content key is missing, so one spec serves both: supply `body` and
    # get the paragraph version, supply `items` and get the grid.

    # Measured off slides 6 (plain) and 22 (2x2 grid) of the escalator
    # portfolio deck.
    "text_picture_a": {
        "regions": [
            {"role": "picture", "box": [759, 0, 521, 720], "content": "image"},
            _text(45, 39, 917, 36, "eyebrow", 14,
                  font="KONE Information", color="1450F5", caps=True),
            _text(45, 91, 577, 104, "title", 34),
            _text(45, 227, 577, 402, "body", 16),
        ],
        "groups": [{
            "content": "items",
            "origins": [[45, 181], [349, 181], [45, 405], [349, 405]],
            "regions": [
                {"role": "icon", "box": [0, 0, 60, 60]},
                _text(0, 75, 274, 149, "text", 15),
            ],
        }],
    },

    # Measured off slides 4 (numbered) and 7 (icons) of the same deck:
    # a banner photo across the top with the eyebrow reversed out of it,
    # then six cells along the bottom.
    "text_picture_g": {
        # only when there IS a photo -- a scrim over white is a grey band
        "scrims": [{"box": [0, 0, 1280, 440], "content": "image"}],
        "regions": [
            {"role": "picture", "box": [0, 0, 1280, 440], "content": "image"},
            _text(45, 39, 917, 36, "eyebrow", 14,
                  font="KONE Information", color="FFFFFF", caps=True),
            _text(45, 262, 697, 125, "title", 40, color="FFFFFF"),
            _text(45, 470, 1190, 40, "body", 16),
        ],
        "groups": [{
            "content": "items",
            "origins": [[45, 476], [249, 476], [453, 476], [657, 476], [861, 476], [1065, 476]],
            "regions": [
                {"role": "icon", "box": [0, 0, 60, 60]},
                _text(0, 71, 170, 83, "text", 15),
            ],
        }],
    },
}

# Refinements that must REPLACE an existing registration rather than
# defer to it. `install` normally leaves a hand-built archetype alone,
# but these are transcribed from the current rendered reference while
# the incumbent came from the superseded gallery markup -- so here the
# newer source wins.
_OVERRIDE = frozenset({"divider_numbering", "agenda_a_table"})


# Archetypes `ARCHETYPES.md` marks `no master`. All but one are already
# hand-built in the engine; TIMELINE is Grade A -- one of the twelve
# that carry most real decks -- so it is transcribed here from its
# reference rendering (`KoneDeck.dc.html` slide 10) rather than left as
# the single hole in the vocabulary. The rail is a 2px hairline behind
# four evenly spaced nodes on the 1190px content width.
_NO_MASTER: dict[str, dict] = {
    "timeline": {
        "regions": [
            {"role": "title", "box": [45, 91, 917, 45], "content": "title"},
            {"role": "axis", "box": [45, 251, 1190, 0]},
        ],
        "groups": [{
            "content": "items",
            "origins": [[45, 240], [342, 240], [639, 240], [936, 240]],
            "regions": [
                {"role": "stat_label", "box": [0, 44, 269, 40], "content": "period"},
                {"role": "body", "box": [0, 92, 269, 120], "content": "text"},
            ],
        }],
    },
}


def build_archetypes(
    grades: Iterable[str] = ("A", "B", "C", "D"),
) -> dict[str, dict]:
    """Every canonical archetype that names a master layout, as engine
    dicts keyed by its `lower_snake` engine key.

    Twins are included, resolved to their parent's geometry. The spec's
    advice ("use the parent") is about which one a designer should
    reach for; a user who writes `TITLE_CONTENT_B` in a brief still
    needs it to render, and by the spec's own definition a twin is
    geometrically identical to its parent.
    """
    layouts, archetypes = load_spec()
    wanted = set(grades)
    out: dict[str, dict] = {}

    for arch in archetypes.values():
        if arch.grade not in wanted:
            continue
        source = arch
        if arch.twin_of:
            source = archetypes.get(arch.twin_of, arch)
        if not source.master:
            if arch.engine_key in _NO_MASTER:
                out[arch.engine_key] = _NO_MASTER[arch.engine_key]
            continue
        layout = layouts.get(source.master)
        if layout is None:
            continue
        spec = _bind_roles(layout)
        # a twin inherits its parent's refinement along with its geometry
        refinement = _REFINEMENTS.get(arch.engine_key) or (
            _REFINEMENTS.get(source.engine_key) if arch.twin_of else None
        )
        if refinement:
            # the reference wins on everything it describes; anything it
            # is silent about (a panel, a picture) keeps its bound form
            spec = {**spec, **refinement}
        if not spec["regions"] and not spec.get("groups") and not arch.is_built:
            # A layout with no bindable content is a blank slide -- real
            # for `BLANK` (logo and nothing else, and the designated
            # replacement for the cut `END_LOGO`), meaningless for a
            # layout that was never built.
            continue
        out[arch.engine_key] = spec
    return out


def _correct_grey_ink(archetypes_module) -> list[str]:
    """Take the engine's caption grey off the brand's type roles.

    The brand allows exactly three inks for type -- black, white and (for
    KONE Information only) blue -- and the engine sets `caption`,
    `body_muted` and `attribution` in a `#727272` grey that appears
    nowhere in the palette. It is visible on any deck carrying a quote or
    a captioned statistic, which is most of them.

    Corrected here rather than in the engine because the engine is
    vendored from the skill and is replaced wholesale when the skill
    updates; a patch applied at install time survives that.
    """
    engine = getattr(archetypes_module, "E", None)
    styles = getattr(engine, "ROLE_STYLE", None)
    if not styles:
        return []
    grey = getattr(engine, "GREY", None)
    black = getattr(engine, "BLACK", None)
    if grey is None or black is None:
        return []

    corrected = []
    for role, style in list(styles.items()):
        if len(style) < 3 or style[2] != grey:
            continue
        styles[role] = tuple(black if i == 2 else v for i, v in enumerate(style))
        corrected.append(role)
    return sorted(corrected)


def install(archetypes_module, grades: Iterable[str] = ("A", "B", "C", "D")) -> list[str]:
    """Register the generated archetypes into the engine's registry.

    Anything already implemented -- under its canonical name or under
    one of its `ARCHETYPES.md` aliases -- is left alone. Those were
    built against a real rendering; this module works from a coarser
    description and must not clobber them.
    """
    registry = archetypes_module.ARCHETYPES
    _, meta = load_spec()
    by_key = {a.engine_key: a for a in meta.values()}
    _correct_grey_ink(archetypes_module)
    for existing in registry.values():
        if isinstance(existing, dict):
            lift_low_rows(existing)

    added: list[str] = []
    # Archetypes with no master layout behind them, so `build_archetypes`
    # cannot derive them. Registered like any other, and equally never
    # allowed to overwrite an incumbent.
    samples = getattr(archetypes_module, "SAMPLES", None)
    for key, spec in _EXTRAS.items():
        if key not in registry:
            registry[key] = copy.deepcopy(spec)
            added.append(key)
        meta = _EXTRA_META.get(key, {})
        if isinstance(samples, dict) and meta.get("sample") and key not in samples:
            samples[key] = copy.deepcopy(meta["sample"])

    for key, spec in build_archetypes(grades).items():
        arch = by_key.get(key)
        if key in _OVERRIDE and key in registry:
            # keep the incumbent's background, replace its geometry
            registry[key] = {
                **({"background": registry[key]["background"]}
                   if "background" in registry[key] else {}),
                **spec,
            }
            added.append(key)
            continue
        if key in registry:
            continue
        if arch and any(alias in registry for alias in arch.aliases):
            continue
        registry[key] = spec
        added.append(key)

    if added:
        try:  # the matcher caches signatures; new names must invalidate them
            from deckguard.skill_bridge import invalidate_archetype_caches

            invalidate_archetype_caches()
        except Exception:
            pass
    return sorted(added)


def coverage(archetypes_module) -> dict[str, tuple[int, int]]:
    """{grade: (implemented, total)} for the canonical vocabulary --
    what the tool can actually render, by grade."""
    _, meta = load_spec()
    registry = archetypes_module.ARCHETYPES
    tally: dict[str, list[int]] = {}
    for arch in meta.values():
        got = arch.engine_key in registry or any(a in registry for a in arch.aliases)
        slot = tally.setdefault(arch.grade, [0, 0])
        slot[0] += bool(got)
        slot[1] += 1
    return {g: (v[0], v[1]) for g, v in sorted(tally.items())}


# --------------------------------------------------------------------------
# whole-deck assembly
# --------------------------------------------------------------------------


def protect_photo_cover(slide, engine=None) -> bool:
    """Scrim the master's own cover, which arrives without one.

    The retained Cover F is a full-bleed photograph with the title
    reversed out of it, and the brand asks for a gradient there. The
    master ships none -- the layout assumes a designer will choose a
    photograph with a quiet corner. A deck built from a brief picks its
    photograph automatically, so the assumption does not hold, and a
    half-year review came back with a white headline lost in a sunlit
    atrium.

    Protects the type that is actually written, sized to the type, so
    the photograph keeps the rest of the frame.
    """
    import importlib

    if engine is None:
        engine = importlib.import_module("kone_engine")

    P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    picture = None
    for shape in slide.shapes:
        if shape._element.tag != f"{P}pic":
            continue
        if shape.width >= engine.X(1200) and shape.height >= engine.X(680):
            picture = shape
            break
    if picture is None:
        return False

    bands = []
    for shape in slide.shapes:
        if shape is picture or not getattr(shape, "has_text_frame", False):
            continue
        text = shape.text_frame.text.strip()
        if not text:
            continue
        top = shape.top / 9525.0
        width = shape.width / 9525.0
        height = shape.height / 9525.0
        px = _run_px(shape) or (64.0 if height > 200 else 16.0)
        region = {"box": [0, top, width, height], "dg": {"px": px}}
        bands.append((top, top + _typeset_height(region, text)))
    if not bands:
        return False

    _draw_scrim(slide, engine, [0, 0, 1280, 720], protect=bands)
    return True


def _run_px(shape) -> Optional[float]:
    """The first run's size in px, when the shape states one."""
    try:
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                if run.font.size is not None:
                    return run.font.size.pt / 0.75
    except Exception:  # noqa: BLE001 -- inherited sizing is normal
        return None
    return None


def _layout_for(archetype, by_partname, blank):
    """The master layout an archetype belongs on, or blank."""
    if archetype is None or not archetype.master:
        return blank
    return by_partname.get(archetype.master) or blank


def _strip_empty_placeholders(slide) -> None:
    """Take the layout's prompt text off a slide we are drawing over.

    Cloned placeholders arrive carrying "Click to add title". The
    archetype draws its own text boxes on top, so the prompts sit
    underneath as live text -- invisible in most renders, and there in
    the outline view and in search.
    """
    for shape in list(slide.shapes):
        if shape.is_placeholder:
            shape._element.getparent().remove(shape._element)


def build_deck(spec: dict, out_path, archetypes_module=None, report=None) -> str:
    """Assemble a deck from a spec, each archetype on its OWN layout.

    The skill's own `kone_deck_creator.build_deck` puts every archetype
    on the BLANK layout and calls `archetypes.render` directly. That
    bypasses everything this module adds, and it showed on the first
    deck a user built through the web tool: icons came out as the
    engine's rasterised PNGs and its blue placeholder chips instead of
    the real KONE pictograms as editable shapes, covers had no scrim so
    white headlines sat on sunlit photographs, dividers came out sand,
    photographs were stretched rather than cropped, and a slide acquired
    a donut chart nobody asked for.

    Same shape as the skill's builder -- master cover, generated body,
    master "Thank you" -- but each body slide is added on the layout its
    archetype actually belongs to, its prompt placeholders are stripped,
    and it renders through `render` above.
    """
    import posixpath

    from pptx import Presentation
    from pptx.oxml.ns import qn

    if archetypes_module is None:
        # Through the loader, never a bare `import archetypes`: the
        # registry is only correct once the gallery's ports and then
        # THIS module's refinements have been merged, in that order.
        # `gallery.install` overwrites what it finds, so installing it
        # second silently reverted the refined agenda to a port with no
        # bullets and the divider to one with no number and no colour.
        from deckguard.skill_bridge import _load_archetypes

        archetypes_module = _load_archetypes()

    creator = _load_creator()
    prs = Presentation(creator.MASTER)
    slide_ids = prs.slides._sldIdLst
    originals = list(slide_ids)
    intro, outro = originals[creator.INTRO_IDX], originals[creator.OUTRO_IDX]
    if spec.get("title"):
        creator._set_title(list(prs.slides)[creator.INTRO_IDX], spec["title"])

    _, meta = load_spec()
    by_engine_key: dict[str, object] = {}
    for archetype in meta.values():
        by_engine_key.setdefault(archetype.engine_key, archetype)
        for alias in archetype.aliases:
            by_engine_key.setdefault(alias, archetype)

    by_partname = {
        posixpath.basename(layout.part.partname).replace(".xml", ""): layout
        for layout in prs.slide_layouts
    }
    blank = next(l for l in prs.slide_layouts if l.name.strip().lower() == "blank")

    for position, entry in enumerate(spec.get("slides") or [], start=1):
        name = entry.get("archetype")
        content = {k: v for k, v in entry.items() if k != "archetype"}
        archetype = by_engine_key.get(str(name).lower())
        slide = prs.slides.add_slide(_layout_for(archetype, by_partname, blank))
        _strip_empty_placeholders(slide)
        if report is not None:
            dropped = unread_keys(archetypes_module.ARCHETYPES.get(name) or {}, content)
            if dropped:
                report.setdefault("dropped", {})[position] = (name, dropped)
        render(slide, name, content, archetypes_module)

    body = [el for el in list(slide_ids) if el not in originals]
    keep = {id(intro), id(outro), *(id(b) for b in body)}
    for element in originals:
        if id(element) not in keep:
            prs.part.drop_rel(element.get(qn("r:id")))
            slide_ids.remove(element)
    for element in list(slide_ids):
        slide_ids.remove(element)
    slide_ids.append(intro)
    for element in body:
        slide_ids.append(element)
    slide_ids.append(outro)

    protect_photo_cover(list(prs.slides)[0])

    prs.save(str(out_path))
    return str(out_path)


def _load_creator():
    from deckguard.skill_bridge import _load_creator as load

    return load()


# --------------------------------------------------------------------------
# what an archetype actually reads
# --------------------------------------------------------------------------


def content_keys(spec: dict) -> list[str]:
    """The content keys a spec reads, annotated with their shape.

    The planning prompt described archetypes from `catalog.json` slots
    and the skill's `SAMPLES`, and 39 of the 80 registered archetypes
    have neither -- the model was told a name and left to guess. Worse,
    a stale sample is an active lie: `agenda_a_table`'s said
    `text1..text4` while the renderer had been rebuilt to read `items`,
    so a planner did as it was told, emitted four keys nothing reads,
    and the agenda came out as a title on an empty slide.

    Derived from the live registry, so it cannot drift.
    """
    out: list[str] = []
    for region in spec.get("regions", []):
        key = region.get("content")
        if not key:
            continue
        out.append(f"{key} ({_shape_of(region)})")
    for group in spec.get("groups", []):
        key = group.get("content")
        if not key:
            continue
        fields = [
            # an icon region carries no content key of its own, but the
            # caller names its pictogram per item -- omitting it from the
            # guide is why decks came back with default icons
            "icon" if r.get("role") == "icon" else r.get("content")
            for r in group.get("regions", [])
            if r.get("content") or r.get("role") == "icon"
        ]
        n = len(group.get("origins") or [])
        if fields:
            shape = "{" + ", ".join(fields) + "}"
            out.append(f"{key} (list of up to {n} × {shape})")
        else:
            out.append(f"{key} (list of up to {n})")
    return out


def _shape_of(region: dict) -> str:
    role = str(region.get("role") or "")
    if role in _PICTURE_REGION_ROLES or role == "image":
        return "filled automatically -- do not supply"
    if role == "icon":
        return "icon name"
    style = region.get("dg") or {}
    if style.get("kind") == "bullets":
        return "list of strings, or {text, sub:[...]}"
    if "stat" in role or "value" in role:
        return "short figure, e.g. 70%"
    return "text"


def unread_keys(spec: dict, content: dict) -> list[str]:
    """Content the archetype has nowhere to put.

    Silent loss is the failure mode this catches: a planner emitted
    `text1..text4` for an agenda whose renderer reads `items`, and the
    slide came out as a title on an empty half. Nothing said so -- not
    the build, not the review page, not the audit. The deck simply had
    less in it than the brief did.
    """
    known = {k.split(" (")[0] for k in content_keys(spec)}
    ignore = {"archetype", "colour", "color", "notes"}
    return sorted(
        key for key, value in (content or {}).items()
        if key not in known and key not in ignore and value not in (None, "", [], {})
    )


# --------------------------------------------------------------------------
# closing dead bands
# --------------------------------------------------------------------------

# How much empty vertical space between a title and the row beneath it
# counts as a hole rather than as breathing room, and the gap left after
# closing one. 69px is the master's own step: a 104px title starting at
# 91 ends at 195, and the grid's content start is 264.
_DEAD_BAND = 200.0
_TITLE_GAP = 69.0


def lift_low_rows(spec: dict) -> int:
    """Pull an item row up under its title when nothing fills the middle.

    Four archetypes place their row of items in the bottom third with
    only a title above -- geometry taken from real KONE slides where a
    paragraph of body copy filled the band between. These archetypes have
    no such paragraph, so a Q2 review came back with 248px of blank sand
    between "Plan of action" and the six things it listed.

    Only fires where the band is demonstrably empty: no region and no
    other group occupies it. Rows only ever move UP, so nothing below can
    be collided into. Returns how many groups moved.
    """
    groups = spec.get("groups") or []
    if not groups:
        return 0

    solid = [
        r for r in spec.get("regions", [])
        if not _is_full_bleed(r["box"])
    ]
    moved = 0
    for group in sorted(groups, key=lambda g: min((o[1] for o in g["origins"]), default=0)):
        origins = group.get("origins") or []
        if not origins:
            continue
        top = min(o[1] for o in origins)
        bottoms = [r["box"][1] + r["box"][3] for r in solid if r["box"][1] + r["box"][3] <= top]
        bottoms += [
            max(o[1] for o in other["origins"]) + _group_height(other)
            for other in groups
            if other is not group and other.get("origins")
            and max(o[1] for o in other["origins"]) + _group_height(other) <= top
        ]
        if not bottoms:
            continue
        floor = max(bottoms)

        # anything straddling the band means the space is spoken for
        straddles = any(
            r["box"][1] < top and r["box"][1] + r["box"][3] > floor for r in solid
        ) or any(
            min(o[1] for o in other["origins"]) < top
            and max(o[1] for o in other["origins"]) + _group_height(other) > floor
            for other in groups if other is not group and other.get("origins")
        )
        if straddles:
            continue

        delta = (top - floor) - _TITLE_GAP
        if top - floor <= _DEAD_BAND or delta <= 0:
            continue
        group["origins"] = [[x, y - delta] for x, y in origins]
        moved += 1
    return moved


def _group_height(group: dict) -> float:
    return max((r["box"][1] + r["box"][3] for r in group.get("regions", [])), default=0.0)


def _is_full_bleed(box) -> bool:
    """A background photograph is not a block the row has to clear."""
    _, _, w, h = box
    return w >= 1200 and h >= 680


# --------------------------------------------------------------------------
# archetypes with no master layout behind them
# --------------------------------------------------------------------------

# The stat band is five cells across 1190 with a 40px gap, so each cell
# is 206 wide and they start every 246px. The row is 152 tall and
# vertically centred on content 90 tall, which puts the number at 307
# and its label at 381.
_MILESTONE_STAT_X = [45 + i * 246 for i in range(5)]

# Routing and a worked example for the extras. `catalog.json` and
# `SAMPLES` describe the archetypes the skill shipped with; an extra
# registered from here is invisible to both, so a planner would see the
# key list and no reason to ever choose it.
_EXTRA_META: dict[str, dict] = {
    "milestone_slide": {
        "purpose": "A finished thing, its proof, and who did it -- one shareable "
                   "slide built from an announcement. Not for a proposal, a "
                   "decision request, or anything needing an argument across "
                   "several beats; those are decks.",
        "keywords": ["milestone", "announcement", "launch", "now live",
                     "migration complete", "programme win", "recognition",
                     "thank you", "transformation", "results", "one slide"],
        "sample": {
            "eyebrow": "Marketing Hub · Request Management",
            "title": "From Monday.com to ServiceNow in six weeks",
            "lede": "Delivered by KBS, Global Marketing, Frontlines and Business "
                    "Partner — with full data continuity.",
            "done": [{"text": "MVP pilot-tested and now live"},
                     {"text": "100% transition completed"}],
            "stats": [{"value": "6", "label": "Weeks end to end"},
                      {"value": "100+", "label": "Users migrated"},
                      {"value": "12", "label": "Frontlines"},
                      {"value": "3+3", "label": "Regions + global teams"},
                      {"value": "0", "label": "Business disruption"}],
            "scope_label": "The frontlines",
            "scope": "KSEA · KMTA · KANZ · KEI · EEM · DACH · GIN · Nordics",
            "next_label": "What's next",
            "next": ["Hypercare and small fixes ongoing",
                     "Power BI reporting integration underway, targeted for Q2"],
            "credits_label": "Thank you",
            "credits": "Arvind, Suresh Kumar, Rupesh and the Hub specialists",
            "classification": "KONE Internal",
        },
    },
}

# One slide, from one announcement email. It exists because the master
# has no recognition slide: a finished thing, its proof, and who did it.
# Transcribed from kone-milestone-slide's published geometry rather than
# eyeballed, so it stays comparable with the reference.
_EXTRAS: dict[str, dict] = {
    "milestone_slide": {
        "background": "FFFFFF",
        "panels": [{"box": [0, 276, 1280, 196], "fill": "F3EEEA"}],
        "rules": [
            {"box": [45, 424, 1190, 1], "fill": "141414"},     # over the scope strip
            {"box": [45, 544, 700, 1], "fill": "D0D0D0"},      # under "What's next"
            {"box": [880, 544, 355, 1], "fill": "D0D0D0"},     # under "Thank you"
        ],
        "regions": [
            _text(45, 47, 790, 20, "eyebrow", 12,
                  font="KONE Information", color="1450F5", caps=True),
            _text(45, 82, 790, 104, "title", 42),
            _text(45, 186, 700, 76, "lede", 17),

            _text(45, 438, 150, 18, "scope_label", 11,
                  font="KONE Information", color="1450F5", caps=True),
            _text(205, 438, 1030, 18, "scope", 13, font="KONE Information"),

            _text(45, 520, 700, 18, "next_label", 12,
                  font="KONE Information", color="1450F5", caps=True),
            _bullets(45, 560, 700, 110, "next", 16, lead=0.5),

            _text(880, 520, 355, 18, "credits_label", 12,
                  font="KONE Information", color="1450F5", caps=True),
            _text(880, 560, 355, 100, "credits", 16),

            _text(45, 664, 400, 16, "classification", 11,
                  font="KONE Information", caps=True),
        ],
        "groups": [
            {
                "content": "stats",
                "origins": [[x, 307] for x in _MILESTONE_STAT_X],
                "regions": [
                    {"role": "dg_text", "box": [0, 0, 206, 66], "content": "value",
                     "dg": {"kind": "text", "px": 62, "font": "KONE Information",
                            "color": "1450F5", "caps": False, "align": "l",
                            "zero_is_black": True}},
                    {"role": "dg_text", "box": [0, 74, 206, 32], "content": "label",
                     "dg": {"kind": "text", "px": 12, "font": "KONE Information",
                            "color": "141414", "caps": True, "align": "l"}},
                ],
            },
            {
                "content": "done",
                "origins": [[880, 186], [880, 230], [880, 274]],
                "regions": [
                    {"role": "dg_tick", "box": [0, 0, 355, 30], "content": "text",
                     "dg": {"kind": "tick", "px": 16, "font": "Inter",
                            "color": "141414", "caps": False, "align": "l"}},
                ],
            },
        ],
    },
}
