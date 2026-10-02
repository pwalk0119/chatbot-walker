"""T030: chunks follow headings, carry their heading path, and never split a table row."""

from src.ingestion.chunker import chunk_markdown

TABLE = "\n".join(
    ["| Event | Date |", "| --- | --- |"]
    + [f"| Fall 2026 deadline number {i} | November {i} |" for i in range(1, 41)]
)

DOC = f"""# Academic Schedule

Intro paragraph about the schedule.

### Fall '26

{TABLE}

### Spring '27

Spring classes begin January 11.
"""


def test_chunks_start_with_their_heading_path():
    chunks = chunk_markdown(DOC, "Academic Schedule", max_chars=600)
    assert chunks[0].text.startswith("Academic Schedule\n\nIntro paragraph")  # H1 == title, once
    fall = "Academic Schedule > Fall '26\n\n| Event | Date |"
    assert any(c.text.startswith(fall) for c in chunks)
    assert chunks[-1].text == "Academic Schedule > Spring '27\n\nSpring classes begin January 11."


def test_large_table_splits_between_rows_and_repeats_its_header():
    chunks = chunk_markdown(DOC, "Academic Schedule", max_chars=600)
    table_chunks = [c for c in chunks if "Fall '26" in c.text]
    assert len(table_chunks) > 1
    for c in table_chunks:
        assert len(c.text) <= 600
        body = c.text.split("\n\n", 1)[1]
        assert body.startswith("| Event | Date |\n| --- | --- |")
        # every table chunk can see the whole table
        assert c.context_text.endswith(TABLE)
    rows = [line for line in TABLE.splitlines()[2:]]
    for row in rows:
        assert sum(row in c.text.splitlines() for c in table_chunks) == 1  # each row exactly once


def test_text_only_chunks_have_no_table_context_and_indexes_are_sequential():
    chunks = chunk_markdown(DOC, "Academic Schedule", max_chars=600)
    assert chunks[0].context_text is None
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_long_paragraph_is_split_on_sentence_boundaries():
    sentence = "Students must file an appeal within ten calendar days."
    chunks = chunk_markdown(" ".join([sentence] * 30), "Parking", max_chars=300)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= 300
        assert c.text.endswith(".")


def test_headings_without_body_produce_no_empty_chunks():
    chunks = chunk_markdown("# A\n\n## B\n\n## C\n\nOnly body.", "Doc")
    assert [c.text for c in chunks] == ["Doc > A > C\n\nOnly body."]
