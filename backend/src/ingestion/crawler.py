"""Bounded crawler: a seed page plus the child pages and PDFs it links to (T029).

The corpus review found that answers often live below the top-level page: the parking
regulations page links to the forms page, which links to the violation appeal PDF. The
crawler follows those links breadth-first, within limits set per seed, and records
each child's parent so answers can draw on the whole chain (FR-006).

It is a polite crawler: it identifies itself, obeys robots.txt, waits between
requests, and skips pages that answer with a bot challenge instead of evading it.
"""

import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from src.ingestion.html_extractor import ExtractedPage, extract_html
from src.ingestion.links import is_pdf_url, normalize_url, site_of
from src.ingestion.pdf_extractor import extract_pdf

logger = logging.getLogger(__name__)

USER_AGENT = (
    "PNW-Policy-Chatbot-Ingest/0.1 (student project; +https://github.com/pwalk0119/chatbot-walker)"
)


@dataclass
class SeedConfig:
    url: str
    # 0 = just the seed; 1 = the seed and the pages/PDFs it links to; and so on.
    max_depth: int = 0
    # Child HTML pages are followed only if their path starts with one of these.
    follow: list[str] = field(default_factory=list)
    # Follow same-site PDF links (attached forms, policies).
    follow_pdfs: bool = True
    max_pages: int = 20


@dataclass
class CrawledDocument:
    page: ExtractedPage
    depth: int
    parent_url: str | None = None


@dataclass
class FetchResult:
    url: str  # final URL after redirects
    status: int
    content_type: str
    content: bytes
    headers: dict[str, str] = field(default_factory=dict)


class FetchBlocked(RuntimeError):
    """The site answered with a bot challenge or refused the request."""


Fetcher = Callable[[str], FetchResult]


def http_fetcher(timeout: float = 30.0) -> Fetcher:
    client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=timeout,
                          follow_redirects=True)

    def fetch(url: str) -> FetchResult:
        response = client.get(url)
        return FetchResult(
            url=str(response.url),
            status=response.status_code,
            content_type=response.headers.get("content-type", ""),
            content=response.content,
            headers={k.lower(): v for k, v in response.headers.items()},
        )

    return fetch


class Crawler:
    def __init__(self, fetch: Fetcher | None = None, delay_seconds: float = 1.0,
                 respect_robots: bool = True) -> None:
        self._fetch = fetch or http_fetcher()
        self._delay = delay_seconds
        self._respect_robots = respect_robots
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last_request = 0.0
        # Shared across seeds so a page linked from two seeds is ingested once.
        self.visited: set[str] = set()

    def crawl(self, seed: SeedConfig) -> list[CrawledDocument]:
        start = normalize_url(seed.url)
        if start is None:
            raise ValueError(f"not a crawlable URL: {seed.url!r}")
        results: list[CrawledDocument] = []
        queue: deque[tuple[str, int, str | None]] = deque([(start, 0, None)])

        while queue and len(results) < seed.max_pages:
            url, depth, parent = queue.popleft()
            if url in self.visited:
                continue
            self.visited.add(url)
            try:
                page = self._get_page(url)
            except FetchBlocked as exc:
                logger.warning("skipped %s: %s", url, exc)
                continue
            except httpx.HTTPError as exc:
                logger.warning("could not fetch %s: %s", url, exc)
                continue
            if page is None:
                continue
            self.visited.add(page.url)  # the post-redirect URL too
            results.append(CrawledDocument(page=page, depth=depth, parent_url=parent))

            if depth >= seed.max_depth:
                continue
            for child in self._children(page, seed, start):
                if child not in self.visited:
                    queue.append((child, depth + 1, page.url))
        return results

    # --- internals ---------------------------------------------------------------

    def _children(self, page: ExtractedPage, seed: SeedConfig, start: str) -> list[str]:
        children = []
        for link in page.child_links:
            path = urlparse(link).path
            if any(path.startswith(prefix) for prefix in seed.follow):
                children.append(link)
        if seed.follow_pdfs:
            children += [p for p in page.pdf_links if site_of(p) == site_of(start)]
        return children

    def _get_page(self, url: str) -> ExtractedPage | None:
        if not self._allowed(url):
            raise FetchBlocked("disallowed by robots.txt")
        self._wait()
        result = self._fetch(url)
        if result.headers.get("x-amzn-waf-action") or (result.status == 202 and not result.content):
            raise FetchBlocked("site returned a bot challenge")
        if result.status in (401, 403, 429):
            raise FetchBlocked(f"HTTP {result.status}")
        if result.status >= 400:
            logger.warning("skipped %s: HTTP %s", url, result.status)
            return None

        final_url = normalize_url(result.url) or url
        if "pdf" in result.content_type.lower() or is_pdf_url(final_url):
            page = extract_pdf(result.content, final_url)
        elif "html" in result.content_type.lower():
            page = extract_html(result.content.decode("utf-8", errors="replace"), final_url)
        else:
            logger.warning("skipped %s: unsupported content type %r", url, result.content_type)
            return None
        if not page.markdown.strip():
            logger.warning("skipped %s: no text extracted", url)
            return None
        return page

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_request = time.monotonic()

    def _allowed(self, url: str) -> bool:
        if not self._respect_robots:
            return True
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        robots = self._robots[origin]
        return robots is None or robots.can_fetch(USER_AGENT, url)

    def _load_robots(self, origin: str) -> RobotFileParser | None:
        try:
            result = self._fetch(f"{origin}/robots.txt")
        except httpx.HTTPError:
            return None  # unreachable robots.txt: no rules to apply
        if result.status >= 400 or "text" not in result.content_type.lower():
            return None
        parser = RobotFileParser()
        parser.parse(result.content.decode("utf-8", errors="replace").splitlines())
        return parser
