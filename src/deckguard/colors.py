"""Color handling: literal srgbClr values and theme color/tint/shade resolution.

Colors in PPTX exist two ways: literal ``srgbClr`` values, and theme color
references (``schemeClr``) with a brightness (tint/shade, i.e. lumMod/
lumOff) adjustment layered on top. Both are handled here:

- ``remap_literal_colors`` walks every fill/line/text color in the deck and
  remaps literal hex values per the config.
- ``remap_theme_colors`` edits the theme XML directly so every shape that
  references a theme slot (and any derived tint of it) is corrected in one
  operation, without touching per-shape XML.
- ``effective_rgb`` resolves a ColorFormat (literal or theme+brightness) to
  the RGB it actually renders as, for audit comparisons.
"""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree
from pptx.dml.color import ColorFormat
from pptx.enum.dml import MSO_COLOR_TYPE, MSO_THEME_COLOR
from pptx.dml.color import RGBColor
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _a(tag: str) -> str:
    return f"{{{A_NS}}}{tag}"


THEME_SLOT_BY_MSO = {
    MSO_THEME_COLOR.DARK_1: "dk1",
    MSO_THEME_COLOR.LIGHT_1: "lt1",
    MSO_THEME_COLOR.DARK_2: "dk2",
    MSO_THEME_COLOR.LIGHT_2: "lt2",
    MSO_THEME_COLOR.ACCENT_1: "accent1",
    MSO_THEME_COLOR.ACCENT_2: "accent2",
    MSO_THEME_COLOR.ACCENT_3: "accent3",
    MSO_THEME_COLOR.ACCENT_4: "accent4",
    MSO_THEME_COLOR.ACCENT_5: "accent5",
    MSO_THEME_COLOR.ACCENT_6: "accent6",
    MSO_THEME_COLOR.HYPERLINK: "hlink",
    MSO_THEME_COLOR.FOLLOWED_HYPERLINK: "folHlink",
}
# BACKGROUND_1/2 and TEXT_1/2 are indirected through the master's <p:clrMap>;
# the common (and default) mapping is bg1->lt1, tx1->dk1, bg2->lt2, tx2->dk2.
CLRMAP_FALLBACK = {
    MSO_THEME_COLOR.BACKGROUND_1: "lt1",
    MSO_THEME_COLOR.TEXT_1: "dk1",
    MSO_THEME_COLOR.BACKGROUND_2: "lt2",
    MSO_THEME_COLOR.TEXT_2: "dk2",
}

CLR_SCHEME_SLOTS = [
    "dk1",
    "lt1",
    "dk2",
    "lt2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
]


def normalize_hex(value: str) -> str:
    """Uppercase 6-digit hex, no leading '#', e.g. '#1450f5' -> '1450F5'."""
    v = value.strip().lstrip("#").upper()
    if len(v) != 6 or any(c not in "0123456789ABCDEF" for c in v):
        raise ValueError(f"invalid hex color: {value!r}")
    return v


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    h = normalize_hex(value)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG relative luminance (0=black, 1=white), gamma-corrected per channel."""

    def channel(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """WCAG contrast ratio, 1 (no contrast) to 21 (black vs white)."""
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def expected_contrast_text_hex(bg_hex: str, dark_hex: str, light_hex: str) -> str:
    """Which of `dark_hex`/`light_hex` is more legible on `bg_hex`, by WCAG
    contrast ratio -- e.g. white text on KONE Blue, black text on a pale
    secondary color, per General_Branding.docx's legibility rule."""
    bg_rgb = hex_to_rgb(bg_hex)
    dark_rgb = hex_to_rgb(dark_hex)
    light_rgb = hex_to_rgb(light_hex)
    return light_hex if contrast_ratio(bg_rgb, light_rgb) > contrast_ratio(bg_rgb, dark_rgb) else dark_hex


def apply_brightness(rgb: tuple[int, int, int], brightness: float) -> tuple[int, int, int]:
    """Approximate PowerPoint's lumMod/lumOff tint(+)/shade(-) adjustment."""
    r, g, b = rgb
    if brightness > 0:
        r = r + (255 - r) * brightness
        g = g + (255 - g) * brightness
        b = b + (255 - b) * brightness
    elif brightness < 0:
        r = r * (1 + brightness)
        g = g * (1 + brightness)
        b = b * (1 + brightness)
    return (round(r), round(g), round(b))


@dataclass
class ThemeColorScheme:
    """dk1/lt1/.../folHlink -> hex, read from one theme part."""

    slots: dict[str, str]


def _read_clr_scheme(theme_root: etree._Element) -> tuple[etree._Element, dict[str, str]]:
    clr_scheme = theme_root.find(f".//{_a('clrScheme')}")
    if clr_scheme is None:
        raise ValueError("theme XML has no <a:clrScheme>")
    slots: dict[str, str] = {}
    for slot in CLR_SCHEME_SLOTS:
        el = clr_scheme.find(_a(slot))
        if el is None:
            continue
        srgb = el.find(_a("srgbClr"))
        if srgb is not None:
            slots[slot] = srgb.get("val").upper()
            continue
        sys_clr = el.find(_a("sysClr"))
        if sys_clr is not None:
            slots[slot] = sys_clr.get("lastClr").upper()
    return clr_scheme, slots


def get_theme_scheme(slide_master) -> ThemeColorScheme:
    theme_part = slide_master.part.part_related_by(RT.THEME)
    root = etree.fromstring(theme_part.blob)
    _, slots = _read_clr_scheme(root)
    return ThemeColorScheme(slots=slots)


def effective_rgb(color: ColorFormat, theme_scheme: ThemeColorScheme | None) -> tuple[int, int, int] | None:
    """Resolve a ColorFormat to the RGB it actually renders as, or None if unset."""
    try:
        color_type = color.type
    except AttributeError:
        return None
    if color_type is None:
        return None
    if color_type == MSO_COLOR_TYPE.RGB:
        rgb = color.rgb
        return (rgb[0], rgb[1], rgb[2]) if rgb is not None else None
    if color_type == MSO_COLOR_TYPE.SCHEME:
        if theme_scheme is None:
            return None
        mso = color.theme_color
        slot = THEME_SLOT_BY_MSO.get(mso) or CLRMAP_FALLBACK.get(mso)
        if slot is None or slot not in theme_scheme.slots:
            return None
        base_hex = theme_scheme.slots[slot]
        base_rgb = hex_to_rgb(base_hex)
        brightness = color.brightness or 0.0
        return apply_brightness(base_rgb, brightness)
    return None


def remap_color_format(color: ColorFormat, remap: dict[str, str]) -> tuple[str, str] | None:
    """If `color` is a literal RGB matching a remap key, rewrite it in place.

    Returns (old_hex, new_hex) if a change was made, else None. Theme
    (scheme-typed) colors are intentionally left alone here — those are
    corrected once, at the theme level, by `remap_theme_colors`.
    """
    try:
        color_type = color.type
    except AttributeError:
        return None
    if color_type != MSO_COLOR_TYPE.RGB or color.rgb is None:
        return None
    old_hex = normalize_hex(str(color.rgb))
    if old_hex not in remap:
        return None
    new_hex = normalize_hex(remap[old_hex])
    color.rgb = RGBColor.from_string(new_hex)
    return old_hex, new_hex


def iter_slide_masters(prs):
    seen_ids = set()
    for master in prs.slide_masters:
        if id(master.part) in seen_ids:
            continue
        seen_ids.add(id(master.part))
        yield master


def remap_theme_colors(prs, remap: dict[str, str]) -> list[dict]:
    """Rewrite matching literal colors in every distinct theme part used by the deck.

    Because derived tints (schemeClr + lumMod/lumOff) resolve relative to
    the theme slot's base color, correcting the slot here fixes every
    shape that references it in one operation.
    """
    changes: list[dict] = []
    seen_theme_parts = set()
    for master in iter_slide_masters(prs):
        theme_part = master.part.part_related_by(RT.THEME)
        if id(theme_part) in seen_theme_parts:
            continue
        seen_theme_parts.add(id(theme_part))

        root = etree.fromstring(theme_part.blob)
        clr_scheme, slots = _read_clr_scheme(root)
        changed = False
        for slot, current_hex in slots.items():
            if current_hex not in remap:
                continue
            new_hex = normalize_hex(remap[current_hex])
            slot_el = clr_scheme.find(_a(slot))
            sys_clr = slot_el.find(_a("sysClr"))
            srgb = slot_el.find(_a("srgbClr"))
            if srgb is not None:
                srgb.set("val", new_hex)
            elif sys_clr is not None:
                # Replace the system color reference with an explicit srgbClr
                # so the corrected value is unambiguous.
                new_el = etree.SubElement(slot_el, _a("srgbClr"))
                new_el.set("val", new_hex)
                slot_el.remove(sys_clr)
            changed = True
            changes.append(
                {
                    "theme_part": theme_part.partname,
                    "slot": slot,
                    "old": f"#{current_hex}",
                    "new": f"#{new_hex}",
                }
            )
        if changed:
            theme_part._blob = etree.tostring(  # noqa: SLF001 — see module docstring
                root, xml_declaration=True, encoding="UTF-8", standalone=True
            )
    return changes
