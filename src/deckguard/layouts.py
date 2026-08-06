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
    return spec


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

    filled = dict(content)
    for key, filename in getattr(archetypes_module, "FIGURES", {}).get(name, {}).items():
        filled.setdefault(key, os.path.join(archetypes_module._icondir, filename))

    # Regions the reference describes more precisely than ROLE_STYLE can
    # express are drawn here and withheld from the engine.
    engine_spec = {k: v for k, v in spec.items() if k not in ("regions", "groups")}
    engine_spec["regions"] = [r for r in spec.get("regions", []) if "dg" not in r]
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
    _paint_layout_background(slide, engine, spec)
    for scrim in spec.get("scrims", []):
        if scrim.get("content") in (None, "") or filled.get(scrim.get("content")):
            _draw_scrim(slide, engine, scrim["box"], scrim.get("opacity", 62))
    for region in spec.get("regions", []):
        if "dg" in region:
            _draw(slide, engine, region, filled.get(region.get("content")))
    for group in spec.get("groups", []):
        items = filled.get(group["content"]) or []
        for (ox, oy), item in zip(group["origins"], items):
            for region in group["regions"]:
                if "dg" not in region:
                    continue
                rx, ry, rw, rh = region["box"]
                shifted = {**region, "box": [ox + rx, oy + ry, rw, rh]}
                _draw(slide, engine, shifted, (item or {}).get(region.get("content")))


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


def _draw_scrim(slide, engine, box, opacity: int = 62) -> None:
    """A gradient over a photo so white type stays readable on it.

    The brand specifies this for `COVER_F_FULLBLEED` and never says how,
    and every archetype that reverses type out of a photograph needs the
    same thing: a banner title came out white-on-pale-escalator and was
    close to invisible.

    Dark at the top and bottom edges, clear through the middle, so it
    protects the eyebrow and the headline without greying out the
    subject of the picture -- which a flat overlay does, and which is
    why the spec calls for a gradient rather than a tint.
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
    for position, alpha in ((0, opacity), (45000, 0), (100000, opacity)):
        stop = etree.SubElement(stops, f"{{{A}}}gs")
        stop.set("pos", str(position))
        colour = etree.SubElement(stop, f"{{{A}}}srgbClr")
        colour.set("val", "141414")
        etree.SubElement(colour, f"{{{A}}}alpha").set("val", str(alpha * 1000))
    lin = etree.SubElement(grad, f"{{{A}}}lin")
    lin.set("ang", "5400000")   # top to bottom
    lin.set("scaled", "0")

    # the gradient must sit directly on the photo, under everything else
    # that follows -- appending puts it last in paint order, which is
    # where the text is about to go
    return shape


def _draw(slide, engine, region: dict, value) -> None:
    """Draw one reference-specified block."""
    if value in (None, "", []):
        return
    style = region["dg"]
    if style["kind"] == "bullets":
        _draw_bullets(slide, engine, region["box"], value, style)
    else:
        _draw_text(slide, engine, region["box"], value, style)


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


def _draw_bullets(slide, engine, box, items, style) -> None:
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
        srgb.set("val", "1450F5")
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
            paragraph.space_after = Pt(px * 0.35)
            engine._run(paragraph, line, "Inter", px, engine._hex("141414"))
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


def _bullets(x, y, w, h, key, px, nested_px=None):
    return {"role": "dg_bullets", "box": [x, y, w, h], "content": key,
            "dg": {"kind": "bullets", "px": px, "nested_px": nested_px or px - 2}}


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
    # Corrected against a real deck, which uses this layout five times.
    # The gallery port and the HTML reference both put the title left
    # and the numeral right; the master's own boxes -- and every real
    # slide -- do the opposite. `Text/body` at 45 carries the number,
    # `Title` at 453 carries the words.
    "divider_numbering": {"regions": [
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
_OVERRIDE = frozenset({"divider_numbering"})


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

    added: list[str] = []
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
