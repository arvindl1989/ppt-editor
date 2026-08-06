"""The KONE photo library, and choosing from it.

Picture choice is a large part of whether a deck reads as designed, and
until now it was effectively random: nine images with nothing recorded
about any of them, picked by position in a sorted list. A deck about
maintenance got a photo of an escalator because it happened to sort
third.

`photos.json` fixes the input side. Each entry carries what the picture
is actually of -- written by looking at it, not inferred from the
filename -- plus a people count, a setting and tags. This module reads
that and answers the only question a renderer has: given this slide,
which photo.

Two things worth knowing about matching here. A photo with no people is
not interchangeable with one carrying four: an architectural facade
suits a divider or a data slide, a technician greeting a family suits a
service story, and swapping them is the difference between a deck that
looks considered and one that looks stocked. And every photo in the set
is landscape, between 1.3 and 1.9 -- so a slot narrower than about 0.8
will crop hard, which `crop_severity` reports rather than hides.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

_VENDORED = Path(__file__).with_name("assets") / "kone-design" / "photos"
_INTERACTIVE = Path("~/.claude/skills/kone-design/assets/photos").expanduser()

_EXTENSIONS = (".jpg", ".jpeg", ".png")

# Below this ratio of slot aspect to photo aspect, the crop starts
# throwing away most of the frame.
HARSH_CROP = 0.55


@dataclass(frozen=True)
class Photo:
    name: str
    path: Path
    note: str = ""
    people: Optional[int] = None  # None means nobody has looked
    setting: str = ""
    tags: tuple = field(default_factory=tuple)

    @property
    def has_people(self) -> Optional[bool]:
        """True, False, or None for "not known".

        The three-way answer matters. Defaulting an undescribed photo to
        zero people made it eligible for every slide that asked for an
        empty architectural shot, and the library still holds nine
        older photos nobody has described -- one of which is a family in
        a lift. Unknown must not masquerade as no.
        """
        return None if self.people is None else self.people > 0


def photos_dir() -> Optional[Path]:
    for base in (_VENDORED, _INTERACTIVE):
        if base.is_dir() and any(base.glob("*.jp*g")):
            return base
    return None


@lru_cache(maxsize=1)
def load_photos() -> dict[str, Photo]:
    """{stem: Photo}. Keyed by stem so the sidecar does not have to
    agree with the library on `.jpg` versus `.jpeg` -- this set ships
    both, for the same kind of picture."""
    base = photos_dir()
    if base is None:
        return {}

    described: dict[str, dict] = {}
    sidecar = base / "photos.json"
    if sidecar.is_file():
        try:
            raw = json.loads(sidecar.read_text()).get("photos", {})
            described = {Path(k).stem: v for k, v in raw.items()}
        except Exception:  # noqa: BLE001 -- a broken sidecar must not lose the library
            described = {}

    out: dict[str, Photo] = {}
    for path in sorted(base.iterdir()):
        if path.suffix.lower() not in _EXTENSIONS:
            continue
        meta = described.get(path.stem, {})
        out[path.stem] = Photo(
            name=path.stem,
            path=path,
            note=meta.get("note", ""),
            people=int(meta["people"]) if "people" in meta else None,
            setting=meta.get("setting", ""),
            # an undescribed photo still matches on the words in its own
            # filename, which is better than matching on nothing
            tags=tuple(meta.get("tags") or re.split(r"[-_]", path.stem)),
        )
    return out


def photo_names() -> list[str]:
    return sorted(load_photos())


def describe(name: str) -> str:
    photo = load_photos().get(name)
    return photo.note if photo else ""


# --------------------------------------------------------------------------
# choosing
# --------------------------------------------------------------------------


def score(photo: Photo, terms: Iterable[str], wants_people: Optional[bool] = None) -> float:
    """How well a photo answers a request. Higher is better, 0 means no."""
    needles = [t.strip().lower() for t in terms if t and t.strip()]
    haystack = " ".join((photo.name, photo.note, photo.setting, *photo.tags)).lower()

    total = 0.0
    for needle in needles:
        if needle in photo.tags:
            total += 3.0          # an explicit tag is the strongest signal
        elif needle in photo.setting.lower():
            total += 2.0
        elif needle in haystack:
            total += 1.0
    if wants_people is not None:
        # unknown is not a match: an undescribed photo may well be full
        # of people, and a slide asking for an empty frame must not get
        # one on the strength of a missing field
        if photo.has_people is not wants_people:
            return 0.0            # a hard filter, not a preference
        total += 0.5
    return total


def find_photos(query: str, wants_people: Optional[bool] = None,
                limit: int = 8) -> list[Photo]:
    """Photos matching a free-text query, best first."""
    terms = re.split(r"[\s,]+", query.strip().lower()) if query else []
    scored = [
        (score(photo, terms, wants_people), photo)
        for photo in load_photos().values()
    ]
    ranked = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1].name))
    return [photo for _, photo in ranked[:limit]]


def choose(query: str = "", wants_people: Optional[bool] = None,
           exclude: Iterable[str] = ()) -> Optional[Photo]:
    """One photo for a slide, avoiding any already used.

    `exclude` is what stops a deck using the same picture four times --
    the single most visible symptom of automatic selection.
    """
    used = set(exclude)
    for photo in find_photos(query, wants_people, limit=len(load_photos()) or 1):
        if photo.name not in used:
            return photo
    # nothing matched, or everything matching is used: fall back to any
    # unused photo rather than repeating one
    for photo in load_photos().values():
        if photo.name in used:
            continue
        if wants_people is None or photo.has_people is wants_people:
            return photo
    return None


def crop_severity(photo: Photo, slot_aspect: float) -> float:
    """How much of the frame a slot throws away, 0 (none) to 1 (all).

    Every photo in this set is landscape between 1.3 and 1.9, so a tall
    slot -- and the archetypes go down to 0.5 -- keeps a narrow vertical
    strip of it. Worth reporting rather than discovering in the render.
    """
    from PIL import Image

    try:
        with Image.open(photo.path) as image:
            width, height = image.size
    except Exception:  # noqa: BLE001
        return 0.0
    if not (width and height and slot_aspect):
        return 0.0
    photo_aspect = width / height
    keep = min(photo_aspect, slot_aspect) / max(photo_aspect, slot_aspect)
    return round(1.0 - keep, 3)
