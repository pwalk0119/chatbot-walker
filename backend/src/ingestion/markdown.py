"""Markdown helpers shared by the HTML and PDF extractors."""

import re


def clean_text(text: str) -> str:
    """Collapse whitespace (including non-breaking spaces) to single spaces."""
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def table_to_markdown(header: list[str], rows: list[list[str]]) -> str:
    """Render rows as a Markdown table, padding short rows so columns never shift (FR-007)."""
    width = max([len(header), *(len(r) for r in rows)], default=0)
    if width == 0:
        return ""

    def fmt(cells: list[str]) -> str:
        cells = [clean_text(c).replace("|", "\\|") for c in cells]
        cells += [""] * (width - len(cells))
        return "| " + " | ".join(cells) + " |"

    lines = [fmt(header), "| " + " | ".join(["---"] * width) + " |"]
    lines += [fmt(r) for r in rows]
    return "\n".join(lines)


def tidy(markdown: str) -> str:
    """Collapse runs of blank lines and end with exactly one newline."""
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
    return markdown + "\n" if markdown else ""
