# linkjuice

**Where does the internal authority of your site actually go?** Crawl it, build the link graph, and get a list of "add a link from *this* page to *that* page" — ordered by how much the target needs it.

[![CI](https://github.com/angelmunizpedraza/linkjuice/actions/workflows/ci.yml/badge.svg)](https://github.com/angelmunizpedraza/linkjuice/actions)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Most internal-linking advice stops at "link related pages". That is not actionable on a site with 300 URLs. `linkjuice` answers the two questions that are: **which pages are starved**, and **which specific page should link to them**.

It is deterministic — no LLM calls, no API keys — so the same crawl always produces the same report and you can put it in CI.

```
$ linkjuice run https://example.com --max-pages 300 --md report.md --csv links.csv

# linkjuice — internal link audit
Pages crawled: 287 · indexable: 241

| Signal                              | Count | What it costs you                                        |
|-------------------------------------|------:|----------------------------------------------------------|
| Orphan pages                        |    14 | No body link points at them: crawlers find them late      |
| Near-orphans (1 inlink)             |    31 | One edit away from becoming orphans                       |
| Deeper than 3 clicks                |    58 | Authority arrives diluted; crawl frequency drops          |
| Dead ends (no outgoing body links)  |     9 | Authority arrives and stops there                         |
| Links to non-indexable URLs         |    22 | Authority spent on pages that cannot rank                 |
| Targets with repetitive anchors     |     4 | One phrase used over and over reads as manipulation       |

## Recommended new internal links
1. **/services/boas-surgery-recovery**
   from `/services/boas-surgery` · similarity 0.30 · orphan: nothing in the body of any page links to it
   suggested anchor: *Recovery after airway surgery*
```

## What it measures

| Signal | How | Why it matters |
|---|---|---|
| **Internal PageRank** | Power iteration over the body-link graph, with dangling-node redistribution. No graph library. | Tells you where authority actually pools, which is rarely where you assumed. |
| **Click depth** | BFS from the entry page over body links only. | Google crawls shallow pages more often. Depth measured through the nav is a lie — every page looks 1 click deep. |
| **Orphans / near-orphans** | Pages with 0 or 1 inbound **body** link. | The classic silent leak: the page exists, ships, and is never found. |
| **Dead ends** | Indexable pages over 100 words with no outgoing body link. | Authority arrives and stops. |
| **Wasted links** | Body links pointing at `noindex`, canonicalised or non-200 URLs. | You are spending link equity on pages that cannot rank. |
| **Anchor concentration** | Distinct anchors ÷ total inbound anchors per target. | The same exact-match phrase repeated 30 times is a pattern, not a strategy. |

### The one thing most tools get wrong

A link in the site-wide navigation is not the same as a link inside a paragraph. If you count both, every page is 1 click from the home page and no page is ever an orphan — the audit reports that everything is fine on a site that is quietly broken.

`linkjuice` classifies every link by its container (`<nav>`, `<header>`, `<footer>`, `<aside>` = boilerplate) and **builds the graph from body links only**. Boilerplate still gets crawled; it just does not count as an editorial vote.

## The recommendations

A proposal has to clear four bars, in this order:

1. **The target needs it** — orphan, near-orphan, unreachable, deeper than 3 clicks, or below-median internal PageRank.
2. **The source can give it** — indexable, reachable from the entry page (a link from an orphan passes authority it never received), at least 250 words of body copy, and not already linking to the target.
3. **They are about the same thing** — TF-IDF cosine similarity above the threshold, computed on title + H1 + body text with a bilingual EN/ES stop list.
4. **The best source wins** — closest topically first, then highest PageRank.

Each proposal comes with a **suggested anchor** taken from the target's own H1 or its most distinctive terms, and a plain-language reason you can paste into a ticket.

Anti-spam guards: no more than 3 new links proposed per source page, never a duplicate of an existing link, never a `noindex` page as source or target.

## Install

```bash
pip install git+https://github.com/angelmunizpedraza/linkjuice.git
```

## Usage

```bash
# crawl a live site
linkjuice run https://yoursite.com --max-pages 300 --md report.md --csv links.csv

# your own site: skip robots.txt and crawl faster
linkjuice run https://yoursite.com --no-robots --delay 0

# one row per page, for a spreadsheet
linkjuice run https://yoursite.com --nodes-csv pages.csv

# local HTML export instead of a live crawl
linkjuice run out/*.html --files

# CI gate: fail the build if a deploy creates orphan pages
linkjuice run https://staging.yoursite.com --max-orphans 0
```

Useful flags: `--min-similarity` (default 0.12), `--min-source-words` (default 250), `--limit` (default 40 proposals), `--no-sitemap`, `--delay`.

The crawler is polite by default: one host, `robots.txt` respected, 0.3 s between requests, `/sitemap.xml` used to seed the queue so pages that are *already* orphaned still get discovered — which is the whole point.

### Python API

```python
from linkjuice import crawl, build_graph, recommend_links

pages = [p for p in crawl("https://example.com", max_pages=200) if p.status == 200]
graph = build_graph(pages, entry=pages[0].url)

for node in graph.orphans():
    print(node.url, node.pagerank)

for rec in recommend_links(pages, graph):
    print(f"{rec.source} -> {rec.target} ({rec.reason})")
```

## Method notes

* **No sklearn, no networkx.** PageRank and TF-IDF are ~40 lines each; the dependency tree stays at `requests` + `beautifulsoup4` so it installs anywhere.
* **Similarity is lexical, not semantic.** It will not spot that "airway obstruction" and "trouble breathing" are the same topic if the pages share no vocabulary. That is a deliberate trade: an embedding model would need an API key and would stop being reproducible.
* **Thresholds are constants at the top of `recommend.py`.** The defaults are tuned for service and content sites; e-commerce with thin product pages needs a lower `--min-source-words`.
* Validated on a 6-page fixture site plus 32 unit tests, no network.

## Project layout

```
linkjuice/
  crawl.py       # HTML → Page: text, links, boilerplate classification, noindex/canonical
  graph.py       # PageRank, click depth, orphans, dead ends, wasted links, anchor diversity
  similarity.py  # TF-IDF cosine, EN/ES stop list, distinctive terms per page
  recommend.py   # source × target proposals with reasons and anchors
  report.py      # Markdown + CSV
  cli.py         # linkjuice run
tests/           # 32 tests + a 6-page fixture site, no network
```

## Related tools by the same author

The full GEO and technical-SEO loop: make the site readable by AI ([geo-check](https://github.com/angelmunizpedraza/geo-check), [llms-txt-generator](https://github.com/angelmunizpedraza/llms-txt-generator)) → make each page **quotable** ([citeable](https://github.com/angelmunizpedraza/citeable)) → make sure the site can **find its own pages** (linkjuice) → verify the bots arrive and the engines cite you ([ai-visibility-tracker](https://github.com/angelmunizpedraza/ai-visibility-tracker), [serp-to-ai-diff](https://github.com/angelmunizpedraza/serp-to-ai-diff)) → tie it to traffic ([ga4-report](https://github.com/angelmunizpedraza/ga4-report)). Technical baseline: [seo-audit](https://github.com/angelmunizpedraza/seo-audit).

## License

MIT © Ángel Muñiz Pedraza — [LinkedIn](https://www.linkedin.com/in/angel-muniz-seo)
