from linkjuice.similarity import similarity_matrix, tokenize, top_terms


def test_stopwords_are_removed_and_short_tokens_dropped():
    tokens = tokenize("The dog and the cat are in a house")
    assert "the" not in tokens and "and" not in tokens and "are" not in tokens
    assert "dog" in tokens and "house" in tokens


def test_spanish_stopwords_are_removed():
    tokens = tokenize("Los perros que están con las personas")
    assert "los" not in tokens and "que" not in tokens and "las" not in tokens
    assert "perros" in tokens and "personas" in tokens


def test_similarity_is_symmetric_and_bounded(pages):
    sims = similarity_matrix(pages)
    a, b = pages[0].url, pages[1].url
    assert sims[(a, b)] == sims[(b, a)]
    assert 0.0 <= sims[(a, b)] <= 1.0


def test_airway_pages_are_closer_to_each_other_than_to_the_eye_page(pages):
    sims = similarity_matrix(pages)
    boas = "https://example.com/boas"
    recovery = "https://example.com/recovery"
    eye = "https://example.com/eye"
    assert sims[(boas, recovery)] > sims[(boas, eye)]


def test_top_terms_are_distinctive(pages):
    eye = next(p for p in pages if p.url.endswith("/eye"))
    terms = top_terms(eye, pages, k=8)
    assert "cherry" in terms or "gland" in terms
