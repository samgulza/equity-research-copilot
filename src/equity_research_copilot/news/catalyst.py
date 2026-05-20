from __future__ import annotations

from dataclasses import dataclass
import re

from equity_research_copilot.adapters.news_adapter import NewsItem


@dataclass
class CatalystEvent:
    ticker: str
    event_type: str
    claim: str
    affected_driver: str
    direction: str
    horizon: str
    materiality_score: float
    novelty_score: float
    priced_in_risk: str
    evidence_sources: list[str]
    counter_evidence: list[str]
    score: float = 0.0
    published_at: str = ""


def score_event(materiality: float, novelty: float, source_quality: float, priced_in_penalty: float) -> float:
    raw = 0.45 * materiality + 0.3 * novelty + 0.25 * source_quality
    return max(0.0, min(1.0, raw - priced_in_penalty))


def _norm(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9가-힣 ]+", " ", text.lower())
    tokens = [tok for tok in cleaned.split() if len(tok) > 2]
    return " ".join(tokens[:12])


def _event_type(text: str, kind: str) -> tuple[str, str, str, float]:
    lowered = text.lower()
    if kind == "filing" or "sec " in lowered or "10-k" in lowered or "10-q" in lowered or "8-k" in lowered:
        return "filing", "Disclosure / governance", "mixed", 0.68
    if any(term in lowered for term in ["earnings", "guidance", "revenue", "eps", "margin", "quarter", "실적", "매출", "영업이익", "순이익", "가이던스"]):
        return "earnings", "Revenue / margin / guidance", "mixed", 0.9
    if any(term in lowered for term in ["ai", "chip", "gpu", "data center", "cloud", "semiconductor", "반도체", "hbm", "데이터센터", "인공지능"]):
        return "ai_infrastructure", "AI infrastructure demand", "positive", 0.78
    if any(term in lowered for term in ["china", "export", "tariff", "ban", "approval", "regulation", "중국", "수출", "관세", "규제", "승인"]):
        return "policy_geopolitics", "Policy / market access", "mixed", 0.82
    if any(term in lowered for term in ["lawsuit", "court", "probe", "investigation", "sec", "소송", "검찰", "조사", "제재", "리콜"]):
        return "legal_regulatory", "Legal / regulatory risk", "negative", 0.7
    if any(term in lowered for term in ["downgrade", "upgrade", "price target", "analyst", "목표가", "투자의견", "상향", "하향", "증권"]):
        return "analyst_revision", "Market expectations", "mixed", 0.55
    return "general_news", "Narrative / sentiment", "mixed", 0.45


def build_catalyst_events(ticker: str, items: list[NewsItem], recent_return: float = 0.0) -> list[CatalystEvent]:
    clusters: dict[str, list[NewsItem]] = {}
    for item in items:
        key = _norm(item.title)
        if not key:
            continue
        clusters.setdefault(key, []).append(item)

    events: list[CatalystEvent] = []
    priced_in_penalty = min(0.22, max(0.0, abs(recent_return) - 0.04))
    for cluster_items in clusters.values():
        primary = sorted(cluster_items, key=lambda x: x.published_at, reverse=True)[0]
        text = f"{primary.title} {primary.summary}"
        event_type, driver, direction, materiality = _event_type(text, primary.kind)
        novelty = max(0.25, 1.0 / len(cluster_items))
        source_quality = 0.85 if primary.source in {"SEC EDGAR", "Reuters", "NVIDIA Newsroom"} else 0.72 if primary.source.startswith("Naver") else 0.62
        score = score_event(materiality, novelty, source_quality, priced_in_penalty)
        priced_in = "high" if priced_in_penalty >= 0.15 else "medium" if priced_in_penalty >= 0.05 else "low"
        events.append(
            CatalystEvent(
                ticker=ticker.upper(),
                event_type=event_type,
                claim=primary.title,
                affected_driver=driver,
                direction=direction,
                horizon="5d-20d",
                materiality_score=round(materiality, 2),
                novelty_score=round(novelty, 2),
                priced_in_risk=priced_in,
                evidence_sources=[item.url for item in cluster_items if item.url][:4],
                counter_evidence=[],
                score=round(score, 2),
                published_at=primary.published_at,
            )
        )
    return sorted(events, key=lambda event: (event.score, event.materiality_score), reverse=True)
