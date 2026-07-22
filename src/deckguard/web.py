"""Minimal hostable web app wrapping the deckguard engine.

Upload a .pptx -> audit or fix it -> download the results. No new logic
lives here — every route just calls into inventory/rules_engine/fixer,
the same functions the CLI uses, so web and CLI can never disagree about
what counts as a violation or a fix.

Run locally:  uvicorn deckguard.web:app --reload
Deploy:       see Procfile / README "Hosting" section.

Optional HTTP Basic Auth: set DECKGUARD_WEB_PASSWORD to require a
password (username is ignored) before any route is reachable. Unset by
default — fine for local use, strongly recommended once this is hosted
somewhere with a public URL.
"""

from __future__ import annotations

import os
import secrets
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pptx import Presentation
from pptx.exc import PackageNotFoundError

from deckguard import report as report_mod
from deckguard import webtemplates as tpl
from deckguard.config import default_config_path, load_config, validate_config
from deckguard.fixer import fix_deck
from deckguard.inventory import build_inventory
from deckguard.rules_engine import audit_deck, sort_violations, summarize

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
STORAGE_ROOT = Path(os.environ.get("DECKGUARD_WEB_STORAGE", "/tmp/deckguard-web"))
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
MAX_STORAGE_AGE_SECONDS = 2 * 60 * 60  # best-effort cleanup of anything older than 2h

app = FastAPI(title="deckguard")
security = HTTPBasic(auto_error=False)


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


async def _save_upload(file: UploadFile, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "source.pptx"
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


@app.get("/", response_class=HTMLResponse)
def index(_auth: None = Depends(_require_auth)):
    return tpl.page_shell("deckguard", tpl.upload_form())


@app.post("/audit", response_class=HTMLResponse)
async def audit_route(file: UploadFile, _auth: None = Depends(_require_auth)):
    _cleanup_old_uploads()
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        return tpl.page_shell("deckguard", tpl.upload_form("Please upload a .pptx file."))

    token = uuid.uuid4().hex
    work_dir = STORAGE_ROOT / token
    source_path = await _save_upload(file, work_dir)

    try:
        config = _load_engine_config()
        prs = _open_presentation_or_error(source_path)
        inventory = build_inventory(prs)
        violations = sort_violations(audit_deck(inventory, config))
        summary = summarize(violations)
    except HTTPException as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        return tpl.page_shell("deckguard", tpl.upload_form(str(exc.detail)))
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(work_dir, ignore_errors=True)
        return tpl.page_shell("deckguard", tpl.upload_form(f"Audit failed: {exc}"))

    report_dict = report_mod.audit_summary_dict(file.filename, violations, summary)
    (work_dir / "audit.json").write_text(report_mod.to_json(report_dict), encoding="utf-8")

    download_links = {"json": f"/download/{token}/audit.json"}
    body = tpl.audit_result_page(file.filename, summary, report_dict["violations"], download_links)
    return tpl.page_shell(f"Audit — {file.filename}", body)


@app.post("/fix", response_class=HTMLResponse)
async def fix_route(file: UploadFile, _auth: None = Depends(_require_auth)):
    _cleanup_old_uploads()
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        return tpl.page_shell("deckguard", tpl.upload_form("Please upload a .pptx file."))

    token = uuid.uuid4().hex
    work_dir = STORAGE_ROOT / token
    source_path = await _save_upload(file, work_dir)
    output_path = work_dir / "fixed.pptx"

    try:
        config = _load_engine_config()
        prs = _open_presentation_or_error(source_path)
        fix_report = fix_deck(
            prs, config, source_path=file.filename, output_path=str(output_path), dry_run=False
        )
    except HTTPException as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        return tpl.page_shell("deckguard", tpl.upload_form(str(exc.detail)))
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(work_dir, ignore_errors=True)
        return tpl.page_shell("deckguard", tpl.upload_form(f"Fix failed: {exc}"))

    report_dict = report_mod.fix_report_to_dict(fix_report)
    (work_dir / "changelog.json").write_text(report_mod.to_json(report_dict), encoding="utf-8")
    (work_dir / "changelog.md").write_text(report_mod.render_fix_md(fix_report), encoding="utf-8")

    download_links = {
        "pptx": f"/download/{token}/fixed.pptx",
        "json": f"/download/{token}/changelog.json",
        "md": f"/download/{token}/changelog.md",
    }
    body = tpl.fix_result_page(
        file.filename, report_dict["summary"], report_dict["changes"], report_dict["manual_review"], download_links
    )
    return tpl.page_shell(f"Fixed — {file.filename}", body)


@app.get("/download/{token}/{filename}")
def download(token: str, filename: str, _auth: None = Depends(_require_auth)):
    # token is always a uuid4().hex we generated; filename must be one of
    # the exact names we ourselves wrote into that directory.
    if not token.isalnum() or filename not in ("audit.json", "fixed.pptx", "changelog.json", "changelog.md"):
        raise HTTPException(status_code=404, detail="Not found")
    path = STORAGE_ROOT / token / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found (results expire after a couple of hours)")
    media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation" if filename.endswith(".pptx") else None
    return FileResponse(path, filename=filename, media_type=media_type)


@app.get("/health")
def health():
    return {"status": "ok"}
