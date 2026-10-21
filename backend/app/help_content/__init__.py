"""Platform-managed Help Center content.

One authoritative source for documentation: Markdown files in ``articles/`` plus the taxonomy and
contextual-help definitions in ``catalog``. ``services.help_center.sync_seed_content`` loads them into the
existing ``help_articles`` / ``contextual_help_definitions`` collections; nothing else stores documentation.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

ARTICLES_DIR = Path(__file__).parent / "articles"
_LIST_FIELDS = ("keywords", "aliases", "related")


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _links(value: str) -> list[dict[str, str]]:
    links = []
    for part in value.split(";"):
        label, _, to = part.partition("=")
        if label.strip() and to.strip().startswith("/"):
            links.append({"label": label.strip(), "to": to.strip()})
    return links


def parse_article(text: str, source: str = "") -> dict[str, Any]:
    """Parse ``---`` front matter (``key: value`` lines) followed by a Markdown body."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{source}: missing front matter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError(f"{source}: unterminated front matter")
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    for required in ("slug", "title", "category", "summary"):
        if not meta.get(required):
            raise ValueError(f"{source}: front matter needs '{required}'")
    article: dict[str, Any] = {
        "slug": meta["slug"],
        "title": meta["title"],
        "category": meta["category"],
        "module": meta.get("module") or None,
        "summary": meta["summary"],
        "order": int(meta.get("order") or 100),
        "links": _links(meta.get("links", "")),
        "body": "\n".join(lines[end + 1:]).strip(),
    }
    for field in _LIST_FIELDS:
        article[field if field != "keywords" else "search_keywords"] = _csv(meta.get(field, ""))
    if meta.get("release"):
        article["release"] = meta["release"]
        article["release_date"] = meta.get("release_date") or None
    return article


def content_hash(article: dict[str, Any]) -> str:
    keys = ("title", "category", "module", "summary", "order", "links", "body", "search_keywords", "aliases", "related", "release", "release_date")
    payload = repr([article.get(k) for k in keys]).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


@lru_cache(maxsize=1)
def load_articles() -> tuple[dict[str, Any], ...]:
    articles = []
    seen: set[str] = set()
    claimed: dict[str, str] = {}
    for path in sorted(ARTICLES_DIR.glob("*.md")):
        article = parse_article(path.read_text(encoding="utf-8"), path.name)
        slug = article["slug"]
        if slug in seen:
            raise ValueError(f"duplicate help article slug: {slug}")
        seen.add(slug)
        article["seed_hash"] = content_hash(article)
        articles.append(article)
    for article in articles:
        for name in article["aliases"]:
            if name in seen or name in claimed:
                raise ValueError(f"help alias '{name}' collides with a slug or another alias")
            claimed[name] = article["slug"]
        for target in article["related"]:
            if target not in seen:
                raise ValueError(f"{article['slug']}: related article '{target}' does not exist")
    return tuple(articles)
