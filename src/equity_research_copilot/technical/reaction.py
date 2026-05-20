from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass
class MarketReaction:
    return_1d: float | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    abnormal_return_1d: float | None = None
    abnormal_return_5d: float | None = None
    abnormal_return_20d: float | None = None
    volume_zscore: float | None = None
    volume_ratio: float | None = None
    gap_return: float | None = None
    reaction_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def analyze_market_reaction(df: pd.DataFrame, benchmark_df: pd.DataFrame | None = None) -> MarketReaction:
    if df.empty or "close" not in df:
        return MarketReaction()
    ordered = df.sort_values("date") if "date" in df else df.copy()
    benchmark = benchmark_df.sort_values("date") if benchmark_df is not None and "date" in benchmark_df else benchmark_df
    returns = {period: _return_over(ordered, period) for period in (1, 5, 20)}
    benchmark_returns = {period: _return_over(benchmark, period) if benchmark is not None else 0.0 for period in (1, 5, 20)}
    abnormal = {
        period: returns[period] - benchmark_returns[period] if returns[period] is not None and benchmark_returns[period] is not None else returns[period]
        for period in (1, 5, 20)
    }
    volume_zscore, volume_ratio = _volume_reaction(ordered)
    gap_return = _gap_return(ordered)
    score = _reaction_score(abnormal, volume_zscore, volume_ratio, gap_return)
    return MarketReaction(
        return_1d=_round(returns[1]),
        return_5d=_round(returns[5]),
        return_20d=_round(returns[20]),
        abnormal_return_1d=_round(abnormal[1]),
        abnormal_return_5d=_round(abnormal[5]),
        abnormal_return_20d=_round(abnormal[20]),
        volume_zscore=_round(volume_zscore),
        volume_ratio=_round(volume_ratio),
        gap_return=_round(gap_return),
        reaction_score=round(score, 3),
    )


def _return_over(df: pd.DataFrame | None, period: int) -> float | None:
    if df is None or len(df) <= period or "close" not in df:
        return None
    current = float(df["close"].iloc[-1])
    base = float(df["close"].iloc[-1 - period])
    if not base:
        return None
    return current / base - 1


def _volume_reaction(df: pd.DataFrame) -> tuple[float | None, float | None]:
    if "volume" not in df or len(df) < 6:
        return None, None
    last_volume = float(df["volume"].iloc[-1])
    lookback = df["volume"].tail(min(len(df), 21)).iloc[:-1].astype(float)
    if lookback.empty:
        return None, None
    mean = float(lookback.mean())
    std = float(lookback.std(ddof=0))
    ratio = last_volume / mean if mean else None
    zscore = (last_volume - mean) / std if std else None
    return zscore, ratio


def _gap_return(df: pd.DataFrame) -> float | None:
    if len(df) < 2 or "open" not in df or "close" not in df:
        return None
    previous_close = float(df["close"].iloc[-2])
    current_open = float(df["open"].iloc[-1])
    if not previous_close:
        return None
    return current_open / previous_close - 1


def _reaction_score(abnormal: dict[int, float | None], volume_zscore: float | None, volume_ratio: float | None, gap_return: float | None) -> float:
    score = 0.0
    if abnormal.get(1) is not None:
        score += min(0.25, abs(abnormal[1]) * 3.0)
    if abnormal.get(5) is not None:
        score += min(0.25, abs(abnormal[5]) * 1.8)
    if abnormal.get(20) is not None:
        score += min(0.18, abs(abnormal[20]) * 0.9)
    if volume_zscore is not None and volume_zscore > 0:
        score += min(0.18, volume_zscore / 8.0)
    if volume_ratio is not None and volume_ratio > 1:
        score += min(0.1, (volume_ratio - 1.0) * 0.08)
    if gap_return is not None:
        score += min(0.08, abs(gap_return) * 2.0)
    return max(0.0, min(1.0, score))


def _round(value: float | None) -> float | None:
    return round(value, 5) if value is not None else None
