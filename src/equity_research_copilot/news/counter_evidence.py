from __future__ import annotations

from equity_research_copilot.adapters.news_adapter import NewsItem
from equity_research_copilot.news.event_extractor import EvidenceSpan, NEGATIVE_TERMS, POSITIVE_TERMS, build_evidence_span


def find_counter_evidence(
    direction: str,
    items: list[NewsItem],
    *,
    primary_url: str = "",
    limit: int = 2,
) -> list[EvidenceSpan]:
    if direction == "positive":
        terms = NEGATIVE_TERMS
    elif direction == "negative":
        terms = POSITIVE_TERMS
    else:
        terms = NEGATIVE_TERMS + POSITIVE_TERMS

    rows: list[EvidenceSpan] = []
    seen: set[str] = set()
    for item in items:
        url = item.canonical_url or item.url
        if primary_url and url == primary_url:
            continue
        text = f"{item.title} {item.summary} {item.body[:3000]}".casefold()
        if not any(term.casefold() in text for term in terms):
            continue
        evidence = build_evidence_span(item, terms)
        if not evidence or not evidence.quote:
            continue
        key = evidence.url or evidence.title
        if key in seen:
            continue
        seen.add(key)
        rows.append(evidence)
        if len(rows) >= limit:
            break
    return rows
