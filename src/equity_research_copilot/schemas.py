from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


EventType = Literal[
    "earnings",
    "guidance",
    "analyst_revision",
    "product",
    "ai_infrastructure",
    "policy_geopolitics",
    "legal_regulatory",
    "filing",
    "supply_chain",
    "mna",
    "management",
    "capital_allocation",
    "macro",
    "general_news",
    "other",
]

EventSubtype = Literal[
    "beat_miss",
    "margin_expansion",
    "margin_compression",
    "segment_growth",
    "one_off_gain_loss",
    "raise",
    "cut",
    "withdraw",
    "reaffirm",
    "order_contract",
    "backlog",
    "shipment",
    "capacity_expansion",
    "inventory_correction",
    "buyback",
    "dividend",
    "dilution",
    "debt_refinancing",
    "capex",
    "approval",
    "investigation",
    "litigation",
    "fine_penalty",
    "export_control",
    "antitrust",
    "mna",
    "spin_off",
    "restructuring",
    "management_change",
    "analyst_upgrade",
    "analyst_downgrade",
    "target_raise",
    "consensus_revision",
    "unknown",
]

Direction = Literal["positive", "negative", "mixed", "neutral"]
Horizon = Literal["1d", "5d", "20d", "60d", "1y", "5d-20d", "unknown"]
PricedInRisk = Literal["low", "medium", "high", "unknown"]
SourceTier = Literal["tier1", "tier2", "tier3", "tier4", "unknown"]


class MetricMentionModel(BaseModel):
    name: str
    value: str
    unit: str = ""
    context: str = ""


class EvidenceSpanModel(BaseModel):
    url: str = ""
    title: str = ""
    source: str = ""
    published_at: str = ""
    quote: str = ""
    char_start: int | None = None
    char_end: int | None = None
    source_tier: SourceTier = "unknown"


class MarketReactionModel(BaseModel):
    return_1d: float | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    abnormal_return_1d: float | None = None
    abnormal_return_5d: float | None = None
    abnormal_return_20d: float | None = None
    volume_zscore: float | None = None
    volume_ratio: float | None = None
    gap_return: float | None = None
    reaction_score: float = Field(default=0.0, ge=0.0, le=1.0)


class CatalystEventModel(BaseModel):
    ticker: str
    company_name: str = ""
    event_type: EventType
    event_subtype: EventSubtype = "unknown"
    claim: str
    affected_driver: str
    direction: Direction
    horizon: Horizon
    entities: list[str] = Field(default_factory=list)
    metrics: list[MetricMentionModel] = Field(default_factory=list)
    evidence_spans: list[EvidenceSpanModel] = Field(default_factory=list)
    counter_evidence: list[EvidenceSpanModel] = Field(default_factory=list)
    materiality_score: float = Field(ge=0.0, le=1.0)
    novelty_score: float = Field(ge=0.0, le=1.0)
    source_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    market_reaction_score: float = Field(default=0.0, ge=0.0, le=1.0)
    priced_in_risk: PricedInRisk
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    published_at: str = ""
    evidence_sources: list[str] = Field(default_factory=list)


def validate_catalyst_event(payload: dict) -> CatalystEventModel:
    return CatalystEventModel.model_validate(payload)
