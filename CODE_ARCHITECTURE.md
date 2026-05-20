# Code Architecture

## 1. Package layout

```text
src/equity_research_copilot/
  adapters/
    openbb_adapter.py       # OpenBB price/fundamental/news endpoint wrapper
    news_adapter.py         # RSS/GDELT/custom news adapter
    sec_dart_adapter.py     # SEC/OpenDART filing adapter
  technical/
    indicators.py           # RSI/MACD/SMA/ATR/volume metrics
    structure.py            # support/resistance/trend/breakout logic
    annotations.py          # chart annotation spec builder
  charts/
    render.py               # matplotlib/plotly chart rendering
  news/
    catalyst.py             # event cards, novelty/materiality scoring
  reports/
    composer.py             # markdown/pdf/html report composition
  evaluation/
    point_in_time.py        # historical evaluation harness
    metrics.py              # hit rate, Brier, excess return
  cli.py                    # command line interface
```

## 2. Recommended command surface

```bash
research-copilot analyze NVDA --days 120 --news-days 14 --format pdf
research-copilot screen --watchlist config/watchlist.example.json --top 10
research-copilot evaluate --start 2025-01-01 --end 2026-01-01 --horizon 20d
research-copilot daily --watchlist config/watchlist.example.json
```

## 3. OpenBB adapter design

OpenBB API endpoint names can change by version/provider. Therefore all OpenBB calls are centralized in `OpenBBAdapter`. The rest of the system consumes normalized DataFrames and typed dicts only.

```python
from equity_research_copilot.adapters.openbb_adapter import OpenBBAdapter

adapter = OpenBBAdapter(provider="yfinance")
prices = adapter.get_price_history("NVDA", start="2026-01-01", end="2026-05-18")
```

If OpenBB is not installed or endpoint mapping changes, the adapter raises `OpenBBUnavailable` with setup instructions instead of leaking import errors across the pipeline.

## 4. LLM boundaries

LLM can:

- explain chart state
- convert news into catalyst cards
- identify counter-thesis
- compose scenario narrative
- critique evidence quality

LLM must not:

- invent prices, financial figures, or dates
- calculate RSI/MACD/returns manually
- fabricate source URLs
- make direct buy/sell instructions
- trigger broker/execution APIs

## 5. Evaluation design

Point-in-time evaluation requires strict temporal isolation.

```text
T date
  -> only data <= T
  -> report predicts horizon H
  -> actual return from T to T+H
  -> compare to benchmark/sector
```

Metrics:

- directional accuracy
- Brier score
- Top-K excess return
- false-positive catalyst rate
- hallucinated source rate
- priced-in error rate
