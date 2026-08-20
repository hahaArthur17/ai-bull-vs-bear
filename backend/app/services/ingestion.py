from __future__ import annotations

import re
from hashlib import sha1
from html import unescape
from xml.etree import ElementTree

import httpx


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    value = " ".join("".join(element.itertext()).split())
    return unescape(re.sub(r"<[^>]+>", " ", value)).strip()


def parse_rss(xml_text: str, ticker: str, limit: int = 20) -> list[dict[str, object]]:
    """Parse RSS 2 or Atom XML into the API's evidence shape."""

    root = ElementTree.fromstring(xml_text)
    entries: list[ElementTree.Element] = []
    for element in root.iter():
        if _tag_name(element.tag) in {"item", "entry"}:
            entries.append(element)
    documents: list[dict[str, object]] = []
    for entry in entries[:limit]:
        title = _text(next((child for child in entry if _tag_name(child.tag) == "title"), None))
        description = _text(
            next(
                (
                    child
                    for child in entry
                    if _tag_name(child.tag) in {"description", "summary", "content"}
                ),
                None,
            )
        )
        link_element = next((child for child in entry if _tag_name(child.tag) == "link"), None)
        link = (link_element.attrib.get("href") if link_element is not None else None) or _text(link_element)
        published = _text(
            next(
                (
                    child
                    for child in entry
                    if _tag_name(child.tag) in {"pubdate", "published", "updated"}
                ),
                None,
            )
        )
        guid = _text(next((child for child in entry if _tag_name(child.tag) == "guid"), None))
        if not title:
            continue
        identity = guid or link or f"{title}|{published}"
        documents.append(
            {
                # Feed positions change whenever a new article is published.
                # Hashing the provider's stable identity prevents an upsert from
                # overwriting yesterday's article with today's first entry.
                "id": f"rss-{ticker.lower()}-{sha1(identity.encode('utf-8')).hexdigest()[:16]}",
                "ticker": ticker.upper(),
                "source_type": "news",
                "title": title,
                "url": link or None,
                "published_at": published or None,
                "excerpt": description or title,
                "metadata": {"source": "RSS import"},
            }
        )
    return documents


def fetch_rss(url: str, ticker: str, limit: int = 20, timeout: int = 15) -> list[dict[str, object]]:
    response = httpx.get(
        url,
        headers={"User-Agent": "AI-Bull-vs-Bear/0.1 educational demo"},
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    return parse_rss(response.text, ticker, limit=limit)


def load_text_evidence(path: str, ticker: str, title: str) -> dict[str, object]:
    with open(path, encoding="utf-8") as source:
        content = source.read().strip()
    return {
        "id": f"filing-{ticker.lower()}-{sha1(path.encode('utf-8')).hexdigest()[:8]}",
        "ticker": ticker.upper(),
        "source_type": "filing",
        "title": title,
        "url": None,
        "published_at": None,
        "excerpt": content,
        "metadata": {"source": "local filing import", "path": path},
    }
