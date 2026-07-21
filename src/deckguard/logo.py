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
