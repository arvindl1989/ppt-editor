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


def pictograms() -> list[str]:
    """The real KONE pictograms, as raster paths.

    Only three exist (`arrow`, `cloud`, `connect`) against archetypes
    that want up to five, so callers cycle them -- which is what the
    HTML reference does too. They are rasterised beside their SVGs
    because a .pptx cannot take an SVG directly; `logo.attach_svg` puts
    the vector back on afterwards.
    """
    base = spec_dir().parent.parent / "icons"
    return [str(p) for p in sorted(base.glob("*.png"))]


def _icon_slots(spec: dict) -> int:
    n = sum(1 for r in spec.get("regions", []) if r.get("role") == "icon")
    for group in spec.get("groups", []):
        per = sum(1 for r in group["regions"] if r.get("role") == "icon")
        n += per * len(group["origins"])
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

    marks = pictograms()
    slots = _icon_slots(spec)
    icons = [marks[i % len(marks)] for i in range(slots)] if marks and slots else None

    engine.render_archetype(
        slide, spec, filled, icons=icons, bg=getattr(archetypes_module, "BG", {}).get(name)
    )


# --------------------------------------------------------------------------
# building and installing
# --------------------------------------------------------------------------


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
