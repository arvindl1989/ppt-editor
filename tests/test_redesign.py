"""Tests for deckguard's AI-assisted redesign (redesign.py): extracting
eligible content from an arbitrary deck, asking Claude to map it onto
compose.py's outline schema, then building it through the same
deterministic pipeline `deckguard create` uses.

No real network/API calls -- every test injects a fake Anthropic-shaped
client, consistent with the rest of this suite's "works with no API key"
philosophy for anything that doesn't require a live account.
"""

import json

import pytest
from pptx.util import Inches

from deckguard.redesign import (
    RedesignError,
    Usage,
    call_claude_for_outline,
    extract_eligible_slides,
    redesign_deck,
)
from deckguard.slide_import import default_template_path
from tests.helpers import add_slide, body_run, new_deck, title_run

TEMPLATE_PATH = default_template_path()
pytestmark = pytest.mark.skipif(not TEMPLATE_PATH.exists(), reason="bundled template asset not present")


# --------------------------------------------------------------------------
# fake Anthropic client
# --------------------------------------------------------------------------


class _FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeUsage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeResponse:
    def __init__(self, content_text, stop_reason="end_turn", input_tokens=1000, output_tokens=500):
        self.content = [_FakeTextBlock(content_text)] if content_text is not None else []
        self.stop_reason = stop_reason
        self.usage = _FakeUsage(input_tokens, output_tokens)


class _FakeStreamCM:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._response


class _FakeMessages:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeStreamCM(self._response)


class _FakeClient:
    def __init__(self, response):
        self.messages = _FakeMessages(response)


def _outline_json(*items):
    return json.dumps({"slides": list(items)})


def _slide_item(index, kind="content", **overrides):
    item = {
        "source_slide_index": index,
        "kind": kind,
        "title": "A title",
        "subtitle": None,
        "bullets": ["Point one", "Point two"],
        "columns": [],
        "quote_text": None,
        "quote_author": None,
        "quote_label": None,
        "stats": [],
        "milestones": [],
        "variant": None,
    }
    item.update(overrides)
    return item


# --------------------------------------------------------------------------
# extract_eligible_slides
# --------------------------------------------------------------------------


def test_extract_eligible_slides_separates_ordinary_from_disqualified():
    prs = new_deck()
    ok_slide = add_slide(prs)
    title_run(ok_slide).text = "Ordinary slide"
    body_run(ok_slide).text = "Some content"

    table_slide = add_slide(prs)
    table_slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(3), Inches(2))

    eligible, skipped = extract_eligible_slides(prs)

    assert [i for i, _p in eligible] == [1]
    assert [s.slide_index for s in skipped] == [2]
    assert "table" in skipped[0].reason


def test_extract_eligible_slides_empty_deck_slide_is_skipped():
    prs = new_deck()
    add_slide(prs)  # title/body placeholders present but empty
    _eligible, skipped = extract_eligible_slides(prs)
    assert len(skipped) == 1


# --------------------------------------------------------------------------
# call_claude_for_outline
# --------------------------------------------------------------------------


def test_call_claude_for_outline_parses_valid_response():
    prs = new_deck()
    slide = add_slide(prs)
    title_run(slide).text = "Quarterly review"
    body_run(slide).text = "Revenue up"
    eligible, _skipped = extract_eligible_slides(prs)

    response_json = _outline_json(_slide_item(1, title="Quarterly review"))
    client = _FakeClient(_FakeResponse(response_json, input_tokens=1200, output_tokens=600))

    raw_slides, usage = call_claude_for_outline(eligible, client=client)

    assert raw_slides[0]["title"] == "Quarterly review"
    assert usage.input_tokens == 1200
    assert usage.output_tokens == 600
    assert usage.model == "claude-opus-5"
    # (1200/1e6)*5 + (600/1e6)*25 = 0.006 + 0.015 = 0.021
    assert usage.estimated_cost_usd == pytest.approx(0.021)


def test_call_claude_for_outline_passes_model_and_effort_through():
    prs = new_deck()
    slide = add_slide(prs)
    title_run(slide).text = "T"
    body_run(slide).text = "B"
    eligible, _ = extract_eligible_slides(prs)

    client = _FakeClient(_FakeResponse(_outline_json(_slide_item(1))))
    call_claude_for_outline(eligible, model="claude-sonnet-5", effort="medium", client=client)

    call_kwargs = client.messages.calls[0]
    assert call_kwargs["model"] == "claude-sonnet-5"
    assert call_kwargs["output_config"]["effort"] == "medium"
    assert call_kwargs["output_config"]["format"]["type"] == "json_schema"


def test_call_claude_for_outline_raises_on_refusal():
    prs = new_deck()
    slide = add_slide(prs)
    title_run(slide).text = "T"
    body_run(slide).text = "B"
    eligible, _ = extract_eligible_slides(prs)

    client = _FakeClient(_FakeResponse(None, stop_reason="refusal"))
    with pytest.raises(RedesignError, match="declined"):
        call_claude_for_outline(eligible, client=client)


def test_call_claude_for_outline_raises_on_invalid_json():
    prs = new_deck()
    slide = add_slide(prs)
    title_run(slide).text = "T"
    body_run(slide).text = "B"
    eligible, _ = extract_eligible_slides(prs)

    client = _FakeClient(_FakeResponse("not json"))
    with pytest.raises(RedesignError, match="not valid JSON"):
        call_claude_for_outline(eligible, client=client)


def test_call_claude_for_outline_raises_on_missing_slides_key():
    prs = new_deck()
    slide = add_slide(prs)
    title_run(slide).text = "T"
    body_run(slide).text = "B"
    eligible, _ = extract_eligible_slides(prs)

    client = _FakeClient(_FakeResponse(json.dumps({"oops": []})))
    with pytest.raises(RedesignError, match="'slides'"):
        call_claude_for_outline(eligible, client=client)


# --------------------------------------------------------------------------
# redesign_deck (end to end)
# --------------------------------------------------------------------------


def test_redesign_deck_builds_a_valid_composed_deck(tmp_path):
    prs = new_deck()
    cover = add_slide(prs, layout_idx=0)
    title_run(cover).text = "Annual Review"

    content = add_slide(prs)
    title_run(content).text = "Highlights"
    body_run(content).text = "Grew nicely"

    table_slide = add_slide(prs)
    table_slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(3), Inches(2))

    src_path = tmp_path / "source.pptx"
    prs.save(str(src_path))

    response_json = _outline_json(
        _slide_item(1, kind="cover", title="Annual Review", subtitle="A great year", bullets=[]),
        _slide_item(2, kind="content", title="Highlights", bullets=["Grew nicely"]),
    )
    client = _FakeClient(_FakeResponse(response_json, input_tokens=2000, output_tokens=800))

    out_path = tmp_path / "redesigned.pptx"
    compose_result, redesign_result = redesign_deck(str(src_path), str(out_path), client=client)

    assert compose_result.slide_count == 2
    assert compose_result.layouts_used[0] == "Cover B"
    assert len(redesign_result.skipped) == 1
    assert redesign_result.skipped[0].slide_index == 3
    assert redesign_result.usage.input_tokens == 2000

    from pptx import Presentation

    out_prs = Presentation(str(out_path))
    assert len(out_prs.slides) == 2


def test_redesign_deck_raises_when_nothing_is_eligible(tmp_path):
    prs = new_deck()
    table_slide = add_slide(prs)
    table_slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(3), Inches(2))
    src_path = tmp_path / "source.pptx"
    prs.save(str(src_path))

    client = _FakeClient(_FakeResponse(_outline_json()))
    with pytest.raises(RedesignError, match="no slide"):
        redesign_deck(str(src_path), str(tmp_path / "out.pptx"), client=client)


def test_usage_estimated_cost_unknown_model_is_zero():
    usage = Usage(input_tokens=1000, output_tokens=1000, model="some-future-model")
    assert usage.estimated_cost_usd == 0.0
