from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class TechnicalSummary:
    market_structure: str
    support_levels: list[float]
    resistance_levels: list[float]
    momentum_state: str
    volume_state: str
    invalidation_levels: list[float]
    confidence: float


def analyze_structure(df: pd.DataFrame) -> TechnicalSummary:
    recent = df.tail(60)
    close = float(df["close"].iloc[-1])
    high_60 = float(recent["high"].max())
    low_60 = float(recent["low"].min())
    sma20 = float(df["sma20"].iloc[-1]) if pd.notna(df["sma20"].iloc[-1]) else close
    sma50 = float(df["sma50"].iloc[-1]) if pd.notna(df["sma50"].iloc[-1]) else close
    rsi14 = float(df["rsi14"].iloc[-1]) if pd.notna(df["rsi14"].iloc[-1]) else 50.0
    vol_ratio = float(df["volume"].iloc[-1] / df["volume_20d"].iloc[-1]) if pd.notna(df["volume_20d"].iloc[-1]) else 1.0

    if close > sma20 > sma50:
        structure = "uptrend / constructive pullback"
    elif close < sma20 < sma50:
        structure = "downtrend / distribution risk"
    else:
        structure = "range / transition"

    if rsi14 >= 70:
        momentum = "overbought momentum"
    elif rsi14 <= 30:
        momentum = "oversold momentum"
    elif rsi14 >= 55:
        momentum = "positive but not extreme"
    else:
        momentum = "neutral/cooling momentum"

    volume_state = "high participation" if vol_ratio >= 1.5 else "normal participation"
    support = sorted([round(float(recent["low"].quantile(0.2)), 2), round(sma50, 2)])
    resistance = sorted([round(float(recent["high"].quantile(0.8)), 2), round(high_60, 2)])
    invalidation = [round(min(support), 2)]

    return TechnicalSummary(
        market_structure=structure,
        support_levels=support,
        resistance_levels=resistance,
        momentum_state=momentum,
        volume_state=volume_state,
        invalidation_levels=invalidation,
        confidence=0.62,
    )
