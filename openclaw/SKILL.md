# Equity Research Copilot Skill

## Purpose

Generate evidence-weighted equity research reports that combine OpenBB market data, news/catalyst analysis, and annotated technical charts.

## Non-goals

- Do not execute trades.
- Do not connect to broker accounts.
- Do not present outputs as financial advice.

## Commands

### Analyze one ticker

```bash
python scripts/generate_demo_report.py --ticker NVDA
```

Production form:

```bash
research-copilot analyze <TICKER> --days 120 --news-days 14 --format markdown|pdf|json
```

### Screen watchlist

```bash
research-copilot screen --watchlist config/watchlist.example.json --top 10
```

### Evaluate

```bash
research-copilot evaluate --start 2025-01-01 --end 2026-01-01 --horizon 20d
```

## Report contract

The report must include:

1. Verdict and confidence
2. Technical structure
3. Annotated chart pack
4. News/catalyst cards
5. Priced-in analysis
6. Scenarios
7. Invalidation levels
8. Risks and counter-thesis
9. Source appendix
10. Research-only disclaimer
