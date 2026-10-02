"""T029: the crawler follows only what a seed allows, politely, and records parents."""

from src.ingestion.crawler import Crawler, FetchResult, SeedConfig

ROBOTS = b"User-agent: *\nDisallow: /private/\n"


def html(*links: str) -> bytes:
    anchors = "".join(f'<a href="{href}">link</a>' for href in links)
    body = f"<main><h1>Page</h1><p>Body text.</p>{anchors}</main>"
    return f"<html><body>{body}</body></html>".encode()


SITE = {
    "https://www.pnw.edu/robots.txt": ("text/plain", ROBOTS),
    "https://www.pnw.edu/parking/regulations/": (
        "text/html", html("/public-safety/forms/", "/housing/", "/private/secret/",
                          "https://other.example/page/")),
    "https://www.pnw.edu/public-safety/forms/": (
        "text/html", html("/public-safety/forms/appeal.pdf", "/public-safety/unlock-office/")),
    "https://www.pnw.edu/public-safety/forms/appeal.pdf": ("application/pdf", None),
    "https://www.pnw.edu/housing/": ("text/html", html()),
}


class FakeSite:
    def __init__(self, pdf_bytes: bytes) -> None:
        self.requested: list[str] = []
        self.pdf_bytes = pdf_bytes

    def __call__(self, url: str) -> FetchResult:
        self.requested.append(url)
        if url.startswith("https://blocked.pnw.edu"):
            return FetchResult(url, 202, "text/html", b"", {"x-amzn-waf-action": "challenge"})
        if url not in SITE:
            return FetchResult(url, 404, "text/html", b"not found")
        ctype, body = SITE[url]
        return FetchResult(url, 200, ctype, body if body is not None else self.pdf_bytes)


def make_pdf() -> bytes:
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Parking appeal form. Reason for appeal.")
    data = doc.tobytes()
    doc.close()
    return data


SEED = SeedConfig(url="https://www.pnw.edu/parking/regulations/", max_depth=2,
                  follow=["/public-safety/forms/"])


def test_follows_allowed_pages_and_pdfs_with_parent_links():
    site = FakeSite(make_pdf())
    docs = Crawler(fetch=site, delay_seconds=0).crawl(SEED)
    got = [(d.page.url, d.depth, d.parent_url) for d in docs]
    assert got == [
        ("https://www.pnw.edu/parking/regulations/", 0, None),
        ("https://www.pnw.edu/public-safety/forms/", 1, "https://www.pnw.edu/parking/regulations/"),
        ("https://www.pnw.edu/public-safety/forms/appeal.pdf", 2,
         "https://www.pnw.edu/public-safety/forms/"),
    ]
    assert docs[2].page.content_type == "pdf"
    # /housing/ is not in `follow`, /private/ is disallowed, other.example is off-site.
    assert not any("housing" in u or "private" in u or "other.example" in u
                   for u in site.requested)


def test_max_depth_zero_fetches_only_the_seed():
    site = FakeSite(make_pdf())
    seed = SeedConfig(url=SEED.url, max_depth=0, follow=SEED.follow)
    docs = Crawler(fetch=site, delay_seconds=0).crawl(seed)
    assert [d.page.url for d in docs] == [SEED.url]


def test_follow_pdfs_false_skips_pdfs():
    site = FakeSite(make_pdf())
    seed = SeedConfig(url=SEED.url, max_depth=2, follow=SEED.follow, follow_pdfs=False)
    docs = Crawler(fetch=site, delay_seconds=0).crawl(seed)
    assert all(d.page.content_type == "html" for d in docs)


def test_pages_are_not_ingested_twice_across_seeds():
    crawler = Crawler(fetch=FakeSite(make_pdf()), delay_seconds=0)
    first = crawler.crawl(SEED)
    second = crawler.crawl(SeedConfig(url="https://www.pnw.edu/public-safety/forms/",
                                      max_depth=1))
    assert len(first) == 3
    assert second == []


def test_bot_challenge_and_404_are_skipped_not_fatal():
    crawler = Crawler(fetch=FakeSite(make_pdf()), delay_seconds=0, respect_robots=False)
    assert crawler.crawl(SeedConfig(url="https://blocked.pnw.edu/catalog")) == []
    assert crawler.crawl(SeedConfig(url="https://www.pnw.edu/missing/")) == []
