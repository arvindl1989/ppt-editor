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

from deckguard import report as report_mod
from deckguard import webtemplates as tpl
from deckguard.config import default_config_path, load_config, validate_config
from deckguard.inventory import build_inventory
from deckguard.preview import archetype_preview_html, org_layout_preview_html, slide_preview_html
from deckguard.redesign import RedesignError
from deckguard.rules_engine import audit_deck, sort_violations, summarize
from deckguard.slide_import import default_template_path
from deckguard.transform import (
    SlidePlan,
    TransformPlan,
    audit_transform_result,
    execute_transform,
    execute_transform_from_brief,
    plan_transform,
    plan_transform_from_brief,
    reference_similarity,
)

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


# --------------------------------------------------------------------------
# Audit (read-only)
# --------------------------------------------------------------------------


@app.post("/audit", response_class=HTMLResponse)
async def audit_route(request: Request, _auth: None = Depends(_require_auth)):
    _cleanup_old_uploads()
    form = await request.form()
    file = form.get("file")
    if not isinstance(file, _FormUploadFile) or not file.filename or not file.filename.lower().endswith(".pptx"):
        return _home("Audit needs an uploaded .pptx deck.", status_code=400)

    token = uuid.uuid4().hex
    work_dir = STORAGE_ROOT / token
    source_path = await _save_upload(file, work_dir)

    try:
        config = _load_engine_config()
        prs = _open_presentation_or_error(source_path)
        violations = sort_violations(audit_deck(build_inventory(prs), config))
        summary = summarize(violations)
    except HTTPException as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        return _home(str(exc.detail), status_code=400)
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(work_dir, ignore_errors=True)
        return _home(f"Audit failed: {exc}", status_code=500)

    report_dict = report_mod.audit_summary_dict(file.filename, violations, summary)
    (work_dir / "audit.json").write_text(report_mod.to_json(report_dict), encoding="utf-8")

    download_links = {"json": f"/download/{token}/audit.json"}
    body = tpl.audit_result_page(file.filename, summary, report_dict["violations"], download_links)
    return HTMLResponse(tpl.page_shell(f"Audit — {file.filename}", body))


# --------------------------------------------------------------------------
# Transform: plan -> review -> execute
# --------------------------------------------------------------------------


def _plan_to_json(plan: TransformPlan, mode: str, deck_name: str) -> str:
    return json.dumps({
        "mode": mode,
        "deck_name": deck_name,
        "ai_suggestions_ran": plan.ai_suggestions_ran,
        "deck_title": plan.deck_title,
        "slides": [asdict(s) for s in plan.slides],
    })


def _plan_from_json(raw: str) -> tuple[TransformPlan, str, str]:
    data = json.loads(raw)
    plan = TransformPlan(
        slides=[SlidePlan(**s) for s in data["slides"]],
        ai_suggestions_ran=data["ai_suggestions_ran"],
        deck_title=data.get("deck_title"),
    )
    return plan, data["mode"], data["deck_name"]


def _review_entries(plan: TransformPlan, mode: str, source_path: Optional[Path]) -> list[dict]:
    """Per-slide dicts for the review page: plan fields plus rendered
    preview HTML. Every preview is fail-soft, so a preview problem can
    never take down the review step itself."""
    current_by_index: dict = {}
    if mode == "deck" and source_path is not None:
        try:
            prs = Presentation(str(source_path))
            inv = build_inventory(prs)
            w_in, h_in = prs.slide_width / 914400, prs.slide_height / 914400
            current_by_index = {
                rec.index: slide_preview_html(rec, w_in, h_in) for rec in inv.slides
            }
        except Exception:  # noqa: BLE001 -- previews are an aid, never load-bearing
            current_by_index = {}

    layouts_by_name: dict = {}
    tmpl_dims = (12192000, 6858000)
    try:
        tmpl_prs = Presentation(str(default_template_path()))
        tmpl_dims = (tmpl_prs.slide_width, tmpl_prs.slide_height)
        layouts_by_name = {l.name: l for m in tmpl_prs.slide_masters for l in m.slide_layouts}
    except Exception:  # noqa: BLE001
        pass

    entries = []
    for s in plan.slides:
        proposed = ""
        archetype_name = s.archetype.get("archetype") if s.archetype else None
        if s.archetype:
            content = {k: v for k, v in s.archetype.items() if k != "archetype"}
            proposed = archetype_preview_html(archetype_name, content)
        elif s.default_action == "rebuild" and s.layout_name in layouts_by_name:
            proposed = org_layout_preview_html(
                layouts_by_name[s.layout_name], tmpl_dims[0], tmpl_dims[1],
                s.title, s.text_blocks, s.image_count,
            )
        entries.append({
            "index": s.index,
            "default_action": s.default_action,
            "layout_name": s.layout_name,
            "archetype_name": archetype_name,
            "reason": s.reason,
            "title_preview": s.title_preview,
            "current_html": current_by_index.get(s.index, ""),
            "proposed_html": proposed,
        })
    return entries


@app.post("/plan", response_class=HTMLResponse)
async def plan_route(request: Request, _auth: None = Depends(_require_auth)):
    _cleanup_old_uploads()
    ai_enabled = bool(os.environ.get("ANTHROPIC_API_KEY"))
    form = await request.form()

    file = form.get("file")
    has_file = isinstance(file, _FormUploadFile) and bool(file.filename)
    reference = form.get("reference")
    has_reference = isinstance(reference, _FormUploadFile) and bool(reference.filename)
    brief = str(form.get("brief") or "").strip() or None

    if has_file and not file.filename.lower().endswith(".pptx"):
        return _home("The deck must be a .pptx file.", status_code=400)
    if has_reference and not reference.filename.lower().endswith(".pptx"):
        return _home("The reference must be a .pptx file.", status_code=400)
    if not has_file and not brief:
        return _home("Upload a deck to transform, or write a brief for a new one.", status_code=400)
    if not has_file and brief and not ai_enabled:
        # Server-side opt-in only for anything that calls the model: never
        # accept a key from the client, never let an unconfigured server
        # silently bill anyone.
        return _home("Building a new deck from a brief needs the server's ANTHROPIC_API_KEY, which isn't set.", status_code=400)

    token = uuid.uuid4().hex
    work_dir = STORAGE_ROOT / token
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        if has_file:
            source_path = await _save_upload(file, work_dir)
            _open_presentation_or_error(source_path)
            reference_path = None
            if has_reference:
                reference_path = await _save_upload(reference, work_dir, filename="reference.pptx")
                _open_presentation_or_error(reference_path)
            plan = plan_transform(
                str(source_path),
                reference_path=str(reference_path) if reference_path else None,
                suggest_archetypes=ai_enabled,
            )
            mode, deck_name = "deck", file.filename
        else:
            source_path = None
            plan = plan_transform_from_brief(brief)
            mode, deck_name = "brief", (plan.deck_title or "new deck")
    except (HTTPException, RedesignError) as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        return _home(str(detail), status_code=400)
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(work_dir, ignore_errors=True)
        return _home(f"Planning failed: {exc}", status_code=500)

    (work_dir / "plan.json").write_text(_plan_to_json(plan, mode, deck_name), encoding="utf-8")
    entries = _review_entries(plan, mode, source_path)
    body = tpl.transform_review_page(deck_name, token, entries, mode, plan.ai_suggestions_ran)
    return HTMLResponse(tpl.page_shell(f"Review plan — {deck_name}", body))


@app.post("/transform/{token}", response_class=HTMLResponse)
async def transform_route(token: str, request: Request, _auth: None = Depends(_require_auth)):
    if not token.isalnum():
        raise HTTPException(status_code=404, detail="Not found")
    work_dir = STORAGE_ROOT / token
    plan_path = work_dir / "plan.json"
    if not plan_path.is_file():
        return _home("That plan has expired — please upload the deck again.", status_code=404)

    plan, mode, deck_name = _plan_from_json(plan_path.read_text(encoding="utf-8"))
    form = await request.form()
    out_path = work_dir / "transformed.pptx"

    try:
        config = _load_engine_config()
        if mode == "brief":
            approved = {s.index for s in plan.slides if form.get(f"include_{s.index}")}
            outcome = execute_transform_from_brief(str(out_path), plan, approved_indices=approved)
            # Whole-deck archetype render: every slide is compliant by
            # construction, so the audit's exclusion covers all of them
            # (plus the retained master cover/outro at the ends).
            prs_len = len(Presentation(str(out_path)).slides)
            audit = audit_transform_result(str(out_path), archetype_indices=set(range(1, prs_len + 1)), rules_config=config)
            similarity = None
        else:
            actions = {}
            for s in plan.slides:
                raw = str(form.get(f"action_{s.index}") or "")
                if raw in ("keep", "rebuild", "archetype"):
                    actions[s.index] = raw
            reference_path = work_dir / "reference.pptx"
            ref = str(reference_path) if reference_path.is_file() else None
            outcome = execute_transform(
                str(work_dir / "source.pptx"), str(out_path), plan, actions=actions,
                reference_path=ref, rules_config=config,
            )
            audit = audit_transform_result(
                str(out_path), archetype_indices=set(outcome.archetype_swapped), rules_config=config,
            )
            similarity = reference_similarity(str(out_path), ref) if ref else None
    except Exception as exc:  # noqa: BLE001
        return _home(f"Transform failed: {exc}", status_code=500)

    outcome_dict = {
        "rebuilt": outcome.rebuilt,
        "archetype_swapped": outcome.archetype_swapped,
        "reference_carryover": outcome.reference_carryover,
        "kept": outcome.kept,
        "layouts_used": outcome.layouts_used,
    }
    report = {
        "deck": deck_name,
        "outcome": outcome_dict,
        "audit_summary": audit["summary"],
        "suppressed_archetype_findings": audit["suppressed_archetype_findings"],
        "violations": [report_mod._violation_dict(v) for v in audit["violations"]],
        "reference_similarity": similarity,
    }
    (work_dir / "transform.json").write_text(report_mod.to_json(report), encoding="utf-8")

    download_links = {"pptx": f"/download/{token}/transformed.pptx", "json": f"/download/{token}/transform.json"}
    body = tpl.transform_result_page(deck_name, outcome_dict, audit, similarity, download_links)
    return HTMLResponse(tpl.page_shell(f"Transformed — {deck_name}", body))


# --------------------------------------------------------------------------
# Downloads / health
# --------------------------------------------------------------------------


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


@app.get("/health")
def health():
    return {"status": "ok"}
