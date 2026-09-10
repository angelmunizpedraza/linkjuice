"""Turn the graph plus the similarity matrix into concrete 'link A to B' proposals."""

from __future__ import annotations

from dataclasses import dataclass

from .crawl import Page
from .graph import SiteGraph
from .similarity import similarity_matrix, top_terms

MIN_SIMILARITY = 0.12      # below this the two pages are not really about the same thing
MIN_SOURCE_WORDS = 250     # a thin page has no room for another link
MAX_NEW_LINKS_PER_SOURCE = 3


@dataclass
class Recommendation:
    source: str
    target: str
    similarity: float
    reason: str
    suggested_anchor: str
    target_pagerank: float

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "similarity": round(self.similarity, 4),
            "suggested_anchor": self.suggested_anchor,
            "target_pagerank": round(self.target_pagerank, 6),
            "reason": self.reason,
        }


def recommend_links(
    pages: list[Page],
    graph: SiteGraph,
    limit: int = 40,
    min_similarity: float = MIN_SIMILARITY,
    min_source_words: int = MIN_SOURCE_WORDS,
) -> list[Recommendation]:
    """Propose internal links, cheapest wins first.

    A proposal has to clear four bars, in this order:
      1. the target is indexable and currently under-linked (orphan, near-orphan,
         deep, or in the bottom half of internal PageRank);
      2. the source is indexable, reachable from the entry page (a link from an
         orphan passes no authority), has enough body copy to host a link, and is
         not already linking to the target;
      3. the two pages are topically close (TF-IDF cosine above the threshold);
      4. the source has authority to give (we prefer higher-PageRank sources).
    """
    by_url = {p.url: p for p in pages}
    sims = similarity_matrix(pages)
    ranked = graph.ranked()
    if not ranked:
        return []

    median_pr = sorted(n.pagerank for n in ranked)[len(ranked) // 2]

    def needs_help(url: str) -> str | None:
        node = graph.nodes.get(url)
        if node is None or not node.indexable or url == graph.entry:
            return None
        if node.inlinks == 0:
            return "orphan: nothing in the body of any page links to it"
        if node.inlinks == 1:
            return "near-orphan: a single internal link points at it"
        if node.depth is None:
            return "unreachable from the entry page by body links"
        if node.depth > 3:
            return f"{node.depth} clicks deep from the entry page"
        if node.pagerank < median_pr:
            return "below-median internal PageRank"
        return None

    targets = [(n, reason) for n in ranked if (reason := needs_help(n.url))]
    out: list[Recommendation] = []
    used_per_source: dict[str, int] = {}

    for node, reason in targets:
        candidates = []
        for source in ranked:
            if source.url == node.url or not source.indexable:
                continue
            if source.depth is None:
                # An orphan cannot pass authority it never receives.
                continue
            src_page = by_url.get(source.url)
            if src_page is None or src_page.words < min_source_words:
                continue
            if node.url in graph.edges.get(source.url, set()):
                continue
            if used_per_source.get(source.url, 0) >= MAX_NEW_LINKS_PER_SOURCE:
                continue
            score = sims.get((source.url, node.url), 0.0)
            if score < min_similarity:
                continue
            # Prefer topical closeness first, then the source's own authority.
            candidates.append((score, source.pagerank, source.url))

        if not candidates:
            continue
        candidates.sort(reverse=True)
        score, _, source_url = candidates[0]
        anchor_terms = top_terms(by_url[node.url], pages, k=4)
        anchor = by_url[node.url].h1 or node.title or " ".join(anchor_terms[:3])
        out.append(
            Recommendation(
                source=source_url,
                target=node.url,
                similarity=score,
                reason=reason,
                suggested_anchor=_anchor(anchor, anchor_terms),
                target_pagerank=node.pagerank,
            )
        )
        used_per_source[source_url] = used_per_source.get(source_url, 0) + 1
        if len(out) >= limit:
            break

    return out


def _anchor(title: str, terms: list[str]) -> str:
    """Prefer a short descriptive phrase over the raw <title>, which is usually padded."""
    cleaned = title.split("|")[0].split(" - ")[0].strip()
    if 3 <= len(cleaned.split()) <= 8:
        return cleaned
    if terms:
        return " ".join(terms[:3])
    return cleaned or "see this page"
