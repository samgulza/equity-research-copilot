from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass
class ThesisRecord:
    ticker: str
    as_of: str
    verdict: str
    confidence: float
    close: float
    horizon_days: int
    support: float
    resistance: float
    catalyst_count: int
    top_catalyst: str
    report_path: str
    evidence_hash: str


def evidence_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def append_record(path: str | Path, record: ThesisRecord) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    return out


def load_records(path: str | Path, ticker: str | None = None) -> list[ThesisRecord]:
    src = Path(path)
    if not src.exists():
        return []
    rows = []
    with src.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if ticker and data.get("ticker") != ticker.upper():
                continue
            rows.append(ThesisRecord(**data))
    return rows


def recent_records(path: str | Path, ticker: str, limit: int = 3) -> list[ThesisRecord]:
    return load_records(path, ticker=ticker)[-limit:]
