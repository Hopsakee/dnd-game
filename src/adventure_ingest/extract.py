"""extract: a book's PDF to text and pictures (BUILD_PLAN M8), with pymupdf4llm.

Writes into the output folder:
- text.md       the text, page by page under <!-- page N --> markers
- images/       every picture in the PDF at its own size (maps, stat blocks)
- pages/        every page rendered, to read a page by eye
- extract.md    the report: words and pictures per page, and the pages that are
                mostly a picture, whose content the text does not hold
"""

from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pymupdf4llm

# A page with a picture and fewer words than this is read from its picture.
FEW_WORDS = 50
PAGE_DPI = 110


@dataclass(frozen=True)
class Page:
    number: int
    words: int
    pictures: int

    @property
    def mostly_picture(self) -> bool:
        return self.pictures > 0 and self.words < FEW_WORDS


@dataclass(frozen=True)
class ExtractReport:
    pages: list[Page]

    @property
    def picture_pages(self) -> list[Page]:
        return [p for p in self.pages if p.mostly_picture]


def extract(pdf: Path, out: Path) -> ExtractReport:
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "pages").mkdir(exist_ok=True)
    doc = pymupdf.open(pdf)
    chunks = pymupdf4llm.to_markdown(doc, page_chunks=True, show_progress=False)
    pages, text = [], []
    for number, (page, chunk) in enumerate(zip(doc, chunks, strict=True), start=1):
        text.append(f"<!-- page {number} -->\n\n{chunk['text'].strip()}\n")
        pictures = page.get_images(full=True)
        for k, picture in enumerate(pictures, start=1):
            pixmap = pymupdf.Pixmap(doc, picture[0])
            if pixmap.alpha or pixmap.n > 3:
                pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
            pixmap.save(out / "images" / f"page-{number:02d}-{k}.png")
        page.get_pixmap(dpi=PAGE_DPI).save(out / "pages" / f"page-{number:02d}.png")
        pages.append(Page(number, len(chunk["text"].split()), len(pictures)))
    (out / "text.md").write_text("\n".join(text))
    report = ExtractReport(pages)
    (out / "extract.md").write_text(render(pdf, report))
    return report


def render(pdf: Path, report: ExtractReport) -> str:
    def plural(n: int, word: str) -> str:
        return f"{n} {word}" if n == 1 else f"{n} {word}s"

    lines = [f"# Extract: {pdf.name}", "",
             f"{len(report.pages)} pages, {sum(p.words for p in report.pages)} words.", ""]
    if report.picture_pages:
        lines += ["## Pages that are mostly a picture", "",
                  "Their content is not in text.md: read the picture in images/ "
                  "(a map, stat blocks, a handout).", ""]
        lines += [f"- page {p.number}: {plural(p.words, 'word')}, "
                  f"{plural(p.pictures, 'picture')}" for p in report.picture_pages]
        lines.append("")
    lines += ["## Every page", "", "| page | words | pictures |", "|---|---|---|"]
    lines += [f"| {p.number} | {p.words} | {p.pictures} |" for p in report.pages]
    return "\n".join(lines) + "\n"
