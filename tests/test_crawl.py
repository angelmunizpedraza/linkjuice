from pathlib import Path

from linkjuice.crawl import normalise, parse_page, same_site

FIX = Path(__file__).parent / "fixtures"


def test_normalise_strips_fragment_and_trailing_slash():
    assert normalise("https://Example.com/a/#top") == "https://example.com/a"
    assert normalise("https://example.com/") == "https://example.com/"
    assert normalise("https://example.com/a?b=1") == "https://example.com/a?b=1"


def test_same_site_ignores_www():
    assert same_site("https://www.example.com/x", "https://example.com/")
    assert not same_site("https://other.com/x", "https://example.com/")


def test_nav_and_footer_links_are_marked_as_boilerplate():
    page = parse_page((FIX / "home.html").read_text(encoding="utf-8"), "https://example.com/home")
    targets = {l.target: l.in_body for l in page.links}
    assert targets["https://example.com/contact"] is False   # nav
    assert targets["https://example.com/terms"] is False     # footer
    assert targets["https://example.com/boas"] is True       # body copy
    assert len(page.body_links) == 2


def test_boilerplate_text_is_excluded_from_the_word_count():
    page = parse_page((FIX / "home.html").read_text(encoding="utf-8"), "https://example.com/home")
    assert "Privacy" not in page.text
    assert "brachycephalic" in page.text
    assert page.words > 100


def test_noindex_page_is_not_indexable():
    page = parse_page((FIX / "privacy.html").read_text(encoding="utf-8"), "https://example.com/privacy")
    assert page.noindex is True
    assert page.indexable is False


def test_canonical_elsewhere_makes_a_page_non_indexable():
    html = '<html><head><link rel="canonical" href="/other"></head><body><p>hi</p></body></html>'
    page = parse_page(html, "https://example.com/dup")
    assert page.canonical_to == "https://example.com/other"
    assert page.indexable is False


def test_self_links_and_offsite_links_are_dropped():
    html = (
        '<html><body><main>'
        '<a href="/self">self</a><a href="https://other.com/x">off</a>'
        '<a href="mailto:a@b.c">mail</a><a href="/doc.pdf">pdf</a>'
        '</main></body></html>'
    )
    page = parse_page(html, "https://example.com/self")
    assert page.links == []
