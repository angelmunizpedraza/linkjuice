import glob
from pathlib import Path

import pytest

from linkjuice.crawl import pages_from_files
from linkjuice.graph import build_graph

FIX = Path(__file__).parent / "fixtures"


def _ordered_files():
    files = sorted(glob.glob(str(FIX / "*.html")))
    # home first: it is the entry page for depth calculations
    return [f for f in files if "home" in f] + [f for f in files if "home" not in f]


@pytest.fixture()
def pages():
    return pages_from_files(_ordered_files())


@pytest.fixture()
def graph(pages):
    return build_graph(pages, entry=pages[0].url)
