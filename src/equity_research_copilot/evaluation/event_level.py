from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def evaluate_archived_events(archive_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    snapshots = _load_snapshots(archive_dir)
    if len(snapshots) < 2:
        empty = pd.DataFrame()
        return empty, {"records": 0, "message": "At least two archived snapshots are required."}

    rows: list[dict[str, Any]] = []
    for previous, current in zip(snapshots, snapshots[1:]):
        current_outcomes = {row.get("ticker"): row for row in current.get("outcomes", {}).get("rows", []) if row.get("ticker")}
        current_candidates = {row.get("ticker"): row for row in current.get("candidates", []) if row.get("ticker")}
        for candidate in previous.get("candidates", []):
            ticker = candidate.get("ticker")
            if not ticker:
                continue
            outcome = current_outcomes.get(ticker)
            next_return = _number(outcome.get("nextReturn")) if outcome else _next_return_from_candidate(candidate, current_candidates.get(ticker))
            catalyst = candidate.get("catalyst", {}) or {}
            setup = candidate.get("setup", {}) or {}
            news = candidate.get("news", {}) or {}
            risk = candidate.get("risk", {}) or {}
            event = _primary_event(catalyst)
            hit = None if next_return is None else int(next_return > 0)
            rows.append(
                {
                    "as_of": previous.get("archive", {}).get("date", ""),
                    "evaluated_on": current.get("archive", {}).get("date", ""),
                    "ticker": ticker,
                    "name": candidate.get("name", ""),
                    "rank": candidate.get("rank"),
                    "score": _number(candidate.get("score")),
                    "event_type": event.get("event_type") or catalyst.get("type") or "unknown",
                    "event_subtype": event.get("event_subtype") or "unknown",
                    "event_direction": event.get("direction") or "mixed",
                    "setup_action": setup.get("action") or "unknown",
                    "setup_score": _number(setup.get("score")),
                    "news_quality": (news.get("relevance") or {}).get("label", ""),
                    "news_relevance_level": (news.get("relevance") or {}).get("level", ""),
                    "catalyst_score": _number(catalyst.get("score")),
                    "catalyst_quality_score": _number(catalyst.get("qualityScore")),
                    "market_reaction_score": _number(candidate.get("marketReaction", {}).get("reactionScore")),
                    "priced_in_risk": event.get("priced_in_risk") or "",
                    "chase_penalty": _number(risk.get("chasePenalty")),
                    "previous_close": _number(candidate.get("price", {}).get("close")),
                    "next_return": next_return,
                    "hit": hit,
                    "claim": catalyst.get("claim", ""),
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return df, {"records": 0, "message": "No event rows found in snapshots."}
    measured = df[df["next_return"].notna()].copy()
    summary: dict[str, Any] = {
        "records": int(len(df)),
        "measured_records": int(len(measured)),
        "avg_next_return": float(measured["next_return"].mean()) if not measured.empty else None,
        "hit_rate": float(measured["hit"].mean()) if not measured.empty else None,
        "by_event_type": _group_summary(measured, "event_type"),
        "by_setup_action": _group_summary(measured, "setup_action"),
        "by_news_relevance": _group_summary(measured, "news_relevance_level"),
    }
    return df, summary


def _load_snapshots(archive_dir: Path) -> list[dict[str, Any]]:
    index_path = archive_dir / "index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            index = {}
        dates = [item.get("date") for item in index.get("dates", []) if isinstance(item, dict)]
    else:
        dates = [path.stem for path in archive_dir.glob("*.json") if path.name != "index.json"]
    snapshots: list[dict[str, Any]] = []
    for date_key in sorted(str(date) for date in dates if date):
        path = archive_dir / f"{date_key}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            snapshots.append(payload)
    return snapshots


def _primary_event(catalyst: dict[str, Any]) -> dict[str, Any]:
    events = catalyst.get("events")
    if isinstance(events, list) and events:
        event = events[0]
        return event if isinstance(event, dict) else {}
    return {}


def _next_return_from_candidate(previous: dict[str, Any], current: dict[str, Any] | None) -> float | None:
    if not current:
        return None
    previous_close = _number(previous.get("price", {}).get("close"))
    current_close = _number(current.get("price", {}).get("close"))
    if not previous_close or current_close is None:
        return None
    return current_close / previous_close - 1


def _group_summary(df: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    if df.empty or column not in df:
        return []
    grouped = []
    for value, group in df.groupby(column, dropna=False):
        grouped.append(
            {
                column: "" if pd.isna(value) else value,
                "count": int(len(group)),
                "hit_rate": float(group["hit"].mean()) if "hit" in group else None,
                "avg_next_return": float(group["next_return"].mean()) if "next_return" in group else None,
                "avg_catalyst_score": float(group["catalyst_score"].mean()) if "catalyst_score" in group else None,
            }
        )
    return sorted(grouped, key=lambda item: (item["count"], item.get("avg_next_return") or 0), reverse=True)


def _number(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
