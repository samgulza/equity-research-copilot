from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

from equity_research_copilot.adapters.news_adapter import NewsAdapter
from equity_research_copilot.adapters.openbb_adapter import OpenBBAdapter
from equity_research_copilot.charts.render import render_chart_pack
from equity_research_copilot.discovery import score_candidates, write_discovery_report
from equity_research_copilot.evaluation.event_level import evaluate_archived_events
from equity_research_copilot.evaluation.point_in_time import evaluate_symbol_history
from equity_research_copilot.memory import ThesisRecord, append_record, evidence_hash, recent_records
from equity_research_copilot.news.article import enrich_news_items
from equity_research_copilot.news.catalyst import build_catalyst_events
from equity_research_copilot.news.relevance import split_direct_company_news
from equity_research_copilot.reports.composer import compose_deep_dive_markdown, write_text_pdf
from equity_research_copilot.technical.indicators import add_indicators
from equity_research_copilot.technical.reaction import analyze_market_reaction
from equity_research_copilot.technical.structure import analyze_structure


def _project_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "examples" / "data" / "nvda_synthetic_ohlcv.csv").exists():
        return cwd
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "examples" / "data" / "nvda_synthetic_ohlcv.csv").exists():
            return parent
    raise FileNotFoundError("Could not locate examples/data/nvda_synthetic_ohlcv.csv")


def demo() -> None:
    root = _project_root()
    csv_path = root / "examples" / "data" / "nvda_synthetic_ohlcv.csv"
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = add_indicators(df)
    summary = analyze_structure(df)
    print(summary)


def _default_start(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _watchlist_symbols(watchlist: str | Path) -> list[str]:
    payload = json.loads(Path(watchlist).read_text(encoding="utf-8"))
    symbols = payload.get("symbols") or payload.get("tickers") or []
    if not symbols:
        raise ValueError("watchlist JSON must include a symbols or tickers list")
    return [str(symbol.get("symbol") if isinstance(symbol, dict) else symbol).upper() for symbol in symbols]


def analyze(
    symbol: str,
    *,
    company_name: str | None = None,
    days: int,
    start: str | None,
    end: str | None,
    provider: str,
    out_dir: str | Path,
    output_format: str,
    with_fundamentals: bool,
    with_news: bool,
    news_days: int,
    news_limit: int,
    include_sec: bool,
    memory_path: str | Path,
) -> None:
    ticker = symbol.upper()
    run_dir = Path(out_dir) / ticker
    chart_dir = run_dir / "charts"
    report_dir = run_dir / "reports"
    data_dir = run_dir / "data"
    for path in [chart_dir, report_dir, data_dir]:
        path.mkdir(parents=True, exist_ok=True)

    adapter = OpenBBAdapter(provider=provider)
    df = adapter.get_price_history(ticker, start=start or _default_start(days), end=end)
    df = add_indicators(df)
    df.to_csv(data_dir / f"{ticker.lower()}_ohlcv.csv", index=False)

    technical = analyze_structure(df)
    charts = render_chart_pack(df, chart_dir, ticker)
    fundamentals = adapter.get_fundamental_snapshot(ticker) if with_fundamentals else None
    recent_return = float(df["close"].iloc[-1] / df["close"].tail(min(len(df), 20)).iloc[0] - 1)
    market_reaction = analyze_market_reaction(df)
    raw_news_items = (
        NewsAdapter(provider=provider).fetch(ticker, days=news_days, limit=news_limit, include_sec=include_sec, company_name=company_name)
        if with_news
        else []
    )
    raw_news_items = enrich_news_items(raw_news_items)
    market = "KR" if ticker.upper().endswith((".KS", ".KQ")) else "US"
    news_items, _rejected_news_items = split_direct_company_news(ticker, company_name, raw_news_items, market=market)
    catalysts = build_catalyst_events(
        ticker,
        news_items,
        recent_return=recent_return,
        company_name=company_name or "",
        market_reaction=market_reaction.to_dict(),
    )
    (data_dir / f"{ticker.lower()}_news.json").write_text(json.dumps([asdict(item) for item in news_items], ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / f"{ticker.lower()}_catalysts.json").write_text(json.dumps([event.to_dict() for event in catalysts], ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot_at = datetime.now(UTC).isoformat(timespec="seconds")
    md_path = report_dir / f"{ticker}_research_memo.md"
    history = recent_records(memory_path, ticker, limit=5)
    markdown = compose_deep_dive_markdown(
        ticker=ticker,
        df=df,
        technical=technical,
        chart_paths=charts,
        provider=provider,
        snapshot_at=snapshot_at,
        fundamentals=fundamentals,
        catalysts=catalysts,
        thesis_history=history,
        report_path=md_path,
    )
    md_path.write_text(markdown, encoding="utf-8")
    verdict = "CONSTRUCTIVE WATCH" if technical.market_structure.startswith("uptrend") else "RISK WATCH" if technical.market_structure.startswith("downtrend") else "WATCH"
    top_catalyst = catalysts[0].claim if catalysts else ""
    record = ThesisRecord(
        ticker=ticker,
        as_of=snapshot_at,
        verdict=verdict,
        confidence=technical.confidence,
        close=float(df["close"].iloc[-1]),
        horizon_days=20,
        support=technical.support_levels[0] if technical.support_levels else float("nan"),
        resistance=technical.resistance_levels[-1] if technical.resistance_levels else float("nan"),
        catalyst_count=len(catalysts),
        top_catalyst=top_catalyst,
        report_path=str(md_path),
        evidence_hash=evidence_hash({"ticker": ticker, "last": float(df["close"].iloc[-1]), "catalysts": [event.claim for event in catalysts[:5]]}),
    )
    append_record(memory_path, record)

    outputs = [md_path]
    if output_format in {"pdf", "both"}:
        pdf_path = report_dir / f"{ticker}_research_memo.pdf"
        write_text_pdf(markdown, pdf_path, f"{ticker} Research Memo", base_dir=md_path.parent)
        outputs.append(pdf_path)

    print(f"Generated {ticker} research artifacts")
    for path in outputs:
        print(f"- {path}")
    for name, path in charts.items():
        print(f"- {name}: {path}")
    print(f"- data: {data_dir / f'{ticker.lower()}_ohlcv.csv'}")
    print(f"- catalysts: {data_dir / f'{ticker.lower()}_catalysts.json'}")
    print(f"- thesis memory: {memory_path}")


def screen(watchlist: str | Path, *, days: int, provider: str, out_dir: str | Path, top: int) -> None:
    symbols = _watchlist_symbols(watchlist)
    rows = []
    adapter = OpenBBAdapter(provider=provider)
    for symbol in symbols:
        ticker = symbol
        df = add_indicators(adapter.get_price_history(ticker, start=_default_start(days)))
        summary = analyze_structure(df)
        last = df.iloc[-1]
        rows.append(
            {
                "ticker": ticker,
                "close": float(last["close"]),
                "market_structure": summary.market_structure,
                "momentum": summary.momentum_state,
                "volume": summary.volume_state,
                "confidence": summary.confidence,
                "support": summary.support_levels[0],
                "resistance": summary.resistance_levels[-1],
            }
        )
    out = pd.DataFrame(rows).sort_values(["confidence", "ticker"], ascending=[False, True]).head(top)
    out_path = Path(out_dir) / "screen" / f"screen_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(out.to_string(index=False))
    print(f"- screen output: {out_path}")


def daily(
    watchlist: str | Path,
    *,
    days: int,
    provider: str,
    out_dir: str | Path,
    top: int,
    output_format: str,
    memory_path: str | Path,
) -> None:
    symbols = _watchlist_symbols(watchlist)[:top]
    run_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    summary_rows = []
    for ticker in symbols:
        analyze(
            ticker,
            days=days,
            start=None,
            end=None,
            provider=provider,
            out_dir=out_dir,
            output_format=output_format,
            company_name=None,
            with_fundamentals=True,
            with_news=True,
            news_days=14,
            news_limit=20,
            include_sec=True,
            memory_path=memory_path,
        )
        report_path = Path(out_dir) / ticker / "reports" / f"{ticker}_research_memo.md"
        summary_rows.append(f"- {ticker}: {report_path}")
    summary_path = Path(out_dir) / "daily" / f"daily_{run_stamp}.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("# Daily Watchlist Run\n\n" + "\n".join(summary_rows) + "\n", encoding="utf-8")
    print(f"- daily summary: {summary_path}")


def evaluate(
    symbol: str,
    *,
    start: str,
    end: str | None,
    horizon_days: int,
    step_days: int,
    lookback_days: int,
    provider: str,
    out_dir: str | Path,
) -> None:
    df, summary = evaluate_symbol_history(
        symbol,
        start=start,
        end=end,
        horizon_days=horizon_days,
        step_days=step_days,
        lookback_days=lookback_days,
        provider=provider,
    )
    root = Path(out_dir) / "evaluation" / symbol.upper()
    root.mkdir(parents=True, exist_ok=True)
    csv_path = root / f"evaluation_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.csv"
    json_path = root / "latest_summary.json"
    df.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"- evaluation rows: {csv_path}")
    print(f"- evaluation summary: {json_path}")


def evaluate_events(*, archive_dir: str | Path, out_dir: str | Path) -> None:
    rows, summary = evaluate_archived_events(Path(archive_dir))
    root = Path(out_dir) / "evaluation" / "events"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    csv_path = root / f"event_evaluation_{stamp}.csv"
    json_path = root / "latest_summary.json"
    rows.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"- event evaluation rows: {csv_path}")
    print(f"- event evaluation summary: {json_path}")


def discover(
    *,
    days: int,
    news_days: int,
    candidate_limit: int,
    top: int,
    provider: str,
    universe: str,
    out_dir: str | Path,
    analyze_top: int,
    output_format: str,
    memory_path: str | Path,
) -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = Path(out_dir) / "discovery"
    root.mkdir(parents=True, exist_ok=True)
    df = score_candidates(days=days, news_days=news_days, candidate_limit=candidate_limit, provider=provider, universe=universe)
    csv_path = root / f"discovery_{stamp}.csv"
    md_path = root / f"discovery_{stamp}.md"
    pdf_path = root / f"discovery_{stamp}.pdf"
    df.to_csv(csv_path, index=False)
    write_discovery_report(df, md_path, top=top)
    try:
        write_text_pdf(md_path.read_text(encoding="utf-8"), pdf_path, "Dynamic Stock Discovery", base_dir=md_path.parent)
    except Exception as exc:
        pdf_path = None
        print(f"- discovery pdf skipped: {exc}")
    print(df.head(top).to_string(index=False) if not df.empty else "No candidates discovered.")
    print(f"- discovery csv: {csv_path}")
    print(f"- discovery report: {md_path}")
    if pdf_path:
        print(f"- discovery pdf: {pdf_path}")
    for _, row in df.head(analyze_top).iterrows() if analyze_top and not df.empty else []:
        ticker = str(row.get("ticker"))
        analyze(
            ticker,
            days=days,
            start=None,
            end=None,
            provider=provider,
            out_dir=out_dir,
            output_format=output_format,
            company_name=str(row.get("name") or ""),
            with_fundamentals=True,
            with_news=True,
            news_days=news_days,
            news_limit=12,
            include_sec=True,
            memory_path=memory_path,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="Run demo analysis on fixture data")

    analyze_parser = sub.add_parser("analyze", help="Generate a live OpenBB deep-dive memo")
    analyze_parser.add_argument("symbol")
    analyze_parser.add_argument("--company-name")
    analyze_parser.add_argument("--days", type=int, default=180)
    analyze_parser.add_argument("--start")
    analyze_parser.add_argument("--end")
    analyze_parser.add_argument("--provider", default="yfinance")
    analyze_parser.add_argument("--out-dir", default="runs")
    analyze_parser.add_argument("--format", choices=["md", "pdf", "both"], default="both")
    analyze_parser.add_argument("--with-fundamentals", action="store_true")
    analyze_parser.add_argument("--with-news", action="store_true")
    analyze_parser.add_argument("--news-days", type=int, default=14)
    analyze_parser.add_argument("--news-limit", type=int, default=20)
    analyze_parser.add_argument("--include-sec", action="store_true")
    analyze_parser.add_argument("--memory-path", default="runs/thesis_memory.jsonl")

    screen_parser = sub.add_parser("screen", help="Screen a JSON watchlist with OpenBB price data")
    screen_parser.add_argument("--watchlist", required=True)
    screen_parser.add_argument("--days", type=int, default=180)
    screen_parser.add_argument("--provider", default="yfinance")
    screen_parser.add_argument("--out-dir", default="runs")
    screen_parser.add_argument("--top", type=int, default=10)

    daily_parser = sub.add_parser("daily", help="Run analyze across a watchlist and write a daily summary")
    daily_parser.add_argument("--watchlist", required=True)
    daily_parser.add_argument("--days", type=int, default=180)
    daily_parser.add_argument("--provider", default="yfinance")
    daily_parser.add_argument("--out-dir", default="runs")
    daily_parser.add_argument("--top", type=int, default=10)
    daily_parser.add_argument("--format", choices=["md", "pdf", "both"], default="md")
    daily_parser.add_argument("--memory-path", default="runs/thesis_memory.jsonl")

    eval_parser = sub.add_parser("evaluate", help="Run point-in-time OHLCV evaluation")
    eval_parser.add_argument("symbol")
    eval_parser.add_argument("--start", required=True)
    eval_parser.add_argument("--end")
    eval_parser.add_argument("--horizon-days", type=int, default=20)
    eval_parser.add_argument("--step-days", type=int, default=5)
    eval_parser.add_argument("--lookback-days", type=int, default=120)
    eval_parser.add_argument("--provider", default="yfinance")
    eval_parser.add_argument("--out-dir", default="runs")

    event_eval_parser = sub.add_parser("evaluate-events", help="Evaluate archived event/setup outcomes from docs/data snapshots")
    event_eval_parser.add_argument("--archive-dir", default="docs/data")
    event_eval_parser.add_argument("--out-dir", default="runs")

    discover_parser = sub.add_parser("discover", help="Dynamically discover stocks from market movers/news, then rank by chart+catalyst")
    discover_parser.add_argument("--days", type=int, default=180)
    discover_parser.add_argument("--news-days", type=int, default=7)
    discover_parser.add_argument("--candidate-limit", type=int, default=25)
    discover_parser.add_argument("--top", type=int, default=10)
    discover_parser.add_argument("--provider", default="yfinance")
    discover_parser.add_argument("--universe", choices=["us", "kr", "all"], default="all")
    discover_parser.add_argument("--out-dir", default="runs")
    discover_parser.add_argument("--analyze-top", type=int, default=3)
    discover_parser.add_argument("--format", choices=["md", "pdf", "both"], default="md")
    discover_parser.add_argument("--memory-path", default="runs/thesis_memory.jsonl")

    args = parser.parse_args()
    if args.command == "demo":
        demo()
    elif args.command == "analyze":
        analyze(
            args.symbol,
            company_name=args.company_name,
            days=args.days,
            start=args.start,
            end=args.end,
            provider=args.provider,
            out_dir=args.out_dir,
            output_format=args.format,
            with_fundamentals=args.with_fundamentals,
            with_news=args.with_news,
            news_days=args.news_days,
            news_limit=args.news_limit,
            include_sec=args.include_sec,
            memory_path=args.memory_path,
        )
    elif args.command == "screen":
        screen(args.watchlist, days=args.days, provider=args.provider, out_dir=args.out_dir, top=args.top)
    elif args.command == "daily":
        daily(
            args.watchlist,
            days=args.days,
            provider=args.provider,
            out_dir=args.out_dir,
            top=args.top,
            output_format=args.format,
            memory_path=args.memory_path,
        )
    elif args.command == "evaluate":
        evaluate(
            args.symbol,
            start=args.start,
            end=args.end,
            horizon_days=args.horizon_days,
            step_days=args.step_days,
            lookback_days=args.lookback_days,
            provider=args.provider,
            out_dir=args.out_dir,
        )
    elif args.command == "evaluate-events":
        evaluate_events(archive_dir=args.archive_dir, out_dir=args.out_dir)
    elif args.command == "discover":
        discover(
            days=args.days,
            news_days=args.news_days,
            candidate_limit=args.candidate_limit,
            top=args.top,
            provider=args.provider,
            universe=args.universe,
            out_dir=args.out_dir,
            analyze_top=args.analyze_top,
            output_format=args.format,
            memory_path=args.memory_path,
        )


if __name__ == "__main__":
    main()
