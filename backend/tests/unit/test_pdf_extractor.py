"""T028: PDF extraction keeps headings, paragraphs, tables and links."""

import pymupdf
import pytest

from src.ingestion.pdf_extractor import extract_pdf

URL = "https://www.pnw.edu/faculty-senate/wp-content/uploads/policy.pdf"


@pytest.fixture(scope="module")
def policy_pdf() -> bytes:
    """A small policy PDF: bold headings, wrapped body text, a ruled table, a link."""
    doc = pymupdf.open()
    doc.set_metadata({"title": "Sample Classroom Policy"})
    page = doc.new_page()
    y = 72

    def write(text: str, bold: bool = False) -> None:
        nonlocal y
        page.insert_text((72, y), text, fontname="hebo" if bold else "helv", fontsize=11)
        y += 14

    write("Preamble", bold=True)
    write("The university respects the rights of faculty to teach and of students to")
    write("learn in a respectful environment.")
    y += 14
    write("Levels of Disruptive Behavior", bold=True)
    write("1. A personal, specific informal warning.")
    write("2. A personal, specific formal warning.")
    y += 10

    # A ruled 3x2 table, so pdfplumber's line-based table finder sees it.
    rows = [("Level", "Action"), ("1", "Informal warning"), ("2", "Formal warning")]
    top, col_x, row_h = y, [72, 200, 400], 18
    for r, (a, b) in enumerate(rows):
        row_top = top + r * row_h
        page.insert_text((col_x[0] + 4, row_top + 13), a, fontname="helv", fontsize=10)
        page.insert_text((col_x[1] + 4, row_top + 13), b, fontname="helv", fontsize=10)
    for r in range(len(rows) + 1):
        page.draw_line((col_x[0], top + r * row_h), (col_x[-1], top + r * row_h))
    for x in col_x:
        page.draw_line((x, top), (x, top + len(rows) * row_h))

    page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(72, 700, 300, 712),
                      "uri": "https://www.pnw.edu/public-safety/forms/appeal.pdf"})
    page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(72, 720, 300, 732),
                      "uri": "https://www.pnw.edu/dean-of-students/"})
    data = doc.tobytes()
    doc.close()
    return data


def test_title_and_type(policy_pdf):
    page = extract_pdf(policy_pdf, URL)
    assert page.title == "Sample Classroom Policy"
    assert page.content_type == "pdf"


def test_bold_lines_become_headings_and_wrapped_lines_rejoin(policy_pdf):
    md = extract_pdf(policy_pdf, URL).markdown
    assert "## Preamble" in md
    assert "## Levels of Disruptive Behavior" in md
    assert ("The university respects the rights of faculty to teach and of students to "
            "learn in a respectful environment.") in md


def test_numbered_items_stay_separate(policy_pdf):
    md = extract_pdf(policy_pdf, URL).markdown
    assert "1. A personal, specific informal warning.\n\n2. A personal" in md


def test_ruled_table_becomes_markdown_without_duplicate_text(policy_pdf):
    md = extract_pdf(policy_pdf, URL).markdown
    table = "| Level | Action |\n| --- | --- |\n| 1 | Informal warning |\n| 2 | Formal warning |"
    assert table in md
    assert md.count("Informal warning") == 1


def test_links_are_collected(policy_pdf):
    page = extract_pdf(policy_pdf, URL)
    assert page.pdf_links == ["https://www.pnw.edu/public-safety/forms/appeal.pdf"]
    assert page.child_links == ["https://www.pnw.edu/dean-of-students/"]
