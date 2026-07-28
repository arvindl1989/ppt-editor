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
    KONE_SPEC_SCHEMA,
    _load_creator,
    _skill_dir,
    _validate_kone_spec,
    build_deck_via_skill,
    call_claude_for_kone_spec,
)
from tests.test_redesign import _FakeClient, _FakeResponse, _kone_slide, _kone_spec_json

_skill_installed = (_skill_dir() / "kone_deck_creator.py").is_file()
needs_skill = pytest.mark.skipif(not _skill_installed, reason="kone-deck-generator skill not installed")


def _known_layouts():
    return set(_load_creator().REGISTRY.keys())


def test_build_deck_via_skill_raises_a_clean_error_when_the_skill_is_not_installed(tmp_path, monkeypatch):
    """Doesn't need the real skill on disk -- exercises the opposite case:
    an actionable RedesignError, never a raw ImportError/FileNotFoundError,
    when KONE_DECK_GENERATOR_DIR points nowhere real."""
    import deckguard.skill_bridge as skill_bridge

    monkeypatch.setattr(skill_bridge, "_creator_module", None)
    monkeypatch.setenv("KONE_DECK_GENERATOR_DIR", str(tmp_path / "does-not-exist"))

    with pytest.raises(RedesignError, match="isn't installed"):
        build_deck_via_skill("A brief.", str(tmp_path / "out.pptx"), client=_FakeClient(_FakeResponse("{}")))


@needs_skill
def test_validate_kone_spec_accepts_a_well_formed_spec():
    spec = json.loads(
        _kone_spec_json(
            "Deck title",
            _kone_slide("section_divider", eyebrow="Overview", title="A new era"),
            _kone_slide("title_content", title="Why it matters", bullets=["Point one", "Point two"]),
            _kone_slide(
                "two_content", title="Compare",
                columns=[{"heading": "Before", "bullets": ["A"]}, {"heading": "After", "bullets": ["B"]}],
            ),
            _kone_slide(
                "three_stats", title="By the numbers",
                stats=[
                    {"label": "Volume", "value": "2x", "desc": "growth"},
                    {"label": "Resolution", "value": "91%", "desc": "resolved"},
                    {"label": "Phases", "value": "3", "desc": "planned"},
                ],
            ),
            _kone_slide(
                "roadmap", eyebrow="2025-2027", title="Where next",
                phases=[
                    {"year": "2025", "title": "Foundation", "desc": "Standardise."},
                    {"year": "2026", "title": "Scale", "desc": "Automate."},
                ],
            ),
            _kone_slide("quote", label="Principle", quote="Ship it.", attribution="A KONE engineer"),
        )
    )
    _validate_kone_spec(spec, _known_layouts())  # must not raise


@needs_skill
def test_validate_kone_spec_rejects_unknown_layout():
    spec = {"title": "T", "slides": [_kone_slide("carousel", title="x")]}
    with pytest.raises(RedesignError, match="unknown layout"):
        _validate_kone_spec(spec, _known_layouts())


@needs_skill
def test_validate_kone_spec_rejects_wrong_column_count():
    spec = {
        "title": "T",
        "slides": [_kone_slide("two_content", title="Compare", columns=[{"heading": "Only one", "bullets": ["A"]}])],
    }
    with pytest.raises(RedesignError, match="exactly 2 columns"):
        _validate_kone_spec(spec, _known_layouts())


@needs_skill
def test_validate_kone_spec_rejects_wrong_stat_count():
    spec = {
        "title": "T",
        "slides": [_kone_slide("three_stats", title="Stats", stats=[{"label": "A", "value": "1", "desc": "d"}])],
    }
    with pytest.raises(RedesignError, match="exactly 3 stats"):
        _validate_kone_spec(spec, _known_layouts())


@needs_skill
def test_validate_kone_spec_rejects_overlong_bullet():
    spec = {
        "title": "T",
        "slides": [_kone_slide("title_content", title="Fine", bullets=["x" * 200])],
    }
    with pytest.raises(RedesignError, match="over the 90-char limit"):
        _validate_kone_spec(spec, _known_layouts())


@needs_skill
def test_validate_kone_spec_rejects_out_of_range_phase_count():
    spec = {
        "title": "T",
        "slides": [_kone_slide("roadmap", title="Roadmap", phases=[{"year": "2025", "title": "Only one", "desc": "d"}])],
    }
    with pytest.raises(RedesignError, match="needs 2-5 phases"):
        _validate_kone_spec(spec, _known_layouts())


@needs_skill
def test_call_claude_for_kone_spec_sends_the_brief_and_returns_usage():
    response_json = _kone_spec_json("T", _kone_slide("title_content", title="X", bullets=["a"]))
    client = _FakeClient(_FakeResponse(response_json, input_tokens=1200, output_tokens=300))

    spec, usage = call_claude_for_kone_spec("Build a deck about X.", client=client)

    assert spec["title"] == "T"
    assert usage.input_tokens == 1200 and usage.output_tokens == 300
    sent = client.messages.calls[0]
    assert "Build a deck about X." in sent["messages"][0]["content"]
    assert sent["output_config"]["format"]["schema"] is KONE_SPEC_SCHEMA


@needs_skill
def test_build_deck_via_skill_renders_a_real_pptx(tmp_path):
    response_json = _kone_spec_json(
        "My deck",
        _kone_slide("title_content", title="Point one", bullets=["a", "b"]),
    )
    client = _FakeClient(_FakeResponse(response_json))

    out_path = tmp_path / "out.pptx"
    compose_result, redesign_result = build_deck_via_skill("A brief.", str(out_path), client=client)

    assert out_path.exists()
    assert compose_result.slide_count == 3  # Cover F + 1 body + Outro
    assert compose_result.layouts_used == ["Cover F", "title_content", "Outro"]
    assert redesign_result.outline is None
    assert redesign_result.usage.input_tokens > 0


@needs_skill
def test_build_deck_via_skill_raises_a_clean_error_for_an_invalid_spec(tmp_path):
    response_json = _kone_spec_json("My deck", _kone_slide("two_content", title="Compare", columns=[]))
    client = _FakeClient(_FakeResponse(response_json))

    with pytest.raises(RedesignError, match="doesn't fit the kone-deck-generator skill's layouts"):
        build_deck_via_skill("A brief.", str(tmp_path / "out.pptx"), client=client)
