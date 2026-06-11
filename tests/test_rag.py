"""Tests for the RAG pipeline: article loader and retriever (no FAISS needed)."""

import pytest
from langchain_core.documents import Document

from src.rag.loader import _parse_frontmatter, load_articles
from src.rag.retriever import KnowledgeRetriever, RetrievedChunk


# ----------------------------------------------------------------- loader

ARTICLE = """---
title: What Is a Stock?
category: stocks
source: SEC Investor.gov
---

A stock represents partial ownership of a company.
"""


def test_parse_frontmatter():
    meta, body = _parse_frontmatter(ARTICLE)
    assert meta["title"] == "What Is a Stock?"
    assert meta["source"] == "SEC Investor.gov"
    assert body.startswith("A stock represents")


def test_parse_frontmatter_absent():
    meta, body = _parse_frontmatter("Just plain text.")
    assert meta == {}
    assert body == "Just plain text."


def test_load_articles_from_directory(tmp_path):
    (tmp_path / "stocks").mkdir()
    (tmp_path / "stocks" / "what-is-a-stock.md").write_text(ARTICLE)
    (tmp_path / "bonds").mkdir()
    (tmp_path / "bonds" / "bond-basics.md").write_text("Bonds are loans to issuers.")
    (tmp_path / "bonds" / "empty.md").write_text("")

    articles = load_articles(tmp_path)
    assert len(articles) == 2  # empty file skipped

    stock = next(a for a in articles if a.category == "stocks")
    assert stock.title == "What Is a Stock?"
    assert stock.source == "SEC Investor.gov"

    bond = next(a for a in articles if a.category == "bonds")
    # No frontmatter: defaults derived from filename/folder.
    assert bond.title == "Bond Basics"
    assert bond.source == "AI Finance Assistant Knowledge Base"


def test_real_knowledge_base_loads():
    articles = load_articles()
    assert len(articles) >= 50
    assert all(a.title and a.category and a.source and a.content for a in articles)
    categories = {a.category for a in articles}
    assert {"basics", "stocks", "bonds", "retirement", "tax"} <= categories


# ------------------------------------------------------------ vector store

def test_articles_to_documents_chunks_with_metadata():
    from src.rag.loader import Article
    from src.rag.vector_store import articles_to_documents

    long_body = "Diversification spreads risk across assets. " * 60  # > chunk_size
    articles = [
        Article(title="Diversification", category="risk_diversification",
                source="Test", content=long_body, path="risk/diversification.md"),
        Article(title="Short", category="basics", source="Test",
                content="One small chunk.", path="basics/short.md"),
    ]
    docs = articles_to_documents(articles)
    assert len(docs) > 2  # the long article was split
    assert all(len(d.page_content) <= 800 for d in docs)
    first = docs[0]
    assert first.metadata == {
        "title": "Diversification", "category": "risk_diversification",
        "source": "Test", "path": "risk/diversification.md",
    }


def test_build_index_empty_kb_raises(tmp_path):
    from src.rag.vector_store import build_index

    with pytest.raises(RuntimeError, match="empty"):
        build_index(str(tmp_path))


def test_sample_portfolios_are_valid():
    from src.data.sample_portfolios import SAMPLE_PORTFOLIOS

    assert len(SAMPLE_PORTFOLIOS) >= 3
    for spec in SAMPLE_PORTFOLIOS.values():
        assert spec["name"]
        for h in spec["holdings"]:
            assert {"symbol", "shares", "asset_type"} <= h.keys()
            assert h["shares"] > 0


# --------------------------------------------------------------- retriever

class FakeStore:
    """Mimics FAISS similarity_search_with_score (returns L2 distances)."""

    def __init__(self, results):
        self.results = results
        self.calls = []

    def similarity_search_with_score(self, query, k, **kwargs):
        self.calls.append({"query": query, "k": k, **kwargs})
        return self.results[:k]


def doc(content, title, category="basics", source="Test"):
    return Document(
        page_content=content,
        metadata={"title": title, "category": category, "source": source},
    )


def test_search_maps_distance_to_score():
    # distance 0 -> score 1.0; distance 2 -> score 0.0
    store = FakeStore([(doc("close match", "A"), 0.0), (doc("far match", "B"), 1.5)])
    chunks = KnowledgeRetriever(store=store).search("query", top_k=2)
    assert chunks[0].score == 1.0
    assert chunks[1].score == 0.25


def test_search_filters_below_threshold():
    # config relevance_threshold is 0.25 -> distance 1.9 (score 0.05) is dropped.
    store = FakeStore([(doc("good", "A"), 0.4), (doc("bad", "B"), 1.9)])
    chunks = KnowledgeRetriever(store=store).search("query", top_k=2)
    assert [c.title for c in chunks] == ["A"]


def test_category_filter_overfetches():
    store = FakeStore([(doc("tax stuff", "T", category="tax"), 0.3)])
    KnowledgeRetriever(store=store).search("query", top_k=4, category="tax")
    call = store.calls[0]
    assert call["k"] == 12  # 3x over-fetch when filtering
    assert call["filter"] == {"category": "tax"}


def test_format_context_numbers_and_attributes():
    chunks = [
        RetrievedChunk("Content one.", "Title One", "basics", "Source A", 0.9),
        RetrievedChunk("Content two.", "Title Two", "stocks", "Source B", 0.8),
    ]
    ctx = KnowledgeRetriever.format_context(chunks)
    assert "[1] Title One (source: Source A)" in ctx
    assert "[2] Title Two (source: Source B)" in ctx


def test_format_context_empty():
    assert "No relevant" in KnowledgeRetriever.format_context([])


def test_citations_deduplicated():
    chunk = RetrievedChunk("c", "Same Title", "basics", "Same Source", 0.9)
    cites = KnowledgeRetriever.citations([chunk, chunk])
    assert len(cites) == 1
    assert cites[0]["title"] == "Same Title"
