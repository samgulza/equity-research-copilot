from __future__ import annotations

from dataclasses import dataclass, field
import re

from equity_research_copilot.adapters.news_adapter import NewsItem


@dataclass
class MetricMention:
    name: str
    value: str
    unit: str = ""
    context: str = ""


@dataclass
class EvidenceSpan:
    url: str = ""
    title: str = ""
    source: str = ""
    published_at: str = ""
    quote: str = ""
    char_start: int | None = None
    char_end: int | None = None
    source_tier: str = "unknown"


@dataclass
class StructuredEvent:
    event_type: str
    event_subtype: str
    affected_driver: str
    direction: str
    horizon: str
    materiality_score: float
    entities: list[str] = field(default_factory=list)
    metrics: list[MetricMention] = field(default_factory=list)
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)


EVENT_RULES: list[tuple[str, str, str, str, str, list[str]]] = [
    (
        "guidance",
        "raise",
        "Revenue / margin / guidance",
        "positive",
        "20d",
        ["guidance raise", "raised guidance", "raises guidance", "guidance raised", "guidance was raised", "raises forecast", "가이던스 상향", "전망 상향"],
    ),
    (
        "guidance",
        "cut",
        "Revenue / margin / guidance",
        "negative",
        "20d",
        ["guidance cut", "cut guidance", "cuts guidance", "guidance lowered", "lowers forecast", "가이던스 하향", "전망 하향"],
    ),
    (
        "guidance",
        "reaffirm",
        "Revenue / margin / guidance",
        "mixed",
        "20d",
        ["reaffirm", "reiterated guidance", "유지", "재확인"],
    ),
    (
        "guidance",
        "unknown",
        "Revenue / margin / guidance",
        "mixed",
        "20d",
        ["guidance", "forecast", "outlook", "전망", "가이던스"],
    ),
    (
        "earnings",
        "margin_expansion",
        "Revenue / margin / earnings quality",
        "positive",
        "5d",
        ["margin expansion", "operating margin rose", "영업이익 증가", "수익성 개선", "마진 개선"],
    ),
    (
        "earnings",
        "margin_compression",
        "Revenue / margin / earnings quality",
        "negative",
        "5d",
        ["margin compression", "margin pressure", "영업이익 감소", "수익성 악화", "마진 압박"],
    ),
    (
        "earnings",
        "beat_miss",
        "Revenue / margin / earnings quality",
        "mixed",
        "5d",
        ["earnings", "revenue", "eps", "profit", "quarter", "실적", "매출", "영업이익", "순이익"],
    ),
    (
        "analyst_revision",
        "analyst_upgrade",
        "Market expectations",
        "positive",
        "5d",
        ["upgrade", "raises price target", "target raise", "목표가 상향", "투자의견 상향", "상향 조정"],
    ),
    (
        "analyst_revision",
        "analyst_downgrade",
        "Market expectations",
        "negative",
        "5d",
        ["downgrade", "cuts price target", "target cut", "목표가 하향", "투자의견 하향", "하향 조정"],
    ),
    (
        "supply_chain",
        "order_contract",
        "Demand / backlog / supply chain",
        "positive",
        "5d-20d",
        ["order", "contract", "backlog", "supply deal", "수주", "계약", "공급계약", "납품"],
    ),
    (
        "supply_chain",
        "capacity_expansion",
        "Capacity / capex / shipment",
        "mixed",
        "60d",
        ["capacity expansion", "new plant", "fab", "증설", "신공장", "생산능력", "캐파"],
    ),
    (
        "supply_chain",
        "inventory_correction",
        "Inventory / pricing / demand cycle",
        "negative",
        "20d",
        ["inventory correction", "destocking", "재고 조정", "재고 부담"],
    ),
    (
        "capital_allocation",
        "buyback",
        "Capital returns",
        "positive",
        "20d",
        ["buyback", "share repurchase", "자사주", "자사주 매입"],
    ),
    (
        "capital_allocation",
        "dividend",
        "Capital returns",
        "positive",
        "20d",
        ["dividend", "배당"],
    ),
    (
        "capital_allocation",
        "dilution",
        "Capital structure",
        "negative",
        "20d",
        ["secondary offering", "share sale", "dilution", "유상증자", "전환사채"],
    ),
    (
        "legal_regulatory",
        "investigation",
        "Legal / regulatory risk",
        "negative",
        "20d",
        ["probe", "investigation", "조사", "수사", "검찰", "공정위"],
    ),
    (
        "legal_regulatory",
        "litigation",
        "Legal / regulatory risk",
        "negative",
        "20d",
        ["lawsuit", "court", "litigation", "소송", "법원"],
    ),
    (
        "legal_regulatory",
        "approval",
        "Regulatory approval / market access",
        "positive",
        "20d",
        ["approval", "cleared", "승인", "허가", "인가"],
    ),
    (
        "legal_regulatory",
        "export_control",
        "Policy / market access",
        "mixed",
        "20d",
        ["export control", "tariff", "ban", "관세", "수출통제", "제재", "금수"],
    ),
    (
        "ai_infrastructure",
        "segment_growth",
        "AI infrastructure demand",
        "positive",
        "5d-20d",
        ["ai", "gpu", "accelerator", "data center", "hbm", "반도체", "데이터센터", "인공지능"],
    ),
    (
        "product",
        "shipment",
        "Product cycle / launch / shipment",
        "mixed",
        "20d",
        ["launch", "new product", "shipment", "출시", "신제품", "출하"],
    ),
    (
        "mna",
        "mna",
        "Corporate action / portfolio change",
        "mixed",
        "60d",
        ["acquisition", "merger", "m&a", "takeover", "인수", "합병"],
    ),
    (
        "management",
        "management_change",
        "Management / governance",
        "mixed",
        "60d",
        ["ceo", "cfo", "management change", "resigns", "대표", "임원", "사임", "선임"],
    ),
    (
        "macro",
        "unknown",
        "Macro / rates / currency",
        "mixed",
        "20d",
        ["fed", "rate", "inflation", "dollar", "환율", "금리", "물가", "연준"],
    ),
]

POSITIVE_TERMS = [
    "beat",
    "raise",
    "upgrade",
    "growth",
    "profit",
    "approval",
    "contract",
    "order",
    "상향",
    "증가",
    "성장",
    "흑자",
    "수주",
    "승인",
    "개선",
]
NEGATIVE_TERMS = [
    "miss",
    "cut",
    "downgrade",
    "decline",
    "loss",
    "probe",
    "lawsuit",
    "recall",
    "하향",
    "감소",
    "적자",
    "부진",
    "조사",
    "소송",
    "리콜",
]


def extract_structured_event(ticker: str, company_name: str, item: NewsItem) -> StructuredEvent:
    text = _combined_text(item)
    lowered = text.casefold()
    if item.kind == "filing" or any(term in lowered for term in ["10-k", "10-q", "8-k", "sec filing"]):
        base = ("filing", "unknown", "Disclosure / governance", "mixed", "20d", 0.68)
    else:
        base = _match_event(lowered)

    event_type, event_subtype, driver, direction, horizon, base_materiality = base
    metrics = extract_metrics(text)
    evidence = build_evidence_span(item, EVENT_TERMS.get(event_type, []) + POSITIVE_TERMS + NEGATIVE_TERMS)
    source_tier = evidence.source_tier if evidence else detect_source_tier(item)
    materiality = base_materiality
    if metrics:
        materiality += 0.08
    if item.body:
        materiality += 0.04
    if source_tier == "tier1":
        materiality += 0.05
    elif source_tier == "tier2":
        materiality += 0.03
    direction = _direction_from_text(lowered, direction)
    return StructuredEvent(
        event_type=event_type,
        event_subtype=event_subtype,
        affected_driver=driver,
        direction=direction,
        horizon=horizon,
        materiality_score=round(_clamp(materiality), 2),
        entities=extract_entities(ticker, company_name, text),
        metrics=metrics,
        evidence_spans=[evidence] if evidence else [],
    )


def build_evidence_span(item: NewsItem, preferred_terms: list[str] | None = None) -> EvidenceSpan | None:
    source_text = item.body or item.summary or item.title
    if not source_text.strip():
        return None
    terms = [term.casefold() for term in preferred_terms or [] if term]
    sentences = _sentences(source_text)
    best = sentences[0] if sentences else source_text.strip()
    best_score = -1
    for sentence in sentences[:60]:
        sentence_l = sentence.casefold()
        score = sum(2 for term in terms if term in sentence_l)
        if _contains_metric(sentence):
            score += 2
        if len(sentence) < 40:
            score -= 1
        if score > best_score:
            best = sentence
            best_score = score
    quote = re.sub(r"\s+", " ", best).strip()
    if len(quote) > 360:
        quote = quote[:357].rstrip() + "..."
    start = source_text.find(best)
    end = start + len(best) if start >= 0 else None
    return EvidenceSpan(
        url=item.canonical_url or item.url,
        title=item.title,
        source=item.source or item.site_name,
        published_at=item.published_at,
        quote=quote,
        char_start=start if start >= 0 else None,
        char_end=end,
        source_tier=detect_source_tier(item),
    )


def detect_source_tier(item: NewsItem) -> str:
    text = " ".join([item.source, item.site_name, item.url]).casefold()
    if any(term in text for term in ["sec.gov", "sec edgar", "dart.fss", "kind.krx", "krx", "investor", "ir.", "newsroom"]):
        return "tier1"
    if any(term in text for term in ["reuters", "apnews", "ap news", "bloomberg", "wsj", "financial times", "marketwatch"]):
        return "tier2"
    if any(term in text for term in ["naver", "yahoo", "zacks", "simplywall", "investing.com", "seekingalpha"]):
        return "tier3"
    if any(term in text for term in ["blog", "twitter", "x.com", "reddit", "stocktwits"]):
        return "tier4"
    return "unknown"


def source_tier_score(tier: str) -> float:
    return {"tier1": 0.95, "tier2": 0.85, "tier3": 0.68, "tier4": 0.35}.get(tier, 0.55)


EVENT_TERMS: dict[str, list[str]] = {}
for event_type, _subtype, _driver, _direction, _horizon, terms in EVENT_RULES:
    EVENT_TERMS.setdefault(event_type, []).extend(terms)


def extract_metrics(text: str) -> list[MetricMention]:
    rows: list[MetricMention] = []
    seen: set[tuple[str, str]] = set()
    pattern = re.compile(
        r"(?P<context>.{0,36})(?P<value>(?:[$₩€£]?\s?\d+(?:[,.]\d+)*(?:\.\d+)?\s?(?:%|bps?|bp|x|배|million|billion|trillion|mn|bn|억원|조원|원|달러|대|건)))(?P<tail>.{0,36})",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        context = re.sub(r"\s+", " ", f"{match.group('context')}{match.group('value')}{match.group('tail')}").strip()
        value = match.group("value").strip()
        name = _metric_name(context)
        key = (name, value)
        if key in seen:
            continue
        seen.add(key)
        rows.append(MetricMention(name=name, value=value, unit=_metric_unit(value), context=context))
        if len(rows) >= 5:
            break
    return rows


def extract_entities(ticker: str, company_name: str, text: str) -> list[str]:
    entities = [ticker.upper()]
    if company_name:
        entities.append(company_name)
    for match in re.finditer(r"\b[A-Z][A-Za-z&.-]{2,}(?:\s+[A-Z][A-Za-z&.-]{2,}){0,2}\b", text):
        value = match.group(0).strip()
        if value.upper() in {"SEC", "CEO", "CFO", "EPS", "AI", "GPU"}:
            continue
        entities.append(value)
    for match in re.finditer(r"[가-힣A-Za-z0-9]+(?:전자|산업|증권|금융|바이오|제약|자동차|모비스|은행|보험|화학|중공업|에너지)", text):
        entities.append(match.group(0))
    unique: list[str] = []
    seen: set[str] = set()
    for entity in entities:
        key = re.sub(r"\s+", "", entity).casefold()
        if len(key) < 2 or key in seen:
            continue
        seen.add(key)
        unique.append(entity)
        if len(unique) >= 8:
            break
    return unique


def _match_event(lowered: str) -> tuple[str, str, str, str, str, float]:
    for event_type, subtype, driver, direction, horizon, terms in EVENT_RULES:
        if any(term.casefold() in lowered for term in terms):
            return event_type, subtype, driver, direction, horizon, _base_materiality(event_type)
    return "general_news", "unknown", "Narrative / sentiment", "mixed", "unknown", 0.43


def _direction_from_text(lowered: str, fallback: str) -> str:
    pos = sum(1 for term in POSITIVE_TERMS if term in lowered)
    neg = sum(1 for term in NEGATIVE_TERMS if term in lowered)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return fallback


def _base_materiality(event_type: str) -> float:
    return {
        "earnings": 0.86,
        "guidance": 0.9,
        "legal_regulatory": 0.78,
        "ai_infrastructure": 0.76,
        "supply_chain": 0.74,
        "capital_allocation": 0.68,
        "mna": 0.74,
        "management": 0.58,
        "analyst_revision": 0.6,
        "macro": 0.5,
        "product": 0.58,
    }.get(event_type, 0.43)


def _combined_text(item: NewsItem) -> str:
    return re.sub(r"\s+", " ", f"{item.title}\n{item.summary}\n{item.body[:8000]}").strip()


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def _contains_metric(text: str) -> bool:
    return bool(re.search(r"\d+(?:[,.]\d+)*(?:\.\d+)?\s?(?:%|bps?|x|배|million|billion|trillion|억원|조원|원|달러)", text, re.I))


def _metric_name(context: str) -> str:
    lowered = context.casefold()
    if any(term in lowered for term in ["revenue", "sales", "매출"]):
        return "revenue"
    if any(term in lowered for term in ["margin", "영업이익률", "마진"]):
        return "margin"
    if any(term in lowered for term in ["eps", "earnings per share"]):
        return "eps"
    if any(term in lowered for term in ["capex", "투자", "설비"]):
        return "capex"
    if any(term in lowered for term in ["order", "contract", "수주", "계약"]):
        return "order_size"
    if any(term in lowered for term in ["fine", "penalty", "벌금", "과징금"]):
        return "penalty"
    return "metric"


def _metric_unit(value: str) -> str:
    match = re.search(r"(%|bps?|bp|x|배|million|billion|trillion|mn|bn|억원|조원|원|달러|대|건)", value, re.I)
    return match.group(1) if match else ""


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
