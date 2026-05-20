# Delivery Index - OpenBB + OpenClaw Equity Research Copilot

## A. PRD / Product Spec

Primary file: `PRD.md`

Defines:

- product objective
- target user
- single-ticker deep-dive flow
- watchlist screening flow
- daily update flow
- non-functional requirements
- report quality criteria
- phase roadmap
- minimum report contract

## B. System + Code Architecture

Primary files:

- `SYSTEM_ARCHITECTURE.md`
- `CODE_ARCHITECTURE.md`
- `openclaw/SKILL.md`
- `schemas/*.json`
- `prompts/*.md`
- `src/equity_research_copilot/*`

Design principle:

- OpenBB/Fincept handle data/terminal functions.
- OpenClaw handles workflow orchestration, prompt routing, report contract, memory, and evaluation.
- The custom layer focuses on news-to-catalyst reasoning, chart annotation, thesis memory, priced-in checks, and point-in-time evaluation.

## C. Actual Report Example

Primary files:

- `examples/reports/NVDA_sample_report.pdf`
- `examples/reports/NVDA_sample_report.md`
- `examples/charts/nvda_daily_structure.png`
- `examples/charts/nvda_momentum_volume.png`
- `examples/charts/nvda_event_overlay.png`

Important caveat:

- The news/quote/fundamental context is based on public information as of 2026-05-19.
- The chart images are generated from a deterministic synthetic OHLCV fixture anchored to the current NVDA quote and record-high levels because the execution environment cannot fetch live OpenBB OHLCV.
- Production use should regenerate chart data through `OpenBBAdapter.get_price_history()`.

## Regenerate demo

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python scripts/generate_demo_report.py
```

## Production command shape

```bash
research-copilot analyze NVDA --days 120 --news-days 14 --format pdf
research-copilot screen --watchlist config/watchlist.example.json --top 10
research-copilot evaluate --start 2025-01-01 --end 2026-01-01 --horizon 20d
```
