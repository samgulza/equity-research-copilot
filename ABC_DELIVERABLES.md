# ABC Deliverables - OpenBB + OpenClaw Equity Research Copilot

## A. PRD / Spec

Primary files:

- `PRD.md` - product definition, target users, use cases, non-functional requirements, MVP phases, report quality bar.
- `SYSTEM_ARCHITECTURE.md` - data, agent, chart annotation, report composer, evaluation architecture.
- `risk_policy.md` - research-only guardrails and forbidden automation behavior.

Core product definition:

> A research copilot that converts public news, filings, and price action into business-driver-aware catalysts, annotated technical charts, scenario analysis, invalidation levels, and a critic-reviewed investment memo. It does not execute trades.

## B. Code Architecture

Primary files:

- `CODE_ARCHITECTURE.md` - module design and extension points.
- `src/equity_research_copilot/adapters/openbb_adapter.py` - OpenBB price/fundamental adapter boundary.
- `src/equity_research_copilot/adapters/news_adapter.py` - news/RSS/GDELT/licensed data adapter boundary.
- `src/equity_research_copilot/technical/indicators.py` - deterministic technical indicators.
- `src/equity_research_copilot/technical/structure.py` - market-structure summary engine.
- `src/equity_research_copilot/technical/annotations.py` - chart annotation contract.
- `src/equity_research_copilot/news/catalyst.py` - catalyst card schema.
- `src/equity_research_copilot/evaluation/*` - point-in-time evaluation skeleton.
- `openclaw/SKILL.md` - OpenClaw skill contract.

Architecture principle:

```text
OpenBB / provider layer -> deterministic feature extraction -> catalyst extraction -> chart annotation -> analyst memo -> critic -> evaluation record
```

LLM responsibilities are intentionally restricted to interpretation, extraction, contradiction checking, and report composition. Price calculations, indicators, and future-return labels are deterministic code.

## C. Actual Report Example

Primary files:

- `examples/reports/NVDA_sample_report.md` - detailed sample memo.
- `examples/reports/NVDA_sample_report_polished.pdf` - polished PDF sample with annotated chart pack.
- `examples/charts/nvda_daily_structure.png` - annotated market-structure chart.
- `examples/charts/nvda_momentum_volume.png` - annotated momentum/volume chart.
- `examples/charts/nvda_event_overlay.png` - event overlay chart.
- `examples/data/nvda_synthetic_ohlcv.csv` - synthetic OHLCV fixture used only for chart annotation demo.

Sample report caveat:

The news/quote context is based on current public-source examples; the charts are synthetic fixtures because this execution environment cannot pull live OHLCV directly. Production mode should regenerate charts through OpenBB before producing a final memo.
