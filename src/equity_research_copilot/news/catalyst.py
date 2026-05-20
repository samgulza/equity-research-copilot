from __future__ import annotations

from dataclasses import asdict, dataclass, field

from equity_research_copilot.adapters.news_adapter import NewsItem
from equity_research_copilot.news.clustering import NewsCluster, cluster_news_items, novelty_score
from equity_research_copilot.news.counter_evidence import find_counter_evidence
from equity_research_copilot.news.event_extractor import EvidenceSpan, MetricMention, extract_structured_event, source_tier_score
from equity_research_copilot.schemas import validate_catalyst_event


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
    counter_evidence: list[EvidenceSpan] = field(default_factory=list)
    company_name: str = ""
    event_subtype: str = "unknown"
    entities: list[str] = field(default_factory=list)
    metrics: list[MetricMention] = field(default_factory=list)
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)
    source_quality_score: float = 0.0
    market_reaction_score: float = 0.0
    score: float = 0.0
    published_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def score_event(
    materiality: float,
    novelty: float,
    source_quality: float,
    market_reaction: float,
    priced_in_penalty: float,
) -> float:
    raw = 0.38 * materiality + 0.24 * novelty + 0.22 * source_quality + 0.16 * market_reaction
    return max(0.0, min(1.0, raw - priced_in_penalty))


def build_catalyst_events(
    ticker: str,
    items: list[NewsItem],
    recent_return: float = 0.0,
    *,
    company_name: str = "",
    market_reaction: dict | None = None,
) -> list[CatalystEvent]:
    market_reaction = market_reaction or {}
    clusters = cluster_news_items(items)
    events: list[CatalystEvent] = []
    reaction_score = float(market_reaction.get("reaction_score") or 0.0)
    priced_in_penalty = _priced_in_penalty(recent_return, reaction_score)
    priced_in = _priced_in_label(recent_return, reaction_score, priced_in_penalty)

    for cluster in clusters:
        primary = sorted(cluster.items, key=lambda x: x.published_at, reverse=True)[0]
        structured = extract_structured_event(ticker, company_name, primary)
        source_quality = _source_quality(cluster, structured.evidence_spans)
        novelty = novelty_score(cluster)
        score = score_event(
            structured.materiality_score,
            novelty,
            source_quality,
            reaction_score,
            priced_in_penalty,
        )
        evidence_sources = _evidence_sources(cluster, structured.evidence_spans)
        counter_evidence = find_counter_evidence(
            structured.direction,
            items,
            primary_url=primary.canonical_url or primary.url,
        )
        event = CatalystEvent(
            ticker=ticker.upper(),
            company_name=company_name,
            event_type=structured.event_type,
            event_subtype=structured.event_subtype,
            claim=primary.title,
            affected_driver=structured.affected_driver,
            direction=structured.direction,
            horizon=structured.horizon,
            entities=structured.entities,
            metrics=structured.metrics,
            evidence_spans=structured.evidence_spans,
            materiality_score=structured.materiality_score,
            novelty_score=novelty,
            source_quality_score=round(source_quality, 2),
            market_reaction_score=round(reaction_score, 2),
            priced_in_risk=priced_in,
            evidence_sources=evidence_sources,
            counter_evidence=counter_evidence,
            score=round(score, 2),
            published_at=primary.published_at,
        )
        validate_catalyst_event(event.to_dict())
        events.append(event)
    return sorted(events, key=lambda event: (event.score, event.materiality_score, event.source_quality_score), reverse=True)


def _source_quality(cluster: NewsCluster, evidence_spans: list[EvidenceSpan]) -> float:
    scores = [source_tier_score(span.source_tier) for span in evidence_spans if span.source_tier]
    if not scores:
        for item in cluster.items[:4]:
            probe = EvidenceSpan(source_tier="unknown")
            if item.source or item.url:
                from equity_research_copilot.news.event_extractor import detect_source_tier

                probe.source_tier = detect_source_tier(item)
            scores.append(source_tier_score(probe.source_tier))
    if not scores:
        return 0.55
    return max(0.0, min(1.0, sum(scores) / len(scores)))


def _evidence_sources(cluster: NewsCluster, evidence_spans: list[EvidenceSpan]) -> list[str]:
    sources: list[str] = []
    for span in evidence_spans:
        if span.url:
            sources.append(span.url)
    for item in cluster.items:
        url = item.canonical_url or item.url
        if url:
            sources.append(url)
    unique: list[str] = []
    seen: set[str] = set()
    for url in sources:
        if url in seen:
            continue
        seen.add(url)
        unique.append(url)
        if len(unique) >= 5:
            break
    return unique


def _priced_in_penalty(recent_return: float, reaction_score: float) -> float:
    move_penalty = min(0.22, max(0.0, abs(recent_return) - 0.04))
    reaction_penalty = min(0.12, max(0.0, reaction_score) * 0.16)
    return min(0.28, move_penalty + reaction_penalty)


def _priced_in_label(recent_return: float, reaction_score: float, penalty: float) -> str:
    if penalty >= 0.18 or abs(recent_return) >= 0.22 or reaction_score >= 0.75:
        return "high"
    if penalty >= 0.07 or abs(recent_return) >= 0.1 or reaction_score >= 0.35:
        return "medium"
    return "low"
