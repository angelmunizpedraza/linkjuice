"""Markdown and CSV output."""

from __future__ import annotations

import csv
import io

from .graph import SiteGraph
from .recommend import Recommendation


def _cell(text: str, limit: int = 58) -> str:
    """A pipe inside a title would split the Markdown table into extra columns."""
    return text.replace("|", "\\|").replace("\n", " ")[:limit]


def _row(node) -> str:
    depth = "—" if node.depth is None else str(node.depth)
    return f"| {_cell(node.title or node.url)} | {node.inlinks} | {depth} | {node.pagerank * 100:.2f} |"


def markdown_report(graph: SiteGraph, recs: list[Recommendation], crawled: int) -> str:
    lines: list[str] = []
    nodes = graph.ranked()
    indexable = [n for n in nodes if n.indexable]
    orphans = graph.orphans()
    near = graph.near_orphans()
    deep = graph.deep_pages()
    dead = graph.dead_ends()
    wasted = graph.wasted_links()
    abuse = graph.exact_anchor_abuse()

    lines.append("# linkjuice — internal link audit")
    lines.append("")
    lines.append(f"Entry page: `{graph.entry}`  ")
    lines.append(f"Pages crawled: **{crawled}** · indexable: **{len(indexable)}**")
    lines.append("")
    lines.append("## Headline numbers")
    lines.append("")
    lines.append("| Signal | Count | What it costs you |")
    lines.append("|---|---:|---|")
    lines.append(f"| Orphan pages | {len(orphans)} | No body link points at them: crawlers find them late or never |")
    lines.append(f"| Near-orphans (1 inlink) | {len(near)} | One edit away from becoming orphans |")
    lines.append(f"| Deeper than 3 clicks | {len(deep)} | Authority arrives diluted; crawl frequency drops |")
    lines.append(f"| Dead ends (no outgoing body links) | {len(dead)} | Authority arrives and stops there |")
    lines.append(f"| Links to non-indexable URLs | {len(wasted)} | Authority spent on pages that cannot rank |")
    lines.append(f"| Targets with repetitive anchors | {len(abuse)} | One phrase used over and over reads as manipulation |")
    lines.append("")

    if orphans:
        lines.append("## Orphans — fix these first")
        lines.append("")
        lines.append("| Page | Inlinks | Depth | PR % |")
        lines.append("|---|---:|---:|---:|")
        lines.extend(_row(n) for n in orphans[:25])
        lines.append("")

    if near:
        lines.append("## Near-orphans")
        lines.append("")
        lines.append("| Page | Inlinks | Depth | PR % |")
        lines.append("|---|---:|---:|---:|")
        lines.extend(_row(n) for n in near[:25])
        lines.append("")

    if wasted:
        lines.append("## Links pointing at pages that cannot rank")
        lines.append("")
        lines.append("| From | To |")
        lines.append("|---|---|")
        for src, tgt in wasted[:25]:
            lines.append(f"| {_cell(src, 90)} | {_cell(tgt, 90)} |")
        lines.append("")

    if abuse:
        lines.append("## Anchor text repeated on the same target")
        lines.append("")
        lines.append("| Page | Inlinks | Distinct anchors |")
        lines.append("|---|---:|---:|")
        for n in abuse[:15]:
            lines.append(f"| {_cell(n.title or n.url)} | {n.inlinks} | {len(set(a.lower() for a in n.anchors))} |")
        lines.append("")

    lines.append("## Top pages by internal PageRank")
    lines.append("")
    lines.append("| Page | Inlinks | Depth | PR % |")
    lines.append("|---|---:|---:|---:|")
    lines.extend(_row(n) for n in indexable[:15])
    lines.append("")

    lines.append("## Recommended new internal links")
    lines.append("")
    if not recs:
        lines.append("No proposal cleared the similarity threshold. Either the site is already "
                     "well linked or the pages are too short for the text model to compare.")
    else:
        lines.append("Ordered by how much the target needs the link. Add each one inside the body "
                     "copy of the source page, in a sentence that already talks about the subject.")
        lines.append("")
        for i, r in enumerate(recs, 1):
            lines.append(f"{i}. **{r.target}**  ")
            lines.append(f"   from `{r.source}` · similarity {r.similarity:.2f} · {r.reason}  ")
            lines.append(f"   suggested anchor: *{r.suggested_anchor}*")
    lines.append("")
    return "\n".join(lines)


def csv_report(recs: list[Recommendation]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["source", "target", "similarity", "suggested_anchor", "target_pagerank", "reason"],
    )
    writer.writeheader()
    for r in recs:
        writer.writerow(r.to_dict())
    return buf.getvalue()


def nodes_csv(graph: SiteGraph) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["url", "title", "indexable", "words", "inlinks", "outlinks", "depth", "pagerank"])
    for n in graph.ranked():
        writer.writerow([
            n.url, n.title, int(n.indexable), n.words, n.inlinks, n.outlinks,
            "" if n.depth is None else n.depth, f"{n.pagerank:.8f}",
        ])
    return buf.getvalue()
