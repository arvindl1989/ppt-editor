"""Tests for skill_bridge.py -- deckguard's bridge to the (out-of-repo,
per-machine) kone-deck-generator skill, used only for redesign_deck's
"no source deck, just a brief" path. No real network calls -- these
inject the same fake Anthropic-shaped client the rest of the redesign
test suite uses.
"""

import json
from pathlib import Path

import pytest

from deckguard.compose import Outline, SlideSpec
from deckguard.redesign import RedesignError
from deckguard.skill_bridge import (
    _load_archetypes,
    _skill_dir,
    _validate_kone_spec,
    apply_archetype_overrides_to_deck,
    build_deck_via_skill,
    build_deck_with_archetypes,
    call_claude_for_kone_spec,
    select_archetype_overrides,
    select_archetype_overrides_for_rebrand,
)
from tests.test_redesign import _FakeClient, _FakeResponse, _kone_slide, _kone_spec_json

_skill_installed = (_skill_dir() / "kone_deck_creator.py").is_file()
needs_skill = pytest.mark.skipif(not _skill_installed, reason="kone-deck-generator skill not installed")


def _known_archetypes():
    return set(_load_archetypes().ARCHETYPES.keys())


def test_build_deck_via_skill_raises_a_clean_error_when_the_skill_is_not_installed(tmp_path, monkeypatch):
    """Doesn't need the real skill on disk -- exercises the opposite case:
    an actionable RedesignError, never a raw ImportError/FileNotFoundError,
    when KONE_DECK_GENERATOR_DIR points nowhere real."""
    import deckguard.skill_bridge as skill_bridge

    monkeypatch.setattr(skill_bridge, "_creator_module", None)
    monkeypatch.setattr(skill_bridge, "_archetypes_module", None)
    monkeypatch.setattr(skill_bridge, "_catalog_cache", None)
    monkeypatch.setenv("KONE_DECK_GENERATOR_DIR", str(tmp_path / "does-not-exist"))

    with pytest.raises(RedesignError, match="isn't installed"):
        build_deck_via_skill("A brief.", str(tmp_path / "out.pptx"), client=_FakeClient(_FakeResponse("{}")))


@needs_skill
def test_validate_kone_spec_accepts_a_well_formed_spec():
    spec = json.loads(
        _kone_spec_json(
            "Deck title",
            _kone_slide("image_section_divider", eyebrow="Overview", title="A new era"),
            _kone_slide("agenda_contents", title="Agenda", items=[{"number": "01", "item": "Kickoff"}]),
            _kone_slide(
                "three_stats", title="By the numbers",
                stats=[
                    {"label": "Volume", "value": "2x", "desc": "growth"},
                    {"label": "Resolution", "value": "91%", "desc": "resolved"},
                    {"label": "Phases", "value": "3", "desc": "planned"},
                ],
            ),
            _kone_slide("quote_context", quote="Ship it.", attribution="A KONE engineer"),
        )
    )
    _validate_kone_spec(spec, _known_archetypes())  # must not raise


@needs_skill
def test_validate_kone_spec_rejects_unknown_archetype():
    spec = {"title": "T", "slides": [_kone_slide("carousel", title="x")]}
    with pytest.raises(RedesignError, match="unknown archetype"):
        _validate_kone_spec(spec, _known_archetypes())


@needs_skill
def test_validate_kone_spec_rejects_a_non_object_slide():
    spec = {"title": "T", "slides": ["not a dict"]}
    with pytest.raises(RedesignError, match="not a JSON object"):
        _validate_kone_spec(spec, _known_archetypes())


def test_validate_kone_spec_rejects_missing_title():
    with pytest.raises(RedesignError, match="missing deck 'title'"):
        _validate_kone_spec({"slides": [{"archetype": "three_stats"}]}, {"three_stats"})


def test_validate_kone_spec_rejects_zero_slides():
    with pytest.raises(RedesignError, match="zero slides"):
        _validate_kone_spec({"title": "T", "slides": []}, {"three_stats"})


@needs_skill
def test_validate_kone_spec_accepts_text_over_typical_length_guidance():
    """Character limits are advisory (the renderer's shrink-to-fit
    handles overflow) -- validation must not reject a merely-long value."""
    spec = {
        "title": "T",
        "slides": [_kone_slide("agenda_contents", title="x" * 200, items=[{"number": "01", "item": "y" * 300}])],
    }
    _validate_kone_spec(spec, _known_archetypes())  # must not raise


@needs_skill
def test_call_claude_for_kone_spec_sends_the_brief_and_returns_usage():
    response_json = _kone_spec_json("T", _kone_slide("agenda_contents", title="X", items=[]))
    client = _FakeClient(_FakeResponse(response_json, input_tokens=1200, output_tokens=300))

    spec, usage = call_claude_for_kone_spec("Build a deck about X.", client=client)

    assert spec["title"] == "T"
    assert usage.input_tokens == 1200 and usage.output_tokens == 300
    sent = client.messages.calls[0]
    assert "Build a deck about X." in sent["messages"][0]["content"]
    # no rigid structured-output schema for this path -- see skill_bridge's
    # own docstring for why (content shape varies too much per archetype)
    assert "output_config" not in sent


@needs_skill
def test_call_claude_for_kone_spec_system_prompt_includes_the_real_archetype_catalog():
    response_json = _kone_spec_json("T", _kone_slide("agenda_contents", title="X", items=[]))
    client = _FakeClient(_FakeResponse(response_json))

    call_claude_for_kone_spec("Build a deck about X.", client=client)

    system = client.messages.calls[0]["system"]
    archetypes = _load_archetypes()
    for name in archetypes.ARCHETYPES:
        assert name in system


@needs_skill
def test_call_claude_for_kone_spec_strips_markdown_code_fences():
    response_json = "```json\n" + _kone_spec_json("T", _kone_slide("agenda_contents", title="X", items=[])) + "\n```"
    client = _FakeClient(_FakeResponse(response_json))

    spec, _usage = call_claude_for_kone_spec("Build a deck about X.", client=client)

    assert spec["title"] == "T"


@needs_skill
def test_build_deck_via_skill_renders_a_real_pptx(tmp_path):
    response_json = _kone_spec_json(
        "My deck",
        _kone_slide("agenda_contents", title="Agenda", items=[{"number": "01", "item": "Point one"}]),
    )
    client = _FakeClient(_FakeResponse(response_json))

    out_path = tmp_path / "out.pptx"
    compose_result, redesign_result = build_deck_via_skill("A brief.", str(out_path), client=client)

    assert out_path.exists()
    assert compose_result.slide_count == 3  # Cover F + 1 body + Outro
    assert compose_result.layouts_used == ["Cover F", "agenda_contents", "Outro"]
    assert redesign_result.outline is None
    assert redesign_result.usage.input_tokens > 0


@needs_skill
def test_build_deck_via_skill_renders_content_over_the_old_hard_limit(tmp_path):
    """Regression guard: a value that would have tripped the retired
    hard character-limit validation must still render successfully."""
    response_json = _kone_spec_json(
        "My deck",
        _kone_slide("quote_context", label="Voice of the business, in their own words", quote="Ship it.", attribution="A KONE engineer"),
    )
    client = _FakeClient(_FakeResponse(response_json))

    out_path = tmp_path / "out.pptx"
    compose_result, _redesign_result = build_deck_via_skill("A brief.", str(out_path), client=client)

    assert out_path.exists()
    assert compose_result.slide_count == 3


@needs_skill
def test_build_deck_via_skill_raises_a_clean_error_for_an_invalid_spec(tmp_path):
    response_json = _kone_spec_json("My deck", _kone_slide("not_a_real_archetype", title="Compare"))
    client = _FakeClient(_FakeResponse(response_json))

    with pytest.raises(RedesignError, match="doesn't fit the kone-deck-generator skill's archetypes"):
        build_deck_via_skill("A brief.", str(tmp_path / "out.pptx"), client=client)


# --------------------------------------------------------------------------
# select_archetype_overrides -- additive, fail-closed pass over an
# already-planned compose.py outline
# --------------------------------------------------------------------------


def _outline_item(kind="content", **overrides):
    item = {
        "source_slide_index": 1, "kind": kind, "title": "A title", "subtitle": None,
        "bullets": ["Point one"], "columns": [], "quote_text": None, "quote_author": None,
        "quote_label": None, "stats": [], "milestones": [], "variant": None,
    }
    item.update(overrides)
    return item


@needs_skill
def test_select_archetype_overrides_returns_a_valid_override():
    items = [_outline_item(kind="stat", title="Resolution", bullets=[])]
    response = json.dumps({"overrides": [
        {"outline_index": 0, "archetype": "hero_stat", "eyebrow": "Resolution", "value": "91%",
         "caption": "resolved", "support": "91% resolved"},
    ]})
    client = _FakeClient(_FakeResponse(response))

    overrides = select_archetype_overrides(items, client=client)

    assert overrides == {0: {
        "archetype": "hero_stat", "eyebrow": "Resolution", "value": "91%",
        "caption": "resolved", "support": "91% resolved",
    }}


def test_select_archetype_overrides_skips_the_call_entirely_with_no_candidate_kinds():
    items = [_outline_item(kind="cover"), _outline_item(kind="quote"), _outline_item(kind="end")]
    client = _FakeClient(_FakeResponse("{}"))

    overrides = select_archetype_overrides(items, client=client)

    assert overrides == {}
    assert client.messages.calls == []


@needs_skill
def test_select_archetype_overrides_rejects_an_unknown_archetype_name():
    items = [_outline_item(kind="content")]
    response = json.dumps({"overrides": [{"outline_index": 0, "archetype": "not_a_real_archetype", "title": "x"}]})
    client = _FakeClient(_FakeResponse(response))

    overrides = select_archetype_overrides(items, client=client)

    assert overrides == {}


@needs_skill
def test_select_archetype_overrides_rejects_an_out_of_range_outline_index():
    items = [_outline_item(kind="content")]
    response = json.dumps({"overrides": [{"outline_index": 5, "archetype": "hero_stat", "value": "x"}]})
    client = _FakeClient(_FakeResponse(response))

    overrides = select_archetype_overrides(items, client=client)

    assert overrides == {}


def test_select_archetype_overrides_fails_closed_on_malformed_json():
    items = [_outline_item(kind="content")]
    client = _FakeClient(_FakeResponse("not json"))

    overrides = select_archetype_overrides(items, client=client)

    assert overrides == {}


def test_select_archetype_overrides_fails_closed_on_refusal():
    items = [_outline_item(kind="content")]
    client = _FakeClient(_FakeResponse('{"overrides": []}', stop_reason="refusal"))

    overrides = select_archetype_overrides(items, client=client)

    assert overrides == {}


# --------------------------------------------------------------------------
# build_deck_with_archetypes
# --------------------------------------------------------------------------


def test_build_deck_with_archetypes_delegates_to_compose_build_deck_with_no_overrides(tmp_path):
    outline = Outline(slides=[SlideSpec(kind="content", title="Highlights", bullets=["Grew nicely"])])

    from deckguard.compose import build_deck as compose_build_deck

    expected_out = tmp_path / "expected.pptx"
    expected = compose_build_deck(outline, str(expected_out))

    got_out = tmp_path / "got.pptx"
    got = build_deck_with_archetypes(outline, str(got_out), overrides={})

    assert got.slide_count == expected.slide_count
    assert got.layouts_used == expected.layouts_used


@needs_skill
def test_build_deck_with_archetypes_renders_an_override_and_skips_fix_deck_for_it(tmp_path):
    outline = Outline(slides=[
        SlideSpec(kind="content", title="Highlights", bullets=["Grew nicely"]),
        SlideSpec(kind="stat", title="Resolution"),  # content irrelevant -- overridden below
    ])
    overrides = {1: {
        "archetype": "hero_stat", "eyebrow": "Resolution", "value": "91.2%",
        "caption": "of all requests cleared within the focus period",
        "support": "674 of 739 tickets resolved.",
    }}

    out_path = tmp_path / "out.pptx"
    result = build_deck_with_archetypes(outline, str(out_path), overrides=overrides)

    assert result.slide_count == 2
    assert result.layouts_used[1] == "hero_stat"

    from pptx import Presentation
    from pptx.dml.color import RGBColor

    prs = Presentation(str(out_path))
    archetype_slide = prs.slides[1]
    texts = [
        s.text_frame.text for s in archetype_slide.shapes
        if getattr(s, "has_text_frame", False) and s.text_frame.text.strip()
    ]
    assert any("91.2%" in t for t in texts)

    # The muted-grey caption/support text (#727272, kone_engine.GREY) is
    # NOT in brand_rules.yaml's approved-colors list -- if fix_deck had
    # run over this slide it would have flagged or remapped it. Confirm
    # it survives untouched.
    grey_runs = [
        run for s in archetype_slide.shapes if getattr(s, "has_text_frame", False)
        for p in s.text_frame.paragraphs for run in p.runs
        if run.font.color.type is not None and str(run.font.color.rgb) == "727272"
    ]
    assert grey_runs, "expected at least one run still using kone_engine's own grey #727272"


@needs_skill
def test_build_deck_with_archetypes_preserves_slide_order_for_a_middle_override(tmp_path):
    """The trickier reorder case: archetype slides are physically added
    to the presentation LAST (after fix_deck runs over everything
    else), so a middle-position override specifically exercises the
    _sldIdLst reassembly -- not just "append one archetype slide at
    the end", which wouldn't catch a reordering bug."""
    outline = Outline(slides=[
        SlideSpec(kind="content", title="First", bullets=["A"]),
        SlideSpec(kind="stat", title="Middle (overridden)"),
        SlideSpec(kind="content", title="Third", bullets=["C"]),
    ])
    overrides = {1: {
        "archetype": "hero_stat", "eyebrow": "Middle", "value": "42%",
        "caption": "in the middle", "support": "middle slide check",
    }}

    out_path = tmp_path / "out.pptx"
    result = build_deck_with_archetypes(outline, str(out_path), overrides=overrides)

    assert result.layouts_used == ["Title and content A", "hero_stat", "Title and content A"]

    from pptx import Presentation

    prs = Presentation(str(out_path))
    titles = [
        next(s.text_frame.text for s in slide.shapes if getattr(s, "has_text_frame", False) and s.text_frame.text.strip())
        for slide in prs.slides
    ]
    assert titles[0] == "First"
    assert "42%" in titles[1] or titles[1] == "MIDDLE"
    assert titles[2] == "Third"


# --------------------------------------------------------------------------
# apply_rebrand's (mode='brand', review=True only) archetype coexistence:
# select_archetype_overrides_for_rebrand + apply_archetype_overrides_to_deck
# --------------------------------------------------------------------------


def _build_simple_deck(out_path, n=3):
    from deckguard.compose import build_deck as compose_build_deck

    outline = Outline(slides=[SlideSpec(kind="content", title=f"Slide {i}", bullets=[f"Point {i}"]) for i in range(1, n + 1)])
    compose_build_deck(outline, str(out_path))


@needs_skill
def test_select_archetype_overrides_for_rebrand_returns_a_valid_override():
    from deckguard.retemplate import SlideProfile

    profiles = {2: SlideProfile(title="Resolution", text_blocks=[[(0, "91% resolved")]], images=[], eligible=True)}
    response = json.dumps({"overrides": [
        {"outline_index": 2, "archetype": "hero_stat", "eyebrow": "Resolution", "value": "91%",
         "caption": "c", "support": "s"},
    ]})
    client = _FakeClient(_FakeResponse(response))

    overrides = select_archetype_overrides_for_rebrand(profiles, client=client)

    assert overrides == {2: {
        "archetype": "hero_stat", "eyebrow": "Resolution", "value": "91%", "caption": "c", "support": "s",
    }}


def test_select_archetype_overrides_for_rebrand_skips_the_call_with_no_candidates():
    client = _FakeClient(_FakeResponse("{}"))

    overrides = select_archetype_overrides_for_rebrand({}, client=client)

    assert overrides == {}
    assert client.messages.calls == []


@needs_skill
def test_apply_archetype_overrides_to_deck_swaps_a_slide_in_place(tmp_path):
    deck_path = tmp_path / "deck.pptx"
    _build_simple_deck(deck_path, n=3)

    overrides = {2: {
        "archetype": "hero_stat", "eyebrow": "Middle", "value": "42%", "caption": "c", "support": "s",
    }}
    layout_by_index = apply_archetype_overrides_to_deck(str(deck_path), overrides)

    assert layout_by_index == {2: "hero_stat"}

    from pptx import Presentation

    prs = Presentation(str(deck_path))
    assert len(prs.slides) == 3
    assert prs.slides[0].shapes.title.text_frame.text == "Slide 1"
    assert prs.slides[2].shapes.title.text_frame.text == "Slide 3"
    texts = [
        s.text_frame.text for s in prs.slides[1].shapes
        if getattr(s, "has_text_frame", False) and s.text_frame.text.strip()
    ]
    assert any("42%" in t for t in texts)


def test_apply_archetype_overrides_to_deck_is_a_noop_with_no_overrides(tmp_path):
    deck_path = tmp_path / "deck.pptx"
    _build_simple_deck(deck_path, n=1)

    result = apply_archetype_overrides_to_deck(str(deck_path), {})

    assert result == {}


# --------------------------------------------------------------------------
# Source-image carryover into an archetype's picture slots
# --------------------------------------------------------------------------


def _blobs(tmp_path, n):
    """n visually distinct image blobs, as raw bytes -- the same shape
    SlideProfile.images / _attach_source_images carry."""
    from tests.helpers import make_pattern_png

    return [Path(make_pattern_png(tmp_path / f"p{i}.png", seed=i)).read_bytes() for i in range(n)]


def _pictures(slide):
    return [s for s in slide.shapes if s.shape_type is not None and s.shape_type.name == "PICTURE"]


@needs_skill
def test_archetype_override_carries_a_source_image_into_a_single_picture_slot(tmp_path):
    """The gap this closes: an image-bearing slide used to render its
    archetype's picture slot as an empty sand placeholder, because
    kone_engine._image() wants a path while everything upstream carries
    raw bytes."""
    from pptx import Presentation

    outline = Outline(slides=[SlideSpec(kind="content", title="Recap", bullets=["a"], images=_blobs(tmp_path, 1))])
    overrides = {0: {
        "archetype": "numbered_summary_picture", "title": "Recap",
        "items": [{"number": "01", "text": "First point"}],
    }}

    out_path = tmp_path / "out.pptx"
    build_deck_with_archetypes(outline, str(out_path), overrides=overrides)

    pics = _pictures(Presentation(str(out_path)).slides[0])
    assert len(pics) == 1
    assert len(pics[0].image.blob) > 0


@needs_skill
def test_archetype_override_carries_one_image_per_group_item(tmp_path):
    from pptx import Presentation

    outline = Outline(slides=[SlideSpec(kind="content", title="Options", bullets=["a"], images=_blobs(tmp_path, 3))])
    overrides = {0: {
        "archetype": "three_picture_cards", "title": "Options",
        "cards": [{"heading": f"Card {i}", "bullets": ["x"]} for i in range(3)],
    }}

    out_path = tmp_path / "out.pptx"
    build_deck_with_archetypes(outline, str(out_path), overrides=overrides)

    pics = _pictures(Presentation(str(out_path)).slides[0])
    assert len(pics) == 3
    assert len({p.image.blob for p in pics}) == 3  # each card got its OWN image, not the same one repeated


@needs_skill
def test_archetype_override_still_renders_with_no_source_images(tmp_path):
    """A picture archetype chosen for a slide that has no images must
    still render (kone_engine falls back to its sand placeholder), never
    raise -- image injection is strictly additive."""
    outline = Outline(slides=[SlideSpec(kind="content", title="Options", bullets=["a"], images=[])])
    overrides = {0: {
        "archetype": "three_picture_cards", "title": "Options",
        "cards": [{"heading": "Card", "bullets": ["x"]}],
    }}

    result = build_deck_with_archetypes(outline, str(tmp_path / "out.pptx"), overrides=overrides)

    assert result.layouts_used == ["three_picture_cards"]


@needs_skill
def test_apply_archetype_overrides_to_deck_carries_images(tmp_path):
    """The brand-mode (--review) path takes its images via an explicit
    images_by_index arg, since it works from a finished deck rather than
    a compose.py outline."""
    from pptx import Presentation

    deck_path = tmp_path / "deck.pptx"
    _build_simple_deck(deck_path, n=2)

    overrides = {2: {"archetype": "numbered_summary_picture", "title": "Recap",
                     "items": [{"number": "01", "text": "Point"}]}}
    apply_archetype_overrides_to_deck(str(deck_path), overrides, images_by_index={2: _blobs(tmp_path, 1)})

    pics = _pictures(Presentation(str(deck_path)).slides[1])
    assert len(pics) == 1 and len(pics[0].image.blob) > 0


@needs_skill
def test_planning_prompt_reports_image_count_and_never_leaks_a_photo_path():
    """The skill's own SAMPLES carry absolute local photo paths (they
    render a standalone gallery); echoing those into the prompt would
    invite the model to emit or invent a path, when picture slots are
    filled automatically."""
    from deckguard.skill_bridge import _kone_archetype_guide

    guide = _kone_archetype_guide()
    assert "/assets/photos/" not in guide
    assert "filled automatically" in guide

    items = [_outline_item(kind="content", images=[b"\x89PNG-fake"])]
    client = _FakeClient(_FakeResponse(json.dumps({"overrides": []})))
    select_archetype_overrides(items, client=client)

    sent = client.messages.calls[0]["messages"][0]["content"]
    assert '"image_count": 1' in sent
    assert "PNG-fake" not in sent  # raw bytes never serialized
