"""Real pictures of the slides, for the page where you pick them.

`preview.archetype_preview_html` draws a wireframe: honest about where
the boxes are, silent about what the slide actually looks like. Asked to
choose between fifty of them, that is not enough -- a photo cover, a
sand statement and a blue quote all preview as a pale rectangle with
some grey lines in it.

So we render the truth once, offline: build a deck holding every
archetype, put it through the same LibreOffice conversion a person would
use to look at it, and keep one PNG per archetype under `assets/previews`.
The web page serves those; anything without one falls back to the
wireframe, so a new archetype is never a broken image.

Rendering needs LibreOffice and poppler, which the Railway image has no
reason to carry. That is why the PNGs are committed rather than built on
boot: `python -m deckguard.thumbs` regenerates them here, and the server
only ever reads files.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from deckguard import brandmode as bm

PREVIEW_DIR = Path(__file__).parent / "assets" / "previews"
WIDTH_PX = 520  # ~2x the widest tile the grid draws, so it stays crisp


def path_for(archetype: str) -> Path | None:
    """The rendered thumbnail for an archetype, if one exists."""
    if not archetype or "/" in archetype or "\\" in archetype or ".." in archetype:
        return None
    candidate = PREVIEW_DIR / f"{archetype}.png"
    return candidate if candidate.is_file() else None


def set_archetypes() -> list[str]:
    """Every archetype either curated set offers, in set order."""
    names: list[str] = []
    for audience in bm.set_names():
        for slide in bm.slides_in(audience):
            name = slide["archetype"]
            if name not in names:
                names.append(name)
    return names


def _tools_present() -> None:
    for tool in ("soffice", "pdftoppm"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"{tool} is not on PATH. Thumbnails are rendered offline and "
                "committed; you only need these to regenerate them.")


def render(names: list[str] | None = None, out_dir: Path | None = None) -> list[Path]:
    """Render one PNG per archetype. Returns the files written."""
    from deckguard import assemble
    from deckguard.preview import sample_content
    from deckguard.registry import _load_archetypes

    _tools_present()
    out_dir = out_dir or PREVIEW_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    built = set(_load_archetypes().ARCHETYPES)
    wanted = [n for n in (names or set_archetypes()) if n in built]
    if not wanted:
        return []

    spec = {
        "title": "Slide previews",
        "date": assemble.bm_date(),
        "slides": [{"archetype": n, **sample_content(n)} for n in wanted],
    }

    written: list[Path] = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        deck = work / "previews.pptx"
        assemble.build(spec, str(deck))
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf",
             "--outdir", str(work), str(deck)],
            check=True, capture_output=True, timeout=900,
        )
        pdf = work / "previews.pdf"
        if not pdf.is_file():
            raise RuntimeError("LibreOffice produced no PDF")
        subprocess.run(
            ["pdftoppm", "-png", "-scale-to-x", str(WIDTH_PX), "-scale-to-y", "-1",
             str(pdf), str(work / "page")],
            check=True, capture_output=True, timeout=900,
        )

        pages = sorted(work.glob("page-*.png"))
        # build_deck keeps the master's cover as page 1 and its "Thank
        # you" last, so body slide i is page i + 1.
        for index, name in enumerate(wanted):
            page = work / f"page-{index + 2:0{len(pages[0].stem.split('-')[1])}d}.png"
            if not page.is_file():
                matches = [p for p in pages if int(p.stem.split("-")[1]) == index + 2]
                if not matches:
                    continue
                page = matches[0]
            target = out_dir / f"{name}.png"
            shutil.copyfile(page, target)
            written.append(target)
    return written


def main() -> None:
    files = render()
    print(f"{len(files)} thumbnails written to {PREVIEW_DIR}")


if __name__ == "__main__":
    main()
