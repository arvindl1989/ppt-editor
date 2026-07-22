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
