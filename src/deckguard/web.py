"""Hostable web app wrapping the deckguard engine -- one capability:
Transform (plan -> per-slide human review -> execute -> audit), plus a
read-only Audit. No engine logic lives here; every route calls the same
functions the CLI uses (`transform.py`, `rules_engine`, `inventory`),
so web and CLI can never disagree about what a transform or a violation
is. The four earlier flows (Fix, Learn, Create, Redesign) folded into
Transform -- their engines and CLI commands remain; only their separate
web UIs are gone.

Run locally:  uvicorn deckguard.web:app --reload
Deploy:       see Procfile / README "Hosting" section.

Optional HTTP Basic Auth: set DECKGUARD_WEB_PASSWORD to require a
password (username is ignored) before any route is reachable. Unset by
default — fine for local use, strongly recommended once this is hosted
somewhere with a public URL.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pptx import Presentation
from pptx.exc import PackageNotFoundError
from starlette.datastructures import UploadFile as _FormUploadFile

from deckguard import webtemplates as tpl
from deckguard.layouts import shape_notes

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
STORAGE_ROOT = Path(os.environ.get("DECKGUARD_WEB_STORAGE", "/tmp/deckguard-web"))
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
MAX_STORAGE_AGE_SECONDS = 2 * 60 * 60  # best-effort cleanup of anything older than 2h

app = FastAPI(title="deckguard")
security = HTTPBasic(auto_error=False)
# Self-hosted brand assets for the web UI itself (the KONE Information
# @font-face webtemplates.py's CSS references) -- separate from the
# kone-deck-generator skill's own vendored copy under assets/, which is
# there to build .pptx files, not to serve the web app's own pages.
app.mount("/static", StaticFiles(directory=Path(__file__).with_name("assets") / "fonts"), name="static")


@app.exception_handler(RequestValidationError)
async def _friendly_validation_error(request: Request, exc: RequestValidationError):
    # A malformed request otherwise 422s with a raw JSON body straight
    # from FastAPI's validation layer -- the one place a request could
    # surface a bare error instead of the friendly page every other
    # failure path renders.
    ai_enabled = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return HTMLResponse(
        tpl.page_shell(
            "deckguard",
            tpl.transform_card(ai_enabled, "That request wasn't in the expected format — please use the form below."),
        ),
        status_code=422,
    )


def _require_auth(credentials: Optional[HTTPBasicCredentials] = Depends(security)) -> None:
    password = os.environ.get("DECKGUARD_WEB_PASSWORD")
    if not password:
        return  # no password configured -> open access
    if credentials is None or not secrets.compare_digest(credentials.password, password):
        raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Basic"})


def _load_engine_config():
    config = load_config(default_config_path())
    errors = validate_config(config, base_dir=default_config_path().parent)
    blocking = [e for e in errors if "logo.new_logo_path does not exist" not in e]
    if blocking:
        # A misconfigured brand_rules.yaml is a server operator problem, not
        # a per-request one -- fail loudly rather than serving broken audits.
        raise RuntimeError(f"brand_rules.yaml is invalid: {'; '.join(blocking)}")
    return config


def _cleanup_old_uploads() -> None:
    now = time.time()
    try:
        for child in STORAGE_ROOT.iterdir():
            if child.is_dir() and now - child.stat().st_mtime > MAX_STORAGE_AGE_SECONDS:
                shutil.rmtree(child, ignore_errors=True)
    except OSError:
        pass


async def _save_upload(file: UploadFile, dest_dir: Path, filename: str = "source.pptx") -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large (50 MB limit)")
            out.write(chunk)
    return dest


def _open_presentation_or_error(path: Path) -> Presentation:
    try:
        return Presentation(str(path))
    except PackageNotFoundError:
        raise HTTPException(status_code=400, detail="That doesn't look like a valid .pptx file.")
    except Exception as exc:  # noqa: BLE001 -- surface a clean message, never a raw traceback
        raise HTTPException(status_code=400, detail=f"Could not open the file: {exc}")


def _home(error: str | None = None, status_code: int = 200) -> HTMLResponse:
    ai_enabled = bool(os.environ.get("ANTHROPIC_API_KEY"))
    body = tpl.home_hero() + tpl.transform_card(ai_enabled, error)
    return HTMLResponse(tpl.page_shell("deckguard", body, home=True), status_code=status_code)


@app.get("/", response_class=HTMLResponse)
def index(_auth: None = Depends(_require_auth)):
    return _home()


@app.get("/download/{token}/{filename}")
def download(token: str, filename: str, _auth: None = Depends(_require_auth)):
    if not token.isalnum() or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="Not found")
    path = STORAGE_ROOT / token / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found (results expire after a couple of hours)")
    media_type = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if filename.endswith(".pptx")
        else "application/json"
    )
    return FileResponse(path, media_type=media_type, filename=filename)


# --------------------------------------------------------------------------
# Build: pick slides -> fill them -> deck
# --------------------------------------------------------------------------


@app.get("/build", response_class=HTMLResponse)
def build_pick(_auth: None = Depends(_require_auth)):
    from deckguard import brandmode

    sets = brandmode.slide_sets()
    slides = {a: brandmode.slides_in(a) for a in brandmode.set_names()}
    body = tpl.builder_pick_page(sets, slides)
    return HTMLResponse(tpl.page_shell("Build a deck", body, wide=True))


@app.post("/build/compose", response_class=HTMLResponse)
async def build_compose(request: Request, _auth: None = Depends(_require_auth)):
    from deckguard import brandmode
    from deckguard.registry import (
        _archetype_image_slots,
        _derived_content_keys,
        _load_archetypes,
    )

    form = await request.form()
    picks = [p for p in form.getlist("pick") if ":" in p]
    if not picks:
        return HTMLResponse(tpl.page_shell(
            "Build a deck",
            tpl.builder_pick_page(brandmode.slide_sets(),
                                  {a: brandmode.slides_in(a) for a in brandmode.set_names()})
            .replace("<h2", '<p class="field-hint" style="color:#b00;">'
                     "Pick at least one slide.</p><h2", 1), wide=True), status_code=400)

    audience = picks[0].split(":", 1)[0]
    wanted = {int(p.split(":", 1)[1]) for p in picks if p.startswith(audience + ":")}
    built = set(_load_archetypes().ARCHETYPES)
    chosen = [s for s in brandmode.slides_in(audience)
              if s["n"] in wanted and s["archetype"] in built]
    if not chosen:
        return _home("Those slides are not built yet. Pick ones with a preview.",
                     status_code=400)

    image_slots = _archetype_image_slots()
    slides = []
    for s in chosen:
        keys = _derived_content_keys(s["archetype"])
        slots = []
        for raw in keys:
            key = raw.split(" (")[0]
            hint = raw[len(key):].strip(" ()")
            if "filled automatically" in raw:
                continue
            slots.append((key, hint))
        slides.append({**s, "id": f"{audience}-{s['n']}", "slots": slots,
                       "photos": s["archetype"] in image_slots})

    token = uuid.uuid4().hex
    work_dir = STORAGE_ROOT / token
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "compose.json").write_text(
        json.dumps({"audience": audience, "slides": slides}), encoding="utf-8")
    body = tpl.builder_edit_page(token, audience, slides)
    return HTMLResponse(tpl.page_shell("Fill the slides", body))


@app.post("/build/generate/{token}", response_class=HTMLResponse)
async def build_generate(token: str, request: Request, _auth: None = Depends(_require_auth)):
    if not token.isalnum():
        raise HTTPException(status_code=404, detail="Not found")
    work_dir = STORAGE_ROOT / token
    compose_path = work_dir / "compose.json"
    if not compose_path.exists():
        return _home("That build has expired. Start again.", status_code=404)

    plan = json.loads(compose_path.read_text())
    form = await request.form()
    spec = _spec_from_form(plan, form)
    if not spec["slides"]:
        return _home("Every slide was dropped, so there was nothing to build.", status_code=400)

    out = work_dir / "deck.pptx"
    try:
        from deckguard import layouts

        layouts.build_deck(spec, str(out))
    except Exception as exc:  # noqa: BLE001
        return _home(f"Building the deck failed: {exc}", status_code=500)

    dropped = len(plan["slides"]) - sum(
        1 for e in plan["slides"] if not form.get(f"d:{e['id']}"))
    body = tpl.builder_result_page(token, plan["audience"], len(spec["slides"]), dropped)
    return HTMLResponse(tpl.page_shell("Deck built", body))


def _spec_from_form(plan: dict, form) -> dict:
    """Turn the filled form back into a deck spec.

    An empty slot is left out rather than filled, so a slide the author
    did not finish comes out short rather than carrying placeholder
    text. Order is whatever the numbers sort to -- they do not have to
    be contiguous, which is what makes inserting one easy.
    """
    slides = []
    for entry in plan["slides"]:
        sid = entry["id"]
        if form.get(f"d:{sid}"):
            continue
        content = {"archetype": entry["archetype"]}
        for key, hint in entry["slots"]:
            raw = str(form.get(f"v:{sid}:{key}") or "").strip()
            if not raw:
                continue
            content[key] = _parse_slot(raw, hint)
        photo = str(form.get(f"p:{sid}") or "").strip()
        if photo:
            content["image"] = photo
        try:
            order = float(form.get(f"o:{sid}") or 0)
        except ValueError:
            order = 0.0
        slides.append((order, content))
        if form.get(f"x:{sid}"):
            slides.append((order + 0.5, dict(content)))

    ordered = [c for _o, c in sorted(slides, key=lambda pair: pair[0])]
    spec = {"title": plan.get("audience", "Deck").title(), "slides": ordered}
    try:
        from deckguard.registry import fill_empty_photo_slots

        fill_empty_photo_slots(spec)
    except Exception:  # noqa: BLE001
        pass
    return spec


def _parse_slot(raw: str, hint: str):
    """A list slot is one item per line; a dict item is `a | b | c` in
    the order the hint names its fields."""
    if "list of" not in hint:
        return raw
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if "×" not in hint and "{" not in hint:
        return lines
    fields = [f.strip() for f in hint.split("{", 1)[-1].rstrip("}) ").split(",")]
    fields = [f.split(":")[0].strip() for f in fields if f]
    out = []
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        out.append({f: (parts[i] if i < len(parts) else "") for i, f in enumerate(fields)})
    return out


@app.get("/health")
def health():
    return {"status": "ok"}
