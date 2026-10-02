"""PDF -> Markdown extraction for ingestion (T028).

pdfplumber reads each page as positioned lines and tables:
- tables become Markdown tables, placed where they appear on the page (FR-007)
- lines inside a table's area are skipped so table text is not duplicated
- short bold or larger-than-body lines become headings, which the chunker splits on
- wrapped lines are rejoined into paragraphs; numbered/bulleted items stay separate

PyMuPDF is the fallback when pdfplumber fails or finds no text.
"""

import io
import logging
import re
from statistics import median

import pdfplumber

from src.ingestion.html_extractor import ExtractedPage
from src.ingestion.links import classify_links
from src.ingestion.markdown import clean_text, table_to_markdown, tidy

logger = logging.getLogger(__name__)

_LIST_ITEM_RE = re.compile(r"^(\d{1,2}[.)]|[a-zA-Z][.)]|[ivxIVX]{1,4}[.)]|[•●▪◦\-–*])\s+")
_MAX_HEADING_CHARS = 90


def extract_pdf(data: bytes, url: str) -> ExtractedPage:
    """Convert a PDF to Markdown and collect the links it contains."""
    try:
        markdown, title, hrefs = _extract_with_pdfplumber(data)
    except Exception as exc:  # malformed PDFs raise many different errors
        logger.warning("pdfplumber failed on %s (%s); falling back to PyMuPDF", url, exc)
        markdown, title, hrefs = "", "", []
    if not markdown.strip():
        markdown, fallback_title, hrefs = _extract_with_pymupdf(data)
        title = title or fallback_title

    if not title:
        first = next((ln for ln in markdown.splitlines() if ln.strip()), "")
        title = first.lstrip("# ").strip()[:120] or url.rsplit("/", 1)[-1]

    child_links, pdf_links = classify_links(hrefs, url)
    return ExtractedPage(url=url, title=title, markdown=tidy(markdown), content_type="pdf",
                         child_links=child_links, pdf_links=pdf_links)


# --- pdfplumber ------------------------------------------------------------------


def _extract_with_pdfplumber(data: bytes) -> tuple[str, str, list[str]]:
    blocks: list[str] = []
    hrefs: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        title = clean_text((pdf.metadata or {}).get("Title") or "")
        body_size = _body_font_size(pdf)
        for page in pdf.pages:
            hrefs.extend(link["uri"] for link in page.hyperlinks if link.get("uri"))
            blocks.extend(_page_blocks(page, body_size))
    return "\n\n".join(b for b in blocks if b), title, hrefs


def _body_font_size(pdf: pdfplumber.PDF) -> float:
    sizes = [c["size"] for page in pdf.pages[:5] for c in page.chars if c.get("size")]
    return median(sizes) if sizes else 0.0


def _page_blocks(page, body_size: float) -> list[str]:
    tables = page.find_tables()
    items: list[tuple[float, str, str]] = []  # (top, kind, content)

    for table in tables:
        rows = [[cell or "" for cell in row] for row in table.extract() if any(row)]
        if rows:
            items.append((table.bbox[1], "table", table_to_markdown(rows[0], rows[1:])))

    def in_table(line: dict) -> bool:
        mid_y = (line["top"] + line["bottom"]) / 2
        return any(t.bbox[1] <= mid_y <= t.bbox[3] for t in tables)

    lines = [ln for ln in page.extract_text_lines(return_chars=True) if not in_table(ln)]
    gaps = [b["top"] - a["bottom"] for a, b in zip(lines, lines[1:], strict=False)
            if b["top"] > a["bottom"]]
    para_gap = (median(gaps) * 1.6) if gaps else 6.0

    paragraph: list[str] = []
    para_top = 0.0
    prev_bottom = None

    def flush() -> None:
        if paragraph:
            items.append((para_top, "text", _join_lines(paragraph)))
            paragraph.clear()

    for line in lines:
        text = clean_text(line["text"])
        if not text:
            continue
        gap = line["top"] - prev_bottom if prev_bottom is not None else 0
        prev_bottom = line["bottom"]
        if _is_heading(line, text, body_size):
            flush()
            if items and items[-1][1] == "heading" and gap <= para_gap:
                # A heading that wrapped onto a second line.
                top, kind, previous = items[-1]
                items[-1] = (top, kind, f"{previous} {text}")
            else:
                items.append((line["top"], "heading", f"## {text}"))
            continue
        if gap > para_gap or _LIST_ITEM_RE.match(text):
            flush()
        if not paragraph:
            para_top = line["top"]
        paragraph.append(text)
    flush()

    items.sort(key=lambda item: item[0])
    return [content for _, _, content in items]


def _is_heading(line: dict, text: str, body_size: float) -> bool:
    if len(text) > _MAX_HEADING_CHARS or text.endswith((".", ",", ";", ":")):
        return False
    if _LIST_ITEM_RE.match(text) or not any(ch.isalpha() for ch in text):
        return False
    chars = [c for c in line.get("chars", []) if c["text"].strip()]
    if not chars:
        return False
    all_bold = all("bold" in c.get("fontname", "").lower() for c in chars)
    larger = body_size and median(c["size"] for c in chars) >= body_size + 1.5
    return bool(all_bold or larger)


def _join_lines(lines: list[str]) -> str:
    """Rejoin wrapped lines, mending words hyphenated across a line break."""
    text = lines[0]
    for nxt in lines[1:]:
        if text.endswith("-") and nxt[:1].islower():
            text = text[:-1] + nxt
        else:
            text = f"{text} {nxt}"
    return text


# --- PyMuPDF fallback ------------------------------------------------------------


def _extract_with_pymupdf(data: bytes) -> tuple[str, str, list[str]]:
    import pymupdf

    blocks: list[str] = []
    hrefs: list[str] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        title = clean_text((doc.metadata or {}).get("title") or "")
        for page in doc:
            hrefs.extend(link["uri"] for link in page.get_links() if link.get("uri"))
            for block in page.get_text("blocks", sort=True):
                text = clean_text(block[4])
                if text:
                    blocks.append(text)
    return "\n\n".join(blocks), title, hrefs
