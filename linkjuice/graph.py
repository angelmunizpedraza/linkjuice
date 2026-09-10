"""The internal link graph: PageRank, click depth, orphans, sinks, anchor diversity."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field

from .crawl import Page

DAMPING = 0.85
ITERATIONS = 60
TOLERANCE = 1e-10


@dataclass
class NodeStats:
    url: str
    title: str
    words: int
    indexable: bool
    pagerank: float = 0.0
    depth: int | None = None          # clicks from the entry page, None = unreachable
    inlinks: int = 0                  # unique source pages, body links only
    outlinks: int = 0                 # unique targets, body links only
    anchors: list[str] = field(default_factory=list)

    @property
    def orphan(self) -> bool:
        return self.indexable and self.inlinks == 0

    @property
    def near_orphan(self) -> bool:
        return self.indexable and self.inlinks == 1

    @property
    def anchor_diversity(self) -> float:
        """1.0 = every inbound anchor is different, 0.0 = all identical."""
        if len(self.anchors) < 2:
            return 1.0
        return len(set(a.lower().strip() for a in self.anchors)) / len(self.anchors)


@dataclass
class SiteGraph:
    entry: str
    nodes: dict[str, NodeStats]
    edges: dict[str, set[str]]        # source -> targets (body links, indexable only)

    # --- views the report needs -------------------------------------------------
    def ranked(self) -> list[NodeStats]:
        return sorted(self.nodes.values(), key=lambda n: n.pagerank, reverse=True)

    def orphans(self) -> list[NodeStats]:
        return [n for n in self.ranked() if n.orphan and n.url != self.entry]

    def near_orphans(self) -> list[NodeStats]:
        return [n for n in self.ranked() if n.near_orphan and n.url != self.entry]

    def deep_pages(self, threshold: int = 3) -> list[NodeStats]:
        return [
            n for n in self.ranked()
            if n.indexable and (n.depth is None or n.depth > threshold)
        ]

    def dead_ends(self) -> list[NodeStats]:
        """Indexable pages with real content that link nowhere in the body."""
        return [n for n in self.ranked() if n.indexable and n.outlinks == 0 and n.words > 100]

    def wasted_links(self) -> list[tuple[str, str]]:
        """Body links pointing at a page that cannot rank (noindex/canonicalised/404)."""
        out: list[tuple[str, str]] = []
        for src, targets in self.edges.items():
            for tgt in targets:
                node = self.nodes.get(tgt)
                if node and not node.indexable:
                    out.append((src, tgt))
        return sorted(out)

    def exact_anchor_abuse(self, min_inlinks: int = 4, max_diversity: float = 0.35) -> list[NodeStats]:
        return [
            n for n in self.ranked()
            if n.inlinks >= min_inlinks and n.anchor_diversity <= max_diversity
        ]


def build_graph(pages: list[Page], entry: str | None = None) -> SiteGraph:
    known = {p.url: p for p in pages}
    entry = entry or (pages[0].url if pages else "")

    nodes: dict[str, NodeStats] = {
        p.url: NodeStats(url=p.url, title=p.title, words=p.words, indexable=p.indexable)
        for p in pages
    }

    edges: dict[str, set[str]] = defaultdict(set)
    inbound_anchors: dict[str, list[str]] = defaultdict(list)
    for page in pages:
        if not page.indexable:
            # A noindex page still passes links, but we do not treat it as a source
            # of authority worth optimising; keep its edges out of the graph.
            continue
        for link in page.body_links:
            if link.target not in known:
                continue
            edges[page.url].add(link.target)
            inbound_anchors[link.target].append(link.anchor)

    for url, node in nodes.items():
        node.outlinks = len(edges.get(url, ()))
        node.anchors = inbound_anchors.get(url, [])
        node.inlinks = len({src for src, tgts in edges.items() if url in tgts})

    _pagerank(nodes, edges)
    _depths(nodes, edges, entry)
    return SiteGraph(entry=entry, nodes=nodes, edges=dict(edges))


def _pagerank(nodes: dict[str, NodeStats], edges: dict[str, set[str]]) -> None:
    """Plain PageRank with dangling-node redistribution. No third-party graph library."""
    urls = list(nodes)
    n = len(urls)
    if n == 0:
        return
    rank = {u: 1.0 / n for u in urls}
    inbound: dict[str, list[str]] = defaultdict(list)
    for src, targets in edges.items():
        for tgt in targets:
            inbound[tgt].append(src)

    for _ in range(ITERATIONS):
        dangling = sum(rank[u] for u in urls if not edges.get(u))
        new: dict[str, float] = {}
        for u in urls:
            incoming = sum(rank[src] / len(edges[src]) for src in inbound.get(u, ()) if edges.get(src))
            new[u] = (1 - DAMPING) / n + DAMPING * (incoming + dangling / n)
        delta = sum(abs(new[u] - rank[u]) for u in urls)
        rank = new
        if delta < TOLERANCE:
            break

    total = sum(rank.values()) or 1.0
    for u in urls:
        nodes[u].pagerank = rank[u] / total


def _depths(nodes: dict[str, NodeStats], edges: dict[str, set[str]], entry: str) -> None:
    if entry not in nodes:
        return
    seen = {entry: 0}
    queue = deque([entry])
    while queue:
        current = queue.popleft()
        for target in edges.get(current, ()):
            if target not in seen:
                seen[target] = seen[current] + 1
                queue.append(target)
    for url, node in nodes.items():
        node.depth = seen.get(url)


def link_counts(pages: list[Page]) -> Counter:
    """How often each target is linked from the body. Useful for spotting nav leakage."""
    counter: Counter = Counter()
    for page in pages:
        for link in page.body_links:
            counter[link.target] += 1
    return counter
