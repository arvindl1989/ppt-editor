"""Content-preserving re-layout: migrate an outdated deck's slides onto
the org template's own sanctioned layouts, via the slide master.

Unlike `fix` (recolors/refonts shapes in place) and `migrate` (replaces
only the first/last slide), this replaces a slide's entire structure --
useful for a genuinely old deck built on ad hoc, non-template layouts,
where the goal isn't to patch colors/fonts but to rebuild each slide on
an approved layout and carry the content over.

Deliberately scoped to TEXT and IMAGES only (titles, body/bullet text,
pictures) -- the content types that map onto a new layout's placeholders
reliably. A slide with a table, chart, embedded object, media, or a
grouped shape is never guessed at: it's left completely untouched and
flagged, rather than silently dropping or mangling content. Matching a
slide to a layout is deterministic (shape-count/type profile match, no
AI), same as the rest of this engine.

Two-phase by design (`propose_retemplate` / `apply_retemplate`) so a
caller -- the web UI in particular -- can show the proposed
slide->layout mapping and let a human accept or override it before
anything is generated, rather than committing to a one-shot guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Optional

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from deckguard.slide_import import (
    _delete_slide,
    _move_slide,
    default_template_path,
    import_layouts,
)

# Shapes types that make a slide's content unsafe to reflow automatically
# -- tables/charts/embedded objects/media don't map onto a placeholder,
# and a group can hide arbitrary complexity behind a single shape.
DISQUALIFYING_SHAPE_TYPES = {"TABLE", "CHART", "EMBEDDED_OLE_OBJECT", "MEDIA", "GROUP"}

# Readable overrides for the generic "contains a <type>" skip-reason
# phrasing below -- OLE is an acronym (stays uppercase), and the
# indefinite article needs to be "an" before it.
_SHAPE_TYPE_PHRASES = {"EMBEDDED_OLE_OBJECT": "an embedded OLE object"}


def _disqualifying_shape_phrase(type_name: str) -> str:
    if type_name in _SHAPE_TYPE_PHRASES:
        return _SHAPE_TYPE_PHRASES[type_name]
    label = type_name.lower().replace("_", " ")
    article = "an" if label[:1] in "aeiou" else "a"
    return f"{article} {label}"

TITLE_PLACEHOLDER_TYPES = {"TITLE", "CENTER_TITLE"}
BODY_PLACEHOLDER_TYPES = {"BODY", "OBJECT", "SUBTITLE"}

MAX_DECORATIVE_SHAPES = 4  # e.g. divider lines/accent rectangles with no text
MAX_TEXT_BLOCKS = 3
MAX_IMAGES = 4
MAX_PREVIEW_CHARS = 120

# classify_slide's ineligibility reason for a genuinely blank slide --
# distinct from every OTHER ineligibility reason (table/chart/media/
# overfull), which mean "this has real content we can't safely
# reinterpret." A blank slide has nothing to protect; redesign.py uses
# this exact string to tell "empty, safe to author from a brief" apart
# from "has content, must never be touched or guessed at."
EMPTY_SLIDE_REASON = "no title, text, or images to migrate"

# The org template's "ordinary content" layouts -- deliberately excludes
# Cover/Section/Agenda/Statement/Quote/Outro/End/REPORT-*/Blank, which are
# special-purpose or structural, not sensible targets for an arbitrary old
# body slide. Listed simplest-first: ties in `match_layout` favor whichever
# candidate appears earliest, so ordering here is a real tie-break, not
# just documentation.
CONTENT_LAYOUT_CANDIDATES = [
    "Title (24pt) and footers",
    "Title and text",
    "Title and content A",
    "Title and content B",
    "Two content A",
    "Two content B",
    "Two content C",
    "Two content D",
    "Three content A",
    "Three content B",
    "Three content C",
    "Three content D",
    "Text and picture A",
    "Text and picture B",
    "Text and picture C",
    "Text and picture F",
    "Text and picture G",
    "Text and picture H",
    "Two pictures and text A",
    "Two pictures and text B",
    "Two pictures and text C",
    "Three pictures and text",
    "Four pictures and text",
    "Fullslide picture",
]


@dataclass
class SlideProfile:
    """What a slide is made of, extracted independent of any target layout."""

    title: Optional[str]
    text_blocks: list  # list[list[tuple[int, str]]] -- one list per non-title text shape, each a (level, text) per paragraph
    images: list  # list[bytes] -- raw image blobs, in shape order
    eligible: bool
    reason: Optional[str] = None


def _is_footer_like(shape, slide_height_in: Optional[float]) -> bool:
    """Small text box tucked in the top/bottom margin -- a footer,
    confidentiality line, date, or page number, not real slide content.

    Mirrors the pagination heuristic rules_engine.py already uses for
    alignment exceptions, broadened beyond numeric-only text: a
    "Confidential | (c) KONE Corporation" footer isn't numeric, but is
    exactly as much chrome as a lone page number is, and was showing up
    as a bogus "body text block" (crowding out real content against
    MAX_TEXT_BLOCKS, and as a misleading preview) before this existed.
    """
    try:
        width_in = shape.width.inches if shape.width is not None else None
        height_in = shape.height.inches if shape.height is not None else None
        top_in = shape.top.inches if shape.top is not None else None
    except AttributeError:
        return False
    small_box = (width_in if width_in is not None else 99) < 4.5 and (height_in if height_in is not None else 99) < 0.6
    if not small_box or top_in is None or not slide_height_in:
        return False
    return top_in < 0.6 or top_in > slide_height_in - 0.75


def _extract_slide_content(slide, slide_height_in: Optional[float] = None):
    """Walk a slide's shapes once and pull out title/text-blocks/images.

    Returns (title, text_blocks, images, disqualify_reason). A non-None
    `disqualify_reason` means the slide has content that's unsafe to
    reinterpret in ANY context -- a table/chart/embedded-object/media/
    group shape, or too many free-form decorative shapes to trust a
    reflow -- and callers should treat the slide as ineligible outright,
    ignoring the other three (empty/undefined) return values.

    Deliberately does NOT apply a cap on text-block or image *count* --
    that's caller-side policy, not a property of the shapes themselves.
    `classify_slide` below applies retemplate's own cap (the org
    template's actual per-layout placeholder capacity, since retemplate
    carries content over VERBATIM); a caller willing to condense or
    rewrite content, like redesign.py, can reasonably choose a higher
    one against this exact same extraction.
    """
    title = None
    text_blocks: list = []
    images: list = []
    decorative = 0

    for shape in slide.shapes:
        try:
            type_name = shape.shape_type.name if shape.shape_type is not None else "UNKNOWN"
        except AttributeError:
            type_name = "UNKNOWN"

        if type_name in DISQUALIFYING_SHAPE_TYPES:
            return None, [], [], f"contains {_disqualifying_shape_phrase(type_name)}"

        ph_type_name = None
        if getattr(shape, "is_placeholder", False):
            try:
                ph_type = shape.placeholder_format.type
                ph_type_name = ph_type.name if ph_type else None
            except (AttributeError, ValueError):
                ph_type_name = None

        has_text = bool(getattr(shape, "has_text_frame", False)) and shape.text_frame.text.strip()

        if ph_type_name in TITLE_PLACEHOLDER_TYPES and has_text and title is None:
            title = shape.text_frame.text.strip()
            continue

        if type_name == MSO_SHAPE_TYPE.PICTURE.name:
            try:
                images.append(shape.image.blob)
            except Exception:  # noqa: BLE001 -- unreadable/corrupt embedded image
                decorative += 1
            continue

        if has_text:
            if _is_footer_like(shape, slide_height_in):
                continue  # boilerplate chrome, not real content -- doesn't count toward eligibility either
            paras = [(p.level, "".join(r.text for r in p.runs)) for p in shape.text_frame.paragraphs]
            paras = [(lvl, t) for lvl, t in paras if t.strip()]
            if paras:
                text_blocks.append(paras)
            continue

        decorative += 1
        if decorative > MAX_DECORATIVE_SHAPES:
            return None, [], [], "too many free-form shapes to safely reflow"

    return title, text_blocks, images, None


def classify_slide(slide, slide_height_in: Optional[float] = None) -> SlideProfile:
    """Extract a slide's title/body-text/image content and decide
    whether it's safe to auto-map onto a new layout at all, under
    retemplate's own (verbatim-carryover) capacity rules."""
    title, text_blocks, images, reason = _extract_slide_content(slide, slide_height_in)
    if reason:
        return SlideProfile(None, [], [], False, reason)
    if title is None and not text_blocks and not images:
        return SlideProfile(None, [], [], False, EMPTY_SLIDE_REASON)
    if len(text_blocks) > MAX_TEXT_BLOCKS:
        return SlideProfile(None, [], [], False, "more body text blocks than any template layout can hold")
    if len(images) > MAX_IMAGES:
        return SlideProfile(None, [], [], False, "more images than any template layout can hold")

    return SlideProfile(title=title, text_blocks=text_blocks, images=images, eligible=True)


@dataclass
class LayoutProfile:
    name: str
    has_title: bool
    n_body: int
    n_picture: int


def _layout_profile(layout) -> LayoutProfile:
    has_title = False
    n_body = 0
    n_picture = 0
    for ph in layout.placeholders:
        ph_type = ph.placeholder_format.type
        name = ph_type.name if ph_type else None
        if name in TITLE_PLACEHOLDER_TYPES:
            has_title = True
        elif name in BODY_PLACEHOLDER_TYPES:
            n_body += 1
        elif name == "PICTURE":
            n_picture += 1
    return LayoutProfile(name=layout.name, has_title=has_title, n_body=n_body, n_picture=n_picture)


@dataclass
class LayoutMatch:
    layout_name: str
    score: int


def match_layout(profile: SlideProfile, layout_profiles: list[LayoutProfile]) -> Optional[LayoutMatch]:
    """Pick the tightest-fitting candidate layout that can hold every
    piece of this slide's content -- never one that would force dropping
    a text block or image. None if nothing qualifies."""
    title_needed = profile.title is not None
    n_body_needed = len(profile.text_blocks)
    n_pic_needed = len(profile.images)

    best: Optional[tuple[int, str]] = None
    for lp in layout_profiles:
        if title_needed and not lp.has_title:
            continue
        if lp.n_body < n_body_needed or lp.n_picture < n_pic_needed:
            continue
        waste = (lp.n_body - n_body_needed) + (lp.n_picture - n_pic_needed)
        if lp.has_title and not title_needed:
            waste += 1
        score = -waste
        if best is None or score > best[0]:
            best = (score, lp.name)

    if best is None:
        return None
    return LayoutMatch(layout_name=best[1], score=best[0])


@dataclass
class SlideProposal:
    slide_index: int  # 1-based
    eligible: bool
    reason: Optional[str] = None
    layout_name: Optional[str] = None
    title_preview: Optional[str] = None
    body_preview: Optional[str] = None
    image_count: int = 0


def _preview(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= MAX_PREVIEW_CHARS else text[: MAX_PREVIEW_CHARS - 1] + "…"


def _candidate_layout_profiles(template_path) -> list[LayoutProfile]:
    tmpl_prs = Presentation(str(template_path))
    layout_by_name = {layout.name: layout for master in tmpl_prs.slide_masters for layout in master.slide_layouts}
    return [
        _layout_profile(layout_by_name[name])
        for name in CONTENT_LAYOUT_CANDIDATES
        if name in layout_by_name
    ]


def propose_retemplate(prs, template_path=None) -> list[SlideProposal]:
    """Classify every slide and propose a target layout for each, without
    changing anything. Safe to call repeatedly / for preview purposes."""
    template_path = template_path or default_template_path()
    layout_profiles = _candidate_layout_profiles(template_path)
    slide_height_in = prs.slide_height / 914400 if prs.slide_height else None

    proposals = []
    for i, slide in enumerate(prs.slides, start=1):
        profile = classify_slide(slide, slide_height_in)
        if not profile.eligible:
            proposals.append(SlideProposal(slide_index=i, eligible=False, reason=profile.reason))
            continue
        match = match_layout(profile, layout_profiles)
        if match is None:
            proposals.append(
                SlideProposal(
                    slide_index=i, eligible=False, reason="no template layout fits this slide's content",
                    image_count=len(profile.images),
                )
            )
            continue
        body_preview = _preview(profile.text_blocks[0][0][1]) if profile.text_blocks and profile.text_blocks[0] else None
        proposals.append(
            SlideProposal(
                slide_index=i, eligible=True, layout_name=match.layout_name,
                title_preview=_preview(profile.title), body_preview=body_preview,
                image_count=len(profile.images),
            )
        )
    return proposals


def _set_text_block(text_frame, block: list) -> None:
    text_frame.clear()
    first = True
    for level, text in block:
        p = text_frame.paragraphs[0] if first else text_frame.add_paragraph()
        first = False
        p.text = text
        p.level = max(0, min(level, 8))


def _transplant_content(new_slide, profile: SlideProfile) -> None:
    body_iter = iter(profile.text_blocks)
    image_iter = iter(profile.images)
    for ph in new_slide.placeholders:
        ph_type = ph.placeholder_format.type
        name = ph_type.name if ph_type else None
        if name in TITLE_PLACEHOLDER_TYPES:
            if profile.title:
                ph.text_frame.text = profile.title
        elif name in BODY_PLACEHOLDER_TYPES:
            block = next(body_iter, None)
            if block:
                _set_text_block(ph.text_frame, block)
        elif name == "PICTURE":
            blob = next(image_iter, None)
            if blob is not None:
                ph.insert_picture(BytesIO(blob))


@dataclass
class RetemplateResult:
    proposals: list  # list[SlideProposal], every slide (eligible or not)
    transformed: list  # slide_index (1-based, ORIGINAL numbering) actually rebuilt
    skipped: list  # slide_index left untouched (ineligible, or not accepted)

    def to_dict(self) -> dict:
        return {
            "proposals": [vars(p) for p in self.proposals],
            "transformed": self.transformed,
            "skipped": self.skipped,
        }


def apply_retemplate(
    deck_path, out_path, accepted_indexes: Optional[set] = None, template_path=None
) -> RetemplateResult:
    """Rebuild every ACCEPTED, eligible slide on its matched template
    layout, carrying its title/body-text/images over; every other slide
    (ineligible, or simply not accepted) is left byte-for-byte untouched.

    `accepted_indexes`: 1-based original slide indices to actually
    transform. None (the default) means "every eligible slide" -- the
    fully-automatic path. A caller doing guided review passes exactly the
    indices a human approved; anything else is filtered out even if it
    was eligible.
    """
    template_path = template_path or default_template_path()
    prs = Presentation(deck_path)
    proposals = propose_retemplate(prs, template_path)
    proposal_by_index = {p.slide_index: p for p in proposals}
    eligible_indexes = {p.slide_index for p in proposals if p.eligible}

    accepted = eligible_indexes if accepted_indexes is None else (set(accepted_indexes) & eligible_indexes)
    all_indexes = set(range(1, len(prs.slides) + 1))
    result = RetemplateResult(proposals=proposals, transformed=sorted(accepted), skipped=sorted(all_indexes - accepted))

    if not accepted:
        import shutil

        shutil.copy(deck_path, out_path)
        return result

    needed_layouts = sorted({proposal_by_index[i].layout_name for i in accepted})
    tmp_path = Path(out_path).with_suffix(".layouts.pptx")
    import_layouts(deck_path, str(template_path), str(tmp_path), needed_layouts)

    try:
        prs2 = Presentation(str(tmp_path))
        imported_master = prs2.slide_masters[-1]
        layout_by_name = {layout.name: layout for layout in imported_master.slide_layouts}
        slide_height_in = prs2.slide_height / 914400 if prs2.slide_height else None

        # Captured once, before any add/move/delete -- a slide's OPC
        # partname never changes, so this is a stable way to keep finding
        # "the original slide at position N" as the deck's slide list
        # shifts underneath us with every replacement.
        original_partnames = [str(s.part.partname).lstrip("/") for s in prs2.slides]

        # Phase A: create every new slide and transplant its content FIRST,
        # with no deletions interleaved. python-pptx's own new-slide
        # partname isn't a scan for a free name -- it's just "current
        # slide count + 1" (PresentationPart._next_slide_partname) -- so a
        # delete between two add_slide() calls shrinks that count and can
        # make the next add_slide() hand out a partname still in use by an
        # earlier new slide from this same run, silently colliding two
        # live slides onto one XML part (confirmed by direct repro: a
        # second replacement reused the first's "slide4.xml"). Doing every
        # add first, before any delete, keeps the count strictly growing
        # for the whole phase, so that collision can never trigger.
        new_partname_by_old: dict[str, str] = {}
        for orig_idx in sorted(accepted):
            old_partname = original_partnames[orig_idx - 1]
            old_slide = next(s for s in prs2.slides if str(s.part.partname).lstrip("/") == old_partname)
            profile = classify_slide(old_slide, slide_height_in)  # re-derive from the still-intact original (bytes are unchanged from `prs`)
            layout = layout_by_name[proposal_by_index[orig_idx].layout_name]

            new_slide = prs2.slides.add_slide(layout)
            _transplant_content(new_slide, profile)
            new_partname_by_old[old_partname] = str(new_slide.part.partname).lstrip("/")

        # Phase B: now that every new slide safely exists, move each into
        # its old slide's position and remove the old slide -- one pair at
        # a time, re-resolving both positions by partname each step since
        # they shift as earlier pairs are processed.
        for orig_idx in sorted(accepted):
            old_partname = original_partnames[orig_idx - 1]
            new_partname = new_partname_by_old[old_partname]
            old_pos = next(i for i, s in enumerate(prs2.slides) if str(s.part.partname).lstrip("/") == old_partname)
            new_pos = next(i for i, s in enumerate(prs2.slides) if str(s.part.partname).lstrip("/") == new_partname)
            _move_slide(prs2, new_pos, old_pos)
            _delete_slide(prs2, old_pos + 1)

        prs2.save(out_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return result
