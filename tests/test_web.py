"""Tests for the web app's single Transform capability (plan -> review
-> execute -> audit) plus read-only Audit, auth, and download safety.
No real network calls: AI-dependent paths run keyless (deterministic
degradation) or with the planner monkeypatched."""

import importlib
import re

from fastapi.testclient import TestClient

def _app():
    from deckguard.web import app

    return app


from tests.helpers import add_rectangle, add_slide, body_run, new_deck, set_run, title_run


def _write_violating_deck(path):
    prs = new_deck()
    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Calibri", color_hex="005EB8")
    prs.save(str(path))


def _write_three_slide_deck(path):
    prs = new_deck()
    c = add_slide(prs)
    title_run(c).text = "Annual Review"
    m = add_slide(prs)
    title_run(m).text = "Resolution rate"
    body_run(m).text = "91.2% resolved"
    e = add_slide(prs)
    title_run(e).text = "Thank you"
    prs.save(str(path))


def _client(tmp_path, monkeypatch, password=None):
    monkeypatch.setenv("DECKGUARD_WEB_STORAGE", str(tmp_path / "storage"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    if password:
        monkeypatch.setenv("DECKGUARD_WEB_PASSWORD", password)
    else:
        monkeypatch.delenv("DECKGUARD_WEB_PASSWORD", raising=False)
    from deckguard import web as web_mod

    importlib.reload(web_mod)  # pick up the env vars set above
    return TestClient(web_mod.app), web_mod


def _post_plan(client, deck_path, reference_path=None):
    files = {"file": (deck_path.name, deck_path.open("rb"), "application/octet-stream")}
    if reference_path is not None:
        files["reference"] = (reference_path.name, reference_path.open("rb"), "application/octet-stream")
    return client.post("/plan", files=files)


# --------------------------------------------------------------------------
# home / audit
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# plan -> review
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# transform (execute)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# download safety / auth
# --------------------------------------------------------------------------


def test_download_rejects_path_traversal_and_unknown_token(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    assert client.get("/download/deadbeef/nothing.pptx").status_code == 404
    assert client.get("/download/deadbeef/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert client.get("/download/not-a-token!/x.pptx").status_code == 404


def test_password_gate(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch, password="s3cret")
    assert client.get("/").status_code == 401
    assert client.get("/", auth=("anyone", "s3cret")).status_code == 200
    assert client.get("/", auth=("anyone", "wrong")).status_code == 401


def test_result_page_names_slides_that_need_a_manual_redraw(tmp_path, monkeypatch):
    """The tool already detects slides the reference deck redrew from
    scratch; the result page has to actually say so, or the user finds
    out in the meeting."""
    from deckguard import webtemplates as tpl

    audit = {"summary": {"critical": 0, "major": 0, "minor": 0}, "violations": [],
             "suppressed_archetype_findings": 0}
    outcome = {"rebuilt": [1], "archetype_swapped": [], "reference_carryover": [2, 3],
               "kept": [], "layouts_used": {}, "needs_manual_redraw": [3, 4, 5],
               "duplicate_logos_removed": 1}
    html = tpl.transform_result_page("d.pptx", outcome, audit, None, {"pptx": "/a", "json": "/b"})

    assert "Slides 3, 4, 5 need a manual redraw" in html
    assert "duplicate logo(s) removed" in html

    quiet = tpl.transform_result_page(
        "d.pptx", {**outcome, "needs_manual_redraw": [], "duplicate_logos_removed": 0},
        audit, None, {"pptx": "/a", "json": "/b"},
    )
    assert "manual redraw" not in quiet


def test_the_brief_plan_page_can_include_or_exclude_every_slide_at_once(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch, password=None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    import deckguard.web as web

    importlib.reload(web)
    from deckguard import webtemplates as templates

    entries = [{"index": i, "archetype_name": f"a{i}", "proposed_html": "<i>x</i>"}
               for i in (1, 2, 3)]
    html = templates.transform_review_page("b", "tok", entries, "brief", True)

    assert 'data-bulk-check="1"' in html and 'data-bulk-check="0"' in html
    assert html.count('name="include_') == 3
    assert html.index('class="card bulkbar"') < html.index('name="include_1"')


def test_a_slide_locked_to_one_action_is_not_reported_as_refusing_it():
    """A slide no template layout fits carries a hidden `keep` rather
    than radios. Counting only radios made "Keep as-is" report it as a
    slide that does not offer keeping -- the one thing it does offer."""
    from deckguard import webtemplates as templates

    entries = [
        {"index": 1, "default_action": "rebuild", "layout_name": "Two Content",
         "current_html": "<i>a</i>", "proposed_html": "<i>b</i>"},
        {"index": 2, "default_action": "keep", "reason": "dense copy",
         "current_html": "<i>a</i>"},
    ]
    html = templates.transform_review_page("d", "tok", entries, "deck", True)

    # slide 2 is locked: a hidden input, no radios
    assert '<input type="hidden" name="action_2" value="keep">' in html
    assert 'name="action_2" value="rebuild"' not in html
    # the script counts a hidden input already carrying the wanted value
    assert "i.type === 'hidden'" in html


def test_the_result_page_says_what_had_nowhere_to_go():
    """A slide came back as a title on an empty half because the brief's
    other four points were planned under keys the archetype does not
    read. Nothing anywhere said so."""
    from deckguard import webtemplates as templates

    outcome = {
        "rebuilt": [], "archetype_swapped": [1], "reference_carryover": [], "kept": [],
        "dropped_content": {2: ("agenda_a_table", ["text1", "text2", "text3", "text4"])},
    }
    audit = {"summary": {"critical": 0, "major": 0, "minor": 0}, "violations": []}
    html = templates.transform_result_page("d.pptx", outcome, audit, None,
                                           {"pptx": "/x.pptx", "json": "/x.json"})

    assert "nowhere to go" in html
    assert "Slide 2" in html and "agenda_a_table" in html
    for key in ("text1", "text2", "text3", "text4"):
        assert f"<code>{key}</code>" in html

    # and stays quiet when nothing was dropped
    outcome["dropped_content"] = {}
    assert "nowhere to go" not in templates.transform_result_page(
        "d.pptx", outcome, audit, None, {"pptx": "/x.pptx", "json": "/x.json"})


def test_the_landing_page_offers_one_flow():
    client = TestClient(_app())
    """It used to describe four products. Three are parked, and
    describing them was the tool's biggest source of confusion."""
    r = client.get("/")
    assert r.status_code == 200
    assert "/build" in r.text
    for gone in ("/audit", "/plan", "Audit only", "Plan transform"):
        assert gone not in r.text, gone


def test_the_parked_routes_are_gone_rather_than_hidden():
    client = TestClient(_app())
    for route in ("/audit", "/plan"):
        assert client.post(route, data={}).status_code == 404, route


def test_no_core_module_imports_from_legacy():
    """Parked code may read the core; the core may never read parked
    code. Without this the split rots back into one tangle."""
    import ast
    import pathlib

    offenders = []
    for path in pathlib.Path("src/deckguard").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            mod = getattr(node, "module", None) or ""
            names = [a.name for a in node.names]
            if "legacy" in mod or any("legacy" in n for n in names):
                offenders.append(f"{path.name}: {mod or names}")
    assert not offenders, offenders
