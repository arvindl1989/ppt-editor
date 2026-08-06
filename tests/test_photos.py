"""Tests for photos.py -- the library and choosing from it.

Matching rules run on a synthetic library so they hold whatever is
installed; the tests reading the real one guard the sidecar, whose
failure mode is silence: a malformed `photos.json` would leave every
photo undescribed and selection back to arbitrary.
"""

import json

import pytest

from deckguard import photos as P

needs_library = pytest.mark.skipif(not P.load_photos(), reason="photo library not installed")


@pytest.fixture
def library(tmp_path, monkeypatch):
    from PIL import Image

    for name, size in (("technician-van.jpg", (300, 200)),
                       ("skyline-dusk.jpeg", (400, 200)),
                       ("family-lobby.jpg", (300, 200)),
                       ("undescribed-escalator-photo.jpg", (300, 200))):
        Image.new("RGB", size, "grey").save(tmp_path / name)
    (tmp_path / "photos.json").write_text(json.dumps({"photos": {
        "technician-van.jpg": {"note": "A KONE technician beside a van",
                               "people": 2, "setting": "field",
                               "tags": ["technician", "service", "van"]},
        "skyline-dusk.jpeg": {"note": "City skyline at dusk", "people": 0,
                              "setting": "skyline", "tags": ["skyline", "dusk"]},
        "family-lobby.jpg": {"note": "A family by a lift", "people": 4,
                             "setting": "lobby", "tags": ["family", "elevator"]},
    }}))
    monkeypatch.setattr(P, "photos_dir", lambda: tmp_path)
    P.load_photos.cache_clear()
    yield tmp_path
    P.load_photos.cache_clear()


def test_the_sidecar_describes_the_library(library):
    lib = P.load_photos()
    assert set(lib) == {"technician-van", "skyline-dusk", "family-lobby",
                        "undescribed-escalator-photo"}
    assert lib["technician-van"].people == 2
    assert lib["skyline-dusk"].has_people is False


def test_a_sidecar_key_matches_regardless_of_extension(library):
    """The set ships both .jpg and .jpeg for the same kind of picture,
    so the sidecar is keyed by stem rather than filename."""
    assert P.load_photos()["skyline-dusk"].setting == "skyline"


def test_an_undescribed_photo_still_matches_on_its_filename(library):
    """Better than matching on nothing -- the nine older photos in the
    real library have no sidecar entry."""
    hits = P.find_photos("escalator")
    assert [h.name for h in hits] == ["undescribed-escalator-photo"]


def test_a_tag_outranks_an_incidental_word(library):
    assert P.find_photos("technician")[0].name == "technician-van"


def test_wanting_people_is_a_filter_not_a_preference(library):
    """An architectural shot and a photo of four people are not
    interchangeable; a slide that needs one must never get the other."""
    assert all(p.has_people for p in P.find_photos("", wants_people=True))
    assert [p.name for p in P.find_photos("", wants_people=False)] == ["skyline-dusk"]


def test_an_undescribed_photo_is_unknown_rather_than_empty(library):
    """It defaulted to zero people, which made every undescribed photo
    eligible for slides wanting an empty architectural frame. Nine
    photos in the real library are undescribed and one of them is a
    family in a lift."""
    unknown = P.load_photos()["undescribed-escalator-photo"]
    assert unknown.people is None and unknown.has_people is None
    assert unknown not in P.find_photos("escalator", wants_people=False)
    assert unknown not in P.find_photos("escalator", wants_people=True)
    assert unknown in P.find_photos("escalator")


def test_choose_never_repeats_a_photo_already_used(library):
    """Reusing one picture four times is the most visible symptom of
    automatic selection."""
    used = []
    for _ in range(4):
        photo = P.choose("", exclude=used)
        assert photo is not None and photo.name not in used
        used.append(photo.name)
    assert P.choose("", exclude=used) is None


def test_choose_falls_back_rather_than_returning_nothing(library):
    """No match must still yield a picture -- an empty photo slot is a
    worse outcome than an imperfect photo."""
    assert P.choose("submarine periscope quantum") is not None


def test_a_broken_sidecar_does_not_lose_the_library(library):
    (library / "photos.json").write_text("{ not json")
    P.load_photos.cache_clear()
    assert len(P.load_photos()) == 4


def test_crop_severity_grows_as_the_slot_narrows(library):
    photo = P.load_photos()["technician-van"]          # 300x200, aspect 1.5
    assert P.crop_severity(photo, 1.5) == 0.0
    assert 0 < P.crop_severity(photo, 1.0) < P.crop_severity(photo, 0.5)


# --------------------------------------------------------------------------
# the shipped library
# --------------------------------------------------------------------------


@needs_library
def test_every_shipped_photo_that_is_described_has_a_usable_description():
    described = [p for p in P.load_photos().values() if p.note]
    assert len(described) >= 30
    for photo in described:
        assert len(photo.note) > 20, f"{photo.name} has a stub description"
        assert photo.tags, f"{photo.name} has no tags"
        assert photo.setting, f"{photo.name} has no setting"


@needs_library
def test_the_library_covers_both_people_and_no_people():
    values = P.load_photos().values()
    assert sum(1 for p in values if p.has_people) >= 20
    assert sum(1 for p in values if not p.has_people) >= 3


@needs_library
def test_a_service_slide_and_a_skyline_slide_get_different_photos():
    service = P.choose("technician maintenance service visit", wants_people=True)
    skyline = P.choose("city growth urban density", wants_people=False)
    assert service is not None and skyline is not None
    assert service.name != skyline.name
    assert service.has_people and not skyline.has_people


@needs_library
def test_the_described_set_is_entirely_landscape():
    """Recorded rather than worked around: the archetypes have picture
    slots down to 0.5 aspect and every described photo is landscape
    between 1.3 and 1.9, so those slots crop hard. (One older,
    undescribed photo IS portrait -- which is why this checks the
    described set rather than the library.)"""
    from PIL import Image

    for photo in P.load_photos().values():
        if not photo.note:
            continue
        with Image.open(photo.path) as image:
            width, height = image.size
        assert width > height, f"{photo.name} is portrait -- update this expectation"
        assert 1.2 < width / height < 2.0
