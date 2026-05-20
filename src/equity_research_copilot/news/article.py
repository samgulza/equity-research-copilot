from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from equity_research_copilot.adapters.news_adapter import NewsItem


TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS and not key.lower().startswith("utm_")
    ]
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def content_hash(*parts: str) -> str:
    text = "\n".join(part.strip() for part in parts if part and part.strip())
    text = re.sub(r"\s+", " ", text).strip().casefold()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ArticleTextExtractor:
    def enrich(self, item: NewsItem) -> NewsItem:
        canonical_url = canonicalize_url(item.url)
        if not canonical_url:
            return replace(
                item,
                canonical_url="",
                content_hash=content_hash(item.title, item.summary),
                extraction_status="no_url",
            )

        try:
            enriched = self._extract_with_trafilatura(item, canonical_url)
            if enriched.body:
                return enriched
        except Exception:
            pass

        try:
            return self._extract_with_bs4(item, canonical_url)
        except Exception as exc:
            return replace(
                item,
                canonical_url=canonical_url,
                content_hash=content_hash(item.title, item.summary),
                extraction_status=f"failed:{type(exc).__name__}",
            )

    def _extract_with_trafilatura(self, item: NewsItem, canonical_url: str) -> NewsItem:
        import trafilatura

        downloaded = trafilatura.fetch_url(canonical_url)
        if not downloaded:
            return replace(item, canonical_url=canonical_url, extraction_status="empty")
        raw = trafilatura.extract(
            downloaded,
            output_format="json",
            with_metadata=True,
            include_comments=False,
            url=canonical_url,
        )
        if not raw:
            return replace(item, canonical_url=canonical_url, extraction_status="empty")
        payload = json.loads(raw)
        body = str(payload.get("text") or "").strip()
        title = item.title or str(payload.get("title") or "")
        published_at = item.published_at or str(payload.get("date") or "")
        source = item.source or str(payload.get("sitename") or payload.get("source") or "")
        return replace(
            item,
            title=title.strip(),
            source=source.strip(),
            published_at=published_at.strip(),
            canonical_url=canonical_url,
            body=body,
            language=str(payload.get("language") or item.language or ""),
            author=str(payload.get("author") or item.author or ""),
            site_name=str(payload.get("sitename") or item.site_name or ""),
            content_hash=content_hash(title, item.summary, body),
            extraction_status="ok" if body else "empty",
        )

    def _extract_with_bs4(self, item: NewsItem, canonical_url: str) -> NewsItem:
        res = requests.get(canonical_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        for node in soup(["script", "style", "noscript", "svg"]):
            node.decompose()
        paragraphs = [p.get_text(" ", strip=True) for p in soup.select("article p, main p, p")]
        paragraphs = [p for p in paragraphs if len(p) >= 40]
        body = "\n".join(paragraphs[:30]).strip()
        site_name = _meta(soup, "og:site_name") or item.site_name
        author = _meta(soup, "author") or _meta(soup, "article:author") or item.author
        published_at = item.published_at or _meta(soup, "article:published_time") or _meta(soup, "date")
        language = item.language or (soup.html.get("lang", "") if soup.html else "")
        return replace(
            item,
            canonical_url=canonical_url,
            body=body,
            language=language,
            author=author,
            site_name=site_name,
            content_hash=content_hash(item.title, item.summary, body),
            extraction_status="ok" if body else "empty",
        )


def enrich_news_items(items: list[NewsItem], limit: int | None = None) -> list[NewsItem]:
    if os.environ.get("ENABLE_ARTICLE_EXTRACTION", "1").strip().lower() in {"0", "false", "no", "off"}:
        return [
            replace(item, canonical_url=canonicalize_url(item.url), content_hash=content_hash(item.title, item.summary, item.body))
            for item in items
        ]
    if limit is None:
        try:
            limit = int(os.environ.get("ARTICLE_EXTRACTION_LIMIT", "2"))
        except ValueError:
            limit = 2
    if limit <= 0:
        return [
            replace(item, canonical_url=canonicalize_url(item.url), content_hash=content_hash(item.title, item.summary, item.body))
            for item in items
        ]

    extractor = ArticleTextExtractor()
    enriched: list[NewsItem] = []
    attempted = 0
    for item in items:
        if item.url and attempted < limit:
            enriched.append(extractor.enrich(item))
            attempted += 1
        else:
            enriched.append(
                replace(item, canonical_url=canonicalize_url(item.url), content_hash=content_hash(item.title, item.summary, item.body))
            )
    return enriched


def _meta(soup: BeautifulSoup, key: str) -> str:
    node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    if node is None:
        return ""
    return str(node.get("content") or "").strip()
