"""Tests for skill_bridge.py -- deckguard's bridge to the (out-of-repo,
per-machine) kone-deck-generator skill, used only for redesign_deck's
"no source deck, just a brief" path. No real network calls -- these
inject the same fake Anthropic-shaped client the rest of the redesign
test suite uses.
"""

import json

import pytest

from deckguard.redesign import RedesignError
from deckguard.skill_bridge import (
    _load_archetypes,
    _skill_dir,
    _validate_kone_spec,
    build_deck_via_skill,
    call_claude_for_kone_spec,
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
