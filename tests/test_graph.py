def test_pagerank_sums_to_one_and_home_leads(graph):
    total = sum(n.pagerank for n in graph.nodes.values())
    assert abs(total - 1.0) < 1e-9
    assert graph.ranked()[0].url.endswith("/home")


def test_orphans_are_detected_and_noindex_pages_are_not_orphans(graph):
    orphan_urls = {n.url for n in graph.orphans()}
    assert orphan_urls == {"https://example.com/endoscopy", "https://example.com/recovery"}
    # privacy has no inlinks either, but it is noindex: it is not a lost opportunity
    assert "https://example.com/privacy" not in orphan_urls


def test_click_depth_from_the_entry_page(graph):
    assert graph.nodes["https://example.com/home"].depth == 0
    assert graph.nodes["https://example.com/boas"].depth == 1
    assert graph.nodes["https://example.com/endoscopy"].depth is None


def test_near_orphans(graph):
    urls = {n.url for n in graph.near_orphans()}
    assert urls == {"https://example.com/boas", "https://example.com/eye"}


def test_dead_ends_are_pages_with_content_and_no_body_links(graph):
    urls = {n.url for n in graph.dead_ends()}
    assert "https://example.com/endoscopy" in urls
    assert "https://example.com/home" not in urls


def test_nav_links_do_not_create_graph_edges(graph):
    # /contact is only linked from the nav, so it never entered the crawl set
    assert "https://example.com/contact" not in graph.nodes
    assert "https://example.com/privacy" not in graph.edges.get("https://example.com/home", set())


def test_anchor_diversity_defaults_to_one_when_there_is_nothing_to_compare(graph):
    node = graph.nodes["https://example.com/endoscopy"]
    assert node.anchor_diversity == 1.0
