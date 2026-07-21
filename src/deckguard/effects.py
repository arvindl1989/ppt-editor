"""Detect and remove forbidden text effects: shadow, glow, reflection, outline, 3d.

python-pptx has no high-level API for these — they live in raw OOXML:

- shadow / glow / reflection: children of ``<a:rPr><a:effectLst>`` (run-level)
  or ``<p:spPr><a:effectLst>`` (shape-level, e.g. a shadow on a picture/box).
- outline: an ``<a:ln>`` element as a direct child of ``<a:rPr>`` with a real
  fill — that's PowerPoint's "text outline" stroke around glyphs, distinct
  from a shape's border (which lives under ``<p:spPr><a:ln>``).
- 3d: ``<a:sp3d>`` / ``<a:scene3d>`` under ``<p:spPr>``.

Detection uses read-only lxml lookups (never `get_or_add_*`, which would
mutate the tree just by inspecting it). Removal only touches elements that
are actually present.
"""

from __future__ import annotations

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def a_qn(tag: str) -> str:
    return f"{{{A_NS}}}{tag}"


def _p(tag: str) -> str:
    return f"{{{P_NS}}}{tag}"


EFFECT_LST_TAG_CATEGORY = {
    "outerShdw": "shadow",
    "innerShdw": "shadow",
    "prstShdw": "shadow",
    "glow": "glow",
    "reflection": "reflection",
}

ALL_CATEGORIES = ("shadow", "glow", "reflection", "outline", "3d")


def _categories_in_effect_lst(effect_lst) -> set[str]:
    if effect_lst is None:
        return set()
    found = set()
    for child in effect_lst:
        local = etree_localname(child.tag)
        if local in EFFECT_LST_TAG_CATEGORY:
            found.add(EFFECT_LST_TAG_CATEGORY[local])
    return found


def etree_localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def get_rPr(run):
    """Read-only rPr lookup — never creates the element as a side effect."""
    return run._r.find(a_qn("rPr"))


def get_spPr(shape):
    return shape._element.find(_p("spPr"))


def detect_run_effects(run) -> set[str]:
    rPr = get_rPr(run)
    if rPr is None:
        return set()
    found = _categories_in_effect_lst(rPr.find(a_qn("effectLst")))
    ln = rPr.find(a_qn("ln"))
    if ln is not None and ln.find(a_qn("noFill")) is None:
        has_fill = any(
            ln.find(a_qn(tag)) is not None
            for tag in ("solidFill", "gradFill", "pattFill", "blipFill")
        )
        if has_fill:
            found.add("outline")
    return found


def detect_shape_effects(shape) -> set[str]:
    """Shape-level effects: effectLst (shadow/glow/reflection on the whole
    shape/picture) plus 3d format (sp3d/scene3d)."""
    spPr = get_spPr(shape)
    if spPr is None:
        return set()
    found = _categories_in_effect_lst(spPr.find(a_qn("effectLst")))
    if spPr.find(a_qn("sp3d")) is not None or spPr.find(a_qn("scene3d")) is not None:
        found.add("3d")
    return found


def remove_run_effects(run) -> set[str]:
    """Strip forbidden effects from a run's rPr. Returns categories removed."""
    rPr = get_rPr(run)
    if rPr is None:
        return set()
    removed = set()
    effect_lst = rPr.find(a_qn("effectLst"))
    cats = _categories_in_effect_lst(effect_lst)
    if cats:
        rPr.remove(effect_lst)
        removed |= cats
    ln = rPr.find(a_qn("ln"))
    if ln is not None and ln.find(a_qn("noFill")) is None:
        has_fill = any(
            ln.find(a_qn(tag)) is not None
            for tag in ("solidFill", "gradFill", "pattFill", "blipFill")
        )
        if has_fill:
            rPr.remove(ln)
            removed.add("outline")
    return removed


def remove_shape_effects(shape) -> set[str]:
    spPr = get_spPr(shape)
    if spPr is None:
        return set()
    removed = set()
    effect_lst = spPr.find(a_qn("effectLst"))
    cats = _categories_in_effect_lst(effect_lst)
    if cats:
        spPr.remove(effect_lst)
        removed |= cats
    sp3d = spPr.find(a_qn("sp3d"))
    scene3d = spPr.find(a_qn("scene3d"))
    if sp3d is not None:
        spPr.remove(sp3d)
        removed.add("3d")
    if scene3d is not None:
        spPr.remove(scene3d)
        removed.add("3d")
    return removed
