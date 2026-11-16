"""extract: the book's PDF to text and pictures, and a report of the pages whose
content is a picture (BUILD_PLAN M8: Azzinax page 6, stat blocks as images)."""

import struct

import pytest

from adventure_ingest.extract import extract

from .conftest import TEST_BOOK


@pytest.fixture(scope="module")
def extracted(tmp_path_factory):
    out = tmp_path_factory.mktemp("extract")
    return out, extract(TEST_BOOK / "book" / "book.pdf", out)


def test_the_text_comes_out_page_by_page(extracted):
    out, _ = extracted
    text = (out / "text.md").read_text()
    assert "<!-- page 3 -->" in text
    assert "DC 12 Strength (Athletics)" in text


def test_pages_that_are_mostly_a_picture_are_reported(extracted):
    _, report = extracted
    assert [page.number for page in report.picture_pages] == [3, 6]


def test_the_pictures_come_out_at_their_own_size(extracted):
    out, _ = extracted
    sizes = {p.name: struct.unpack(">II", p.read_bytes()[16:24])
             for p in sorted((out / "images").glob("*.png"))}
    assert sizes == {"page-03-1.png": (800, 600), "page-06-1.png": (608, 420)}


def test_every_page_is_rendered_for_reading(extracted):
    out, _ = extracted
    assert len(list((out / "pages").glob("page-*.png"))) == 7


def test_the_report_names_the_pages_to_read_by_eye(extracted):
    out, _ = extracted
    report = (out / "extract.md").read_text()
    assert "page 6: 1 word, 1 picture" in report
