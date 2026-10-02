"""HTML -> Markdown extraction for ingestion (T027).

PNW pages keep important content in accordions (e.g. each term's deadlines on the
academic schedule) and in TablePress tables. Generic extractors drop much of that, so
the main content area is converted to Markdown here directly:

- accordion toggles become headings, so a table stays labeled with its term (FR-007)
- accordion / tab / expandable-section bodies are kept even though they render
  collapsed, because their text is already in the DOM (FR-010)
- every <table> becomes a Markdown table with header/row pairing intact (FR-007)

trafilatura is the fallback for pages with no identifiable main content area.
"""

import re
from dataclasses import dataclass, field

import trafilatura
from bs4 import BeautifulSoup, NavigableString, Tag

from src.ingestion.links import classify_links
from src.ingestion.markdown import clean_text as _clean_text
from src.ingestion.markdown import table_to_markdown, tidy

# Containers tried in order to find a page's main content.
_MAIN_SELECTORS = ["main", "[role=main]", "article", "#content", ".content"]

# Never content: page chrome, scripts, media, and widgets.
_DROP_TAGS = ["script", "style", "noscript", "template", "svg", "img", "picture", "video",
              "audio", "iframe", "canvas", "form", "input", "select", "textarea",
              "nav", "header", "footer"]
_DROP_CLASS_RE = re.compile(
    r"(^|[-_ ])(share|social|breadcrumb|skip-link|print|favorite|rating)([-_ ]|$)", re.IGNORECASE
)

_HEADING_TAGS = {f"h{i}": i for i in range(1, 7)}
# Paragraphs styled as headings, e.g. <p class="h4">Fall 2025</p> on the academic schedule.
_HEADING_CLASS_RE = re.compile(r"^h([1-6])$")
# Toggles of collapsible sections (accordions, tabs, expanders).
_TOGGLE_CLASS_RE = re.compile(r"accordion__toggle|accordion-button|accordion-header|"
                              r"tab-title|tabs__tab|toggle-title|expand-title", re.IGNORECASE)
_TOGGLE_HEADING_LEVEL = 3

_BLOCK_TAGS = {"p", "div", "section", "article", "main", "aside", "ul", "ol", "li", "table",
               "blockquote", "dl", "dt", "dd", "pre", "figure", "figcaption", "details",
               "summary", "hr", "address", "button", *_HEADING_TAGS}

_TITLE_SUFFIX_RE = re.compile(r"\s+[-|–]\s+Purdue University Northwest\s*$")


@dataclass
class ExtractedPage:
    url: str
    title: str
    markdown: str
    content_type: str = "html"
    child_links: list[str] = field(default_factory=list)  # same-site HTML pages
    pdf_links: list[str] = field(default_factory=list)


def extract_html(html: str, url: str) -> ExtractedPage:
    """Convert a page to Markdown and collect the links found in its main content."""
    soup = BeautifulSoup(html, "html.parser")
    title = _page_title(soup)
    main = _find_main(soup)

    if main is None:
        markdown = trafilatura.extract(
            html, url=url, include_tables=True, include_links=False, output_format="markdown"
        ) or ""
        link_root: Tag = soup.body or soup
    else:
        _strip_noise(main)
        markdown = _render_blocks(main)
        link_root = main

    child_links, pdf_links = _collect_links(link_root, url)
    return ExtractedPage(url=url, title=title, markdown=tidy(markdown),
                         child_links=child_links, pdf_links=pdf_links)


# --- Page structure --------------------------------------------------------------


def _page_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return _clean_text(h1.get_text(" "))
    if soup.title and soup.title.string:
        return _TITLE_SUFFIX_RE.sub("", soup.title.string.strip())
    return ""


def _find_main(soup: BeautifulSoup) -> Tag | None:
    for selector in _MAIN_SELECTORS:
        found = soup.select_one(selector)
        if found and found.get_text(strip=True):
            return found
    return None


def _strip_noise(root: Tag) -> None:
    for tag in root.find_all(_DROP_TAGS):
        tag.decompose()
    for tag in root.find_all(True):
        if tag.decomposed:
            continue
        classes = " ".join(tag.get("class") or [])
        if classes and _DROP_CLASS_RE.search(classes):
            tag.decompose()
    # Buttons are UI, except the toggles that label collapsible content.
    for button in root.find_all("button"):
        if not _is_toggle(button):
            button.decompose()


# --- Markdown rendering ----------------------------------------------------------


def _render_blocks(node: Tag) -> str:
    blocks: list[str] = []
    inline: list[str] = []

    def flush_inline() -> None:
        text = _clean_text(" ".join(inline))
        if text:
            blocks.append(text)
        inline.clear()

    for child in node.children:
        if isinstance(child, NavigableString):
            if child.__class__.__name__ in ("Comment", "Doctype", "ProcessingInstruction"):
                continue
            inline.append(str(child))
            continue
        if not isinstance(child, Tag):
            continue
        if child.name not in _BLOCK_TAGS:
            inline.append(child.get_text(" "))
            continue
        flush_inline()
        rendered = _render_block(child)
        if rendered:
            blocks.append(rendered)
    flush_inline()
    return "\n\n".join(blocks)


def _render_block(tag: Tag) -> str:
    name = tag.name
    if name in _HEADING_TAGS:
        return _heading(_HEADING_TAGS[name], tag.get_text(" "))
    if _is_toggle(tag):
        return _heading(_TOGGLE_HEADING_LEVEL, tag.get_text(" "))
    if name == "summary":
        return _heading(_TOGGLE_HEADING_LEVEL, tag.get_text(" "))
    if name == "p":
        level = _heading_class_level(tag)
        if level:
            return _heading(level, tag.get_text(" "))
        return _clean_text(tag.get_text(" "))
    if name in ("ul", "ol"):
        return _render_list(tag, depth=0)
    if name == "table":
        return render_table(tag)
    if name == "dl":
        return _render_definition_list(tag)
    if name == "blockquote":
        inner = _render_blocks(tag)
        return "\n".join(f"> {line}" if line else ">" for line in inner.splitlines())
    if name == "pre":
        return f"```\n{tag.get_text().strip()}\n```"
    if name == "hr":
        return ""
    level = _heading_class_level(tag)
    if level:
        return _heading(level, tag.get_text(" "))
    # Generic container (div, section, details, li outside a list, ...): recurse.
    return _render_blocks(tag)


def _heading(level: int, text: str) -> str:
    text = _clean_text(text)
    return f"{'#' * level} {text}" if text else ""


def _heading_class_level(tag: Tag) -> int | None:
    for cls in tag.get("class") or []:
        match = _HEADING_CLASS_RE.match(cls)
        if match:
            return int(match.group(1))
    return None


def _is_toggle(tag: Tag) -> bool:
    classes = " ".join(tag.get("class") or [])
    if classes and _TOGGLE_CLASS_RE.search(classes):
        return True
    return tag.name == "button" and tag.get("aria-controls") is not None


def _render_list(tag: Tag, depth: int) -> str:
    lines: list[str] = []
    ordered = tag.name == "ol"
    for i, li in enumerate(tag.find_all("li", recursive=False), start=1):
        marker = f"{i}." if ordered else "-"
        indent = "  " * depth
        nested = [c for c in li.find_all(["ul", "ol"], recursive=False)]
        for n in nested:
            n.extract()
        text = _clean_text(li.get_text(" "))
        if text:
            lines.append(f"{indent}{marker} {text}")
        for n in nested:
            sub = _render_list(n, depth + 1)
            if sub:
                lines.append(sub)
    return "\n".join(lines)


def _render_definition_list(tag: Tag) -> str:
    lines = []
    for item in tag.find_all(["dt", "dd"], recursive=False):
        text = _clean_text(item.get_text(" "))
        if not text:
            continue
        lines.append(f"**{text}**" if item.name == "dt" else f": {text}")
    return "\n".join(lines)


def render_table(table: Tag) -> str:
    """Render an HTML table as a Markdown table, keeping each row's cells together.

    The header comes from <thead> or, failing that, the first row. Cells spanning
    several columns are repeated so every row has the same number of cells.
    """
    rows: list[list[str]] = []
    header: list[str] | None = None
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue  # belongs to a nested table
        cells: list[str] = []
        for cell in tr.find_all(["th", "td"], recursive=False):
            text = _clean_text(cell.get_text(" "))
            span = int(cell.get("colspan", 1) or 1)
            cells.extend([text] * max(span, 1))
        if not cells:
            continue
        in_thead = tr.find_parent("thead") is not None
        if header is None and (in_thead or all(c.name == "th" for c in tr.find_all(["th", "td"]))):
            header = cells
        else:
            rows.append(cells)
    if header is None:
        if not rows:
            return ""
        header, rows = rows[0], rows[1:]

    markdown = table_to_markdown(header, rows)
    caption = table.find("caption")
    if caption and caption.get_text(strip=True):
        markdown = f"**{_clean_text(caption.get_text(' '))}**\n\n{markdown}"
    return markdown


# --- Links -----------------------------------------------------------------------


def _collect_links(root: Tag, base_url: str) -> tuple[list[str], list[str]]:
    return classify_links([a["href"] for a in root.find_all("a", href=True)], base_url)
