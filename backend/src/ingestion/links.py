"""Link normalization shared by the extractors and the crawler."""

from urllib.parse import parse_qsl, urldefrag, urlencode, urljoin, urlparse, urlunparse

# Tracking parameters that make one page look like many (e.g. ?utm_source=chatgpt.com).
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_")


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    """Absolute http(s) URL without #fragment or tracking parameters; None if not crawlable."""
    url = (url or "").strip()
    if not url or url.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    absolute, _ = urldefrag(urljoin(base_url, url) if base_url else url)
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not k.lower().startswith(_TRACKING_PREFIXES)]
    return urlunparse(parsed._replace(query=urlencode(query)))


def site_of(url: str) -> str:
    """Registrable domain, e.g. 'https://catalog.pnw.edu/x' -> 'pnw.edu'."""
    host = (urlparse(url).hostname or "").lower()
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def classify_links(hrefs: list[str], base_url: str) -> tuple[list[str], list[str]]:
    """Split raw hrefs into (same-site page links, PDF links), normalized and de-duplicated."""
    base = normalize_url(base_url) or base_url
    pages: list[str] = []
    pdfs: list[str] = []
    for href in hrefs:
        url = normalize_url(href, base_url)
        if url is None or url == base:
            continue
        if is_pdf_url(url):
            if url not in pdfs:
                pdfs.append(url)
        elif site_of(url) == site_of(base_url) and url not in pages:
            pages.append(url)
    return pages, pdfs
