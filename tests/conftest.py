import glob
from pathlib import Path

import pytest

from linkjuice.crawl import pages_from_files
from linkjuice.graph import build_graph

FIX = Path(__file__).parent / "fixtures"


def _ordered_files():
    files = sorted(glob.glob(str(FIX / "*.html")))
    # home first: it is the entry page for depth calculations.
    # match on the file name, never on the full path: a CI runner works
    # inside /home/runner, which would make every path match "home".
    return ([f for f in files if Path(f).name.startswith("home")]
            + [f for f in files if not Path(f).name.startswith("home")])


@pytest.fixture()
def pages():
    return pages_from_files(_ordered_files())


@pytest.fixture()
def graph(pages):
    return build_graph(pages, entry=pages[0].url)
