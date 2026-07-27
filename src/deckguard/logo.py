"""Logo detection (perceptual hash) and replacement.

Old logos are identified by perceptual hash rather than exact byte
match, since the same logo is routinely re-exported/re-compressed across
a legacy deck estate. Replacement swaps the embedded image part and
rewrites the `<a:blip r:embed>` reference only — the shape's `spPr`/
`xfrm` (position, size, rotation, crop) is left untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import imagehash
from PIL import Image
from pptx.enum.shapes import MSO_SHAPE_TYPE

DEFAULT_MATCH_THRESHOLD = 10  # max Hamming distance to count as a logo match

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _a(tag: str) -> str:
    return f"{{{A_NS}}}{tag}"


def _p(tag: str) -> str:
    return f"{{{P_NS}}}{tag}"


def _r_embed_attr() -> str:
    return f"{{{R_NS}}}embed"


def compute_phash(image_bytes: bytes) -> str:
    with Image.open(BytesIO(image_bytes)) as img:
        return str(imagehash.phash(img))


def hamming_distance(hash_a: str, hash_b: str) -> int:
    return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)


def iter_picture_shapes(shapes):
    """Recurse into groups, yielding every picture shape."""
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_picture_shapes(shape.shapes)
        elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            yield shape


@dataclass
class LogoMatch:
    shape: object
    phash: str
    matched_hash: str
    distance: int


def find_old_logo_matches(
    shapes, old_hashes: list[str], threshold: int = DEFAULT_MATCH_THRESHOLD
) -> list[LogoMatch]:
    matches = []
    if not old_hashes:
        return matches
    for shape in iter_picture_shapes(shapes):
        try:
            phash = compute_phash(shape.image.blob)
        except Exception:  # noqa: BLE001 — unreadable/corrupt image, skip rather than crash
            continue
        best = min(old_hashes, key=lambda h: hamming_distance(phash, h))
        distance = hamming_distance(phash, best)
        if distance <= threshold:
            matches.append(LogoMatch(shape=shape, phash=phash, matched_hash=best, distance=distance))
    return matches


def replace_logo_image(shape, new_image_path: str) -> None:
    """Swap the embedded image, preserving the shape's position/size/crop."""
    image_part, rId = shape.part.get_or_add_image_part(new_image_path)
    blip = shape._element.blipFill.blip
    blip.rEmbed = rId


def find_background_blip(container_element):
    """Return the `<a:blip>` of a slide/layout/master's own page-level
    background-fill image (`<p:cSld><p:bg><p:bgPr><a:blipFill><a:blip>`),
    or None.

    A logo is sometimes not a picture *shape* at all -- it's baked into
    the page background fill (a banner/header image, or the whole page
    background) via `<p:bg>`, which lives outside the shape tree
    entirely. `iter_picture_shapes` (shape-tree only) can never see this,
    which is exactly why such a logo appears invisible to deckguard even
    though it's visibly present in the deck.
    """
    bg = container_element.find(f"{_p('cSld')}/{_p('bg')}")
    if bg is None:
        return None
    return bg.find(f".//{_a('blip')}")


def find_old_logo_background_match(
    part, container_element, old_hashes: list[str], threshold: int = DEFAULT_MATCH_THRESHOLD
) -> "LogoMatch | None":
    """Same idea as `find_old_logo_matches`, scoped to a page-level
    background-fill image rather than a shape."""
    if not old_hashes:
        return None
    blip = find_background_blip(container_element)
    if blip is None:
        return None
    rid = blip.get(_r_embed_attr())
    if not rid:
        return None
    try:
        image_part = part.related_part(rid)
        phash = compute_phash(image_part.blob)
    except Exception:  # noqa: BLE001 -- unreadable/corrupt/missing image, skip rather than crash
        return None
    best = min(old_hashes, key=lambda h: hamming_distance(phash, h))
    distance = hamming_distance(phash, best)
    if distance <= threshold:
        return LogoMatch(shape=blip, phash=phash, matched_hash=best, distance=distance)
    return None


def replace_background_image(part, blip_element, new_image_path: str) -> None:
    """Swap a page-level background-fill image found via `find_background_blip`."""
    image_part, rId = part.get_or_add_image_part(new_image_path)
    blip_element.set(_r_embed_attr(), rId)


def find_shapes_in_region(shapes, region_emu: tuple) -> list:
    """Top-level shapes (deliberately NOT recursing into groups -- a
    logo lockup built as a group is one match, not each of its individual
    paths) whose own bounding box is fully contained within
    `region_emu = (left, top, width, height)`.

    Exists for the case `find_old_logo_matches` can't handle at all: an
    old brand mark that isn't a raster picture, so there's no image to
    perceptual-hash -- e.g. a wordmark drawn as vector freeform shapes
    directly on a slide master. A logo's one reliable property across
    however differently it was constructed is that it sits in a fixed,
    small corner region of every slide -- so unlike hash matching (which
    identifies WHAT the old logo looks like), this identifies WHERE it
    lives, config-driven and opt-in (`logo.old_logo_region_in`) for the
    same reason `old_logo_hashes` is opt-in: guessing at removing
    shapes from a master, without a human confirming the region first,
    is exactly the kind of silent guess this project avoids everywhere
    else.
    """
    r_left, r_top, r_width, r_height = region_emu
    r_right, r_bottom = r_left + r_width, r_top + r_height
    matches = []
    for shape in shapes:
        left, top, width, height = shape.left, shape.top, shape.width, shape.height
        if None in (left, top, width, height):
            continue
        if left >= r_left and top >= r_top and (left + width) <= r_right and (top + height) <= r_bottom:
            matches.append(shape)
    return matches


def _next_shape_id_in_tree(spTree) -> int:
    """Same contract as python-pptx's own `_next_shape_id` (smallest
    positive integer not already used), but scoped to THIS shape tree's
    own `p:cNvPr/@id` values only -- confirmed necessary the hard way: a
    slide MASTER has a `p:sldLayoutIdLst` sibling (outside the shape
    tree, listing the layouts that belong to it) whose `p:sldLayoutId`
    elements use a completely different id namespace that starts at
    2^31 by OOXML convention. python-pptx's own `_next_shape_id`
    property does a document-WIDE `//@id` XPath scan (an absolute path,
    so it searches from the document root no matter which element it's
    called on) and picks those up too, handing back a shape id above
    2^31 -- which overflows a signed 32-bit int and produced a .pptx
    PowerPoint outright refused to open, confirmed by inspecting the
    output directly. Safe to call on a slide's shape tree (nothing else
    on a slide uses a bare, unprefixed `id` attribute); only actually
    matters for a master, but used everywhere here for one code path
    that's correct in both cases rather than two that silently diverge.
    """
    used_ids = {
        int(el.get("id")) for el in spTree.iter(_p("cNvPr"))
        if el.get("id") is not None and el.get("id").isdigit()
    }
    n = 1
    while n in used_ids:
        n += 1
    return n


def replace_shapes_in_region_with_logo(shape_container, matches: list, new_image_path: str, region_emu: tuple) -> None:
    """Delete every shape in `matches` from `shape_container` (a
    master/layout/slide's own `.shapes`) and insert the new logo image
    in their place, sized to fit within `region_emu` preserving its
    native aspect ratio (never stretched), anchored to the region's
    top-left corner.
    """
    r_left, r_top, r_width, r_height = region_emu
    spTree = shape_container._spTree
    for shape in matches:
        spTree.remove(shape._element)

    image_part, rId = shape_container.part.get_or_add_image_part(new_image_path)
    native_width, native_height = image_part.image.size
    scale = min(r_width / native_width, r_height / native_height)
    cx, cy = int(native_width * scale), int(native_height * scale)
    left = r_left + (r_width - cx) // 2
    top = r_top + (r_height - cy) // 2

    id_ = _next_shape_id_in_tree(spTree)
    name = "Picture %d" % id_
    spTree.add_pic(id_, name, image_part.desc, rId, left, top, cx, cy)
