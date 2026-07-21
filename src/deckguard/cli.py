"""deckguard CLI — brand compliance automation for PowerPoint decks."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import click
from pptx import Presentation
from pptx.exc import PackageNotFoundError
from rich.console import Console
from rich.table import Table

from deckguard import report as report_mod
from deckguard.config import ConfigError, default_config_path, load_config, validate_config
from deckguard.fixer import fix_deck
from deckguard.inventory import build_inventory
from deckguard.logo import compute_phash
from deckguard.rules_engine import audit_deck, sort_violations, summarize

console = Console(stderr=True)
SEVERITY_STYLE = {"critical": "bold red", "major": "yellow", "minor": "cyan"}


def _open_presentation(path: str) -> Presentation:
    try:
        return Presentation(path)
    except PackageNotFoundError:
        console.print(f"[bold red]error:[/] '{path}' is not a valid .pptx file")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 — surface any parse failure as a clean one-liner
        console.print(f"[bold red]error:[/] could not open '{path}': {exc}")
        sys.exit(1)


def _load_rules(rules_path: Optional[str]) -> dict:
    """Load + validate rules for audit/fix.

    Unlike the standalone `validate-rules` command (where a missing logo
    file is correctly a hard error — that's its job), audit/fix degrade
    gracefully here: logo detection is a no-op until `old_logo_hashes` is
    populated and `new_logo_path` points at a real file anyway, so a
    missing placeholder logo is a warning, not a blocker, for everything
    else in the deterministic engine.
    """
    path = rules_path or default_config_path()
    try:
        config = load_config(path)
    except ConfigError as exc:
        console.print(f"[bold red]error:[/] {exc}")
        sys.exit(1)
    errors = validate_config(config, base_dir=Path(path).parent)
    blocking = [e for e in errors if "logo.new_logo_path does not exist" not in e]
    warnings = [e for e in errors if "logo.new_logo_path does not exist" in e]
    for w in warnings:
        console.print(f"[yellow]warning:[/] {w} — logo replacement will be skipped")
    if blocking:
        console.print(f"[bold red]error:[/] '{path}' failed validation:")
        for e in blocking:
            console.print(f"  - {e}")
        sys.exit(1)
    return config


def _print_violation_table(violations, title: str) -> None:
    if not violations:
        console.print(f"[green]{title}: no violations found[/]")
        return
    table = Table(title=title)
    table.add_column("Slide")
    table.add_column("Severity")
    table.add_column("Rule")
    table.add_column("Shape")
    table.add_column("Message")
    table.add_column("Fix?")
    for v in violations:
        style = SEVERITY_STYLE.get(v.severity, "")
        table.add_row(
            str(v.slide_index),
            f"[{style}]{v.severity}[/]",
            v.rule,
            v.shape_name or "",
            v.message,
            "yes" if v.auto_fixable else "no",
        )
    console.print(table)


@click.group()
@click.version_option()
def main():
    """deckguard — PowerPoint brand compliance automation."""


@main.command()
@click.argument("deck", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "fmt", type=click.Choice(["json", "md"]), default="md")
def inspect(deck: str, fmt: str):
    """Print a full structured inventory of DECK: shapes, fills, fonts, images, effects."""
    prs = _open_presentation(deck)
    inventory = build_inventory(prs)
    if fmt == "json":
        click.echo(report_mod.to_json(report_mod.inventory_to_dict(inventory)))
    else:
        click.echo(report_mod.render_inventory_md(inventory, Path(deck).name))


@main.command()
@click.argument("deck", type=click.Path(exists=True, dir_okay=False))
@click.option("--rules", "rules_path", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--dry-run", is_flag=True, help="Compute and report fixes without writing an output file.")
@click.option("--out", "out_dir", type=click.Path(file_okay=False), default=None, help="Output directory (default: alongside DECK).")
def fix(deck: str, rules_path: Optional[str], dry_run: bool, out_dir: Optional[str]):
    """Apply deterministic brand-compliance fixes to DECK, writing <name>_fixed.pptx."""
    config = _load_rules(rules_path)
    prs = _open_presentation(deck)

    deck_path = Path(deck)
    out_directory = Path(out_dir) if out_dir else deck_path.parent
    out_directory.mkdir(parents=True, exist_ok=True)
    output_path = out_directory / f"{deck_path.stem}_fixed.pptx"
    changelog_json_path = out_directory / f"{deck_path.stem}_changelog.json"
    changelog_md_path = out_directory / f"{deck_path.stem}_changelog.md"

    fix_report = fix_deck(
        prs, config, source_path=str(deck_path), output_path=str(output_path), dry_run=dry_run
    )

    changelog_json_path.write_text(report_mod.to_json(report_mod.fix_report_to_dict(fix_report)), encoding="utf-8")
    changelog_md_path.write_text(report_mod.render_fix_md(fix_report), encoding="utf-8")

    if dry_run:
        console.print(f"[cyan]dry run:[/] no file written. Change log: {changelog_json_path}, {changelog_md_path}")
    else:
        console.print(f"[green]wrote:[/] {output_path}")
    console.print(
        f"{len(fix_report.changes)} changes applied, "
        f"[yellow]{len(fix_report.manual_review)} need manual review[/]"
    )


def _audit_one(deck_path: Path, config: dict) -> tuple[list, dict]:
    prs = _open_presentation(str(deck_path))
    inventory = build_inventory(prs)
    violations = sort_violations(audit_deck(inventory, config))
    return violations, {"slides": len(inventory.slides)}


def _write_or_print(content: str, out_path: Optional[Path]) -> None:
    if out_path:
        out_path.write_text(content, encoding="utf-8")
        console.print(f"[green]wrote:[/] {out_path}")
    else:
        click.echo(content)


@main.command()
@click.argument("target", type=click.Path(exists=True))
@click.option("--rules", "rules_path", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--ai/--no-ai", default=False, help="Enable the Phase 2 AI visual audit layer (requires ANTHROPIC_API_KEY).")
@click.option("--out", "out_dir", type=click.Path(file_okay=False), default=None)
@click.option("--format", "fmt", type=click.Choice(["json", "md", "csv"]), default="md")
def audit(target: str, rules_path: Optional[str], ai: bool, out_dir: Optional[str], fmt: str):
    """Audit TARGET (a .pptx file or a folder of decks) for brand violations."""
    config = _load_rules(rules_path)

    if ai:
        if os.environ.get("ANTHROPIC_API_KEY"):
            console.print("[cyan]note:[/] AI visual audit (Phase 2) is not yet implemented — running XML-only audit.")
        else:
            console.print("[cyan]note:[/] ANTHROPIC_API_KEY not set — AI audit skipped, running XML-only audit.")

    target_path = Path(target)
    out_directory = Path(out_dir) if out_dir else None
    if out_directory:
        out_directory.mkdir(parents=True, exist_ok=True)

    fail_on = set((config.get("audit", {}) or {}).get("fail_on", []) or [])
    should_fail = False

    if target_path.is_dir():
        deck_paths = sorted(target_path.glob("*.pptx"))
        if not deck_paths:
            console.print(f"[yellow]no .pptx files found in {target_path}[/]")
            sys.exit(0)
        rows = []
        for deck_path in deck_paths:
            violations, meta = _audit_one(deck_path, config)
            summary = summarize(violations)
            _print_violation_table(violations, deck_path.name)
            if any(v.severity in fail_on for v in violations):
                should_fail = True
            rows.append(
                {
                    "deck": deck_path.name,
                    "slides": meta["slides"],
                    "critical": summary["critical"],
                    "major": summary["major"],
                    "minor": summary["minor"],
                    "total": summary["total"],
                    "pct_auto_fixable": round(100 * summary["auto_fixable"] / summary["total"], 1)
                    if summary["total"]
                    else 100.0,
                }
            )
            if out_directory:
                report_ext = {"json": "json", "md": "md", "csv": "csv"}[fmt]
                report_path = out_directory / f"{deck_path.stem}_audit.{report_ext}"
                report_path.write_text(_render_audit(violations, summary, deck_path.name, fmt), encoding="utf-8")

        summary_csv = report_mod.render_batch_summary_csv(rows)
        if out_directory:
            (out_directory / "summary.csv").write_text(summary_csv, encoding="utf-8")
            console.print(f"[green]wrote:[/] {out_directory / 'summary.csv'}")
        else:
            click.echo(summary_csv)
    else:
        violations, _meta = _audit_one(target_path, config)
        summary = summarize(violations)
        _print_violation_table(violations, target_path.name)
        if any(v.severity in fail_on for v in violations):
            should_fail = True
        content = _render_audit(violations, summary, target_path.name, fmt)
        out_path = None
        if out_directory:
            out_path = out_directory / f"{target_path.stem}_audit.{fmt}"
        _write_or_print(content, out_path)

    if should_fail:
        sys.exit(1)


def _render_audit(violations, summary, deck_name, fmt) -> str:
    if fmt == "json":
        return report_mod.to_json(report_mod.audit_summary_dict(deck_name, violations, summary))
    if fmt == "csv":
        return report_mod.render_audit_csv(violations)
    return report_mod.render_audit_md(deck_name, violations, summary)


@main.command("hash-logo")
@click.argument("image", type=click.Path(exists=True, dir_okay=False))
def hash_logo(image: str):
    """Print the perceptual hash of IMAGE, for pasting into logo.old_logo_hashes."""
    data = Path(image).read_bytes()
    try:
        phash = compute_phash(data)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]error:[/] could not read '{image}' as an image: {exc}")
        sys.exit(1)
    click.echo(phash)


@main.command("validate-rules")
@click.argument("rules_path", type=click.Path(exists=True, dir_okay=False), required=False, default=None)
def validate_rules_cmd(rules_path: Optional[str]):
    """Check a brand_rules.yaml file for syntax and semantic errors."""
    path = rules_path or default_config_path()
    try:
        config = load_config(path)
    except ConfigError as exc:
        console.print(f"[bold red]invalid:[/] {exc}")
        sys.exit(1)
    errors = validate_config(config, base_dir=Path(path).parent)
    if errors:
        console.print(f"[bold red]{len(errors)} error(s) in {path}:[/]")
        for e in errors:
            console.print(f"  - {e}")
        sys.exit(1)
    console.print(f"[green]OK:[/] {path} is valid")


@main.command()
@click.argument("deck", type=click.Path(exists=True, dir_okay=False))
@click.option("--template", type=click.Path(exists=True, dir_okay=False), required=True)
def migrate(deck: str, template: str):
    """Move DECK onto TEMPLATE. Phase 3 — not yet implemented."""
    console.print("[yellow]migrate: not yet implemented[/] (Phase 3 — see docs/migration_design.md)")


if __name__ == "__main__":
    main()
