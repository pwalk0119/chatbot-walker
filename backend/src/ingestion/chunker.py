"""Heading-aware, table-preserving chunker (T030).

A fixed-size text splitter scrambles deadline tables (corpus review), so chunks are
built from whole Markdown blocks instead:

- the document is split into sections at headings
- each chunk starts with its heading path ("Academic Schedule > Fall '26") so it still
  says what it is about when retrieved on its own
- blocks are packed into chunks up to a size limit, never splitting a table row
- a table too large for one chunk is split between rows, repeating its header row,
  and every chunk drawn from a table keeps the full table in `context_text` (FR-007)
"""

import re
from dataclasses import dataclass

# ~300 tokens. bge-base reads at most 512 tokens, and anything beyond is ignored.
DEFAULT_MAX_CHARS = 1200

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    index: int
    text: str
    # Full Markdown table(s) this chunk was drawn from, if any
    context_text: str | None = None


@dataclass
class _Section:
    path: list[str]
    blocks: list[str]


def chunk_markdown(markdown: str, title: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in _sections(markdown):
        breadcrumb = _breadcrumb(title, section.path)
        budget = max(max_chars - len(breadcrumb) - 2, 200)
        for body, tables in _pack(section.blocks, budget):
            chunks.append(Chunk(
                index=len(chunks),
                text=f"{breadcrumb}\n\n{body}",
                context_text=_table_context(breadcrumb, tables),
            ))
    return chunks


# --- Sections --------------------------------------------------------------------


def _blocks(markdown: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", markdown) if b.strip()]


def _sections(markdown: str) -> list[_Section]:
    sections: list[_Section] = []
    stack: list[tuple[int, str]] = []  # (level, heading text)
    current = _Section(path=[], blocks=[])
    for block in _blocks(markdown):
        match = _HEADING_RE.match(block)
        if match and "\n" not in block:
            if current.blocks:
                sections.append(current)
            level, text = len(match.group(1)), match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
            current = _Section(path=[t for _, t in stack], blocks=[])
        else:
            current.blocks.append(block)
    if current.blocks:
        sections.append(current)
    return sections


def _breadcrumb(title: str, path: list[str]) -> str:
    parts = [title] if title else []
    for heading in path:
        if not parts or heading.casefold() != parts[-1].casefold():
            parts.append(heading)
    return " > ".join(parts)


# --- Packing ---------------------------------------------------------------------


def _is_table(block: str) -> bool:
    lines = block.splitlines()
    return len(lines) >= 2 and all(line.startswith("|") for line in lines)


def _pieces(block: str, budget: int) -> list[tuple[str, str | None]]:
    """Split one block into pieces that fit the budget: (piece, source table or None)."""
    if _is_table(block):
        if len(block) <= budget:
            return [(block, block)]
        header, divider, *rows = block.splitlines()
        pieces, current = [], [header, divider]
        for row in rows:
            if len("\n".join([*current, row])) > budget and len(current) > 2:
                pieces.append(("\n".join(current), block))
                current = [header, divider]
            current.append(row)  # a single over-long row is kept whole, never cut
        pieces.append(("\n".join(current), block))
        return pieces

    if len(block) <= budget:
        return [(block, None)]
    pieces, current = [], ""
    for sentence in _SENTENCE_SPLIT_RE.split(block):
        if current and len(current) + 1 + len(sentence) > budget:
            pieces.append((current, None))
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append((current, None))
    return pieces


def _pack(blocks: list[str], budget: int) -> list[tuple[str, list[str]]]:
    """Group blocks into chunk bodies; return (body, tables used) pairs."""
    packed: list[tuple[str, list[str]]] = []
    body: list[str] = []
    tables: list[str] = []

    def flush() -> None:
        if body:
            packed.append(("\n\n".join(body), list(tables)))
        body.clear()
        tables.clear()

    for block in blocks:
        for piece, table in _pieces(block, budget):
            size = len("\n\n".join([*body, piece]))
            if body and size > budget:
                flush()
            body.append(piece)
            if table and table not in tables:
                tables.append(table)
    flush()
    return packed


def _table_context(breadcrumb: str, tables: list[str]) -> str | None:
    if not tables:
        return None
    return f"{breadcrumb}\n\n" + "\n\n".join(tables)
