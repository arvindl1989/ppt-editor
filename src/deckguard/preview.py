"""Schematic slide previews for the Transform review page -- pure HTML
renderers, no rendering engine, no external dependencies.

This deliberately does NOT try to be pixel-accurate (that would need
LibreOffice on the server -- heavy and unverified on the current
deploy). It draws honest wireframes from data deckguard already
extracts: real positions, sizes, fills, and text.

Three renderers, one per thing a review card can show:

- `slide_preview_html(SlideRecord, ...)` -- the CURRENT slide, from the
  same inventory snapshot audit uses. Works for every slide, including
  ineligible ones (a table/chart shows as a labeled box).
- `archetype_preview_html(name, content)` -- a PROPOSED archetype
  slide, drawn from the skill's own ARCHETYPES region/group data and
  ROLE_STYLE table (imported at call time, so a skill update changes
  these previews with zero code change here -- same contract as the
  renderer itself).
- `org_layout_preview_html(layout, ...)` -- a PROPOSED org-template
  rebuild: the layout's real placeholder geometry with the slide's own
  verbatim content placed in reading order.

All three emit a fixed-aspect container (`aspect-ratio:1280/720`,
`container-type:inline-size`) with children positioned in percentages
and fonts in `cqw` units, so one preview scales to whatever card width
the page gives it.

`cqw` specifically, never `cqh`: `container-type:inline-size` only
establishes an INLINE-axis query container, so block-axis container
units have no container to resolve against and silently fall back to
the small viewport height. Text sized in `cqh` therefore came out at a
size that had nothing to do with the preview box -- a 60pt title
rendered at 100px inside a 372px-tall frame, ~2.4x oversized, blowing
out of its box and clipping mid-word. Because the frame's aspect is
fixed, the inline axis carries the same information: 1cqh == 0.5625cqw.

Every renderer is fail-soft: any error degrades to a plain gray card
naming the slide, never an exception -- previews are a review aid, not
a load-bearing step.
"""

from __future__ import annotations

import html
import importlib
import re
from typing import Optional

SLIDE_W_PX = 1280.0
SLIDE_H_PX = 720.0
_MAX_TEXT = 110  # chars per text box in a preview -- enough to recognize the slide

_FRAME_ATTR = ' data-dg-frame="1"'
_FRAME_STYLE = (
    "position:relative;aspect-ratio:1280/720;container-type:inline-size;"
    "background:{bg};overflow:hidden;border:1px solid #D0D0D0;border-radius:6px;width:100%;"
)


def _esc(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def _clip(text: str, limit: int = _MAX_TEXT) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _fallback_card(label: str) -> str:
    return (
        f'<div{_FRAME_ATTR} style="{_FRAME_STYLE.format(bg="#F3EEE6")}display:flex;align-items:center;'
        f'justify-content:center;color:#727272;font-size:0.8rem;">{_esc(label)}</div>'
    )


def _box(left_pct, top_pct, w_pct, h_pct, inner: str, extra_style: str = "", label: str = "") -> str:
    # `data-dg-shape` is the hook deckguard.visual measures against: it
    # marks the box a shape's content has to stay inside, so a headless
    # browser can tell overflow and collisions from correct layout
    # without anyone eyeballing a screenshot.
    attr = f' data-dg-shape="{_esc(label)}"' if label else ' data-dg-shape=""'
    return (
        # border-box, because filled shapes carry padding: under the
        # default content-box that padding is ADDED to the declared
        # width, so a shape drew wider and taller than the shape
        # actually is -- found by deckguard.visual reporting shapes
        # hanging off a slide edge that nothing in the deck sits past.
        f'<div{attr} style="position:absolute;box-sizing:border-box;'
        f'left:{left_pct:.2f}%;top:{top_pct:.2f}%;'
        f'width:{w_pct:.2f}%;height:{h_pct:.2f}%;overflow:hidden;{extra_style}">{inner}</div>'
    )


def _placeholder_box(left_pct, top_pct, w_pct, h_pct, label: str, bg: str = "#F3EEE6", name: str = "") -> str:
    # A box too small to hold its own label gets drawn as a plain
    # swatch. The label is preview chrome, not deck content, and a
    # 0.15in chevron with "GROUP" jammed into it is both unreadable and
    # a false "content overflows its box" finding for deckguard.visual.
    # At 1.6cqw a glyph is ~0.96% of slide width.
    fits = w_pct >= len(label) * 0.96 and h_pct >= 2.5
    inner = (
        f'<span style="font-size:max(6px,1.6cqw);letter-spacing:.08em;color:#727272;'
        f'white-space:nowrap;">{_esc(label)}</span>'
    ) if fits else ""
    return _box(
        left_pct, top_pct, w_pct, h_pct, inner,
        f"background:{bg};display:flex;align-items:center;justify-content:center;",
        label=name or label,
    )


# --------------------------------------------------------------------------
# Current slide, from the inventory snapshot
# --------------------------------------------------------------------------

_BOXY_TYPES = {"TABLE", "CHART", "GROUP", "MEDIA", "OLE_OBJECT", "EMBEDDED_OLE_OBJECT"}

_AVG_GLYPH_EM = 0.52  # mean advance width of a lowercase sans glyph, in em
_LINE_HEIGHT = 1.25
_MIN_FIT_SCALE = 0.45  # never shrink past this -- illegible is worse than tight


def _fit_scale(paragraphs, width_in: Optional[float], height_in: Optional[float]) -> float:
    """How much a text box's type has to shrink to stay inside its own
    box, as PowerPoint's "shrink text on overflow" autofit would.

    deckguard has no text-shaping engine, so this estimates: a glyph
    advances ~0.52em, a line occupies 1.25x its point size. Rough, but
    it is the difference between a preview that reads like the slide and
    one where a 60pt heading in a narrow column overruns its box and
    gets sliced mid-word by the frame's clip.

    Returns 1.0 (no shrink) whenever the box is unknown or the text
    already fits, so it can only ever tighten an overflowing box.
    """
    if not width_in or not height_in:
        return 1.0
    box_w_pt, box_h_pt = width_in * 72.0, height_in * 72.0
    if box_w_pt <= 0 or box_h_pt <= 0:
        return 1.0

    used_pt = 0.0
    widest_word_pt = 0.0
    for para in paragraphs:
        text = "".join(r.text for r in para.runs).strip()
        pt = max((r.size_pt or 12.0) for r in para.runs) if para.runs else 12.0
        if not text:
            used_pt += pt * _LINE_HEIGHT
            continue
        for word in text.split():
            widest_word_pt = max(widest_word_pt, len(word) * pt * _AVG_GLYPH_EM)
        per_line = max(box_w_pt / (pt * _AVG_GLYPH_EM), 1.0)
        used_pt += max(1, -(-len(text) // int(per_line))) * pt * _LINE_HEIGHT

    scale = 1.0
    if used_pt > box_h_pt:  # too many lines to stack
        scale = box_h_pt / used_pt
    if widest_word_pt > box_w_pt:  # a single word wider than the column
        scale = min(scale, box_w_pt / widest_word_pt)
    return max(min(scale, 1.0), _MIN_FIT_SCALE)


def slide_preview_html(slide_record, slide_w_in: float = 13.333, slide_h_in: float = 7.5) -> str:
    """Wireframe of an existing slide from its inventory `SlideRecord` --
    real geometry, real solid fills, real text (clipped)."""
    try:
        parts = []

        # Decorative panels drawn on the slide's LAYOUT render behind
        # every slide built on it but never appear in the slide's own
        # shape tree. Skipping them made previews lie about the slides
        # that lean on them hardest: the AMP layout puts a full KONE
        # Blue panel behind its right-hand text column, so its white
        # body text previewed as white-on-white and read as missing.
        # Drawn first, so the slide's own shapes paint over them.
        for bg_shape in getattr(slide_record, "layout_background_shapes", None) or []:
            if None in (bg_shape.left_in, bg_shape.top_in, bg_shape.width_in, bg_shape.height_in):
                continue
            if not (bg_shape.fill and bg_shape.fill.type == "solid"
                    and bg_shape.fill.colors and bg_shape.fill.colors[0].hex):
                continue
            parts.append(_box(
                bg_shape.left_in / slide_w_in * 100, bg_shape.top_in / slide_h_in * 100,
                bg_shape.width_in / slide_w_in * 100, bg_shape.height_in / slide_h_in * 100,
                "", f"background:#{bg_shape.fill.colors[0].hex};",
                label=bg_shape.name or "layout background",
            ))

        for shape in slide_record.shapes:
            if None in (shape.left_in, shape.top_in, shape.width_in, shape.height_in):
                continue
            left = shape.left_in / slide_w_in * 100
            top = shape.top_in / slide_h_in * 100
            w = shape.width_in / slide_w_in * 100
            h = shape.height_in / slide_h_in * 100

            type_name = (shape.shape_type or "").upper()
            if shape.image is not None or type_name == "PICTURE":
                parts.append(_placeholder_box(left, top, w, h, "IMG", name=shape.name or "picture"))
                continue
            if type_name in _BOXY_TYPES:
                parts.append(_placeholder_box(left, top, w, h, type_name, bg="#EEF2FE", name=shape.name or type_name))
                continue

            fill_hex = None
            if shape.fill and shape.fill.type == "solid" and shape.fill.colors and shape.fill.colors[0].hex:
                fill_hex = shape.fill.colors[0].hex

            # One point is 1/(slide width in points) of the inline axis.
            # This is the whole reason type in a preview lands at the
            # same relative size it has on the slide.
            pt_to_cqw = 100.0 / (slide_w_in * 72.0)
            fit = _fit_scale(shape.paragraphs, shape.width_in, shape.height_in)

            lines = []
            for para in shape.paragraphs[:4]:
                run_bits = []
                for run in para.runs:
                    if not run.text.strip():
                        continue
                    color = f"#{run.color.hex}" if run.color and run.color.hex else "#141414"
                    size_cqw = min(max((run.size_pt or 12.0) * fit * pt_to_cqw, 0.8), 9.0)
                    weight = "600" if run.bold else "400"
                    run_bits.append(
                        f'<span style="color:{color};font-size:{size_cqw:.2f}cqw;font-weight:{weight};">'
                        f"{_esc(_clip(run.text))}</span>"
                    )
                if run_bits:
                    lines.append(
                        f'<div style="line-height:{_LINE_HEIGHT};">' + " ".join(run_bits) + "</div>"
                    )

            style = "overflow-wrap:anywhere;"  # wrap a long word, never slice it
            if fill_hex:
                style += f"background:#{fill_hex};padding:1.5% 2%;"
            if not lines and not fill_hex:
                continue  # nothing visible to draw for this shape
            parts.append(_box(left, top, w, h, "".join(lines), style, label=shape.name or "text"))

        return f'<div{_FRAME_ATTR} style="{_FRAME_STYLE.format(bg="#FFFFFF")}">{"".join(parts)}</div>'
    except Exception:
        return _fallback_card(f"slide {getattr(slide_record, 'index', '?')}")


# --------------------------------------------------------------------------
# Proposed archetype slide, from the skill's own declarative data
# --------------------------------------------------------------------------

_BG_NAMES = {"sand": "#F3EEEA", "blue": "#1450F5", "white": "#FFFFFF"}


def _role_css(role: str, engine) -> str:
    """Font/color CSS for a text role, read from kone_engine's own
    ROLE_STYLE so previews track the skill's styling exactly."""
    style = engine.ROLE_STYLE.get(role)
    if style is None:
        return "font-size:1.6cqw;color:#141414;"
    font, px, color, caps, bold, _fit = style
    css = f"font-size:{px / 12.8:.2f}cqw;color:#{color};"
    if caps:
        css += "text-transform:uppercase;letter-spacing:.05em;"
    if bold:
        css += "font-weight:600;"
    if "Information" in font:
        css += "font-family:'KONE Information','Inter',sans-serif;"
    return css


def archetype_preview_html(archetype_name: str, content: dict) -> str:
    """Wireframe of a proposed archetype slide, drawn from the SAME
    region/group data the pptx renderer consumes -- what you approve is
    what renders."""
    try:
        from deckguard.registry import _ensure_skill_on_path, _load_archetypes

        _ensure_skill_on_path()
        archetypes_mod = _load_archetypes()
        engine = importlib.import_module("kone_engine")
        arch = archetypes_mod.ARCHETYPES[archetype_name]

        bg = archetypes_mod.BG.get(archetype_name) or arch.get("background")
        bg_hex = _BG_NAMES.get(bg, f"#{bg}" if bg and len(str(bg)) == 6 else "#FFFFFF")

        parts = []

        def draw(role, box, val):
            x, y, w, h = box
            left, top = x / SLIDE_W_PX * 100, y / SLIDE_H_PX * 100
            wp, hp = w / SLIDE_W_PX * 100, h / SLIDE_H_PX * 100
            if role in ("picture", "image_band"):
                parts.append(_placeholder_box(left, top, wp, hp, "PHOTO"))
            elif role == "figure":
                parts.append(_placeholder_box(left, top, wp, hp, "CHART", bg="#EEF2FE"))
            elif role == "panel":
                parts.append(_box(left, top, wp, hp, "", "background:#1450F5;"))
            elif role == "panel_sand":
                parts.append(_box(left, top, wp, hp, "", "background:#F3EEEA;"))
            elif role == "axis":
                parts.append(_box(left, top, wp, max(hp, 0.2), "", "background:#D0D0D0;"))
            elif role == "icon":
                parts.append(_box(left, top, wp, hp, "", "background:#1450F5;border-radius:12%;"))
            elif role == "table":
                parts.append(_placeholder_box(left, top, wp, hp, "TABLE", bg="#FFFFFF"))
            elif role == "bullets":
                items = val if isinstance(val, list) else [val]
                lines = "".join(
                    f'<div style="font-size:1.25cqw;color:#141414;line-height:1.4;">'
                    f'<span style="color:#1450F5;">&bull;</span> {_esc(_clip(item, 60))}</div>'
                    for item in items[:5]
                )
                parts.append(_box(left, top, wp, hp, lines))
            else:
                if isinstance(val, list):
                    # A list reaching a plain text region rendered as
                    # Python source -- "['Standardise intake', ...]" --
                    # on every archetype whose bullet slot is not role
                    # `bullets`. Show it as lines instead.
                    val = " · ".join(
                        str(v.get("text", next(iter(v.values()), "")) if isinstance(v, dict) else v)
                        for v in val)
                text = _clip(val, _MAX_TEXT)
                if text:
                    parts.append(
                        _box(left, top, wp, hp, f'<span style="{_role_css(role, engine)}line-height:1.15;">{_esc(text)}</span>')
                    )

        for reg in arch.get("regions", []):
            key = reg.get("content")
            val = content.get(key) if key else reg.get("value", "")
            if key and key not in content and "value" not in reg:
                if reg.get("role") in ("picture", "image_band", "figure", "icon"):
                    val = ""  # slot still drawn as a placeholder box
                else:
                    continue
            draw(reg["role"], reg["box"], val)

        for grp in arch.get("groups", []):
            items = content.get(grp["content"], [])
            for (ox, oy), item in zip(grp["origins"], items):
                for reg in grp["regions"]:
                    rx, ry, rw, rh = reg["box"]
                    cval = item.get(reg["content"]) if reg.get("content") and isinstance(item, dict) else reg.get("value", "")
                    draw(reg["role"], [ox + rx, oy + ry, rw, rh], cval)

        return f'<div{_FRAME_ATTR} style="{_FRAME_STYLE.format(bg=bg_hex)}">{"".join(parts)}</div>'
    except Exception:
        return _fallback_card(archetype_name)


# --------------------------------------------------------------------------
# Proposed org-template rebuild: real placeholder geometry + verbatim content
# --------------------------------------------------------------------------

_TITLE_PH = {"TITLE", "CENTER_TITLE"}
_BODY_PH = {"BODY", "OBJECT", "SUBTITLE"}


def org_layout_preview_html(
    layout, slide_w_emu: int, slide_h_emu: int,
    title: Optional[str], text_blocks: list, image_count: int = 0,
) -> str:
    """Wireframe of what a rebuild onto `layout` (a python-pptx
    SlideLayout) would hold: its real placeholder boxes, with the
    slide's own verbatim title/body text placed in reading order --
    the same order `_transplant_content` fills them."""
    try:
        bodies, pictures, parts = [], [], []
        title_ph = None
        for ph in layout.placeholders:
            if None in (ph.left, ph.top, ph.width, ph.height):
                continue
            name = ph.placeholder_format.type.name if ph.placeholder_format.type else None
            if "logo" in (ph.name or "").lower() or "tagline" in (ph.name or "").lower():
                continue
            if name in _TITLE_PH and title_ph is None:
                title_ph = ph
            elif name in _BODY_PH:
                bodies.append(ph)
            elif name == "PICTURE":
                pictures.append(ph)
        bodies.sort(key=lambda p: (p.top or 0, p.left or 0))
        pictures.sort(key=lambda p: (p.top or 0, p.left or 0))

        def pct(ph):
            return (
                ph.left / slide_w_emu * 100, ph.top / slide_h_emu * 100,
                ph.width / slide_w_emu * 100, ph.height / slide_h_emu * 100,
            )

        outline = "border:1px dashed #A1B9FB;"
        if title_ph is not None:
            left, top, w, h = pct(title_ph)
            inner = f'<span style="font-size:3.1cqw;color:#141414;line-height:1.1;">{_esc(_clip(title or "", 80))}</span>'
            parts.append(_box(left, top, w, h, inner, outline))
        for i, ph in enumerate(bodies):
            left, top, w, h = pct(ph)
            block = text_blocks[i] if i < len(text_blocks) else []
            lines = "".join(
                f'<div style="font-size:1.4cqw;color:#141414;line-height:1.35;">{_esc(_clip(line, 70))}</div>'
                for line in block[:5]
            )
            parts.append(_box(left, top, w, h, lines, outline))
        for i, ph in enumerate(pictures):
            left, top, w, h = pct(ph)
            parts.append(_placeholder_box(left, top, w, h, "PHOTO" if i < image_count else "PHOTO SLOT"))

        return f'<div{_FRAME_ATTR} style="{_FRAME_STYLE.format(bg="#FFFFFF")}">{"".join(parts)}</div>'
    except Exception:
        return _fallback_card(getattr(layout, "name", "layout"))


# --------------------------------------------------------------------------
# sample content, for previewing an archetype before it has any
# --------------------------------------------------------------------------

# Words chosen so a wireframe reads as the SHAPE of the slide rather than
# as lorem: a preview whose job is "what am I picking" needs the reader
# to recognise a quote slide as a quote slide at thumbnail size.
_SAMPLE_WORDS = {
    "title": "Request Management moves to ServiceNow",
    "eyebrow": "Marketing Hub", "heading": "Standardise intake",
    "subtitle": "What changed, and what happens next",
    "lede": "The Hub moved its entire framework across with full data continuity.",
    "statement": "Repair is no longer the cheaper option.",
    "body": "Volume roughly doubled year on year while resolution held at 91 per cent.",
    "text": "Standardise intake and reporting on ServiceNow.",
    "quote": "A benchmark in easy to work with, easy to work for.",
    "context": "Said at the April review, after the first full quarter on the new intake.",
    "label": "Frontlines", "value": "12", "number": "01", "item": "What changed",
    "period": "Q2 2026", "caption": "Marketing Hub", "footer": "Marketing Hub · April 2026",
    "scope": "KSEA · KMTA · KANZ · KEI · EEM", "name": "Suresh Kumar",
    "note": "And the Hub specialists.", "credits": "Arvind, Rupesh and Golda",
    "support": "Measured across twelve frontlines over six weeks.",
    "attribution": "Head of Marketing Operations", "classification": "KONE Internal",
}


# Repeated slots -- the four cells of a numbers row, the five columns of
# an icon row -- filled with the same word read as a rendering fault
# rather than as a layout ("12 FRONTLINES" four times over). These give
# each cell in a group its own word, so the preview shows a row of four
# different things, which is what the slide is for.
_SAMPLE_SERIES = {
    "number": ["01", "02", "03", "04", "05", "06"],
    "value": ["12", "91%", "2x", "48", "6", "3"],
    "label": ["Frontlines", "Resolved", "Volume", "Weeks", "Regions", "Owners"],
    "heading": ["Standardise intake", "Automate routing", "Publish status",
                "Review monthly", "Retire the inbox", "Hand over"],
    "item": ["What changed", "Why now", "Who owns it", "What is next",
             "How we measure", "Where to ask"],
    "title": ["What changed", "Why now", "Who owns it", "What is next",
              "How we measure", "Where to ask"],
    "period": ["Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026", "Q1 2027", "Q2 2027"],
    "name": ["Suresh Kumar", "Golda Fernandes", "Rupesh Nair", "Arvind Lal",
             "Mei Tan", "Jonas Virtanen"],
    "text": ["Standardise intake on ServiceNow.", "Route by request type.",
             "Publish live queue status.", "Review the backlog monthly.",
             "Retire the shared inbox.", "Hand over to the regions."],
}


def _sample_word(key: str, index: int = 0) -> str:
    for stem, series in _SAMPLE_SERIES.items():
        if stem in key:
            return series[index % len(series)]
    for stem, word in _SAMPLE_WORDS.items():
        if stem in key:
            return word
    return "Marketing Hub"


def sample_content(archetype_name: str) -> dict:
    """Plausible content for an archetype, for preview only.

    Prefers the skill's own worked example where one exists; otherwise
    fills each slot from its name. Never used to build a deck -- the
    builder leaves an unfilled slot empty rather than inventing copy.
    """
    try:
        from deckguard.registry import _derived_content_keys, _load_archetypes

        archetypes = _load_archetypes()
        sample = getattr(archetypes, "SAMPLES", {}).get(archetype_name)
        if isinstance(sample, dict):
            return dict(sample)
        out: dict = {}
        for raw in _derived_content_keys(archetype_name):
            key = raw.split(" (")[0]
            if "filled automatically" in raw:
                continue
            match = re.search(r"list of up to (\d+) × \{([^}]*)\}", raw)
            if match:
                count = min(int(match.group(1)), 4)
                fields = [f.strip().split(":")[0] for f in match.group(2).split(",")]
                out[key] = [{f: _sample_word(f, i) for f in fields}
                            for i in range(count)]
            elif "list of" in raw:
                out[key] = ["Standardise intake on ServiceNow",
                            "Automate repeat request types",
                            "Publish live queue status"]
            else:
                out[key] = _sample_word(key)
        return out
    except Exception:  # noqa: BLE001 -- a preview must never break the page
        return {}
