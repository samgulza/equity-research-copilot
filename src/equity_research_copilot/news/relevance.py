from __future__ import annotations

import re

from equity_research_copilot.adapters.news_adapter import NewsItem


LOW_SIGNAL_TITLE_TERMS = [
    "[그래픽]",
    "그래픽",
    "시황",
    "마감시황",
    "인기 검색",
    "검색 종목",
    "가격 비교",
    "코스피",
    "코스닥",
    "환율",
    "파란불",
]


def compact_text(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.casefold())


def company_match_terms(symbol: str, company_name: str | None = None) -> list[str]:
    terms: list[str] = []
    code = symbol.split(".")[0].strip()
    if code:
        terms.append(code)

    name = (company_name or "").strip()
    if name:
        cleaned = re.sub(r"\s+", "", name)
        cleaned = re.sub(r"\(.*?\)", "", cleaned)
        cleaned = re.sub(r"(보통주|우선주|홀딩스|지주|주식회사)$", "", cleaned)
        terms.extend([name, cleaned])
        if cleaned.upper().startswith("HD") and len(cleaned) > 4:
            terms.append(cleaned[2:])
        for token in re.split(r"[\s/&.,()+-]+", name):
            token = token.strip()
            if len(compact_text(token)) >= 3:
                terms.append(token)
        if len(cleaned) >= 4:
            terms.append(cleaned[:4])

    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        compacted = compact_text(term)
        if len(compacted) < 2 or compacted in seen:
            continue
        seen.add(compacted)
        unique.append(compacted)
    return sorted(unique, key=len, reverse=True)


def text_directly_mentions_company(symbol: str, company_name: str | None, text: str) -> bool:
    haystack = compact_text(text)
    return any(term in haystack for term in company_match_terms(symbol, company_name))


def news_item_directly_mentions_company(symbol: str, company_name: str | None, item: NewsItem) -> bool:
    return text_directly_mentions_company(symbol, company_name, item.title)


def is_low_signal_title(title: str) -> bool:
    lowered = title.casefold()
    return any(term in lowered for term in LOW_SIGNAL_TITLE_TERMS)


def split_direct_company_news(
    symbol: str,
    company_name: str | None,
    items: list[NewsItem],
    *,
    market: str = "",
) -> tuple[list[NewsItem], list[NewsItem]]:
    if market.upper() != "KR":
        return items, []

    direct: list[NewsItem] = []
    rejected: list[NewsItem] = []
    for item in items:
        if news_item_directly_mentions_company(symbol, company_name, item) and not is_low_signal_title(item.title):
            direct.append(item)
        else:
            rejected.append(item)
    return direct, rejected
