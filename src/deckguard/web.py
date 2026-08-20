"""The deck builder: one page, one button.

Give it anything -- a brief, an announcement email, a deck of your own,
a set of slides you picked -- and it builds a deck. There is no mode to
choose first, because the inputs already say what you want:

    brief only          the planner drafts the slides
    slides picked       exactly those, in that order
    a deck attached     its designs are mined and offered as templates
    any combination     all of it, in one pass

Nothing is approved in advance. Generating gives you a .pptx and an
editable list of what it built, on the same page, so every decision is
reversible after the fact rather than demanded before.

The module path stays `deckguard.web:app` because the Procfile and
railway.json name it.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.datastructures import UploadFile as _FormUploadFile

from deckguard import screens
from deckguard import ui

STORAGE_ROOT = Path(os.environ.get("DECKGUARD_WEB_STORAGE", "/tmp/deckguard-web"))
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 80 * 1024 * 1024
UPLOAD_TTL_SECONDS = 2 * 60 * 60

app = FastAPI(title="KONE deck builder", docs_url=None, redoc_url=None)
_security = HTTPBasic(auto_error=False)


def _require_auth(credentials: Optional[HTTPBasicCredentials] = Depends(_security)) -> None:
    """Optional password gate. Unset means open, which is fine locally
    and is not fine on a public URL -- so the landing page says so."""
    expected = os.environ.get("DECKGUARD_WEB_PASSWORD")
    if not expected:
        return
    if credentials is None or credentials.password != expected:
        raise HTTPException(
            status_code=401, detail="Not authorised",
            headers={"WWW-Authenticate": "Basic"},
        )


@app.exception_handler(RequestValidationError)
async def _validation_error(_request: Request, exc: RequestValidationError):
    return HTMLResponse(
        ui.page("Deck builder", screens.home(error=str(exc.errors()[:1]))),
        status_code=400,
    )


# --------------------------------------------------------------------------
# storage
# --------------------------------------------------------------------------


def _cleanup() -> None:
    cutoff = time.time() - UPLOAD_TTL_SECONDS
    try:
        for child in STORAGE_ROOT.iterdir():
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
    except FileNotFoundError:
        pass


async def _save_upload(upload, work_dir: Path, filename: str) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / filename
    size = 0
    with path.open("wb") as handle:
        while chunk := await upload.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                handle.close()
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="That file is over 80MB.")
            handle.write(chunk)
    return path


def _session(token: str) -> dict:
    path = STORAGE_ROOT / token / "session.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That deck has expired. Start again.")
    return json.loads(path.read_text())


def _save_session(token: str, data: dict) -> None:
    work = STORAGE_ROOT / token
    work.mkdir(parents=True, exist_ok=True)
    (work / "session.json").write_text(json.dumps(data), encoding="utf-8")


# --------------------------------------------------------------------------
# routes
# --------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def index(_auth: None = Depends(_require_auth)):
    return HTMLResponse(ui.page("Deck builder", screens.home()))


@app.post("/generate", response_class=HTMLResponse)
async def generate(request: Request, _auth: None = Depends(_require_auth)):
    """The only button. Reads whatever was given and builds."""
    _cleanup()
    form = await request.form()
    brief = str(form.get("brief") or "").strip()
    audience = str(form.get("audience") or "internal").strip()
    title = str(form.get("title") or "").strip()
    picks = [p for p in form.getlist("pick") if p]
    sections = [s for s in form.getlist("section") if s]
    upload = form.get("deck")
    has_deck = isinstance(upload, _FormUploadFile) and bool(upload.filename)

    if not brief and not picks and not has_deck:
        return HTMLResponse(
            ui.page("Deck builder", screens.home(
                error="Give it something to work from — a brief, some slides, or a deck.")),
            status_code=400)

    token = uuid.uuid4().hex
    work = STORAGE_ROOT / token
    work.mkdir(parents=True, exist_ok=True)

    mined: dict = {}
    if has_deck:
        if not upload.filename.lower().endswith(".pptx"):
            shutil.rmtree(work, ignore_errors=True)
            return HTMLResponse(
                ui.page("Deck builder", screens.home(error="The deck must be a .pptx file.")),
                status_code=400)
        source = await _save_upload(upload, work, "source.pptx")
        try:
            from deckguard.deckmine import mine_reference

            mined = mine_reference(str(source), prefix="yours")
        except Exception as exc:  # noqa: BLE001 -- a deck we cannot read is not fatal
            mined = {"error": str(exc)}

    from deckguard import assemble

    try:
        plan = assemble.plan(
            brief=brief, audience=audience, picks=picks, mined=mined,
            title=title, sections=sections,
        )
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(work, ignore_errors=True)
        return HTMLResponse(
            ui.page("Deck builder", screens.home(error=f"Planning failed: {exc}")),
            status_code=400)

    _save_session(token, {"plan": plan, "audience": audience, "mined": mined})
    return await _build_and_show(token, plan, audience, mined)


async def _build_and_show(token: str, plan: dict, audience: str, mined: dict) -> HTMLResponse:
    from deckguard import assemble

    out = STORAGE_ROOT / token / "deck.pptx"
    try:
        checks = assemble.build(plan, str(out), mined=mined)
    except Exception as exc:  # noqa: BLE001
        return HTMLResponse(
            ui.page("Deck builder", screens.home(error=f"Building failed: {exc}")),
            status_code=500)
    body = screens.result(token, plan, audience, mined, checks)
    return HTMLResponse(ui.page("Your deck", body))


@app.post("/rebuild/{token}", response_class=HTMLResponse)
async def rebuild(token: str, request: Request, _auth: None = Depends(_require_auth)):
    """Edits from the result page: text, order, drop, duplicate."""
    if not token.isalnum():
        raise HTTPException(status_code=404, detail="Not found")
    session = _session(token)
    form = await request.form()

    from deckguard import assemble

    plan = assemble.apply_edits(session["plan"], form)
    session["plan"] = plan
    _save_session(token, session)
    return await _build_and_show(token, plan, session["audience"], session.get("mined") or {})


@app.get("/download/{token}/{filename}")
def download(token: str, filename: str, _auth: None = Depends(_require_auth)):
    if not token.isalnum() or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="Not found")
    path = STORAGE_ROOT / token / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found (decks expire after two hours)")
    return FileResponse(
        path, filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


@app.get("/preview/{filename}")
def preview(filename: str, _auth: None = Depends(_require_auth)):
    """A rendered thumbnail of an archetype. Committed, not built here."""
    from deckguard import thumbs

    if not filename.endswith(".png"):
        raise HTTPException(status_code=404, detail="Not found")
    path = thumbs.path_for(filename[:-4])
    if path is None:
        raise HTTPException(status_code=404, detail="Not found")
    # These change only when someone regenerates them, and the page
    # asks for forty at once.
    return FileResponse(path, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})


@app.get("/health")
def health():
    return {"ok": True}
