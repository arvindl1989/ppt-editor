import importlib
import re

from fastapi.testclient import TestClient

from tests.helpers import add_rectangle, add_slide, body_run, new_deck, set_run, title_run


def _write_violating_deck(path):
    prs = new_deck()
    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Calibri", color_hex="005EB8")
    prs.save(str(path))


def _write_remap_violating_deck(path):
    """A shape fill (off-brand color) and body-text font (off-brand,
    already-approved black color) violation on the MIDDLE slide.

    Deliberately not on the title/heading (subject to the separate
    heading_always_dark contrast rule, which overrides any color
    regardless of remap target) and not a shape fill's text color left
    unapproved (Inter's text_colors rule restricts to black/white only,
    which would swallow any other override) -- both would make it
    impossible to tell whether a *palette remap* override actually took
    effect end to end. Three slides so /fix's cover/outro migration
    (first + last slide only) leaves this one untouched."""
    prs = new_deck()
    add_slide(prs)
    slide = add_slide(prs)
    add_rectangle(slide, name="Panel", fill_hex="005EB8", left_in=1, top_in=1, width_in=2, height_in=1)
    set_run(body_run(slide), text="Body copy", font="Calibri", color_hex="141414")
    add_slide(prs)
    prs.save(str(path))


def _write_deck_pair_for_learn(old_path, new_path):
    """An old deck using an off-brand color/font, and a reference deck
    where those same elements use the corresponding brand color/font --
    close enough in usage-count to be a confident correlation."""
    old_prs = new_deck()
    slide = add_slide(old_prs)
    set_run(body_run(slide), text="Body copy", font="Arial", color_hex="AABBCC")
    old_prs.save(str(old_path))

    new_prs = new_deck()
    slide2 = add_slide(new_prs)
    set_run(body_run(slide2), text="Body copy", font="Inter", color_hex="1450F5")
    new_prs.save(str(new_path))


def _client(tmp_path, monkeypatch, password=None):
    monkeypatch.setenv("DECKGUARD_WEB_STORAGE", str(tmp_path / "storage"))
    if password:
        monkeypatch.setenv("DECKGUARD_WEB_PASSWORD", password)
    else:
        monkeypatch.delenv("DECKGUARD_WEB_PASSWORD", raising=False)
    from deckguard import web as web_mod

    importlib.reload(web_mod)  # pick up the env vars set above
    return TestClient(web_mod.app), web_mod


def test_index_renders(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "deckguard" in resp.text


def test_audit_flow(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)

    with deck.open("rb") as f:
        resp = client.post("/audit", files={"file": ("d.pptx", f, "application/octet-stream")})
    assert resp.status_code == 200
    assert "critical" in resp.text
    assert "/download/" in resp.text


def test_fix_flow_and_download(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)

    with deck.open("rb") as f:
        resp = client.post("/fix", files={"file": ("d.pptx", f, "application/octet-stream")})
    assert resp.status_code == 200
    assert "changes applied" in resp.text.lower() or "changes-applied" in resp.text.lower() or "Fixed" in resp.text

    import re

    m = re.search(r'/download/([a-f0-9]+)/fixed\.pptx', resp.text)
    assert m, "no fixed.pptx download link found in response"
    dl = client.get(m.group(0))
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith("application/vnd.openxmlformats")

    changelog_url = m.group(0).replace("fixed.pptx", "changelog.json")
    dl_json = client.get(changelog_url)
    assert dl_json.status_code == 200


def test_fix_flow_also_migrates_non_standard_cover_and_outro(tmp_path, monkeypatch):
    """The /fix route (the one Railway/the hosted tool actually calls)
    must run the same cover/outro migration the CLI's `migrate` command
    does -- this was missing initially (migrate was CLI-only), so the
    hosted tool never picked up the new cover/outro at all."""
    client, _ = _client(tmp_path, monkeypatch)
    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)  # single slide, not on a KONE Cover/Outro layout

    with deck.open("rb") as f:
        resp = client.post("/fix", files={"file": ("d.pptx", f, "application/octet-stream")})
    assert resp.status_code == 200
    assert "org template" in resp.text

    m = re.search(r'/download/([a-f0-9]+)/fixed\.pptx', resp.text)
    assert m
    dl = client.get(m.group(0))
    assert dl.status_code == 200

    from pptx import Presentation
    import io

    prs = Presentation(io.BytesIO(dl.content))
    assert prs.slides[0].slide_layout.name in ("Cover B", "Outro")


def _panel_fill_hex(prs):
    for shape in prs.slides[1].shapes:
        if shape.name == "Panel":
            return str(shape.fill.fore_color.rgb)
    raise AssertionError("Panel shape not found on middle slide")


def _body_run(prs):
    return prs.slides[1].placeholders[1].text_frame.paragraphs[0].runs[0]


def test_fix_flow_shows_remap_override_table(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    deck = tmp_path / "d.pptx"
    _write_remap_violating_deck(deck)  # fill #005EB8 (-> #1450F5), font Calibri (-> Inter)

    with deck.open("rb") as f:
        resp = client.post("/fix", files={"file": ("d.pptx", f, "application/octet-stream")})
    assert resp.status_code == 200
    assert "Review remapped colors" in resp.text
    assert "005EB8" in resp.text and "Calibri" in resp.text
    assert re.search(r'/regenerate/[a-f0-9]+', resp.text), "no regenerate form action found"


def test_regenerate_applies_approved_color_and_font_overrides(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    deck = tmp_path / "d.pptx"
    _write_remap_violating_deck(deck)

    with deck.open("rb") as f:
        resp = client.post("/fix", files={"file": ("d.pptx", f, "application/octet-stream")})
    m = re.search(r'/regenerate/([a-f0-9]+)', resp.text)
    assert m
    token = m.group(1)

    resp2 = client.post(
        f"/regenerate/{token}",
        data={"color_override__005EB8": "FF5F28", "font_override__Calibri": "Inter SemiBold"},
    )
    assert resp2.status_code == 200

    dl_m = re.search(r'/download/([a-f0-9]+)/fixed\.pptx', resp2.text)
    assert dl_m
    dl = client.get(dl_m.group(0))
    assert dl.status_code == 200

    import io

    from pptx import Presentation

    prs = Presentation(io.BytesIO(dl.content))
    assert _panel_fill_hex(prs) == "FF5F28"
    assert _body_run(prs).font.name == "Inter SemiBold"


def test_regenerate_ignores_non_approved_override(tmp_path, monkeypatch):
    """A submitted override that isn't in the brand-approved palette must
    be silently ignored, keeping the deterministic default target --
    overrides are constrained to brand guidelines, not free-form."""
    client, _ = _client(tmp_path, monkeypatch)
    deck = tmp_path / "d.pptx"
    _write_remap_violating_deck(deck)

    with deck.open("rb") as f:
        resp = client.post("/fix", files={"file": ("d.pptx", f, "application/octet-stream")})
    token = re.search(r'/regenerate/([a-f0-9]+)', resp.text).group(1)

    resp2 = client.post(f"/regenerate/{token}", data={"color_override__005EB8": "ABCDEF"})
    assert resp2.status_code == 200

    dl_m = re.search(r'/download/([a-f0-9]+)/fixed\.pptx', resp2.text)
    dl = client.get(dl_m.group(0))

    import io

    from pptx import Presentation

    prs = Presentation(io.BytesIO(dl.content))
    assert _panel_fill_hex(prs) == "1450F5"  # unchanged default target, not the rejected ABCDEF


def test_regenerate_unknown_token_gives_clean_message(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    resp = client.post("/regenerate/deadbeef", data={})
    assert resp.status_code == 200
    assert "expired" in resp.text.lower()


def test_corrupt_file_gives_clean_error_not_500(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    resp = client.post("/audit", files={"file": ("bad.pptx", b"not a real pptx", "application/octet-stream")})
    assert resp.status_code == 200  # rendered as a friendly error page, not a crash
    assert "valid .pptx" in resp.text
    assert "Traceback" not in resp.text


def test_download_rejects_path_traversal_and_unknown_token(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    resp = client.get("/download/deadbeef/../../../etc/passwd")
    assert resp.status_code == 404
    resp2 = client.get("/download/0000000000000000000000000000000/fixed.pptx")
    assert resp2.status_code == 404


SAMPLE_OUTLINE = """slides:
  - kind: cover
    title: "Composed via the web app"
  - kind: content
    title: "What's inside"
    bullets: ["First point", "Second point"]
"""


def test_create_flow_fresh_deck_and_download(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    resp = client.post("/create", data={"outline": SAMPLE_OUTLINE})
    assert resp.status_code == 200
    assert "Composed" in resp.text

    m = re.search(r'/download/([a-f0-9]+)/composed\.pptx', resp.text)
    assert m, "no composed.pptx download link found in response"
    dl = client.get(m.group(0))
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_create_flow_append_to_existing_deck(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    legacy = tmp_path / "legacy.pptx"
    prs = new_deck()
    add_slide(prs)
    prs.save(str(legacy))

    with legacy.open("rb") as f:
        resp = client.post(
            "/create",
            data={"outline": SAMPLE_OUTLINE},
            files={"existing_file": ("legacy.pptx", f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    assert "Composed" in resp.text
    assert "slides built" in resp.text or "2</b>" in resp.text


def test_create_flow_tolerates_existing_file_sent_as_plain_text(tmp_path, monkeypatch):
    """Some REST clients default a form-data field to "text" instead of
    "file" -- sending existing_file as a plain filename string, not an
    actual upload. That used to 422 with a raw FastAPI validation error
    before the request body was ever read; it should degrade to "no
    file supplied" and compose a fresh deck instead."""
    client, _ = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/create",
        data={"outline": SAMPLE_OUTLINE, "existing_file": "some deck.pptx"},
    )
    assert resp.status_code == 200
    assert "Composed" in resp.text
    assert "Traceback" not in resp.text
    assert "value_error" not in resp.text


def test_create_flow_rejects_empty_outline(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    resp = client.post("/create", data={"outline": "   "})
    assert resp.status_code == 200
    assert "paste a YAML outline" in resp.text


def test_create_flow_invalid_outline_gives_clean_message(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    resp = client.post("/create", data={"outline": "slides:\n  - kind: not-a-real-kind\n"})
    assert resp.status_code == 200
    assert "unknown kind" in resp.text
    assert "Traceback" not in resp.text


def test_learn_flow_and_downloads(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    old_path = tmp_path / "old.pptx"
    new_path = tmp_path / "new.pptx"
    _write_deck_pair_for_learn(old_path, new_path)

    with old_path.open("rb") as fo, new_path.open("rb") as fn:
        resp = client.post(
            "/learn",
            files={
                "old_file": ("old.pptx", fo, "application/octet-stream"),
                "new_file": ("new.pptx", fn, "application/octet-stream"),
            },
        )
    assert resp.status_code == 200
    assert "high-confidence" in resp.text
    assert "AABBCC" in resp.text and "1450F5" in resp.text.upper()

    m = re.search(r'/download/([a-f0-9]+)/fixed\.pptx', resp.text)
    assert m, "no fixed.pptx download link found in response"
    dl_pptx = client.get(m.group(0))
    assert dl_pptx.status_code == 200

    dl_yaml = client.get(m.group(0).replace("fixed.pptx", "brand_rules.yaml"))
    assert dl_yaml.status_code == 200
    assert b"AABBCC" in dl_yaml.content.upper() or b"aabbcc" in dl_yaml.content.lower()

    dl_json = client.get(m.group(0).replace("fixed.pptx", "learn_report.json"))
    assert dl_json.status_code == 200


def test_learn_requires_both_files_valid(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    old_path = tmp_path / "old.pptx"
    new_path = tmp_path / "new.pptx"
    _write_deck_pair_for_learn(old_path, new_path)

    with old_path.open("rb") as fo:
        resp = client.post(
            "/learn",
            files={
                "old_file": ("old.pptx", fo, "application/octet-stream"),
                "new_file": ("bad.pptx", b"not a real pptx", "application/octet-stream"),
            },
        )
    assert resp.status_code == 200
    assert "valid .pptx" in resp.text or "Learn failed" in resp.text
    assert "Traceback" not in resp.text


def test_password_gate(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch, password="s3cret")
    assert client.get("/").status_code == 401
    assert client.get("/", auth=("x", "wrong")).status_code == 401
    assert client.get("/", auth=("x", "s3cret")).status_code == 200
