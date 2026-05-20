from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
import json
import os
import re
from typing import Iterable
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup


@dataclass
class NewsItem:
    title: str
    source: str
    published_at: str
    url: str
    summary: str = ""
    kind: str = "news"
    canonical_url: str = ""
    body: str = ""
    language: str = ""
    author: str = ""
    site_name: str = ""
    content_hash: str = ""
    extraction_status: str = "not_attempted"


class NewsAdapter:
    def __init__(self, provider: str = "yfinance") -> None:
        self.provider = provider

    def _obb(self):
        try:
            from openbb import obb  # type: ignore

            return obb
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("OpenBB is required for live news/filing adapters.") from exc

    def fetch_company_news(self, symbol: str, days: int = 14, limit: int = 20) -> list[NewsItem]:
        obb = self._obb()
        start = (date.today() - timedelta(days=days)).isoformat()
        try:
            result = obb.news.company(symbol=symbol, start_date=start, limit=limit, provider=self.provider)
            df = result.to_df()
        except Exception:
            return []
        if df is None or df.empty:
            return []
        rows: list[NewsItem] = []
        for idx, row in df.reset_index().iterrows():
            published = row.get("date", idx)
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            rows.append(
                NewsItem(
                    title=title,
                    source=str(row.get("source") or self.provider),
                    published_at=str(published),
                    url=str(row.get("url") or ""),
                    summary=str(row.get("summary") or row.get("text") or ""),
                    kind="news",
                )
            )
        return rows

    def fetch_sec_filings(self, symbol: str, limit: int = 10) -> list[NewsItem]:
        obb = self._obb()
        try:
            result = obb.equity.fundamental.filings(symbol=symbol, provider="sec", limit=limit)
            df = result.to_df()
        except Exception:
            return []
        if df is None or df.empty:
            return []
        rows: list[NewsItem] = []
        for _, row in df.reset_index(drop=True).iterrows():
            form = str(row.get("report_type") or row.get("form_type") or "SEC filing")
            desc = str(row.get("primary_doc_description") or row.get("primary_doc") or "").strip()
            title = f"SEC {form}" + (f": {desc}" if desc else "")
            rows.append(
                NewsItem(
                    title=title,
                    source="SEC EDGAR",
                    published_at=str(row.get("accepted_date") or row.get("filing_date") or ""),
                    url=str(row.get("filing_detail_url") or row.get("report_url") or row.get("complete_submission_url") or ""),
                    summary=f"Filing date: {row.get('filing_date', '')}; report date: {row.get('report_date', '')}",
                    kind="filing",
                )
            )
        return rows

    def fetch_naver_item_news(self, symbol: str, limit: int = 10) -> list[NewsItem]:
        code = symbol.split(".")[0]
        if not (code.isdigit() and len(code) == 6):
            return []
        url = f"https://finance.naver.com/item/news_news.naver?code={code}&page=1"
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            res.encoding = "euc-kr"
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception:
            return []
        rows: list[NewsItem] = []
        for tr in soup.select("table.type5 tr"):
            title_link = tr.select_one("td.title a")
            if not title_link:
                continue
            info = [td.get_text(" ", strip=True) for td in tr.select("td.info, td.date")]
            href = title_link.get("href") or ""
            full_url = "https://finance.naver.com" + href if href.startswith("/") else href
            rows.append(
                NewsItem(
                    title=title_link.get_text(" ", strip=True),
                    source=info[0] if info else "Naver Finance",
                    published_at=info[-1] if info else "",
                    url=full_url,
                    summary="",
                    kind="news",
                )
            )
            if len(rows) >= limit:
                break
        return rows

    def fetch_naver_search_news(
        self,
        query: str,
        days: int = 14,
        limit: int = 20,
        required_terms: Iterable[str] = (),
    ) -> list[NewsItem]:
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")
        if not client_id or not client_secret or not query.strip():
            return []
        try:
            res = requests.get(
                "https://openapi.naver.com/v1/search/news.json",
                params={
                    "query": query,
                    "display": max(1, min(limit, 100)),
                    "sort": "date",
                },
                headers={
                    "X-Naver-Client-Id": client_id,
                    "X-Naver-Client-Secret": client_secret,
                },
                timeout=10,
            )
            res.raise_for_status()
            payload = res.json()
        except Exception:
            return []

        cutoff = date.today() - timedelta(days=days)
        required = [_compact(term) for term in required_terms if term]
        rows: list[NewsItem] = []
        for item in payload.get("items", []):
            title = _clean_naver_html(str(item.get("title") or ""))
            desc = _clean_naver_html(str(item.get("description") or ""))
            if not title:
                continue
            haystack = _compact(f"{title} {desc}")
            if required and not any(term in haystack for term in required):
                continue
            published_raw = str(item.get("pubDate") or "")
            published = published_raw
            if published_raw:
                try:
                    parsed = parsedate_to_datetime(published_raw)
                    published_date = parsed.date()
                    published = published_date.isoformat()
                    if published_date < cutoff:
                        continue
                except Exception:
                    pass
            rows.append(
                NewsItem(
                    title=title,
                    source="Naver Search News",
                    published_at=published,
                    url=str(item.get("originallink") or item.get("link") or ""),
                    summary=desc,
                    kind="news",
                )
            )
        return rows

    def fetch_gdelt_news(self, query: str, days: int = 7, limit: int = 20) -> list[NewsItem]:
        if not query.strip():
            return []
        try:
            res = requests.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params={
                    "query": query,
                    "mode": "ArtList",
                    "format": "json",
                    "maxrecords": max(1, min(limit, 250)),
                    "sort": "HybridRel",
                    "timespan": f"{max(1, days)}d",
                },
                headers={"User-Agent": "equity-research-copilot/0.1"},
                timeout=12,
            )
            res.raise_for_status()
            payload = res.json()
        except Exception:
            return []

        rows: list[NewsItem] = []
        for item in payload.get("articles", []):
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            if not title or not url:
                continue
            rows.append(
                NewsItem(
                    title=title,
                    source=str(item.get("sourceCommonName") or item.get("domain") or "GDELT"),
                    published_at=str(item.get("seendate") or ""),
                    url=url,
                    summary=str(item.get("summary") or ""),
                    kind="gdelt",
                    language=str(item.get("language") or ""),
                    site_name=str(item.get("domain") or ""),
                )
            )
        return rows

    def fetch_rss_feeds(self, feed_urls: Iterable[str], limit: int = 20, source_label: str = "RSS") -> list[NewsItem]:
        rows: list[NewsItem] = []
        for feed_url in feed_urls:
            feed_url = feed_url.strip()
            if not feed_url:
                continue
            try:
                res = requests.get(feed_url, headers={"User-Agent": "equity-research-copilot/0.1"}, timeout=10)
                res.raise_for_status()
                root = ElementTree.fromstring(res.content)
            except Exception:
                continue

            channel_title = _find_text(root, "./channel/title") or source_label
            for node in list(root.findall(".//item")) + list(root.findall(".//{http://www.w3.org/2005/Atom}entry")):
                title = _find_text(node, "title") or _find_text(node, "{http://www.w3.org/2005/Atom}title")
                link = _find_text(node, "link")
                if not link:
                    atom_link = node.find("{http://www.w3.org/2005/Atom}link")
                    link = atom_link.get("href", "") if atom_link is not None else ""
                if link:
                    link = urljoin(feed_url, link)
                summary = (
                    _find_text(node, "description")
                    or _find_text(node, "summary")
                    or _find_text(node, "{http://www.w3.org/2005/Atom}summary")
                    or ""
                )
                published = (
                    _find_text(node, "pubDate")
                    or _find_text(node, "published")
                    or _find_text(node, "updated")
                    or _find_text(node, "{http://www.w3.org/2005/Atom}published")
                    or _find_text(node, "{http://www.w3.org/2005/Atom}updated")
                    or ""
                )
                title = _clean_naver_html(title or "")
                if not title:
                    continue
                rows.append(
                    NewsItem(
                        title=title,
                        source=channel_title,
                        published_at=published,
                        url=link or feed_url,
                        summary=_clean_naver_html(summary),
                        kind="rss",
                        site_name=channel_title,
                    )
                )
                if len(rows) >= limit:
                    return rows
        return rows

    def fetch_company_ir_feeds(self, symbol: str, company_name: str | None = None, limit: int = 20) -> list[NewsItem]:
        feed_urls = _company_ir_feed_urls(symbol, company_name)
        return self.fetch_rss_feeds(feed_urls, limit=limit, source_label="Company IR")

    def fetch(
        self,
        symbol: str,
        terms: Iterable[str] = (),
        days: int = 14,
        limit: int = 20,
        include_sec: bool = True,
        company_name: str | None = None,
    ) -> list[NewsItem]:
        is_korean = symbol.upper().endswith((".KS", ".KQ"))
        if is_korean:
            code = symbol.split(".")[0]
            search_query = company_name or code
            required_terms = [company_name or "", code]
            items = self.fetch_naver_search_news(search_query, days=days, limit=limit, required_terms=required_terms)
            item_news = self.fetch_naver_item_news(symbol, limit=max(4, limit // 2))
            items = _dedupe_news(items + item_news)
            if not items:
                items = self.fetch_company_news(symbol, days=days, limit=limit)
        else:
            items = self.fetch_company_news(symbol, days=days, limit=limit)
        if include_sec and not is_korean:
            items.extend(self.fetch_sec_filings(symbol, limit=min(limit, 10)))
        extra_items: list[NewsItem] = []
        if _env_enabled("ENABLE_GDELT"):
            gdelt_query = _gdelt_query(symbol, company_name)
            extra_items.extend(self.fetch_gdelt_news(gdelt_query, days=days, limit=max(4, limit // 2)))
        rss_feeds = _split_env("NEWS_RSS_FEEDS")
        if rss_feeds:
            extra_items.extend(self.fetch_rss_feeds(rss_feeds, limit=max(4, limit // 2)))
        extra_items.extend(self.fetch_company_ir_feeds(symbol, company_name, limit=max(4, limit // 2)))
        if extra_items:
            items = _dedupe_news(items + extra_items)
        terms_l = [term.lower() for term in terms if term]
        if terms_l:
            filtered = []
            for item in items:
                haystack = f"{item.title} {item.summary}".lower()
                if any(term in haystack for term in terms_l):
                    filtered.append(item)
            items = filtered
        return items

    @staticmethod
    def normalize(items: list[NewsItem]) -> list[dict]:
        return [asdict(item) for item in items]


def _clean_naver_html(value: str) -> str:
    value = unescape(value)
    value = re.sub(r"</?b>", "", value)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _dedupe_news(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    deduped: list[NewsItem] = []
    for item in items:
        key = (
            re.sub(r"^https?://", "", (item.canonical_url or item.url).lower()).rstrip("/")
            or item.content_hash
            or re.sub(r"[^0-9a-z가-힣]+", "", item.title.lower())[:120]
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _compact(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.lower())


def _find_text(node: ElementTree.Element, path: str) -> str:
    found = node.find(path)
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _split_env(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def _env_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _company_ir_feed_urls(symbol: str, company_name: str | None = None) -> list[str]:
    urls: list[str] = []
    raw_json = os.environ.get("COMPANY_IR_FEEDS_JSON", "").strip()
    if raw_json:
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            keys = [symbol.upper(), symbol.split(".")[0], (company_name or "").strip()]
            for key in keys:
                value = payload.get(key)
                if isinstance(value, str):
                    urls.extend(_split_inline(value))
                elif isinstance(value, list):
                    urls.extend(str(item).strip() for item in value if str(item).strip())
    urls.extend(_split_env("COMPANY_IR_FEEDS"))
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def _split_inline(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _gdelt_query(symbol: str, company_name: str | None = None) -> str:
    code = symbol.split(".")[0]
    if company_name:
        return f'"{company_name}" OR "{code}"'
    return f'"{symbol.upper()}" OR "{code}"'
