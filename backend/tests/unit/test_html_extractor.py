"""T027: HTML extraction keeps tables, accordion content, and the right links."""

from src.ingestion.html_extractor import extract_html

URL = "https://www.pnw.edu/registrar/academic-schedule/"

PAGE = """
<html><head><title>Academic Schedule - Registrar - Purdue University Northwest</title></head>
<body>
  <header><nav><a href="/admissions/">Admissions</a> Site menu</nav></header>
  <main>
    <h1>Academic Schedule</h1>
    <div class="share-buttons"><button>Share</button> Star this page</div>
    <p>Refer to the <a href="refund-withdrawal-schedule/">Refund and Withdraw Schedule</a>.</p>
    <div class="accordion__group">
      <div class="accordion">
        <button class="accordion__toggle">Fall '26</button>
        <div class="accordion__content"><div class="accordion__interior">
          <table class="tablepress">
            <thead><tr><th>Event</th><th>Date</th><th>Time</th></tr></thead>
            <tbody>
              <tr><td>Classes Begin</td><td>August 24</td><td>8:00 A.M.</td></tr>
              <tr><td>Last Day to Drop a Full-Term Course</td><td>November 13</td>
                  <td>4:30 P.M.</td></tr>
              <tr><td>Labor Day | Campus Closed</td><td>September 7</td><td></td></tr>
            </tbody>
          </table>
        </div></div>
      </div>
      <div class="accordion">
        <button class="accordion__toggle">2025-2026 Academic Year</button>
        <div class="accordion__content">
          <p class="h4">Fall 2025</p>
          <ul><li>Classes Begin – August 25</li><li>Breaks<ul><li>Fall Break</li></ul></li></ul>
        </div>
      </div>
    </div>
    <p><a href="https://www.pnw.edu/registrar/forms/drop.pdf">Drop form (PDF)</a>
       <a href="https://catalog.pnw.edu/content.php?catoid=4#top">Catalog</a>
       <a href="https://www.example.com/elsewhere">External</a>
       <a href="mailto:registrar@pnw.edu">Email us</a></p>
    <script>trackPage()</script>
  </main>
  <footer>Copyright Purdue</footer>
</body></html>
"""


def test_title_prefers_h1():
    assert extract_html(PAGE, URL).title == "Academic Schedule"


def test_table_rows_stay_intact_under_their_term_heading():
    md = extract_html(PAGE, URL).markdown
    assert "### Fall '26\n\n| Event | Date | Time |\n| --- | --- | --- |" in md
    assert "| Last Day to Drop a Full-Term Course | November 13 | 4:30 P.M. |" in md
    # A pipe inside a cell is escaped so it cannot shift the columns.
    assert "| Labor Day \\| Campus Closed | September 7 |  |" in md


def test_collapsed_accordion_content_is_kept():
    md = extract_html(PAGE, URL).markdown
    assert "### 2025-2026 Academic Year" in md
    assert "#### Fall 2025" in md  # <p class="h4"> is treated as a heading
    assert "- Classes Begin – August 25" in md
    assert "  - Fall Break" in md  # nested list keeps its indentation


def test_page_chrome_scripts_and_share_widgets_are_dropped():
    md = extract_html(PAGE, URL).markdown
    for noise in ("Site menu", "Copyright", "trackPage", "Share", "Star this page"):
        assert noise not in md


def test_links_are_absolute_same_site_and_split_into_pages_and_pdfs():
    page = extract_html(PAGE, URL)
    assert page.child_links == [
        "https://www.pnw.edu/registrar/academic-schedule/refund-withdrawal-schedule/",
        "https://catalog.pnw.edu/content.php?catoid=4",  # subdomain counts; #fragment dropped
    ]
    assert page.pdf_links == ["https://www.pnw.edu/registrar/forms/drop.pdf"]


def test_table_without_thead_uses_first_row_and_expands_colspan():
    html = """<main><table>
        <tr><th>Term</th><th>Refund</th></tr>
        <tr><td colspan="2">Week 1</td></tr>
        <tr><td>Fall</td><td>100%</td></tr>
    </table></main>"""
    md = extract_html(html, URL).markdown
    assert "| Term | Refund |\n| --- | --- |\n| Week 1 | Week 1 |\n| Fall | 100% |" in md


def test_falls_back_to_trafilatura_without_a_main_area():
    paragraph = "<p>The parking appeal must be filed within ten days.</p>"
    html = f"<html><body>{paragraph * 5}</body></html>"
    page = extract_html(html, URL)
    assert "parking appeal must be filed" in page.markdown
