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

from deckguard import learn as learn_mod
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


def _blocking_errors(errors: list[str]) -> tuple[list[str], list[str]]:
    """Split validate_config() errors into (blocking, logo-path-only warnings).

    A missing placeholder logo file is a no-op elsewhere in the
    deterministic engine (logo detection only ever runs once
    `old_logo_hashes` is populated), so every command except the
    standalone `validate-rules` (whose whole job is being strict) treats
    it as a warning rather than a hard blocker.
    """
    blocking = [e for e in errors if "logo.new_logo_path does not exist" not in e]
    warnings = [e for e in errors if "logo.new_logo_path does not exist" in e]
    return blocking, warnings


def _load_rules(rules_path: Optional[str]) -> dict:
    """Load + validate rules for audit/fix/learn."""
    path = rules_path or default_config_path()
    try:
        config = load_config(path)
    except ConfigError as exc:
        console.print(f"[bold red]error:[/] {exc}")
        sys.exit(1)
    errors = validate_config(config, base_dir=Path(path).parent)
    blocking, warnings = _blocking_errors(errors)
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
@click.option(
    "--rebuild-layouts", is_flag=True,
    help="Also rebuild any slide flagged non_standard_layout onto an approved layout, verbatim, before "
    "patching colors/fonts -- fix_deck's own patches can correct anything on a slide's EXISTING layout, "
    "never the layout itself. Deterministic, no AI, no API key.",
)
def fix(deck: str, rules_path: Optional[str], dry_run: bool, out_dir: Optional[str], rebuild_layouts: bool):
    """Apply deterministic brand-compliance fixes to DECK, writing <name>_fixed.pptx."""
    config = _load_rules(rules_path)

    deck_path = Path(deck)
    out_directory = Path(out_dir) if out_dir else deck_path.parent
    out_directory.mkdir(parents=True, exist_ok=True)
    output_path = out_directory / f"{deck_path.stem}_fixed.pptx"
    changelog_json_path = out_directory / f"{deck_path.stem}_changelog.json"
    changelog_md_path = out_directory / f"{deck_path.stem}_changelog.md"

    retemplate_result = None
    fix_source = str(deck_path)
    tmp_retemplated: Optional[Path] = None
    if rebuild_layouts:
        import tempfile

        from deckguard.retemplate import rebuild_non_standard_layout_slides

        tmp_retemplated = Path(tempfile.mkstemp(suffix=".pptx")[1])
        retemplate_result = rebuild_non_standard_layout_slides(fix_source, str(tmp_retemplated), rules_config=config)
        fix_source = str(tmp_retemplated)

    try:
        prs = _open_presentation(fix_source)
        fix_report = fix_deck(
            prs, config, source_path=str(deck_path), output_path=str(output_path), dry_run=dry_run
        )
    finally:
        if tmp_retemplated:
            tmp_retemplated.unlink(missing_ok=True)

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
    if retemplate_result and retemplate_result.transformed:
        console.print(
            f"[cyan]{len(retemplate_result.transformed)} slide(s)[/] rebuilt onto an approved layout: "
            f"{retemplate_result.transformed}"
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
@click.argument("old_deck", type=click.Path(exists=True, dir_okay=False))
@click.argument("new_deck", type=click.Path(exists=True, dir_okay=False))
@click.option("--rules", "rules_path", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--apply", "apply_flag", is_flag=True, help="Write matching proposals into the rules file (preserving its comments/structure).")
@click.option("--min-confidence", type=click.Choice(["high", "low"]), default="high", help="Minimum confidence level to --apply.")
@click.option("--out", "out_path", type=click.Path(dir_okay=False), default=None)
@click.option("--format", "fmt", type=click.Choice(["json", "md"]), default="md")
@click.option(
    "--transform", "transform_path", type=click.Path(dir_okay=False), default=None,
    help="Also write OLD_DECK rebuilt with the learned colors/fonts applied, onto the org template's own "
    "approved layouts (same engine `redesign --mode brand` uses) -- its own wording and images carried over "
    "verbatim, cover/content/end alike. Uses --min-confidence proposals regardless of whether --apply is set.",
)
@click.option(
    "--review", is_flag=True, default=False,
    help="--transform only: adds one small AI pass that rebuilds a leftover divider/transition slide onto the "
    "org template's Section Divider layout, and flags leftover placeholder/confidentiality text. Needs an "
    "ANTHROPIC_API_KEY.",
)
def learn(
    old_deck: str, new_deck: str, rules_path: Optional[str], apply_flag: bool, min_confidence: str,
    out_path: Optional[str], fmt: str, transform_path: Optional[str], review: bool,
):
    """Compare OLD_DECK against an already-on-brand NEW_DECK and propose
    colors.remap/fonts.remap additions, based on usage-count correlation
    (a color/font that vanishes from OLD while a new one appears at a
    similar count is proposed as a replacement). Layout/structure is not
    analyzed for the proposals themselves -- only color and font usage
    -- but --transform rebuilds OLD_DECK onto the org's own approved
    layouts too, using the same engine `redesign --mode brand` does."""
    if review and not transform_path:
        console.print("[bold red]error:[/] --review only applies together with --transform.")
        sys.exit(1)
    if review and not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[bold red]error:[/] ANTHROPIC_API_KEY is not set — --review needs an Anthropic API key.")
        sys.exit(1)

    config = _load_rules(rules_path)
    old_prs = _open_presentation(old_deck)
    new_prs = _open_presentation(new_deck)

    result = learn_mod.learn(old_prs, new_prs, config)

    all_proposals = result.color_proposals + result.font_proposals + result.layout_panel_proposals
    n_high = sum(1 for p in all_proposals if p.confidence == "high")
    n_low = sum(1 for p in all_proposals if p.confidence == "low")
    console.print(
        f"[green]{n_high} high-confidence[/] and [yellow]{n_low} low-confidence[/] proposal(s); "
        f"{len(result.unmatched_old_colors)} unmatched color(s), {len(result.unmatched_old_fonts)} unmatched font(s)"
    )

    content = (
        report_mod.to_json(report_mod.learn_result_to_dict(result))
        if fmt == "json"
        else report_mod.render_learn_md(result, Path(old_deck).name, Path(new_deck).name)
    )
    _write_or_print(content, Path(out_path) if out_path else None)

    if apply_flag:
        target_path = Path(rules_path) if rules_path else default_config_path()
        candidate = learn_mod.apply_learned(config, result, min_confidence=min_confidence)
        errors = validate_config(candidate, base_dir=target_path.parent)
        blocking, _warnings = _blocking_errors(errors)
        if blocking:
            console.print("[bold red]error:[/] applying these proposals would produce an invalid config, aborting:")
            for e in blocking:
                console.print(f"  - {e}")
            sys.exit(1)
        applied = learn_mod.write_learned_to_yaml(target_path, result, min_confidence=min_confidence)
        console.print(f"[green]applied {applied} proposal(s) to {target_path}[/]")

    if transform_path:
        from deckguard.redesign import RedesignError, redesign_deck

        candidate = learn_mod.apply_learned(config, result, min_confidence=min_confidence)
        out = Path(transform_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            compose_result, redesign_result = redesign_deck(
                old_deck, str(out), rules_config=candidate, mode="brand", review=review,
                reference_path=new_deck,
            )
        except RedesignError as exc:
            console.print(f"[bold red]error:[/] {exc}")
            sys.exit(1)
        console.print(
            f"[green]wrote:[/] {out} — [cyan]{compose_result.slide_count} slide(s)[/] using layouts: "
            f"{', '.join(sorted(set(compose_result.layouts_used)))}"
        )
        if redesign_result.skipped:
            table = Table(title="Skipped (needs manual handling)")
            table.add_column("Slide")
            table.add_column("Reason")
            for s in redesign_result.skipped:
                table.add_row(str(s.slide_index), s.reason)
            console.print(table)
        if compose_result.manual_review:
            console.print(f"[yellow]{len(compose_result.manual_review)} finding(s) need manual review[/]")
        if redesign_result.review_notes:
            console.print("[yellow]--review findings:[/]")
            for note in redesign_result.review_notes:
                console.print(f"  [yellow]-[/] {note}")
        if redesign_result.reference_match_notes:
            console.print("[cyan]exact reference match:[/]")
            for note in redesign_result.reference_match_notes:
                console.print(f"  [cyan]-[/] {note}")


@main.command()
@click.argument("deck", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--template", type=click.Path(exists=True, dir_okay=False), default=None,
    help="Org template .pptx to migrate onto (default: the bundled KONE master template).",
)
@click.option("--cover-slide", type=int, default=3, show_default=True, help="Slide number in TEMPLATE to use as the cover.")
@click.option("--outro-slide", type=int, default=11, show_default=True, help="Slide number in TEMPLATE to use as the outro.")
@click.option("--out", "out_dir", type=click.Path(file_okay=False), default=None, help="Output directory (default: alongside DECK).")
def migrate(deck: str, template: Optional[str], cover_slide: int, outro_slide: int, out_dir: Optional[str]):
    """Replace DECK's cover/outro slides with the org template's, if they're not already on it.

    Only touches the first and last slide, and only if each isn't
    already built on one of the template's Cover/Outro layouts. Title
    (and subtitle, for the cover) text carries over into the new slide's
    placeholders; everything else in DECK is untouched.
    """
    from deckguard.slide_import import replace_intro_outro

    deck_path = Path(deck)
    out_directory = Path(out_dir) if out_dir else deck_path.parent
    out_directory.mkdir(parents=True, exist_ok=True)
    output_path = out_directory / f"{deck_path.stem}_migrated.pptx"

    result = replace_intro_outro(
        str(deck_path),
        str(output_path),
        template_path=template,
        cover_slide_num=cover_slide,
        outro_slide_num=outro_slide,
    )

    console.print(f"[green]wrote:[/] {output_path}")
    if result["cover_replaced"]:
        console.print(f"[cyan]cover replaced[/] (title carried over: {result.get('cover_title')!r})")
    else:
        console.print("[cyan]cover already on the template — left alone[/]")
    if result["outro_replaced"]:
        console.print(f"[cyan]outro replaced[/] (title carried over: {result.get('outro_title')!r})")
    else:
        console.print("[cyan]outro already on the template — left alone[/]")


@main.command()
@click.argument("deck", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--template", type=click.Path(exists=True, dir_okay=False), default=None,
    help="Org template .pptx to migrate onto (default: the bundled KONE master template).",
)
@click.option("--all", "accept_all", is_flag=True, help="Rebuild every eligible slide (skip the review step).")
@click.option(
    "--accept", "accept_csv", default=None,
    help="Comma-separated 1-based slide numbers to rebuild (e.g. 1,3,5). Ignored slides are left untouched.",
)
@click.option("--out", "out_dir", type=click.Path(file_okay=False), default=None, help="Output directory (default: alongside DECK).")
def retemplate(deck: str, template: Optional[str], accept_all: bool, accept_csv: Optional[str], out_dir: Optional[str]):
    """Rebuild DECK's slides onto the org template's own layouts, carrying
    over title/body text and images.

    Unlike `fix` (recolors/refonts in place) and `migrate` (cover/outro
    only), this replaces a slide's entire structure -- for genuinely
    outdated decks built on ad hoc layouts. Scoped to text and images
    only: a slide with a table, chart, embedded object, media, or a
    grouped shape is never guessed at, always left completely untouched.

    Run with neither --all nor --accept to just see the proposed mapping
    (a dry run, nothing written) -- review it, then re-run with --all or
    --accept to actually generate the deck.
    """
    from deckguard.retemplate import apply_retemplate, propose_retemplate

    deck_path = Path(deck)
    prs = _open_presentation(str(deck_path))
    proposals = propose_retemplate(prs, template_path=template)

    table = Table(title=f"Retemplate proposal — {deck_path.name}")
    table.add_column("Slide")
    table.add_column("Eligible")
    table.add_column("Layout / reason")
    table.add_column("Title / preview")
    for p in proposals:
        if p.eligible:
            table.add_row(str(p.slide_index), "[green]yes[/]", p.layout_name, p.title_preview or p.body_preview or "")
        else:
            table.add_row(str(p.slide_index), "[red]no[/]", p.reason, "")
    console.print(table)

    if not accept_all and not accept_csv:
        console.print("[dim]Dry run only — nothing written. Re-run with --all or --accept 1,3,5 to generate the deck.[/]")
        return

    accepted = None
    if accept_csv:
        try:
            accepted = {int(x.strip()) for x in accept_csv.split(",") if x.strip()}
        except ValueError:
            raise click.ClickException(f"--accept must be a comma-separated list of slide numbers, got: {accept_csv!r}")

    out_directory = Path(out_dir) if out_dir else deck_path.parent
    out_directory.mkdir(parents=True, exist_ok=True)
    output_path = out_directory / f"{deck_path.stem}_retemplated.pptx"

    result = apply_retemplate(str(deck_path), str(output_path), accepted_indexes=accepted, template_path=template)

    console.print(f"[green]wrote:[/] {output_path}")
    console.print(f"[cyan]rebuilt {len(result.transformed)} slide(s)[/]: {result.transformed}")
    if result.skipped:
        console.print(f"[dim]left {len(result.skipped)} slide(s) untouched[/]: {result.skipped}")


@main.command()
@click.argument("outline_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--out", "out_path", type=click.Path(dir_okay=False), required=True, help="Where to write the composed .pptx.")
@click.option(
    "--append", "append_path", type=click.Path(exists=True, dir_okay=False), default=None,
    help="Append the outline's slides onto a copy of this existing deck instead of starting a fresh one.",
)
@click.option(
    "--template", type=click.Path(exists=True, dir_okay=False), default=None,
    help="Org template .pptx to build on (default: the bundled KONE master template).",
)
@click.option("--rules", "rules_path", type=click.Path(exists=True, dir_okay=False), default=None)
def create(outline_path: str, out_path: str, append_path: Optional[str], template: Optional[str], rules_path: Optional[str]):
    """Generate an on-brand deck from OUTLINE_PATH (a YAML content outline), built directly on the org template's own layouts.

    Every slide goes straight onto an approved master layout -- colors
    and fonts come from the template's theme, never hand-set -- so a
    composed deck needs no separate `fix` pass: the result is already
    run through the same fixer `deckguard fix` uses before it's saved.
    Pass --append to add the outline's slides onto a copy of an existing
    deck instead of starting a new one; that deck's own pre-existing
    slides are left completely untouched. See README for the outline
    schema (slide kinds: cover, agenda, section, content, quote,
    statement, stat, timeline, end, blank).
    """
    from deckguard.compose import ComposeError, build_deck, load_outline

    config = _load_rules(rules_path)
    try:
        outline = load_outline(outline_path)
    except ComposeError as exc:
        console.print(f"[bold red]error:[/] {exc}")
        sys.exit(1)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = build_deck(
            outline, str(out), template_path=template, existing_deck_path=append_path, rules_config=config
        )
    except (ComposeError, KeyError) as exc:
        console.print(f"[bold red]error:[/] {exc}")
        sys.exit(1)

    console.print(f"[green]wrote:[/] {out}")
    console.print(f"[cyan]{result.slide_count} slide(s)[/] using layouts: {', '.join(sorted(set(result.layouts_used)))}")
    if result.manual_review:
        console.print(f"[yellow]{len(result.manual_review)} finding(s) need manual review[/] (e.g. all-caps content is flagged, never auto-rewritten)")


@main.command("create-archetype")
@click.argument("spec_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--out", "out_path", type=click.Path(dir_okay=False), required=True, help="Where to write the composed .pptx.")
def create_archetype(spec_path: str, out_path: str):
    """Generate an on-brand deck from SPEC_PATH -- a JSON spec
    ({"title": ..., "slides": [{"archetype": <name>, ...content...}]})
    -- built from the kone-deck-generator skill's 23-archetype library
    (real icons, charts, backgrounds; already brand-compliant, no
    separate fix pass needed). No AI call, no API key needed -- for
    that, plan from a brief instead with `deckguard redesign --brief`,
    which uses this exact same renderer.

    See the skill's own catalog.json for the archetype list (purpose,
    routing keywords, and slots per archetype) and archetypes_batch1/2/3.py's
    SAMPLES for a worked content example of each.
    """
    import json

    from deckguard.redesign import RedesignError
    from deckguard.skill_bridge import _load_archetypes, _load_creator, _validate_kone_spec

    try:
        spec = json.loads(Path(spec_path).read_text())
    except json.JSONDecodeError as exc:
        console.print(f"[bold red]error:[/] {spec_path} is not valid JSON: {exc}")
        sys.exit(1)

    try:
        creator = _load_creator()
        archetypes = _load_archetypes()
        _validate_kone_spec(spec, set(archetypes.ARCHETYPES.keys()))
    except RedesignError as exc:
        console.print(f"[bold red]error:[/] {exc}")
        sys.exit(1)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    creator.build_deck(spec, str(out))

    used = sorted({s["archetype"] for s in spec["slides"]})
    console.print(f"[green]wrote:[/] {out}")
    console.print(f"[cyan]{len(spec['slides']) + 2} slide(s)[/] using archetypes: {', '.join(used)}")


@main.command("sync-skill")
@click.option(
    "--source", "source_dir", type=click.Path(exists=True, file_okay=False), default=None,
    help="Skill directory to sync from (default: ~/.claude/skills/kone-deck-generator, "
    "or KONE_DECK_GENERATOR_DIR if set).",
)
def sync_skill(source_dir: Optional[str]):
    """Re-vendor the kone-deck-generator skill into deckguard's own assets.

    Everything that consumes the skill (archetype list, planning prompt,
    picture-slot map) is already derived from the skill's own files at
    runtime, so after a skill update this copy step -- plus a commit --
    is ALL that's needed for the deployed tool to pick it up: no code
    changes. Copies the engine/archetype .py files, catalog.json,
    fonts/, and assets/icons/ byte-for-byte; reports what changed.
    """
    import filecmp
    import shutil as _shutil

    from deckguard.skill_bridge import _VENDORED_SKILL_DIR, _skill_dir

    src = Path(source_dir) if source_dir else _skill_dir()
    if src.resolve() == _VENDORED_SKILL_DIR.resolve():
        console.print(
            "[bold red]error:[/] the resolved skill directory IS the vendored copy -- nothing newer to sync from. "
            "Install the updated skill at ~/.claude/skills/kone-deck-generator or pass --source."
        )
        sys.exit(1)
    if not (src / "kone_deck_creator.py").is_file():
        console.print(f"[bold red]error:[/] {src} doesn't look like the kone-deck-generator skill (no kone_deck_creator.py)")
        sys.exit(1)

    patterns = ["*.py", "catalog.json", "fonts/*.ttf", "assets/icons/*"]
    changed, added, same = [], [], 0
    for pattern in patterns:
        for src_file in sorted(src.glob(pattern)):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(src)
            dest_file = _VENDORED_SKILL_DIR / rel
            if dest_file.is_file() and filecmp.cmp(src_file, dest_file, shallow=False):
                same += 1
                continue
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            (changed if dest_file.exists() else added).append(str(rel))
            _shutil.copy2(src_file, dest_file)

    # Files vendored earlier but gone from the skill (a retired module,
    # e.g. kone_planner.py in a past update) -- removed so the vendored
    # copy never diverges into a stale superset of the real skill.
    removed = []
    for pattern in patterns:
        for dest_file in sorted(_VENDORED_SKILL_DIR.glob(pattern)):
            rel = dest_file.relative_to(_VENDORED_SKILL_DIR)
            if dest_file.is_file() and not (src / rel).is_file():
                dest_file.unlink()
                removed.append(str(rel))

    for label, names in (("updated", changed), ("added", added), ("removed", removed)):
        for name in names:
            console.print(f"  [cyan]{label}[/] {name}")
    if not (changed or added or removed):
        console.print("[green]vendored copy already up to date[/]")
    else:
        console.print(
            f"[green]synced from {src}[/] -- {len(changed)} updated, {len(added)} added, {len(removed)} removed. "
            "Review, run the test suite, then commit."
        )


@main.command()
@click.argument("deck", type=click.Path(exists=True, dir_okay=False), required=False, default=None)
@click.option("--out", "out_path", type=click.Path(dir_okay=False), required=True, help="Where to write the redesigned .pptx.")
@click.option(
    "--brief", default=None,
    help="Topic/description to author new content from. Required if DECK is omitted; also fills any blank "
    "slides in DECK when one is given, alongside redesigning its real content.",
)
@click.option("--slides", "target_slides", type=int, default=None, help="Target total slide count (default: let Claude judge). Ignored in --mode brand.")
@click.option("--model", default="claude-opus-5", show_default=True, help="Claude model to use for the redesign judgment call. Ignored in --mode brand.")
@click.option("--effort", type=click.Choice(["low", "medium", "high", "xhigh", "max"]), default="high", show_default=True)
@click.option("--notes", default=None, help="Extra steering text appended to the model's instructions (e.g. \"prefer stat slides for anything with a percentage\"). Ignored in --mode brand.")
@click.option(
    "--mode", type=click.Choice(["rewrite", "brand"]), default="rewrite", show_default=True,
    help="'rewrite': Claude picks each slide's kind/layout and re-lays-out its existing wording -- never rewords or "
    "condenses; a slide with more text than one layout holds is split across multiple output slides instead. "
    "'brand': fully deterministic, no API key needed -- text/images carry over verbatim, only layout/variant and the cover/closing slide change.",
)
@click.option(
    "--review", is_flag=True, default=False,
    help="--mode brand only: adds one small, optional AI call that looks at slides brand mode left untouched and "
    "rebuilds any that read as a short divider/transition page (e.g. \"Appendix\") onto the org template's own "
    "Section Divider layout. Needs an ANTHROPIC_API_KEY (unlike the rest of --mode brand).",
)
@click.option(
    "--template", type=click.Path(exists=True, dir_okay=False), default=None,
    help="Org template .pptx to build on (default: the bundled KONE master template).",
)
@click.option("--rules", "rules_path", type=click.Path(exists=True, dir_okay=False), default=None)
def redesign(
    deck: Optional[str], out_path: str, brief: Optional[str], target_slides: Optional[int],
    model: str, effort: str, notes: Optional[str], mode: str, review: bool, template: Optional[str], rules_path: Optional[str],
):
    """Build a deck onto the org template, from any starting point: an
    existing DECK (re-lays-out its real content), DECK plus --brief
    (also authors its blank slides), or --brief alone with no DECK at
    all (a brand-new deck built from nothing, the way a designer would
    from a topic). All three need --mode rewrite (the default) and
    Claude's judgment. For a slide that already has real content, that
    judgment is layout ONLY -- which kind/layout fits it, and, when it
    doesn't fit on one slide, how to split its existing wording across
    several rather than condensing -- never a word changed. A blank
    slide or a bare brief is the opposite: there's nothing to preserve,
    so the model is authoring real content there, grounded in the brief.

    --mode brand is a different, fully deterministic animal: no LLM
    call, no API key, and no wording changes -- it just carries DECK's
    text/images over verbatim onto approved layouts (picked for visual
    variety) and swaps a confidently-detected cover/closing slide onto
    the current brand layout. Needs a DECK; --brief doesn't apply.

    Whichever mode, everything downstream is identical to `create`:
    same deterministic layout selection, same final brand-compliance
    pass, so nothing about color, font, or approved-layout judgment is
    ever left to the model -- only "what kind of slide is this, and how
    should its existing content be laid out" is (and in --mode brand,
    not even that). A slide with a table, chart, embedded object, or
    more content than any layout can hold is never guessed at -- it's
    skipped and reported, same as `retemplate`.

    --mode rewrite requires an ANTHROPIC_API_KEY (the `anthropic`
    package is a base dependency) and prints the API's real token usage
    and a rough cost estimate when done. --mode brand --review also
    needs one, for that one small extra call; --mode brand alone does not.
    """
    from deckguard.redesign import RedesignError, redesign_deck

    needs_api_key = mode == "rewrite" or review
    if needs_api_key and not os.environ.get("ANTHROPIC_API_KEY"):
        reason = "`redesign` needs an Anthropic API key" if mode == "rewrite" else "--review needs an Anthropic API key"
        console.print(f"[bold red]error:[/] ANTHROPIC_API_KEY is not set — {reason}.")
        sys.exit(1)
    if mode == "brand" and not deck:
        console.print("[bold red]error:[/] --mode brand needs a DECK to work from (it never authors content).")
        sys.exit(1)
    if review and mode != "brand":
        console.print("[bold red]error:[/] --review only applies to --mode brand.")
        sys.exit(1)
    if not deck and not brief:
        console.print("[bold red]error:[/] pass a DECK to redesign, --brief to build from scratch, or both.")
        sys.exit(1)

    config = _load_rules(rules_path)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        compose_result, redesign_result = redesign_deck(
            deck, str(out), brief=brief, target_slides=target_slides, model=model, effort=effort, notes=notes,
            template_path=template, rules_config=config, mode=mode, review=review,
        )
    except RedesignError as exc:
        console.print(f"[bold red]error:[/] {exc}")
        sys.exit(1)

    console.print(f"[green]wrote:[/] {out}")
    console.print(
        f"[cyan]{compose_result.slide_count} slide(s)[/] using layouts: {', '.join(sorted(set(compose_result.layouts_used)))}"
    )
    skip_title = "Skipped (needs manual handling)" if mode == "brand" else "Skipped (not sent to the model — needs manual handling)"
    if redesign_result.skipped:
        table = Table(title=skip_title)
        table.add_column("Slide")
        table.add_column("Reason")
        for s in redesign_result.skipped:
            table.add_row(str(s.slide_index), s.reason)
        console.print(table)
    if compose_result.manual_review:
        console.print(f"[yellow]{len(compose_result.manual_review)} finding(s) need manual review[/]")
    if redesign_result.review_notes:
        console.print("[yellow]--review findings:[/]")
        for note in redesign_result.review_notes:
            console.print(f"  [yellow]-[/] {note}")

    if mode == "brand" and not review:
        console.print("[dim]mode: brand — fully deterministic, no API call made[/]")
    else:
        u = redesign_result.usage
        console.print(
            f"[dim]tokens: {u.input_tokens} in / {u.output_tokens} out — "
            f"est. cost ${u.estimated_cost_usd:.3f} ({u.model})[/]"
        )


@main.command("visual-check")
@click.argument("deck", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "fmt", type=click.Choice(["json", "md"]), default="md")
def visual_check(deck: str, fmt: str):
    """Measure what DECK's slides actually LAY OUT to, in a headless browser.

    Everything else here reads XML. This renders each slide's preview and
    measures the result, so it catches what structure can't see: text
    overflowing its box, shapes hanging off the slide edge, type below the
    legible floor, and text without enough contrast against what is
    actually behind it.
    """
    from deckguard import visual as visual_mod

    if not visual_mod.playwright_available():
        console.print(
            "[bold red]unavailable:[/] visual-check needs Playwright and a Chromium "
            "build. Install with 'pip install playwright' and point "
            "DECKGUARD_CHROMIUM at a browser binary."
        )
        sys.exit(1)

    report = visual_mod.audit_deck_previews(deck)
    if fmt == "json":
        click.echo(visual_mod.to_json(report))
        return

    summary = report.summary
    console.print(
        f"[bold]{Path(deck).name}[/] — {report.frames_measured} slides measured, "
        f"{summary.get('major', 0)} major, {summary.get('minor', 0)} minor"
    )
    if not report.findings:
        console.print("[bold green]clean:[/] nothing renders outside its box.")
        return
    table = Table(show_header=True, header_style="bold")
    for col in ("Slide", "Severity", "Rule", "Shape", "What renders wrong"):
        table.add_column(col)
    for f in report.findings:
        color = "red" if f.severity == "major" else "yellow"
        table.add_row(
            str(f.frame_index + 1), f"[{color}]{f.severity}[/]", f.rule,
            f.shape_name, f.message,
        )
    console.print(table)

if __name__ == "__main__":
    main()
