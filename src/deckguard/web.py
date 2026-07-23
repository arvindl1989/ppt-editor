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

import copy
import json
import os
import secrets
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pptx import Presentation
from pptx.exc import PackageNotFoundError

from deckguard import learn as learn_mod
from deckguard import report as report_mod
from deckguard import webtemplates as tpl
from deckguard.compose import ComposeError, build_deck, load_outline
from deckguard.config import default_config_path, load_config, validate_config
from deckguard.fixer import fix_deck
from deckguard.fonts import normalize_key as font_normalize_key
from deckguard.inventory import build_inventory
from deckguard.rules_engine import audit_deck, sort_violations, summarize
from deckguard.slide_import import replace_intro_outro

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


@app.get("/", response_class=HTMLResponse)
def index(_auth: None = Depends(_require_auth)):
    return tpl.page_shell("deckguard", tpl.upload_form() + tpl.compose_form())


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


def _migrate_and_fix(source_path: Path, deck_name: str, config: dict, work_dir: Path):
    """Shared by /fix and /regenerate: run best-effort cover/outro
    migration, then fix_deck, writing fixed.pptx + changelogs into
    work_dir. Returns (fix_report, migrate_result)."""
    migrated_path = work_dir / "migrated.pptx"
    output_path = work_dir / "fixed.pptx"

    # Cover/outro migration runs first (best-effort -- if it fails for any
    # reason, fall back to fixing the deck as-uploaded rather than
    # blocking the whole request on a newer, more failure-prone step).
    migrate_result = {"cover_replaced": False, "outro_replaced": False}
    fix_source_path = source_path
    try:
        migrate_result = replace_intro_outro(str(source_path), str(migrated_path))
        fix_source_path = migrated_path
    except Exception:  # noqa: BLE001
        pass

    prs = _open_presentation_or_error(fix_source_path)
    fix_report = fix_deck(
        prs, config, source_path=deck_name, output_path=str(output_path), dry_run=False
    )

    report_dict = report_mod.fix_report_to_dict(fix_report)
    (work_dir / "changelog.json").write_text(report_mod.to_json(report_dict), encoding="utf-8")
    (work_dir / "changelog.md").write_text(report_mod.render_fix_md(fix_report), encoding="utf-8")
    return fix_report, migrate_result


def _fix_result_body(deck_name: str, fix_report, migrate_result: dict, config: dict, token: str) -> str:
    report_dict = report_mod.fix_report_to_dict(fix_report)
    download_links = {
        "pptx": f"/download/{token}/fixed.pptx",
        "json": f"/download/{token}/changelog.json",
        "md": f"/download/{token}/changelog.md",
    }
    migrate_note = None
    if migrate_result["cover_replaced"] or migrate_result["outro_replaced"]:
        parts = []
        if migrate_result["cover_replaced"]:
            parts.append("cover")
        if migrate_result["outro_replaced"]:
            parts.append("outro")
        migrate_note = f"Also replaced the {' and '.join(parts)} slide with the org template's (title carried over)."
    remap_summary = report_mod.remap_overrides_summary(fix_report)
    approved_colors = config.get("colors", {}).get("approved", []) or []
    approved_fonts = config.get("fonts", {}).get("approved", []) or []
    return tpl.fix_result_page(
        deck_name,
        report_dict["summary"],
        report_dict["changes"],
        report_dict["manual_review"],
        download_links,
        migrate_note=migrate_note,
        remap_summary=remap_summary,
        approved_colors=approved_colors,
        approved_fonts=approved_fonts,
        token=token,
    )


@app.post("/fix", response_class=HTMLResponse)
async def fix_route(file: UploadFile, _auth: None = Depends(_require_auth)):
    _cleanup_old_uploads()
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        return tpl.page_shell("deckguard", tpl.upload_form("Please upload a .pptx file."))

    token = uuid.uuid4().hex
    work_dir = STORAGE_ROOT / token
    source_path = await _save_upload(file, work_dir)
    (work_dir / "meta.json").write_text(json.dumps({"deck_name": file.filename}), encoding="utf-8")

    try:
        config = _load_engine_config()
        fix_report, migrate_result = _migrate_and_fix(source_path, file.filename, config, work_dir)
    except HTTPException as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        return tpl.page_shell("deckguard", tpl.upload_form(str(exc.detail)))
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(work_dir, ignore_errors=True)
        return tpl.page_shell("deckguard", tpl.upload_form(f"Fix failed: {exc}"))

    body = _fix_result_body(file.filename, fix_report, migrate_result, config, token)
    return tpl.page_shell(f"Fixed — {file.filename}", body)


@app.post("/regenerate/{token}", response_class=HTMLResponse)
async def regenerate_route(token: str, request: Request, _auth: None = Depends(_require_auth)):
    if not token.isalnum():
        raise HTTPException(status_code=404, detail="Not found")
    work_dir = STORAGE_ROOT / token
    source_path = work_dir / "source.pptx"
    meta_path = work_dir / "meta.json"
    if not source_path.is_file() or not meta_path.is_file():
        return tpl.page_shell(
            "deckguard", tpl.upload_form("Those results have expired — please upload the deck again.")
        )
    deck_name = json.loads(meta_path.read_text(encoding="utf-8"))["deck_name"]

    form = await request.form()
    color_overrides: dict[str, str] = {}
    font_overrides: dict[str, str] = {}
    for key, value in form.multi_items():
        if not value:
            continue
        if key.startswith("color_override__"):
            color_overrides[key[len("color_override__"):]] = str(value)
        elif key.startswith("font_override__"):
            font_overrides[key[len("font_override__"):]] = str(value)

    try:
        base_config = _load_engine_config()
    except RuntimeError as exc:
        return tpl.page_shell("deckguard", tpl.upload_form(str(exc)))

    # Overrides apply on top of a scratch copy of the server's real config,
    # scoped to this one request -- never mutate brand_rules.yaml itself
    # (same pattern /learn uses for its scratch rules-file copy).
    config = copy.deepcopy(base_config)
    approved_colors = {h.lstrip("#").upper() for h in (config.get("colors", {}).get("approved", []) or [])}
    approved_fonts = set(config.get("fonts", {}).get("approved", []) or [])
    color_remap = config.setdefault("colors", {}).setdefault("remap", {})
    for old_hex, new_hex in color_overrides.items():
        if new_hex.upper() not in approved_colors:
            continue  # not a brand-approved color -- ignore, keep the default target
        color_remap[f"#{old_hex}"] = f"#{new_hex}"
    font_remap = config.setdefault("fonts", {}).setdefault("remap", {})
    approved_font_keys = {font_normalize_key(f) for f in approved_fonts}
    for old_font, new_font in font_overrides.items():
        if font_normalize_key(new_font) not in approved_font_keys:
            continue  # not a brand-approved font -- ignore, keep the default target
        font_remap[old_font] = new_font

    try:
        fix_report, migrate_result = _migrate_and_fix(source_path, deck_name, config, work_dir)
    except HTTPException as exc:
        return tpl.page_shell("deckguard", tpl.upload_form(str(exc.detail)))
    except Exception as exc:  # noqa: BLE001
        return tpl.page_shell("deckguard", tpl.upload_form(f"Regenerate failed: {exc}"))

    body = _fix_result_body(deck_name, fix_report, migrate_result, config, token)
    return tpl.page_shell(f"Fixed — {deck_name}", body)


@app.post("/learn", response_class=HTMLResponse)
async def learn_route(
    old_file: UploadFile, new_file: UploadFile, _auth: None = Depends(_require_auth)
):
    _cleanup_old_uploads()
    for f in (old_file, new_file):
        if not f.filename or not f.filename.lower().endswith(".pptx"):
            return tpl.page_shell("deckguard", tpl.upload_form("Please upload two .pptx files."))

    token = uuid.uuid4().hex
    work_dir = STORAGE_ROOT / token
    old_path = await _save_upload(old_file, work_dir, "old.pptx")
    new_path = await _save_upload(new_file, work_dir, "new.pptx")

    try:
        config = _load_engine_config()
        old_prs = _open_presentation_or_error(old_path)
        new_prs = _open_presentation_or_error(new_path)
        result = learn_mod.learn(old_prs, new_prs, config)

        # Apply onto a scratch copy of the real rules file, never the
        # server's actual brand_rules.yaml -- a web request shouldn't
        # mutate shared server state. Reuses the same comment-preserving
        # write path the CLI's --apply uses.
        rules_copy = work_dir / "brand_rules.yaml"
        shutil.copy(default_config_path(), rules_copy)
        applied = learn_mod.write_learned_to_yaml(rules_copy, result, min_confidence="high")
        updated_config = load_config(rules_copy)

        old_prs_for_fix = _open_presentation_or_error(old_path)
        output_path = work_dir / "fixed.pptx"
        fix_report = fix_deck(
            old_prs_for_fix,
            updated_config,
            source_path=old_file.filename,
            output_path=str(output_path),
            dry_run=False,
        )
    except HTTPException as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        return tpl.page_shell("deckguard", tpl.upload_form(str(exc.detail)))
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(work_dir, ignore_errors=True)
        return tpl.page_shell("deckguard", tpl.upload_form(f"Learn failed: {exc}"))

    result_dict = report_mod.learn_result_to_dict(result)
    (work_dir / "learn_report.json").write_text(report_mod.to_json(result_dict), encoding="utf-8")
    fix_report_dict = report_mod.fix_report_to_dict(fix_report)

    download_links = {
        "pptx": f"/download/{token}/fixed.pptx",
        "yaml": f"/download/{token}/brand_rules.yaml",
        "json": f"/download/{token}/learn_report.json",
    }
    body = tpl.learn_result_page(
        old_file.filename, new_file.filename, result_dict, fix_report_dict["summary"], applied, download_links
    )
    return tpl.page_shell(f"Learned — {old_file.filename} -> {new_file.filename}", body)


@app.post("/create", response_class=HTMLResponse)
async def create_route(
    request: Request,
    existing_file: Optional[UploadFile] = None,
    _auth: None = Depends(_require_auth),
):
    _cleanup_old_uploads()
    form = await request.form()
    outline_text = str(form.get("outline", "")).strip()
    if not outline_text:
        return tpl.page_shell("deckguard", tpl.compose_form("Please paste a YAML outline."))

    token = uuid.uuid4().hex
    work_dir = STORAGE_ROOT / token
    work_dir.mkdir(parents=True, exist_ok=True)
    outline_path = work_dir / "outline.yaml"
    outline_path.write_text(outline_text, encoding="utf-8")

    existing_path = None
    if existing_file is not None and existing_file.filename:
        if not existing_file.filename.lower().endswith(".pptx"):
            shutil.rmtree(work_dir, ignore_errors=True)
            return tpl.page_shell("deckguard", tpl.compose_form("The existing deck to append to must be a .pptx file."))
        existing_path = await _save_upload(existing_file, work_dir, "existing.pptx")

    try:
        config = _load_engine_config()
        outline = load_outline(outline_path)
        output_path = work_dir / "composed.pptx"
        result = build_deck(
            outline, str(output_path),
            existing_deck_path=str(existing_path) if existing_path else None,
            rules_config=config,
        )
    except ComposeError as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        return tpl.page_shell("deckguard", tpl.compose_form(str(exc)))
    except HTTPException as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        return tpl.page_shell("deckguard", tpl.compose_form(str(exc.detail)))
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(work_dir, ignore_errors=True)
        return tpl.page_shell("deckguard", tpl.compose_form(f"Compose failed: {exc}"))

    out_name = existing_file.filename if (existing_file is not None and existing_file.filename) else "new deck"
    download_links = {"pptx": f"/download/{token}/composed.pptx"}
    body = tpl.compose_result_page(out_name, report_mod.compose_result_to_dict(result), download_links)
    return tpl.page_shell(f"Composed — {out_name}", body)


@app.get("/download/{token}/{filename}")
def download(token: str, filename: str, _auth: None = Depends(_require_auth)):
    # token is always a uuid4().hex we generated; filename must be one of
    # the exact names we ourselves wrote into that directory.
    allowed = (
        "audit.json", "fixed.pptx", "changelog.json", "changelog.md",
        "brand_rules.yaml", "learn_report.json", "composed.pptx",
    )
    if not token.isalnum() or filename not in allowed:
        raise HTTPException(status_code=404, detail="Not found")
    path = STORAGE_ROOT / token / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found (results expire after a couple of hours)")
    media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation" if filename.endswith(".pptx") else None
    return FileResponse(path, filename=filename, media_type=media_type)


@app.get("/health")
def health():
    return {"status": "ok"}
