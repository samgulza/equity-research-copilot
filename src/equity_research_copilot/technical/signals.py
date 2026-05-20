from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

import pandas as pd

from equity_research_copilot.technical.structure import TechnicalSummary


@dataclass
class TradingSetup:
    setup_type: str
    action: str
    score: float
    confidence: float
    entry_low: float | None
    entry_high: float | None
    stop_loss: float | None
    target_1: float | None
    target_2: float | None
    risk_reward: float | None
    thesis: str
    invalidation: str
    signals: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None and math.isfinite(value) else None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def build_trading_setup(df: pd.DataFrame, technical: TechnicalSummary) -> TradingSetup:
    if df.empty or len(df) < 30:
        return TradingSetup(
            setup_type="insufficient_data",
            action="wait",
            score=0.0,
            confidence=0.2,
            entry_low=None,
            entry_high=None,
            stop_loss=None,
            target_1=None,
            target_2=None,
            risk_reward=None,
            thesis="가격 시계열이 부족해 셋업 판정 보류",
            invalidation="데이터 보강 필요",
            signals=[],
            warnings=["insufficient price history"],
        )

    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = _num(last.get("close")) or 0.0
    sma20 = _num(last.get("sma20")) or close
    sma50 = _num(last.get("sma50")) or sma20
    sma100 = _num(last.get("sma100")) or sma50
    rsi14 = _num(last.get("rsi14")) or 50.0
    macd = _num(last.get("macd")) or 0.0
    macd_signal = _num(last.get("macd_signal")) or 0.0
    macd_hist = _num(last.get("macd_hist")) or 0.0
    prev_macd_hist = _num(prev.get("macd_hist")) or macd_hist
    atr14 = _num(last.get("atr14"))
    if not atr14 or atr14 <= 0:
        atr14 = max(close * 0.025, 0.01)
    volume = _num(last.get("volume")) or 0.0
    volume_20d = _num(last.get("volume_20d")) or volume or 1.0
    volume_ratio = volume / volume_20d if volume_20d else 1.0

    recent = df.tail(60)
    prior_high_20 = _num(df["high"].shift(1).rolling(20).max().iloc[-1])
    prior_low_20 = _num(df["low"].shift(1).rolling(20).min().iloc[-1])
    high_60 = _num(recent["high"].max()) or close
    low_60 = _num(recent["low"].min()) or close
    range_width = max(high_60 - low_60, atr14)
    range_position = _clamp((close - low_60) / range_width)

    trend_full = close > sma20 > sma50 > sma100
    trend_partial = close > sma20 > sma50
    below_trend = close < sma20 < sma50
    breakout = bool(prior_high_20 and close > prior_high_20 and volume_ratio >= 1.15)
    breakdown = bool(prior_low_20 and close < prior_low_20)
    pullback = close >= sma50 and abs(close - sma20) <= atr14 * 1.1 and not breakout
    macd_rising = macd > macd_signal and macd_hist >= prev_macd_hist
    volume_confirmed = volume_ratio >= 1.25
    extended = (close - sma20) / atr14 >= 2.2 or rsi14 >= 74

    score = 0.25
    signals: list[str] = []
    warnings: list[str] = []

    if trend_full:
        score += 0.24
        signals.append("20/50/100일선 정배열")
    elif trend_partial:
        score += 0.18
        signals.append("20/50일선 우상향")
    elif below_trend:
        score -= 0.15
        warnings.append("단기 추세 하방 배열")

    if breakout:
        score += 0.18
        signals.append("20일 고점 돌파와 거래량 동반")
    if pullback:
        score += 0.14
        signals.append("20일선 근처 건설적 눌림")
    if macd_rising:
        score += 0.1
        signals.append("MACD 히스토그램 개선")
    if volume_confirmed:
        score += 0.1
        signals.append(f"거래량 {volume_ratio:.1f}배 참여")
    if 45 <= rsi14 <= 68:
        score += 0.08
        signals.append("RSI가 과열 전 구간")
    elif rsi14 > 74:
        score -= 0.12
        warnings.append("RSI 과열")
    elif rsi14 < 35:
        score -= 0.06
        warnings.append("RSI 약세")

    if range_position >= 0.9 and not breakout:
        score -= 0.08
        warnings.append("60일 박스 상단 근접")
    if extended:
        score -= 0.14
        warnings.append("단기 이격 과대")
    if breakdown:
        score -= 0.22
        warnings.append("20일 저점 이탈")

    score = round(_clamp(score), 3)

    stop_candidates = [close - atr14 * 1.35]
    if technical.support_levels:
        stop_candidates.append(float(min(technical.support_levels)) * 0.985)
    if prior_low_20:
        stop_candidates.append(prior_low_20 * 0.985)
    stop_loss = min(stop_candidates) if stop_candidates else close - atr14 * 1.5
    if stop_loss >= close:
        stop_loss = close - atr14 * 1.5
    risk = max(close - stop_loss, atr14 * 0.5)

    if breakout and prior_high_20:
        setup_type = "volume_breakout"
        action = "breakout_watch" if not extended else "avoid_chase"
        entry_low = max(prior_high_20, close - atr14 * 0.35)
        entry_high = close + atr14 * 0.25
        thesis = "거래량이 붙은 고점 돌파형 셋업"
    elif pullback and score >= 0.5:
        setup_type = "trend_pullback"
        action = "pullback_watch"
        entry_low = max(stop_loss + risk * 0.35, sma20 - atr14 * 0.45)
        entry_high = min(close + atr14 * 0.25, sma20 + atr14 * 0.85)
        thesis = "상승 추세 안의 눌림목 셋업"
    elif breakdown or below_trend:
        setup_type = "risk_distribution"
        action = "risk_watch"
        entry_low = None
        entry_high = None
        thesis = "추세 훼손 또는 분산 위험 구간"
    elif extended:
        setup_type = "extended_move"
        action = "avoid_chase"
        entry_low = None
        entry_high = None
        thesis = "이미 단기 이격이 커 추격보다 재평가가 필요한 구간"
    elif score >= 0.55:
        setup_type = "base_building"
        action = "long_watch"
        entry_low = close - atr14 * 0.5
        entry_high = close + atr14 * 0.25
        thesis = "추세와 모멘텀이 동시에 유지되는 감시 셋업"
    else:
        setup_type = "no_trade_zone"
        action = "wait"
        entry_low = None
        entry_high = None
        thesis = "아직 진입 근거보다 확인해야 할 조건이 많음"

    target_1 = close + risk * 2.0
    target_2 = close + risk * 3.0
    if technical.resistance_levels:
        target_1 = max(target_1, float(min(technical.resistance_levels)))
        target_2 = max(target_2, float(max(technical.resistance_levels)))
    risk_reward = (target_1 - close) / risk if risk > 0 else None
    confidence = round(_clamp(0.35 + score * 0.5 + min(len(signals), 4) * 0.04 - len(warnings) * 0.04), 3)
    invalidation = f"{_round(stop_loss)} 이탈 시 셋업 무효" if stop_loss else "명확한 무효화 가격 없음"

    return TradingSetup(
        setup_type=setup_type,
        action=action,
        score=score,
        confidence=confidence,
        entry_low=_round(entry_low),
        entry_high=_round(entry_high),
        stop_loss=_round(stop_loss),
        target_1=_round(target_1),
        target_2=_round(target_2),
        risk_reward=round(risk_reward, 2) if risk_reward is not None and math.isfinite(risk_reward) else None,
        thesis=thesis,
        invalidation=invalidation,
        signals=signals[:5],
        warnings=warnings[:5],
    )
