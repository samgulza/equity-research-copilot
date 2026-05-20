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

GENERIC_COMPANY_TERMS = {
    "class",
    "co",
    "company",
    "corp",
    "corporation",
    "digital",
    "group",
    "holding",
    "holdings",
    "inc",
    "incorporated",
    "ltd",
    "plc",
    "systems",
    "technologies",
}


def compact_text(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.casefold())


def company_match_terms(symbol: str, company_name: str | None = None) -> list[str]:
    terms: list[str] = []
    code = symbol.split(".")[0].strip()
    if code and (code.isdigit() or len(code) >= 3):
        terms.append(code)

    name = (company_name or "").strip()
    if name:
        cleaned = re.sub(r"\s+", "", name)
        cleaned = re.sub(r"\(.*?\)", "", cleaned)
        cleaned = re.sub(
            r"(보통주|우선주|홀딩스|지주|주식회사|corporation|incorporated|holdings|holding|company|corp|inc|ltd|plc)$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        terms.extend([name, cleaned])
        if cleaned.upper().startswith("HD") and len(cleaned) > 4:
            terms.append(cleaned[2:])
        words = [token.strip() for token in re.split(r"[\s/&.,()+-]+", name) if token.strip()]
        if len(words) >= 2:
            first = compact_text(words[0])
            if first not in GENERIC_COMPANY_TERMS:
                terms.append("".join(words[:2]))
        has_korean = bool(re.search(r"[가-힣]", cleaned))
        for token in re.split(r"[\s/&.,()+-]+", name):
            token = token.strip()
            compacted = compact_text(token)
            if (has_korean or len(words) == 1) and len(compacted) >= 4 and compacted not in GENERIC_COMPANY_TERMS:
                terms.append(token)
        if has_korean and len(cleaned) >= 4:
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
    text = f"{item.title} {item.summary} {item.body[:5000]}"
    return text_directly_mentions_company(symbol, company_name, text)


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
    if market.upper() != "KR" and not company_name:
        return items, []

    direct: list[NewsItem] = []
    rejected: list[NewsItem] = []
    for item in items:
        if news_item_directly_mentions_company(symbol, company_name, item) and not is_low_signal_title(item.title):
            direct.append(item)
        else:
            rejected.append(item)
    return direct, rejected
