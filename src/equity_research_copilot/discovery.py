from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

from equity_research_copilot.adapters.news_adapter import NewsAdapter, NewsItem
from equity_research_copilot.adapters.openbb_adapter import OpenBBAdapter
from equity_research_copilot.news.article import enrich_news_items
from equity_research_copilot.news.catalyst import CatalystEvent, build_catalyst_events
from equity_research_copilot.news.relevance import split_direct_company_news
from equity_research_copilot.technical.indicators import add_indicators
from equity_research_copilot.technical.reaction import analyze_market_reaction
from equity_research_copilot.technical.signals import build_trading_setup
from equity_research_copilot.technical.structure import analyze_structure


@dataclass
class DiscoveryCandidate:
    symbol: str
    name: str
    sources: list[str]
    price: float | None = None
    percent_change: float | None = None
    volume: float | None = None
    market_cap: float | None = None
    market: str = "US"


def _discovery_df(fn, source: str) -> pd.DataFrame:
    try:
        df = fn(provider="yfinance").to_df()
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty or "symbol" not in df:
        return pd.DataFrame()
    out = df.copy()
    out["discovery_source"] = source
    return out


def _naver_candidates(page_url: str, source: str, suffix: str, limit: int) -> list[DiscoveryCandidate]:
    try:
        res = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        res.encoding = "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception:
        return []
    rows: list[DiscoveryCandidate] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="/item/main.naver?code="]'):
        href = link.get("href") or ""
        match = re.search(r"code=(\d{6})", href)
        if not match:
            continue
        code = match.group(1)
        if code in seen:
            continue
        seen.add(code)
        name = link.get_text(" ", strip=True)
        if not name or "ETN" in name.upper() or "ETF" in name.upper() or "인버스" in name or "레버리지" in name:
            continue
        rows.append(DiscoveryCandidate(symbol=f"{code}.{suffix}", name=name, sources=[source], market="KR"))
        if len(rows) >= limit:
            break
    return rows


def collect_korean_candidates(limit_per_source: int = 40) -> list[DiscoveryCandidate]:
    specs = [
        ("kr_kospi_marketcap", "https://finance.naver.com/sise/sise_market_sum.naver?sosok=0", "KS"),
        ("kr_kosdaq_marketcap", "https://finance.naver.com/sise/sise_market_sum.naver?sosok=1", "KQ"),
        ("kr_risers", "https://finance.naver.com/sise/sise_rise.naver", "KS"),
        ("kr_volume", "https://finance.naver.com/sise/sise_quant.naver", "KS"),
    ]
    merged: dict[str, DiscoveryCandidate] = {}
    for source, url, suffix in specs:
        for candidate in _naver_candidates(url, source, suffix, limit_per_source):
            item = merged.setdefault(candidate.symbol, candidate)
            for src in candidate.sources:
                if src not in item.sources:
                    item.sources.append(src)
    return list(merged.values())


def collect_candidates(limit_per_source: int = 40, universe: str = "all") -> list[DiscoveryCandidate]:
    from openbb import obb  # type: ignore

    candidates: list[DiscoveryCandidate] = []
    if universe in {"us", "all"}:
        candidates.extend(_collect_us_candidates(obb, limit_per_source))
    if universe in {"kr", "all"}:
        candidates.extend(collect_korean_candidates(limit_per_source))
    return candidates


def _collect_us_candidates(obb, limit_per_source: int = 40) -> list[DiscoveryCandidate]:
    source_specs = [
        ("gainers", obb.equity.discovery.gainers),
        ("growth_tech", obb.equity.discovery.growth_tech),
        ("undervalued_growth", obb.equity.discovery.undervalued_growth),
        ("active", obb.equity.discovery.active),
    ]
    merged: dict[str, DiscoveryCandidate] = {}
    for source, fn in source_specs:
        df = _discovery_df(fn, source).head(limit_per_source)
        for _, row in df.iterrows():
            symbol = str(row.get("symbol") or "").upper().strip()
            if not symbol or "." in symbol or "-" in symbol:
                continue
            item = merged.setdefault(
                symbol,
                DiscoveryCandidate(
                    symbol=symbol,
                    name=str(row.get("name") or ""),
                    sources=[],
                    price=_num(row.get("price")),
                    percent_change=_num(row.get("percent_change")),
                    volume=_num(row.get("volume")),
                    market_cap=_num(row.get("market_cap")),
                    market="US",
                ),
            )
            if source not in item.sources:
                item.sources.append(source)
    return list(merged.values())


def _num(value) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _classify_news(text: str) -> str:
    lowered = text.lower()
    negative_terms = [
        "소송",
        "조사",
        "리콜",
        "적자",
        "부진",
        "하향",
        "감소",
        "규제",
        "제재",
        "lawsuit",
        "probe",
        "downgrade",
        "miss",
        "decline",
        "loss",
    ]
    positive_terms = [
        "실적",
        "수주",
        "상향",
        "흑자",
        "성장",
        "ai",
        "hbm",
        "반도체",
        "earnings",
        "beat",
        "upgrade",
        "guidance",
        "contract",
        "growth",
    ]
    if any(term in lowered for term in negative_terms):
        return "negative"
    if any(term in lowered for term in positive_terms):
        return "positive"
    return "mixed"


def summarize_news_read(
    items: list[NewsItem],
    catalysts: list[CatalystEvent],
    *,
    rejected_count: int = 0,
) -> dict[str, str | int]:
    counts = {"positive": 0, "negative": 0, "mixed": 0}
    bullets = []
    stance_by_title = {event.claim: event.direction if event.direction in counts else "mixed" for event in catalysts}
    for item in items[:10]:
        stance = stance_by_title.get(item.title) or _classify_news(f"{item.title} {item.summary} {item.body[:1000]}")
        counts[stance] += 1
        summary = f"{stance}: {item.title}"
        if item.source:
            summary += f" ({item.source})"
        bullets.append(summary)
    top = catalysts[0] if catalysts else None
    if not items and rejected_count:
        read = (
            f"검색 뉴스 {rejected_count}건은 제목 기준으로 기업명/티커가 직접 확인되지 않아 핵심 촉매에서 제외했다. "
            "차트/시장 스크리닝 신호 중심의 감시 후보로만 봐야 한다."
        )
    elif not items:
        read = "최근 직접 관련 뉴스가 충분히 잡히지 않아 차트/시장 스크리닝 신호 중심으로만 판단해야 한다."
    elif counts["negative"] > counts["positive"]:
        read = "부정/리스크성 뉴스가 우세해 차트가 좋아도 추격보다 리스크 확인이 먼저다."
    elif counts["positive"] > 0 and top and top.score >= 0.55:
        read = f"긍정 catalyst가 확인된다. 핵심 이슈는 '{top.claim}'이며, 차트 신호와 함께 감시할 만하다."
    elif counts["positive"] > 0:
        read = "긍정 뉴스는 있으나 materiality가 아직 약해 가격 반응과 후속 기사 확인이 필요하다."
    else:
        read = "뚜렷한 방향성 뉴스보다 일반 보도 비중이 높아, 후보 유지에는 추가 catalyst가 필요하다."
    return {
        "news_positive_count": counts["positive"],
        "news_negative_count": counts["negative"],
        "news_mixed_count": counts["mixed"],
        "news_read": read,
        "news_headlines": "\n".join(bullets[:6]),
    }


def assess_chase_risk(*, recent_return: float, news_text: str, sources: list[str]) -> tuple[str, float, str]:
    text = news_text.lower()
    risk_terms = [
        "상한가",
        "급등",
        "장중 상한가",
        "투자주의",
        "투자경고",
        "거래정지",
        "단일계좌",
        "과열",
        "폭등",
        "soaring",
        "surge",
        "explosive upside",
        "record highs",
    ]
    penalty = 0.0
    reasons = []
    if any(term in text for term in risk_terms):
        penalty += 0.28
        reasons.append("뉴스가 이미 급등/상한가/투자주의성 움직임을 설명")
    if recent_return >= 0.35:
        penalty += 0.22
        reasons.append("20거래일 수익률이 35% 이상")
    elif recent_return >= 0.2:
        penalty += 0.12
        reasons.append("20거래일 수익률이 20% 이상")
    if "kr_risers" in sources and len(sources) <= 2:
        penalty += 0.08
        reasons.append("상승률 리스트 의존도가 높음")
    if penalty >= 0.3:
        return "after_move_watch", min(penalty, 0.45), "; ".join(reasons)
    if penalty > 0:
        return "watch_with_chase_risk", min(penalty, 0.45), "; ".join(reasons)
    return "news_first_watch", 0.0, "뉴스 catalyst와 차트 구조를 함께 감시"


def score_candidates(
    *,
    days: int = 180,
    news_days: int = 7,
    candidate_limit: int = 40,
    provider: str = "yfinance",
    universe: str = "all",
) -> pd.DataFrame:
    price_adapter = OpenBBAdapter(provider=provider)
    news_adapter = NewsAdapter(provider=provider)
    rows = []
    for candidate in collect_candidates(limit_per_source=candidate_limit, universe=universe):
        try:
            df = add_indicators(price_adapter.get_price_history(candidate.symbol, start=(pd.Timestamp.today() - pd.Timedelta(days=days)).date().isoformat()))
            technical = analyze_structure(df)
            market_reaction = analyze_market_reaction(df)
        except Exception as exc:
            rows.append({"ticker": candidate.symbol, "name": candidate.name, "error": str(exc), "score": 0.0})
            continue

        last = df.iloc[-1]
        recent_return = float(df["close"].iloc[-1] / df["close"].tail(min(len(df), 20)).iloc[0] - 1)
        raw_news_items = news_adapter.fetch(
            candidate.symbol,
            days=news_days,
            limit=12,
            include_sec=(candidate.market != "KR"),
            company_name=candidate.name,
        )
        raw_news_items = enrich_news_items(raw_news_items)
        news_items, rejected_news_items = split_direct_company_news(
            candidate.symbol,
            candidate.name,
            raw_news_items,
            market=candidate.market,
        )
        catalysts = build_catalyst_events(
            candidate.symbol,
            news_items,
            recent_return=recent_return,
            company_name=candidate.name,
            market_reaction=market_reaction.to_dict(),
        )
        top_catalyst = catalysts[0] if catalysts else None
        news_read = summarize_news_read(news_items, catalysts, rejected_count=len(rejected_news_items))

        source_score = 0.0
        for source in candidate.sources:
            source_score += {
                "growth_tech": 0.18,
                "gainers": 0.08,
                "undervalued_growth": 0.12,
                "active": 0.06,
                "kr_risers": 0.04,
                "kr_volume": 0.06,
                "kr_kospi_marketcap": 0.1,
                "kr_kosdaq_marketcap": 0.1,
            }.get(source, 0.04)
        tech_score = 0.0
        if technical.market_structure.startswith("uptrend"):
            tech_score += 0.25
        elif "range" in technical.market_structure:
            tech_score += 0.08
        if "positive" in technical.momentum_state:
            tech_score += 0.14
        elif "cooling" in technical.momentum_state:
            tech_score += 0.04
        if "high" in technical.volume_state:
            tech_score += 0.08
        setup = build_trading_setup(df, technical)
        setup_score = setup.score * 0.18
        if setup.action in {"avoid_chase", "risk_watch"}:
            setup_score -= 0.06
        catalyst_score = (top_catalyst.score if top_catalyst else 0.0) * 0.4
        news_text = f"{top_catalyst.claim if top_catalyst else ''}\n{news_read.get('news_headlines', '')}"
        agent_view, chase_penalty, chase_reason = assess_chase_risk(
            recent_return=recent_return,
            news_text=news_text,
            sources=candidate.sources,
        )
        move_score = min(0.05, max(0.0, abs(float(candidate.percent_change or 0.0)) * 0.25))
        total = round(max(0.0, source_score + tech_score + setup_score + catalyst_score + move_score - chase_penalty), 3)
        rows.append(
            {
                "ticker": candidate.symbol,
                "ticker_name": f"{candidate.symbol} ({candidate.name})",
                "market": candidate.market,
                "name": candidate.name,
                "score": total,
                "sources": ",".join(candidate.sources),
                "close": float(last["close"]),
                "percent_change": candidate.percent_change,
                "recent_return_20d": round(recent_return, 4),
                "abnormal_return_1d": market_reaction.abnormal_return_1d,
                "abnormal_return_5d": market_reaction.abnormal_return_5d,
                "abnormal_return_20d": market_reaction.abnormal_return_20d,
                "volume_zscore": market_reaction.volume_zscore,
                "volume_ratio": market_reaction.volume_ratio,
                "gap_return": market_reaction.gap_return,
                "market_reaction_score": market_reaction.reaction_score,
                "market_structure": technical.market_structure,
                "momentum": technical.momentum_state,
                "volume_state": technical.volume_state,
                "support": technical.support_levels[0] if technical.support_levels else None,
                "resistance": technical.resistance_levels[-1] if technical.resistance_levels else None,
                "setup_type": setup.setup_type,
                "setup_action": setup.action,
                "setup_score": setup.score,
                "setup_confidence": setup.confidence,
                "setup_entry_low": setup.entry_low,
                "setup_entry_high": setup.entry_high,
                "setup_stop_loss": setup.stop_loss,
                "setup_target_1": setup.target_1,
                "setup_target_2": setup.target_2,
                "setup_risk_reward": setup.risk_reward,
                "setup_thesis": setup.thesis,
                "setup_invalidation": setup.invalidation,
                "setup_signals": "\n".join(setup.signals),
                "setup_warnings": "\n".join(setup.warnings),
                "catalyst_count": len(catalysts),
                "raw_news_count": len(raw_news_items),
                "relevant_news_count": len(news_items),
                "filtered_news_count": len(rejected_news_items),
                "top_catalyst_score": top_catalyst.score if top_catalyst else 0.0,
                "top_catalyst": top_catalyst.claim if top_catalyst else "",
                "top_catalyst_type": top_catalyst.event_type if top_catalyst else "",
                "agent_view": agent_view,
                "chase_risk_penalty": round(chase_penalty, 3),
                "chase_risk_reason": chase_reason,
                **news_read,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["score", "top_catalyst_score", "ticker"], ascending=[False, False, True])


def write_discovery_report(df: pd.DataFrame, out_path: str | Path, top: int = 10) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# 동적 종목 후보 리포트", "", "> 뉴스/공시/시장 움직임과 차트 구조를 함께 본 감시 후보입니다. 매수/매도 추천이 아닙니다.", ""]
    if df.empty:
        lines.append("No candidates discovered.")
    else:
        cols = [
            "후보",
            "시장",
            "점수",
            "판정",
            "발굴경로",
            "차트구조",
            "모멘텀",
            "셋업",
            "핵심뉴스",
            "뉴스해석",
            "지지",
            "저항",
        ]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "|".join(["---"] * len(cols)) + "|")
        display_cols = {
            "후보": "ticker_name",
            "시장": "market",
            "점수": "score",
            "판정": "agent_view",
            "발굴경로": "sources",
            "차트구조": "market_structure",
            "모멘텀": "momentum",
            "셋업": "setup_thesis",
            "핵심뉴스": "top_catalyst",
            "뉴스해석": "news_read",
            "지지": "support",
            "저항": "resistance",
        }
        for _, row in df.head(top).iterrows():
            vals = [str(row.get(src, "")).replace("|", "/").replace("\n", " ") for src in display_cols.values()]
            lines.append("| " + " | ".join(vals) + " |")
        lines.extend(["", "## 종목별 뉴스 분석", ""])
        for _, row in df.head(top).iterrows():
            lines.append(f"### {row.get('ticker_name', row.get('ticker', ''))}")
            lines.append("")
            lines.append(f"- 뉴스 해석: {row.get('news_read', '')}")
            lines.append(f"- 에이전트 판정: {row.get('agent_view', '')} ({row.get('chase_risk_reason', '')})")
            lines.append(
                f"- 뉴스 분류: 긍정 {row.get('news_positive_count', 0)} / 부정 {row.get('news_negative_count', 0)} / 중립·혼재 {row.get('news_mixed_count', 0)}"
            )
            headlines = str(row.get("news_headlines") or "").splitlines()
            if headlines:
                lines.append("- 주요 기사:")
                for headline in headlines[:6]:
                    lines.append(f"  - {headline}")
            else:
                lines.append("- 주요 기사: 없음")
            lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
