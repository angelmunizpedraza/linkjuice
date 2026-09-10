"""linkjuice — internal link graph analysis and link recommendations for SEO."""

from .crawl import Page, crawl, parse_page
from .graph import SiteGraph, build_graph
from .similarity import similarity_matrix, top_terms
from .recommend import Recommendation, recommend_links

__all__ = [
    "Page",
    "crawl",
    "parse_page",
    "SiteGraph",
    "build_graph",
    "similarity_matrix",
    "top_terms",
    "Recommendation",
    "recommend_links",
]
__version__ = "0.1.0"
