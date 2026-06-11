"""Retrieval pipeline with relevance scoring and source attribution."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.config import get_config
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    content: str
    title: str
    category: str
    source: str
    score: float  # similarity in [0, 1], higher is more relevant


class KnowledgeRetriever:
    """Semantic search over the financial knowledge base.

    Supports optional category filtering (e.g. tax agent restricts to 'tax').
    """

    def __init__(self, store=None):
        self._store = store

    @property
    def store(self):
        if self._store is None:
            from src.rag.vector_store import load_index

            self._store = load_index()
        return self._store

    def search(
        self,
        query: str,
        top_k: int | None = None,
        category: str | None = None,
    ) -> list[RetrievedChunk]:
        cfg = get_config()
        k = top_k or cfg["rag.top_k"]
        threshold = cfg.get("rag.relevance_threshold", 0.0)

        kwargs = {}
        if category:
            kwargs["filter"] = {"category": category}
        # Over-fetch when filtering so post-filter results still fill top_k.
        results = self.store.similarity_search_with_score(
            query, k=k * 3 if category else k, **kwargs
        )

        chunks: list[RetrievedChunk] = []
        for doc, distance in results:
            # FAISS returns L2 distance over normalized embeddings; map to [0,1].
            score = max(0.0, 1.0 - float(distance) / 2.0)
            if score < threshold:
                continue
            chunks.append(
                RetrievedChunk(
                    content=doc.page_content,
                    title=doc.metadata.get("title", ""),
                    category=doc.metadata.get("category", ""),
                    source=doc.metadata.get("source", ""),
                    score=round(score, 3),
                )
            )
        return chunks[:k]

    @staticmethod
    def format_context(chunks: list[RetrievedChunk]) -> str:
        """Render chunks as numbered context with attribution for the LLM."""
        if not chunks:
            return "No relevant knowledge base articles found."
        blocks = []
        for i, c in enumerate(chunks, 1):
            blocks.append(f"[{i}] {c.title} (source: {c.source})\n{c.content}")
        return "\n\n".join(blocks)

    @staticmethod
    def citations(chunks: list[RetrievedChunk]) -> list[dict]:
        seen, cites = set(), []
        for c in chunks:
            key = (c.title, c.source)
            if key in seen:
                continue
            seen.add(key)
            cites.append(
                {"title": c.title, "source": c.source, "category": c.category, "score": c.score}
            )
        return cites
