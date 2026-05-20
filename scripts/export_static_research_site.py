from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


THEME_RULES: dict[str, list[str]] = {
    "AI / 반도체": ["ai", "반도체", "hbm", "메모리", "삼성", "하이닉스", "nvidia", "micron", "chip", "semiconductor"],
    "자동차 / 전동화": ["현대차", "기아", "전기차", "미래차", "자율주행", "배터리", "타이어", "열관리", "ev"],
    "바이오 / 헬스케어": ["바이오", "제약", "임상", "fda", "의약품", "헬스케어", "펩트론", "케어젠"],
    "보험 / 금융": ["보험", "은행", "금융", "생명", "증권", "연결 실적"],
    "ETF / 수급": ["etf", "레버리지", "인버스", "커버드콜", "개미", "외국인", "수급"],
    "노동 / 규제": ["노조", "파업", "규제", "조사", "소송", "공정위", "노동", "strike", "lawsuit", "probe"],
    "실적 / 가이던스": ["실적", "영업이익", "매출", "가이던스", "성장", "흑자", "적자", "earnings", "guidance", "revenue"],
}

LOW_SIGNAL_TITLE_TERMS = [
    "[그래픽]",
    "그래픽",
    "시황",
    "마감시황",
    "인기 검색",
    "검색 종목",
    "가격 비교",
    "코스피",
    "코스닥",
    "환율",
    "파란불",
]


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "src" / "equity_research_copilot").exists():
            return parent
    return Path.cwd()


def _latest_discovery(runs_dir: Path) -> Path:
    candidates = sorted((runs_dir / "discovery").glob("discovery_*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No discovery CSV found under {runs_dir / 'discovery'}")
    return candidates[0]


def _clean_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    return value


def _candidate_data_dir(runs_dir: Path, ticker: str) -> Path | None:
    exact = runs_dir / ticker
    if exact.exists():
        return exact / "data"
    upper = ticker.upper()
    for path in runs_dir.iterdir():
        if path.is_dir() and path.name.upper() == upper:
            return path / "data"
    return None


def _load_ohlcv(runs_dir: Path, ticker: str, limit: int) -> list[dict[str, Any]]:
    data_dir = _candidate_data_dir(runs_dir, ticker)
    if not data_dir or not data_dir.exists():
        return []
    files = sorted(data_dir.glob("*_ohlcv.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        return []
    df = pd.read_csv(files[0])
    if "date" not in df or "close" not in df:
        return []
    keep = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "sma20",
        "sma50",
        "sma100",
        "rsi14",
        "macd",
        "macd_signal",
        "macd_hist",
        "volume_20d",
    ]
    out = df[[col for col in keep if col in df]].tail(limit).copy()
    return _json_ready(out.to_dict(orient="records"))


def _load_json_list(runs_dir: Path, ticker: str, suffix: str) -> list[dict[str, Any]]:
    data_dir = _candidate_data_dir(runs_dir, ticker)
    if not data_dir or not data_dir.exists():
        return []
    files = sorted(data_dir.glob(f"*_{suffix}.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        return []
    try:
        payload = json.loads(files[0].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _headline_items(headlines: str) -> list[dict[str, str]]:
    items = []
    for raw in headlines.splitlines():
        line = raw.strip()
        if not line:
            continue
        stance, title = "mixed", line
        match = re.match(r"^(positive|negative|mixed):\s*(.+)$", line, re.IGNORECASE)
        if match:
            stance = match.group(1).lower()
            title = match.group(2).strip()
        source = ""
        source_match = re.search(r"\(([^()]+)\)\s*$", title)
        if source_match:
            source = source_match.group(1)
            title = title[: source_match.start()].strip()
        items.append({"stance": stance, "title": title, "source": source})
    return items[:8]


def _compact_text(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.casefold())


def _name_tokens(name: str) -> list[str]:
    cleaned = re.sub(r"\s+", "", name)
    cleaned = re.sub(r"(보통주|우선주|우|홀딩스|지주|주식회사|\(.*?\))", "", cleaned)
    tokens = [name.strip(), cleaned.strip()]
    if cleaned.upper().startswith("HD") and len(cleaned) > 4:
        tokens.append(cleaned[2:])
    if len(cleaned) >= 4:
        tokens.append(cleaned[:4])
    return [token for token in tokens if len(_compact_text(token)) >= 2]


def _ticker_tokens(ticker: str) -> list[str]:
    tokens = [ticker, ticker.split(".")[0]]
    return [token for token in tokens if len(_compact_text(token)) >= 2]


def _token_hits(name: str, ticker: str, text: str) -> list[str]:
    haystack = _compact_text(text)
    hits = []
    for token in _name_tokens(name) + _ticker_tokens(ticker):
        compacted = _compact_text(token)
        if compacted and compacted in haystack:
            hits.append(token)
    return hits


def _text_direct(name: str, ticker: str, text: str) -> bool:
    return bool(_token_hits(name, ticker, text))


def _low_signal_title(title: str) -> bool:
    lowered = title.casefold()
    return any(term in lowered for term in LOW_SIGNAL_TITLE_TERMS)


def _direct_headlines(name: str, ticker: str, headlines: list[dict[str, str]], news_items: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = [item for item in headlines if _text_direct(name, ticker, item.get("title", "")) and not _low_signal_title(item.get("title", ""))]
    seen = {_compact_text(item.get("title", "")) for item in rows}
    for item in news_items:
        title = _clean_text(item.get("title"))
        if not title or not _text_direct(name, ticker, title) or _low_signal_title(title):
            continue
        key = _compact_text(title)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"stance": "mixed", "title": title, "source": _clean_text(item.get("source"))})
    return rows[:8]


def _direct_events(name: str, ticker: str, catalysts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in catalysts
        if _text_direct(name, ticker, _clean_text(event.get("claim"))) and not _low_signal_title(_clean_text(event.get("claim")))
    ]


def _sanitize_news_read(raw_read: str, raw_claim: str, display_claim: str, direct_count: int) -> str:
    if not display_claim:
        return "기업명/티커가 제목에 직접 확인되는 촉매가 없어 차트와 수급 중심의 감시 후보로만 봅니다."
    if raw_claim and raw_claim != display_claim and raw_claim in raw_read:
        return f"핵심 촉매를 제목 기준 직접 관련 뉴스로 재선별했다. 현재 표시 이슈는 '{display_claim}'입니다."
    if direct_count == 1 and "핵심 이슈" not in raw_read:
        return f"직접 관련 뉴스 1건이 확인된다. 핵심 이슈는 '{display_claim}'입니다."
    return raw_read


def _news_relevance(
    name: str,
    ticker: str,
    top_claim: str,
    headlines: list[dict[str, str]],
    catalysts: list[dict[str, Any]],
) -> dict[str, Any]:
    core_text = " ".join([top_claim, _clean_text(catalysts[0].get("claim")) if catalysts else ""])
    haystack = " ".join(
        [core_text]
        + [item.get("title", "") for item in headlines]
        + [_clean_text(event.get("claim")) for event in catalysts[:5]]
        + [_clean_text(event.get("affected_driver")) for event in catalysts[:5]]
    )
    haystack_l = haystack.casefold()
    core_hits = _token_hits(name, ticker, core_text)
    direct_hits = _token_hits(name, ticker, haystack)
    if core_hits:
        return {"level": "direct", "label": "직접 관련", "score": 1.0, "note": "핵심 촉매 안에서 기업명 또는 티커가 직접 확인됨"}
    if direct_hits:
        return {"level": "partial", "label": "부분 직접", "score": 0.78, "note": "주변 기사에는 후보명이 있으나 핵심 촉매 제목은 별도 확인 필요"}
    if any(keyword in haystack_l for terms in THEME_RULES.values() for keyword in terms):
        return {"level": "theme", "label": "테마 관련", "score": 0.65, "note": "기업 직접 뉴스보다 업종/테마 뉴스 비중이 높음"}
    return {"level": "weak", "label": "관련성 약함", "score": 0.35, "note": "후보명과 기사 주체가 어긋날 수 있어 원문 확인 필요"}


def _stance_label(agent_view: str, chase_penalty: float | None) -> str:
    if agent_view == "after_move_watch":
        return "추격 금지 감시"
    if agent_view == "watch_with_chase_risk" or (chase_penalty or 0) >= 0.12:
        return "추격 리스크"
    if agent_view == "news_first_watch":
        return "뉴스 우선 감시"
    return "중립 감시"


def _price_snapshot(series: list[dict[str, Any]], fallback_close: float | None, fallback_return: float | None) -> dict[str, Any]:
    if len(series) >= 2:
        last = series[-1]
        prev = series[-2]
        close = _clean_number(last.get("close"))
        prev_close = _clean_number(prev.get("close"))
        day_change = close / prev_close - 1 if close and prev_close else None
        return {"close": close, "dayChange": day_change, "recentReturn20d": fallback_return}
    return {"close": fallback_close, "dayChange": None, "recentReturn20d": fallback_return}


def _latest_close(series: list[dict[str, Any]]) -> tuple[float | None, str]:
    if not series:
        return None, ""
    last = series[-1]
    return _clean_number(last.get("close")), _clean_text(last.get("date"))


def _build_candidates(df: pd.DataFrame, runs_dir: Path, top: int, series_limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in df.head(top).iterrows():
        ticker = _clean_text(row.get("ticker")).upper()
        if not ticker:
            continue
        name = _clean_text(row.get("name"))
        raw_headlines = _headline_items(_clean_text(row.get("news_headlines")))
        raw_catalysts = _load_json_list(runs_dir, ticker, "catalysts")
        news_items = _load_json_list(runs_dir, ticker, "news")
        direct_news_items = [
            item
            for item in news_items
            if _text_direct(name, ticker, _clean_text(item.get("title"))) and not _low_signal_title(_clean_text(item.get("title")))
        ]
        direct_events = _direct_events(name, ticker, raw_catalysts)
        headlines = _direct_headlines(name, ticker, raw_headlines, direct_news_items)
        series = _load_ohlcv(runs_dir, ticker, series_limit)
        raw_top_claim = _clean_text(row.get("top_catalyst"))
        raw_top_catalyst_score = _clean_number(row.get("top_catalyst_score")) or 0.0
        top_claim = raw_top_claim if _text_direct(name, ticker, raw_top_claim) and not _low_signal_title(raw_top_claim) else ""
        top_catalyst_score = raw_top_catalyst_score if top_claim else 0.0
        catalyst_type = _clean_text(row.get("top_catalyst_type")) or "uncategorized"
        if not top_claim and headlines:
            top_claim = headlines[0]["title"]
            top_catalyst_score = min(raw_top_catalyst_score, 0.45)
            catalyst_type = "company_news"
        elif not top_claim and direct_events:
            top_claim = _clean_text(direct_events[0].get("claim"))
            top_catalyst_score = _clean_number(direct_events[0].get("score")) or 0.0
            catalyst_type = _clean_text(direct_events[0].get("event_type")) or "company_news"
        catalysts = direct_events[:8]
        relevance = _news_relevance(name, ticker, top_claim, headlines, catalysts)
        score = _clean_number(row.get("score")) or 0.0
        if raw_top_claim and raw_top_claim != top_claim:
            score = max(0.0, score - max(0.0, raw_top_catalyst_score - top_catalyst_score) * 0.4)
        catalyst_strength = round(min(1.0, top_catalyst_score * relevance["score"]), 3)
        chase_penalty = _clean_number(row.get("chase_risk_penalty")) or 0.0
        recent_return = _clean_number(row.get("recent_return_20d"))
        headline_counts = {"positive": 0, "negative": 0, "mixed": 0}
        for headline in headlines:
            stance = headline.get("stance") if headline.get("stance") in headline_counts else "mixed"
            headline_counts[stance] += 1
        news_read = _sanitize_news_read(_clean_text(row.get("news_read")), raw_top_claim, top_claim, len(headlines))
        rows.append(
            {
                "rank": len(rows) + 1,
                "ticker": ticker,
                "name": name,
                "market": _clean_text(row.get("market")),
                "sources": [item for item in _clean_text(row.get("sources")).split(",") if item],
                "score": round(score, 3),
                "agentView": _clean_text(row.get("agent_view")),
                "stance": _stance_label(_clean_text(row.get("agent_view")), chase_penalty),
                "price": _price_snapshot(series, _clean_number(row.get("close")), recent_return),
                "technical": {
                    "structure": _clean_text(row.get("market_structure")),
                    "momentum": _clean_text(row.get("momentum")),
                    "volume": _clean_text(row.get("volume_state")),
                    "support": _clean_number(row.get("support")),
                    "resistance": _clean_number(row.get("resistance")),
                },
                "news": {
                    "read": news_read,
                    "positive": headline_counts["positive"],
                    "negative": headline_counts["negative"],
                    "mixed": headline_counts["mixed"],
                    "headlines": headlines,
                    "rawItems": direct_news_items[:8],
                    "relevance": relevance,
                },
                "catalyst": {
                    "count": len(catalysts),
                    "score": round(top_catalyst_score, 3),
                    "qualityScore": catalyst_strength,
                    "claim": top_claim,
                    "type": catalyst_type,
                    "events": catalysts,
                },
                "risk": {
                    "chasePenalty": round(chase_penalty, 3),
                    "reason": _clean_text(row.get("chase_risk_reason")),
                    "relevanceHaircut": round(1.0 - relevance["score"], 2),
                },
                "series": series,
            }
        )
    return rows


def _build_themes(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"score": 0.0, "tickers": set(), "positive": 0, "negative": 0, "mixed": 0})
    for candidate in candidates:
        text = " ".join(
            [
                candidate["catalyst"]["claim"],
                candidate["news"]["read"],
                " ".join(item["title"] for item in candidate["news"]["headlines"]),
            ]
        ).lower()
        matched = False
        for theme, keywords in THEME_RULES.items():
            if any(keyword in text for keyword in keywords):
                matched = True
                weight = candidate["score"] * (0.6 + 0.4 * candidate["news"]["relevance"]["score"])
                buckets[theme]["score"] += weight
                buckets[theme]["tickers"].add(candidate["ticker"])
                buckets[theme]["positive"] += candidate["news"]["positive"]
                buckets[theme]["negative"] += candidate["news"]["negative"]
                buckets[theme]["mixed"] += candidate["news"]["mixed"]
        if not matched:
            buckets["개별 종목 뉴스"]["score"] += candidate["score"] * 0.5
            buckets["개별 종목 뉴스"]["tickers"].add(candidate["ticker"])
            buckets["개별 종목 뉴스"]["positive"] += candidate["news"]["positive"]
            buckets["개별 종목 뉴스"]["negative"] += candidate["news"]["negative"]
            buckets["개별 종목 뉴스"]["mixed"] += candidate["news"]["mixed"]
    max_score = max((bucket["score"] for bucket in buckets.values()), default=1.0) or 1.0
    themes = []
    for theme, bucket in buckets.items():
        themes.append(
            {
                "name": theme,
                "score": round(bucket["score"], 3),
                "heat": round(bucket["score"] / max_score * 100),
                "tickers": sorted(bucket["tickers"]),
                "sentiment": {"positive": bucket["positive"], "negative": bucket["negative"], "mixed": bucket["mixed"]},
            }
        )
    return sorted(themes, key=lambda item: item["score"], reverse=True)


def _build_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    sentiment = {"positive": 0, "negative": 0, "mixed": 0}
    for candidate in candidates:
        sentiment["positive"] += candidate["news"]["positive"]
        sentiment["negative"] += candidate["news"]["negative"]
        sentiment["mixed"] += candidate["news"]["mixed"]
    count = len(candidates)
    return {
        "candidateCount": count,
        "avgScore": round(sum(item["score"] for item in candidates) / count, 3) if count else 0,
        "directNewsCount": sum(1 for item in candidates if item["news"]["relevance"]["level"] == "direct"),
        "partialNewsCount": sum(1 for item in candidates if item["news"]["relevance"]["level"] == "partial"),
        "themeNewsCount": sum(1 for item in candidates if item["news"]["relevance"]["level"] == "theme"),
        "weakNewsCount": sum(1 for item in candidates if item["news"]["relevance"]["level"] == "weak"),
        "chaseRiskCount": sum(1 for item in candidates if item["risk"]["chasePenalty"] > 0),
        "availableSeriesCount": sum(1 for item in candidates if item["series"]),
        "sentiment": sentiment,
    }


def _report_date(generated_at: str, override: str | None = None) -> str:
    if override:
        return override
    try:
        return datetime.fromisoformat(generated_at).date().isoformat()
    except ValueError:
        return date.today().isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _previous_snapshot(archive_dir: Path, current_date: str) -> dict[str, Any] | None:
    index = _read_json(archive_dir / "index.json") or {}
    dates = [item.get("date") for item in index.get("dates", []) if isinstance(item, dict)]
    previous_dates = sorted(item for item in dates if isinstance(item, str) and item < current_date)
    if not previous_dates:
        return None
    return _read_json(archive_dir / f"{previous_dates[-1]}.json")


def _build_outcomes(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    runs_dir: Path,
    series_limit: int,
) -> dict[str, Any]:
    if not previous:
        return {
            "previousDate": None,
            "currentDate": current["archive"]["date"],
            "summary": {"trackedCount": 0, "withPriceCount": 0, "positiveCount": 0, "negativeCount": 0, "averageReturn": None},
            "rows": [],
            "note": "이전 날짜 스냅샷이 생기면 전일 후보의 다음날 움직임을 자동으로 계산합니다.",
        }

    current_by_ticker = {item["ticker"]: item for item in current.get("candidates", [])}
    rows = []
    for item in previous.get("candidates", []):
        ticker = item.get("ticker")
        if not ticker:
            continue
        current_item = current_by_ticker.get(ticker)
        current_series = current_item.get("series", []) if current_item else _load_ohlcv(runs_dir, ticker, series_limit)
        current_close, current_price_date = _latest_close(current_series)
        if current_close is None and current_item:
            current_close = _clean_number(current_item.get("price", {}).get("close"))
        previous_close = _clean_number(item.get("price", {}).get("close"))
        next_return = current_close / previous_close - 1 if current_close and previous_close else None
        rows.append(
            {
                "ticker": ticker,
                "name": item.get("name", ""),
                "previousRank": item.get("rank"),
                "previousScore": item.get("score"),
                "previousStance": item.get("stance", ""),
                "previousClose": previous_close,
                "currentClose": current_close,
                "currentPriceDate": current_price_date,
                "nextReturn": next_return,
                "outcome": "up" if next_return is not None and next_return > 0 else "down" if next_return is not None and next_return < 0 else "pending",
                "catalyst": item.get("catalyst", {}).get("claim", ""),
                "newsQuality": item.get("news", {}).get("relevance", {}).get("label", ""),
            }
        )

    measured = [row for row in rows if row["nextReturn"] is not None]
    average = sum(row["nextReturn"] for row in measured) / len(measured) if measured else None
    return {
        "previousDate": previous.get("archive", {}).get("date"),
        "currentDate": current["archive"]["date"],
        "summary": {
            "trackedCount": len(rows),
            "withPriceCount": len(measured),
            "positiveCount": sum(1 for row in measured if row["nextReturn"] > 0),
            "negativeCount": sum(1 for row in measured if row["nextReturn"] < 0),
            "averageReturn": average,
        },
        "rows": rows,
        "note": "전일 스냅샷의 후보를 현재 수집된 최신 종가와 비교한 사후 점검입니다.",
    }


def _write_archive(payload: dict[str, Any], out_path: Path) -> None:
    archive_dir = out_path.parent / "data"
    archive_dir.mkdir(parents=True, exist_ok=True)
    date_key = payload["archive"]["date"]
    archive_path = archive_dir / f"{date_key}.json"
    archive_path.write_text(json.dumps(_json_ready(payload), ensure_ascii=False, indent=2), encoding="utf-8")

    index_path = archive_dir / "index.json"
    index = _read_json(index_path) or {"latest": None, "dates": []}
    by_date = {item.get("date"): item for item in index.get("dates", []) if isinstance(item, dict)}
    by_date[date_key] = {
        "date": date_key,
        "path": f"data/{date_key}.json",
        "generatedAt": payload["generatedAt"],
        "candidateCount": payload["summary"]["candidateCount"],
        "avgScore": payload["summary"]["avgScore"],
        "outcomeTrackedCount": payload["outcomes"]["summary"]["withPriceCount"],
    }
    dates = [by_date[key] for key in sorted(by_date.keys(), reverse=True)]
    index = {"latest": date_key, "dates": dates}
    index_path.write_text(json.dumps(_json_ready(index), ensure_ascii=False, indent=2), encoding="utf-8")


def build_payload(discovery_csv: Path, runs_dir: Path, top: int, series_limit: int, report_date: str | None = None) -> dict[str, Any]:
    df = pd.read_csv(discovery_csv)
    if "score" in df:
        df = df.sort_values(["score", "top_catalyst_score", "ticker"], ascending=[False, False, True])
    candidates = _build_candidates(df, runs_dir, top=top, series_limit=series_limit)
    themes = _build_themes(candidates)
    summary = _build_summary(candidates)
    focus = next((item["ticker"] for item in candidates if item["series"]), candidates[0]["ticker"] if candidates else "")
    payload = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sourceDiscovery": str(discovery_csv),
        "reportTitle": "Equity Research Copilot",
        "reportSubtitle": "뉴스 촉매, 테마 강도, 차트 구조를 한 화면에서 검증하는 정적 리서치 노트",
        "researchOnly": True,
        "summary": summary,
        "themes": themes,
        "focusTicker": focus,
        "candidates": candidates,
        "analystNotes": [
            "점수는 매수 추천이 아니라 감시 우선순위입니다.",
            "관련성 약함 표시는 기사 주체가 후보 기업과 직접 맞지 않을 수 있다는 의미입니다.",
            "추격 리스크가 높은 후보는 뉴스보다 가격 선반영 여부를 먼저 확인해야 합니다.",
        ],
    }
    date_key = _report_date(payload["generatedAt"], report_date)
    payload["archive"] = {"date": date_key, "path": f"data/{date_key}.json"}
    return payload


def main() -> None:
    root = _project_root()
    parser = argparse.ArgumentParser(description="Export key-free static data for the HTML research report.")
    parser.add_argument("--runs-dir", type=Path, default=root / "runs")
    parser.add_argument("--discovery-csv", type=Path)
    parser.add_argument("--out", type=Path, default=root / "docs" / "report-data.json")
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--series-limit", type=int, default=160)
    parser.add_argument("--date", help="Override archive date as YYYY-MM-DD.")
    parser.add_argument("--no-archive", action="store_true", help="Write only the latest report-data.json.")
    args = parser.parse_args()

    discovery_csv = args.discovery_csv or _latest_discovery(args.runs_dir)
    payload = build_payload(discovery_csv, args.runs_dir, top=args.top, series_limit=args.series_limit, report_date=args.date)
    previous = None if args.no_archive else _previous_snapshot(args.out.parent / "data", payload["archive"]["date"])
    payload["outcomes"] = _build_outcomes(previous, payload, args.runs_dir, args.series_limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(_json_ready(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.no_archive:
        _write_archive(payload, args.out)
    print(f"Wrote {args.out}")
    print(f"Source discovery: {discovery_csv}")
    print(f"Candidates: {payload['summary']['candidateCount']}")
    print(f"Archive date: {payload['archive']['date']}")
    print(f"Outcome rows: {payload['outcomes']['summary']['withPriceCount']}")


if __name__ == "__main__":
    main()
