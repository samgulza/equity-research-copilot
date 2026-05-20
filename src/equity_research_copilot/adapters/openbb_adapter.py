from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


class OpenBBUnavailable(RuntimeError):
    pass


@dataclass
class OpenBBAdapter:
    provider: str = "yfinance"

    def _obb(self) -> Any:
        try:
            from openbb import obb  # type: ignore
            return obb
        except Exception as exc:  # pragma: no cover
            raise OpenBBUnavailable(
                "OpenBB is not installed or failed to import. Install with: "
                "pip install openbb openbb-charting openbb-mcp-server"
            ) from exc

    def get_price_history(self, symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        """Return normalized OHLCV dataframe.

        This adapter intentionally centralizes OpenBB endpoint assumptions. If an endpoint changes,
        patch it here only.
        """
        obb = self._obb()
        try:
            result = obb.equity.price.historical(
                symbol=symbol,
                start_date=start,
                end_date=end,
                provider=self.provider,
            )
            df = result.to_df() if hasattr(result, "to_df") else pd.DataFrame(result)
        except Exception as exc:  # pragma: no cover
            raise OpenBBUnavailable(
                f"OpenBB price endpoint failed for {symbol}. Check provider='{self.provider}' "
                "and OpenBB command reference for the installed version."
            ) from exc

        df = df.reset_index()
        lower = {c: str(c).lower() for c in df.columns}
        df = df.rename(columns=lower)
        if "date" not in df.columns:
            for cand in ["timestamp", "index"]:
                if cand in df.columns:
                    df = df.rename(columns={cand: "date"})
                    break
        required = {"date", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing OHLCV columns from OpenBB result: {sorted(missing)}")
        return df[["date", "open", "high", "low", "close", "volume"]]

    def get_fundamental_snapshot(self, symbol: str) -> dict[str, Any]:
        obb = self._obb()
        candidates = [
            ("equity.fundamental.metrics", lambda: obb.equity.fundamental.metrics(symbol=symbol, provider=self.provider)),
            ("equity.fundamental.ratios", lambda: obb.equity.fundamental.ratios(symbol=symbol, provider=self.provider)),
        ]
        for name, fn in candidates:
            try:
                result = fn()
                if hasattr(result, "to_df"):
                    return {"endpoint": name, "data": result.to_df().to_dict(orient="records")}
                return {"endpoint": name, "data": result}
            except Exception:
                continue
        return {"endpoint": None, "data": None, "warning": "No supported OpenBB fundamental endpoint succeeded."}
