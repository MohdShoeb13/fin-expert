"""FAISS vector store: chunking, embedding, indexing, and persistence."""

from __future__ import annotations

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.config import PROJECT_ROOT, get_config
from src.core.logging import get_logger
from src.rag.loader import Article, load_articles

logger = get_logger(__name__)

_embeddings: HuggingFaceEmbeddings | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        model = get_config()["rag.embedding_model"]
        logger.info("Loading embedding model %s", model)
        _embeddings = HuggingFaceEmbeddings(model_name=model)
    return _embeddings


def articles_to_documents(articles: list[Article]) -> list[Document]:
    cfg = get_config()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg["rag.chunk_size"],
        chunk_overlap=cfg["rag.chunk_overlap"],
    )
    docs: list[Document] = []
    for article in articles:
        for chunk in splitter.split_text(article.content):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "title": article.title,
                        "category": article.category,
                        "source": article.source,
                        "path": article.path,
                    },
                )
            )
    return docs


def index_dir() -> Path:
    return PROJECT_ROOT / get_config()["rag.index_dir"]


def build_index(kb_dir: str | None = None) -> FAISS:
    """(Re)build the FAISS index from the knowledge base and persist it."""
    articles = load_articles(kb_dir)
    if not articles:
        raise RuntimeError("Knowledge base is empty; cannot build index")
    docs = articles_to_documents(articles)
    logger.info("Indexing %d chunks from %d articles", len(docs), len(articles))
    store = FAISS.from_documents(docs, get_embeddings())
    store.save_local(str(index_dir()))
    return store


def load_index() -> FAISS:
    """Load the persisted index, building it on first run."""
    path = index_dir()
    if (path / "index.faiss").exists():
        return FAISS.load_local(
            str(path), get_embeddings(), allow_dangerous_deserialization=True
        )
    logger.info("No persisted index found; building from knowledge base")
    return build_index()


if __name__ == "__main__":
    build_index()
    print(f"Index built at {index_dir()}")
