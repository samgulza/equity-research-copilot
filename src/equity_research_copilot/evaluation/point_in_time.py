from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from equity_research_copilot.adapters.openbb_adapter import OpenBBAdapter
from equity_research_copilot.technical.indicators import add_indicators
from equity_research_copilot.technical.structure import analyze_structure


@dataclass
class PredictionRecord:
    ticker: str
    as_of: str
    horizon: str
    probability_up: float
    verdict: str
    evidence_hash: str


class PointInTimeEvaluator:
    def run(self, records: list[PredictionRecord]) -> dict:
        if not records:
            return {"records": 0, "message": "No prediction records supplied."}
        return {"records": len(records), "message": "Use evaluate_symbol_history for OHLCV-based evaluation."}


def _probability_from_structure(market_structure: str, momentum_state: str, volume_state: str) -> float:
    prob = 0.5
    if market_structure.startswith("uptrend"):
        prob += 0.12
    elif market_structure.startswith("downtrend"):
        prob -= 0.12
    if "positive" in momentum_state:
        prob += 0.06
    elif "cooling" in momentum_state:
        prob -= 0.03
    if "high" in volume_state:
        prob += 0.02
    return max(0.05, min(0.95, prob))


def evaluate_symbol_history(
    symbol: str,
    *,
    start: str,
    end: str | None = None,
    horizon_days: int = 20,
    step_days: int = 5,
    lookback_days: int = 120,
    provider: str = "yfinance",
) -> tuple[pd.DataFrame, dict]:
    adapter = OpenBBAdapter(provider=provider)
    df = adapter.get_price_history(symbol, start=start, end=end)
    df = add_indicators(df)
    df["date"] = pd.to_datetime(df["date"])
    rows = []
    for idx in range(lookback_days, len(df) - horizon_days, step_days):
        window = df.iloc[max(0, idx - lookback_days): idx + 1].copy()
        if len(window) < 60:
            continue
        summary = analyze_structure(window)
        prob = _probability_from_structure(summary.market_structure, summary.momentum_state, summary.volume_state)
        close = float(df.iloc[idx]["close"])
        future_close = float(df.iloc[idx + horizon_days]["close"])
        future_return = future_close / close - 1
        rows.append(
            {
                "ticker": symbol.upper(),
                "as_of": df.iloc[idx]["date"].date().isoformat(),
                "horizon_days": horizon_days,
                "close": close,
                "future_close": future_close,
                "future_return": future_return,
                "probability_up": prob,
                "predicted_up": int(prob >= 0.5),
                "actual_up": int(future_return > 0),
                "market_structure": summary.market_structure,
                "momentum_state": summary.momentum_state,
                "volume_state": summary.volume_state,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out, {"records": 0, "message": "Not enough rows for evaluation."}
    accuracy = float((out["predicted_up"] == out["actual_up"]).mean())
    brier = float(((out["probability_up"] - out["actual_up"]) ** 2).mean())
    avg_return_when_up = float(out.loc[out["predicted_up"] == 1, "future_return"].mean())
    summary = {
        "ticker": symbol.upper(),
        "records": int(len(out)),
        "horizon_days": horizon_days,
        "step_days": step_days,
        "directional_accuracy": accuracy,
        "brier_score": brier,
        "avg_return_when_predicted_up": avg_return_when_up,
        "provider": provider,
    }
    return out, summary
