"""linkjuice command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .crawl import crawl, pages_from_files
from .graph import build_graph
from .recommend import recommend_links
from .report import csv_report, markdown_report, nodes_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="linkjuice",
        description="Internal link graph audit: orphans, click depth, internal PageRank, "
                    "and concrete link recommendations.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="crawl a site and write the audit")
    run.add_argument("target", help="root URL, or one or more local HTML files with --files")
    run.add_argument("extra", nargs="*", help="further local HTML files when using --files")
    run.add_argument("--files", action="store_true", help="treat the arguments as local HTML files")
    run.add_argument("--max-pages", type=int, default=200)
    run.add_argument("--delay", type=float, default=0.3, help="seconds between requests")
    run.add_argument("--no-robots", action="store_true", help="ignore robots.txt (use on your own site)")
    run.add_argument("--no-sitemap", action="store_true", help="do not seed the queue from /sitemap.xml")
    run.add_argument("--limit", type=int, default=40, help="maximum link recommendations")
    run.add_argument("--min-similarity", type=float, default=0.12)
    run.add_argument("--min-source-words", type=int, default=250,
                     help="ignore pages shorter than this as link sources")
    run.add_argument("--md", help="write the Markdown report here")
    run.add_argument("--csv", help="write the recommendations as CSV here")
    run.add_argument("--nodes-csv", help="write one row per crawled page here")
    run.add_argument("--max-orphans", type=int, default=None,
                     help="exit 1 if more than this many orphan pages are found (CI gate)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.files:
        paths = [args.target, *args.extra]
        missing = [p for p in paths if not Path(p).exists()]
        if missing:
            print(f"linkjuice: file not found: {', '.join(missing)}", file=sys.stderr)
            return 2
        pages = pages_from_files(paths)
    else:
        pages = list(
            crawl(
                args.target,
                max_pages=args.max_pages,
                delay=args.delay,
                respect_robots=not args.no_robots,
                seed_from_sitemap=not args.no_sitemap,
            )
        )
        pages = [p for p in pages if p.status == 200]

    if not pages:
        print("linkjuice: nothing crawled — check the URL, robots.txt or your connection",
              file=sys.stderr)
        return 2

    graph = build_graph(pages, entry=pages[0].url)
    recs = recommend_links(
        pages,
        graph,
        limit=args.limit,
        min_similarity=args.min_similarity,
        min_source_words=args.min_source_words,
    )
    md = markdown_report(graph, recs, crawled=len(pages))

    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")
    if args.csv:
        Path(args.csv).write_text(csv_report(recs), encoding="utf-8")
    if args.nodes_csv:
        Path(args.nodes_csv).write_text(nodes_csv(graph), encoding="utf-8")
    if not (args.md or args.csv or args.nodes_csv):
        print(md)

    orphans = len(graph.orphans())
    if args.max_orphans is not None and orphans > args.max_orphans:
        print(f"linkjuice: {orphans} orphan pages, above --max-orphans {args.max_orphans}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
