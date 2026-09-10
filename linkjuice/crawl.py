"""Fetch pages and turn HTML into a Page: text, internal links, and where each link sits."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Iterable, Iterator
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

# Chrome-ish UA: several CDNs answer differently to the requests default.
USER_AGENT = "linkjuice/0.1 (+https://github.com/angelmunizpedraza/linkjuice)"

# Stripped before counting words. <nav>/<footer>/<header>/<aside> stay in the tree
# because we need them to classify links as boilerplate, but their text is excluded.
NOISE_TAGS = {"script", "style", "noscript", "svg", "template", "form", "iframe"}
BOILERPLATE_TAGS = {"nav", "footer", "header", "aside"}

SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".zip", ".gz", ".mp4", ".mp3", ".avi", ".doc", ".docx", ".xls",
    ".xlsx", ".ppt", ".pptx", ".css", ".js", ".json", ".xml", ".rss",
)


@dataclass
class Link:
    target: str
    anchor: str
    in_body: bool  # False when the link lives in nav/footer/header/aside


@dataclass
class Page:
    url: str
    title: str = ""
    h1: str = ""
    status: int = 200
    words: int = 0
    text: str = ""
    noindex: bool = False
    canonical_to: str | None = None
    links: list[Link] = field(default_factory=list)

    @property
    def body_links(self) -> list[Link]:
        return [l for l in self.links if l.in_body]

    @property
    def indexable(self) -> bool:
        """A page worth spending internal authority on."""
        if self.noindex or self.status != 200:
            return False
        if self.canonical_to and self.canonical_to != self.url:
            return False
        return True


def normalise(url: str) -> str:
    """Drop the fragment, drop a trailing slash (except the root), lowercase the host."""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    netloc = parsed.netloc.lower()
    rebuilt = f"{parsed.scheme}://{netloc}{path}"
    if parsed.query:
        rebuilt += f"?{parsed.query}"
    return rebuilt


def same_site(url: str, root: str) -> bool:
    a, b = urlparse(url), urlparse(root)
    return a.netloc.lower().removeprefix("www.") == b.netloc.lower().removeprefix("www.")


def _crawlable(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    path = urlparse(url).path.lower()
    return not path.endswith(SKIP_EXTENSIONS)


def parse_page(html: str, url: str, status: int = 200) -> Page:
    """HTML -> Page. Pure function: this is what the tests exercise."""
    soup = BeautifulSoup(html, "html.parser")
    page = Page(url=normalise(url), status=status)

    if soup.title and soup.title.string:
        page.title = soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        page.h1 = h1.get_text(" ", strip=True)

    robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    if robots and "noindex" in (robots.get("content") or "").lower():
        page.noindex = True

    canonical = soup.find("link", attrs={"rel": re.compile(r"^canonical$", re.I)})
    if canonical and canonical.get("href"):
        page.canonical_to = normalise(urljoin(url, canonical["href"]))

    # Links first, while the boilerplate containers are still in the tree.
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        target = normalise(urljoin(url, href))
        if not _crawlable(target) or not same_site(target, url):
            continue
        if target == page.url:
            continue
        in_body = not any(p.name in BOILERPLATE_TAGS for p in a.parents if p.name)
        page.links.append(Link(target=target, anchor=a.get_text(" ", strip=True), in_body=in_body))

    for tag in soup.find_all(list(NOISE_TAGS | BOILERPLATE_TAGS)):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    page.text = re.sub(r"\s+", " ", main.get_text(" ", strip=True))
    page.words = len(page.text.split())
    return page


def _sitemap_urls(root: str, session: requests.Session, timeout: float) -> list[str]:
    """Best-effort: /sitemap.xml, one level of index expansion."""
    found: list[str] = []
    try:
        resp = session.get(urljoin(root, "/sitemap.xml"), timeout=timeout)
        if resp.status_code != 200:
            return found
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", resp.text)
        children = [u for u in locs if u.endswith(".xml")]
        found.extend(u for u in locs if not u.endswith(".xml"))
        for child in children[:10]:
            try:
                sub = session.get(child, timeout=timeout)
                found.extend(
                    u for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sub.text)
                    if not u.endswith(".xml")
                )
            except requests.RequestException:
                continue
    except requests.RequestException:
        pass
    return found


def crawl(
    root: str,
    max_pages: int = 200,
    delay: float = 0.3,
    timeout: float = 15.0,
    respect_robots: bool = True,
    seed_from_sitemap: bool = True,
) -> Iterator[Page]:
    """Breadth-first crawl of one host. Yields pages as they are fetched."""
    root = normalise(root)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    robots = RobotFileParser()
    if respect_robots:
        try:
            robots.set_url(urljoin(root, "/robots.txt"))
            robots.read()
        except Exception:  # noqa: BLE001 - a missing robots.txt must not stop the crawl
            robots = RobotFileParser()
            robots.parse([])

    queue: list[str] = [root]
    if seed_from_sitemap:
        for u in _sitemap_urls(root, session, timeout):
            n = normalise(u)
            if same_site(n, root) and _crawlable(n):
                queue.append(n)

    seen: set[str] = set()
    while queue and len(seen) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        if respect_robots and not robots.can_fetch(USER_AGENT, url):
            continue
        seen.add(url)
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
        except requests.RequestException:
            yield Page(url=url, status=0)
            continue
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype.lower():
            continue
        page = parse_page(resp.text, str(resp.url), resp.status_code)
        page.url = url  # keep the queued identity so the graph stays consistent
        yield page
        for link in page.links:
            if link.target not in seen and link.target not in queue:
                queue.append(link.target)
        if delay:
            time.sleep(delay)


def pages_from_files(paths: Iterable[str], base: str = "https://example.com") -> list[Page]:
    """Score a local export instead of a live site: file name becomes the path."""
    import pathlib

    out: list[Page] = []
    for p in paths:
        path = pathlib.Path(p)
        url = f"{base.rstrip('/')}/{path.stem}"
        out.append(parse_page(path.read_text(encoding="utf-8", errors="ignore"), url))
    return out
