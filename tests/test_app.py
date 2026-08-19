"""The one-page tool: give it something, get a deck, edit it.

There is no mode to choose and no approval step, so these tests are
mostly about the four ways input arrives and what each produces.
"""

import importlib
import re

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from deckguard import web as web_mod

    return TestClient(importlib.reload(web_mod).app)


def _token(html: str) -> str:
    found = re.search(r"/download/([a-f0-9]+)/deck\.pptx", html)
    assert found, "no deck was offered for download"
    return found.group(1)


def test_the_landing_page_asks_for_input_not_for_a_mode(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Build a KONE deck" in r.text
    # one button, not a choice of products
    assert r.text.count('type="submit"') == 1
    for gone in ("Audit only", "Plan transform", "/audit", "/plan"):
        assert gone not in r.text, gone


def test_picked_slides_are_honoured_exactly_and_in_order(client):
    r = client.post("/generate", data={
        "audience": "internal", "title": "Probe",
        "pick": ["internal:8", "internal:16"],
    })
    assert r.status_code == 200
    assert "numbered_icon_row_6" in r.text and "kone_numbers" in r.text
    body = r.text
    assert body.index("numbered_icon_row_6") < body.index("kone_numbers")


def test_giving_it_nothing_says_so_rather_than_building_an_empty_deck(client):
    r = client.post("/generate", data={"audience": "internal"})
    assert r.status_code == 400
    assert "something to work from" in r.text


def test_a_deck_is_downloadable_the_moment_it_is_built(client):
    """No approval step: generating produces the file."""
    r = client.post("/generate", data={"audience": "internal", "pick": ["internal:8"]})
    deck = client.get(f"/download/{_token(r.text)}/deck.pptx")
    assert deck.status_code == 200
    assert deck.content[:2] == b"PK"


def test_edits_reorder_drop_and_duplicate_then_rebuild(client):
    r = client.post("/generate", data={
        "audience": "internal", "pick": ["internal:8", "internal:16", "internal:20"]})
    token = _token(r.text)
    edited = client.post(f"/rebuild/{token}", data={
        "o:0": "30", "o:1": "10", "o:2": "20", "dup:2": "on",
    })
    assert edited.status_code == 200

    from io import BytesIO

    from pptx import Presentation

    deck = client.get(f"/download/{token}/deck.pptx")
    slides = Presentation(BytesIO(deck.content)).slides
    # three picked, one duplicated, plus the master's cover and outro
    assert len(slides) == 6


def test_an_expired_token_says_so(client):
    r = client.post("/rebuild/" + "0" * 32, data={})
    assert r.status_code == 404


# --------------------------------------------------------------------------
# using someone else's deck
# --------------------------------------------------------------------------


def _a_deck(tmp_path):
    from deckguard import assemble

    out = tmp_path / "source.pptx"
    plan = assemble.plan(audience="internal", title="Source",
                         picks=["internal:8", "internal:16", "internal:20"])
    assemble.build(plan, str(out))
    return out


def test_an_uploaded_deck_becomes_templates_that_actually_render(client, tmp_path):
    """The trap this keeps falling into: a template that is registered
    but has no content, or content but no role styles, builds a deck of
    blank pages and downloads happily."""
    source = _a_deck(tmp_path)
    with source.open("rb") as handle:
        r = client.post("/generate", files={"deck": ("mine.pptx", handle.read())},
                        data={"audience": "internal", "title": "From my deck"})
    assert r.status_code == 200
    assert "templates read from your deck" in r.text

    from io import BytesIO

    from pptx import Presentation

    deck = client.get(f"/download/{_token(r.text)}/deck.pptx")
    slides = list(Presentation(BytesIO(deck.content)).slides)
    body = slides[1:-1]          # between the master's retained cover and outro
    assert body, "nothing was built from the mined templates"
    with_text = [
        s for s in body
        if any(sh.text_frame.text.strip() for sh in s.shapes
               if getattr(sh, "has_text_frame", False))
    ]
    assert len(with_text) >= len(body) // 2, "mined slides came out blank"


def test_a_deck_that_cannot_be_read_is_reported_not_crashed(client):
    r = client.post("/generate", files={"deck": ("broken.pptx", b"not a pptx at all")},
                    data={"audience": "internal", "brief": "", "pick": ["internal:8"]})
    assert r.status_code == 200
    assert "Could not read that deck" in r.text


def test_only_pptx_is_accepted(client):
    r = client.post("/generate", files={"deck": ("notes.txt", b"hello")},
                    data={"audience": "internal"})
    assert r.status_code == 400
    assert ".pptx" in r.text


# --------------------------------------------------------------------------
# preflight
# --------------------------------------------------------------------------


def test_preflight_runs_on_every_build_and_says_when_it_is_clean(client):
    r = client.post("/generate", data={"audience": "internal", "pick": ["internal:8"]})
    assert "Preflight" in r.text


def test_preflight_ignores_the_masters_zero_sized_placeholders(tmp_path):
    """The master's latent DATE / FOOTER / SLIDE_NUMBER placeholders come
    back as 0x0 boxes parked at y=720. Flagging them made every deck
    report findings nobody could act on, which teaches people to ignore
    preflight entirely."""
    from deckguard import assemble

    out = tmp_path / "clean.pptx"
    plan = assemble.plan(audience="internal", title="T", picks=["internal:8", "internal:16"])
    checks = assemble.build(plan, str(out))
    floor_hits = [m for _n, m in checks["findings"] if "past the floor" in m]
    assert not floor_hits, floor_hits


def test_preflight_still_catches_a_real_violation(tmp_path):
    from pptx import Presentation
    from pptx.util import Emu, Pt

    from deckguard import assemble

    out = tmp_path / "dirty.pptx"
    plan = assemble.plan(audience="internal", title="T", picks=["internal:8"])
    assemble.build(plan, str(out))

    prs = Presentation(str(out))
    box = prs.slides[1].shapes.add_textbox(Emu(400000), Emu(400000), Emu(2000000), Emu(300000))
    run = box.text_frame.paragraphs[0].add_run()
    run.text = "- a dash pretending to be a bullet"
    run.font.size = Pt(12)
    prs.save(str(out))

    findings = assemble.preflight(str(out))["findings"]
    assert any("dash standing in for a bullet" in m for _n, m in findings), findings
