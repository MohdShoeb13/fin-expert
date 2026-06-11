"""Knowledge base loader.

Articles are markdown files under knowledge_base/<category>/<slug>.md with
YAML frontmatter (title, source). The folder name is the category, which
powers category-based retrieval filtering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.core.config import PROJECT_ROOT, get_config


@dataclass
class Article:
    title: str
    category: str
    source: str
    content: str
    path: str = field(default="")


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            return meta, parts[2].strip()
    return {}, raw.strip()


def load_articles(kb_dir: str | Path | None = None) -> list[Article]:
    base = Path(kb_dir) if kb_dir else PROJECT_ROOT / get_config()["rag.knowledge_base_dir"]
    articles: list[Article] = []
    for md_file in sorted(base.rglob("*.md")):
        meta, body = _parse_frontmatter(md_file.read_text())
        if not body:
            continue
        articles.append(
            Article(
                title=meta.get("title", md_file.stem.replace("-", " ").title()),
                category=meta.get("category", md_file.parent.name),
                source=meta.get("source", "AI Finance Assistant Knowledge Base"),
                content=body,
                path=str(md_file.relative_to(base)),
            )
        )
    return articles
