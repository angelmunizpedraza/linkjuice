from linkjuice.recommend import recommend_links


def test_orphans_get_a_proposal(pages, graph):
    recs = recommend_links(pages, graph, min_source_words=100)
    targets = {r.target for r in recs}
    assert "https://example.com/endoscopy" in targets
    assert "https://example.com/recovery" in targets


def test_no_proposal_duplicates_an_existing_link(pages, graph):
    recs = recommend_links(pages, graph, min_source_words=100)
    for r in recs:
        assert r.target not in graph.edges.get(r.source, set())


def test_orphan_pages_are_never_used_as_sources(pages, graph):
    recs = recommend_links(pages, graph, min_source_words=100)
    for r in recs:
        assert graph.nodes[r.source].depth is not None


def test_noindex_pages_are_never_a_source_or_a_target(pages, graph):
    recs = recommend_links(pages, graph, min_source_words=100)
    for r in recs:
        assert graph.nodes[r.source].indexable
        assert graph.nodes[r.target].indexable


def test_similarity_threshold_is_respected(pages, graph):
    strict = recommend_links(pages, graph, min_source_words=100, min_similarity=0.95)
    assert strict == []


def test_thin_pages_are_not_used_as_sources(pages, graph):
    recs = recommend_links(pages, graph, min_source_words=10_000)
    assert recs == []


def test_recommendation_is_serialisable(pages, graph):
    recs = recommend_links(pages, graph, min_source_words=100)
    row = recs[0].to_dict()
    assert set(row) == {"source", "target", "similarity", "suggested_anchor", "target_pagerank", "reason"}
