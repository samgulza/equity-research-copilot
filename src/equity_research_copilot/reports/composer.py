from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any

import pandas as pd

from equity_research_copilot.memory import ThesisRecord
from equity_research_copilot.news.catalyst import CatalystEvent
from equity_research_copilot.technical.structure import TechnicalSummary


REPORT_TEMPLATE = Template("""
# ${ticker} Research Memo

## Verdict

${verdict}

## Technical Summary

${technical_summary}

## Catalyst Summary

${catalyst_summary}

## Scenarios

${scenarios}

## Risk / Invalidation

${risks}
""")


def write_markdown_report(path: str | Path, **kwargs) -> Path:
    out = Path(path)
    out.write_text(REPORT_TEMPLATE.substitute(**kwargs), encoding="utf-8")
    return out


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _rel(path: Path, base: Path) -> str:
    if not path.is_absolute():
        path = path.resolve()
    if not base.is_absolute():
        base = base.resolve()
    try:
        return str(path.relative_to(base.parent))
    except ValueError:
        import os

        return os.path.relpath(path, base.parent)


def compose_deep_dive_markdown(
    *,
    ticker: str,
    df: pd.DataFrame,
    technical: TechnicalSummary,
    chart_paths: dict[str, Path],
    provider: str,
    snapshot_at: str,
    fundamentals: dict[str, Any] | None = None,
    catalysts: list[CatalystEvent] | None = None,
    thesis_history: list[ThesisRecord] | None = None,
    report_path: Path | None = None,
) -> str:
    recent = df.tail(60)
    last = df.iloc[-1]
    first = df.iloc[0]
    close = float(last["close"])
    start_close = float(first["close"])
    period_return = close / start_close - 1
    high_60 = float(recent["high"].max())
    low_60 = float(recent["low"].min())
    vol = int(float(last["volume"]))
    vol_avg = float(last.get("volume_20d", 0) or 0)
    vol_ratio = float(vol / vol_avg) if vol_avg else float("nan")
    rsi = float(last.get("rsi14", 50) or 50)
    macd = float(last.get("macd", 0) or 0)
    macd_signal = float(last.get("macd_signal", 0) or 0)

    base = report_path or Path(".")
    chart_lines = []
    labels = {
        "market_structure": "Market structure",
        "momentum_volume": "Momentum and volume",
        "event_overlay": "Event overlay scaffold",
    }
    for key, path in chart_paths.items():
        chart_lines.append(f"### {labels.get(key, key)}\n\n![{labels.get(key, key)}]({_rel(path, base)})")

    priced_in = (
        "상승 추세가 유지되지만 단기 고점권에 가까워, 좋은 뉴스가 이미 가격에 일부 반영됐을 가능성을 같이 봐야 합니다."
        if close > (technical.resistance_levels[0] if technical.resistance_levels else close)
        else "가격이 저항선 아래에서 쉬고 있어, 새 catalyst가 실제 매수세로 연결되는지 확인해야 합니다."
    )
    verdict = "WATCH"
    if technical.market_structure.startswith("uptrend") and rsi < 72:
        verdict = "CONSTRUCTIVE WATCH"
    elif technical.market_structure.startswith("downtrend"):
        verdict = "RISK WATCH"

    fundamentals_note = "No fundamental endpoint succeeded in this run."
    if fundamentals:
        endpoint = fundamentals.get("endpoint")
        warning = fundamentals.get("warning")
        if endpoint:
            records = fundamentals.get("data") or []
            fundamentals_note = f"OpenBB fundamental snapshot endpoint: {endpoint}; records: {len(records) if isinstance(records, list) else 'available'}."
        elif warning:
            fundamentals_note = warning

    catalyst_rows = []
    evidence_rows = []
    for event in (catalysts or [])[:8]:
        source = event.evidence_sources[0] if event.evidence_sources else ""
        catalyst_rows.append(
            f"| {event.event_type}/{event.event_subtype} | {event.direction} | {event.affected_driver} | {event.materiality_score:.2f} | {event.novelty_score:.2f} | {event.score:.2f} | {event.priced_in_risk} | {event.claim} | {source} |"
        )
        evidence = event.evidence_spans[0].quote if event.evidence_spans else ""
        counter = event.counter_evidence[0].quote if event.counter_evidence else ""
        if evidence or counter:
            evidence_rows.append(f"- **{event.event_type}**: {evidence or 'No extracted span.'}" + (f" Counter: {counter}" if counter else ""))
    catalyst_text = "\n".join(catalyst_rows) if catalyst_rows else "| - | - | - | - | - | - | - | No live catalyst found in configured sources. | - |"
    evidence_text = "\n".join(evidence_rows) if evidence_rows else "- No article-body evidence span was extracted in this run."

    history_rows = []
    for item in (thesis_history or [])[-5:]:
        history_rows.append(f"| {item.as_of} | {item.verdict} | {item.confidence:.2f} | {item.close:.2f} | {item.top_catalyst or '-'} |")
    history_text = "\n".join(history_rows) if history_rows else "| - | - | - | - | No prior thesis memory for this ticker. |"

    return f"""# {ticker.upper()} Deep-Dive Research Memo

> Research-only output. This is not investment advice and does not trigger orders.

## 1. Verdict

| Field | Value |
|---|---|
| Ticker | {ticker.upper()} |
| Snapshot | {snapshot_at} |
| Provider | OpenBB / {provider} |
| Verdict | **{verdict}** |
| Confidence | {technical.confidence:.2f} |
| Last close | {close:.2f} |
| Period return | {_pct(period_return)} |

## 2. Technical Structure

- Market structure: **{technical.market_structure}**
- Momentum state: **{technical.momentum_state}**
- Volume state: **{technical.volume_state}**
- 60D high/low: **{high_60:.2f} / {low_60:.2f}**
- Support levels: {', '.join(f'{x:.2f}' for x in technical.support_levels)}
- Resistance levels: {', '.join(f'{x:.2f}' for x in technical.resistance_levels)}
- Invalidation levels: {', '.join(f'{x:.2f}' for x in technical.invalidation_levels)}

## 3. Chart Annotations

{chr(10).join(chart_lines)}

## 4. Momentum / Participation

- RSI14: **{rsi:.2f}**
- MACD / signal: **{macd:.2f} / {macd_signal:.2f}**
- Latest volume: **{vol:,}**
- Volume vs 20D average: **{vol_ratio:.2f}x**

## 5. News / Catalyst Cards

| Type | Direction | Driver | Materiality | Novelty | Score | Priced-in risk | Claim | Source |
|---|---|---|---:|---:|---:|---|---|---|
{catalyst_text}

## 6. Priced-In Assessment

{priced_in}

### Evidence / Counter Evidence

{evidence_text}

## 7. Scenario Table

| Scenario | Conditions | What to watch |
|---|---|---|
| Bull | Holds support and breaks resistance with participation | Close above {technical.resistance_levels[-1] if technical.resistance_levels else high_60:.2f}, volume expansion |
| Base | Range continues near current levels | Choppy action between support and resistance |
| Bear | Support breaks or negative catalyst dominates | Close below {technical.invalidation_levels[0] if technical.invalidation_levels else low_60:.2f} |

## 8. Risks and Counter-Thesis

- A good company narrative can still be fully priced in.
- Technical indicators are descriptive, not causal.
- Catalyst extraction is structured and evidence-first, but source relevance and materiality still need analyst review.
- OpenBB provider coverage and endpoint behavior can change by version.

## 9. Watchpoints

1. Breakout confirmation above resistance.
2. Support/invalidation loss.
3. Volume expansion on the move, not only direction.
4. Fresh catalyst quality and source relevance.

## 10. Thesis Memory

| As of | Verdict | Confidence | Close | Top catalyst |
|---|---|---:|---:|---|
{history_text}

## 11. Data / Source Appendix

- Price source: OpenBB {provider} equity price historical endpoint.
- Rows: {len(df)}
- Date range: {pd.to_datetime(df['date']).iloc[0].date()} to {pd.to_datetime(df['date']).iloc[-1].date()}
- Fundamental snapshot: {fundamentals_note}
- Catalyst count: {len(catalysts or [])}
"""


def write_text_pdf(markdown: str, path: str | Path, title: str, base_dir: str | Path | None = None) -> Path:
    import re

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    base = Path(base_dir) if base_dir is not None else out.parent
    styles = getSampleStyleSheet()
    font_candidates = [
        Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
        Path("/System/Library/Fonts/Supplemental/NotoSansGothic-Regular.ttf"),
    ]
    for font_path in font_candidates:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont("KR-Regular", str(font_path)))
            for style in styles.byName.values():
                style.fontName = "KR-Regular"
            break
    for name in ("BodyText", "Normal"):
        styles[name].fontSize = 8.5
        styles[name].leading = 11
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    lines = markdown.splitlines()
    idx = 0
    while idx < len(lines):
        raw = lines[idx]
        line = raw.strip()
        if not line:
            story.append(Spacer(1, 6))
            idx += 1
            continue
        image_match = re.match(r"!\[[^\]]*\]\(([^)]+)\)", line)
        if image_match:
            image_path = Path(image_match.group(1))
            if not image_path.is_absolute():
                image_path = base / image_path
            if image_path.exists():
                img = Image(str(image_path))
                max_width = 6.8 * inch
                ratio = img.imageHeight / img.imageWidth
                img.drawWidth = max_width
                img.drawHeight = max_width * ratio
                story.extend([img, Spacer(1, 8)])
            idx += 1
            continue
        if line.startswith("|"):
            table_lines = []
            while idx < len(lines) and lines[idx].strip().startswith("|"):
                table_lines.append(lines[idx].strip())
                idx += 1
            rows = []
            for table_line in table_lines:
                cells = [cell.strip() for cell in table_line.strip("|").split("|")]
                if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    continue
                rows.append([Paragraph(cell or " ", styles["BodyText"]) for cell in cells])
            if rows:
                available_width = 9.2 * inch
                col_width = available_width / max(1, len(rows[0]))
                table = Table(rows, colWidths=[col_width] * len(rows[0]), repeatRows=1)
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f4f7")),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d5dd")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ]
                    )
                )
                story.extend([table, Spacer(1, 8)])
            continue
        if line.startswith("# "):
            story.append(Paragraph(line[2:], styles["Title"]))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], styles["Heading2"]))
        elif line.startswith("### "):
            story.append(Paragraph(line[4:], styles["Heading3"]))
        elif line.startswith("- "):
            story.append(Paragraph("&bull; " + line[2:], styles["BodyText"]))
        else:
            story.append(Paragraph(line, styles["BodyText"]))
        idx += 1
    SimpleDocTemplate(str(out), pagesize=landscape(letter), title=title).build(story)
    return out
