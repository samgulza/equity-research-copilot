from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def register_korean_font(styles) -> str:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
        Path("/System/Library/Fonts/Supplemental/NotoSansGothic-Regular.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    for font_path in candidates:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont("KR-Regular", str(font_path)))
            for style in styles.byName.values():
                style.fontName = "KR-Regular"
            return "KR-Regular"
    return "Helvetica"


def p(text: str, style) -> Paragraph:
    return Paragraph(escape(str(text or "")).replace("\n", "<br/>"), style)


def chart_path(root: Path, ticker: str, kind: str) -> Path | None:
    stem = ticker.lower()
    path = root / ticker / "charts" / f"{stem}_{kind}.png"
    return path if path.exists() else None


def headline_items(value: str, limit: int = 4) -> list[str]:
    items = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    return items[:limit]


def build_pdf(csv_path: Path, out_path: Path, runs_dir: Path, top: int) -> Path:
    df = pd.read_csv(csv_path).head(top)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    font = register_korean_font(styles)
    body = ParagraphStyle("KRBody", parent=styles["BodyText"], fontName=font, fontSize=9.2, leading=12)
    small = ParagraphStyle("KRSmall", parent=body, fontSize=8.2, leading=10)
    title = ParagraphStyle("KRTitle", parent=styles["Title"], fontName=font, fontSize=19, leading=24, textColor=colors.HexColor("#111827"))
    h2 = ParagraphStyle("KRH2", parent=styles["Heading2"], fontName=font, fontSize=13.5, leading=17, textColor=colors.HexColor("#1f2937"))
    h3 = ParagraphStyle("KRH3", parent=styles["Heading3"], fontName=font, fontSize=11.5, leading=14, textColor=colors.HexColor("#1f2937"))

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="동적 종목 후보 리포트",
    )
    story = [
        Paragraph("동적 종목 후보 리포트", title),
        p("뉴스 catalyst와 차트 구조를 함께 본 감시 후보입니다. 매수/매도 추천이 아닙니다.", body),
        Spacer(1, 8),
    ]

    summary_rows = [[p("후보", small), p("시장", small), p("점수", small), p("판정", small), p("차트", small), p("핵심 뉴스", small)]]
    for _, row in df.iterrows():
        summary_rows.append(
            [
                p(row.get("ticker_name", row.get("ticker", "")), small),
                p(row.get("market", ""), small),
                p(f"{row.get('score', 0):.3f}", small),
                p(row.get("agent_view", ""), small),
                p(f"{row.get('market_structure', '')}<br/>{row.get('momentum', '')}", small),
                p(row.get("top_catalyst", ""), small),
            ]
        )
    summary_table = Table(summary_rows, colWidths=[32 * mm, 13 * mm, 13 * mm, 25 * mm, 38 * mm, 62 * mm], repeatRows=1)
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d5dd")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([summary_table, PageBreak()])

    for idx, row in df.iterrows():
        ticker = str(row.get("ticker", ""))
        ticker_name = str(row.get("ticker_name", ticker))
        story.append(Paragraph(f"{idx + 1}. {ticker_name}", h2))
        meta = (
            f"시장: {row.get('market', '')}  |  점수: {float(row.get('score', 0)):.3f}  |  "
            f"차트: {row.get('market_structure', '')} / {row.get('momentum', '')}"
        )
        story.extend([p(meta, body), Spacer(1, 4)])
        story.append(p(f"<b>뉴스 해석</b>: {row.get('news_read', '')}", body))
        story.append(p(f"<b>핵심 뉴스</b>: {row.get('top_catalyst', '')}", body))
        story.append(p(f"<b>에이전트 판정</b>: {row.get('agent_view', '')} - {row.get('chase_risk_reason', '')}", body))
        story.append(p(f"<b>20거래일 수익률 / 추격위험 감점</b>: {row.get('recent_return_20d', '')} / {row.get('chase_risk_penalty', '')}", body))
        story.append(
            p(
                f"<b>뉴스 분류</b>: 긍정 {row.get('news_positive_count', 0)} / "
                f"부정 {row.get('news_negative_count', 0)} / 중립·혼재 {row.get('news_mixed_count', 0)}",
                body,
            )
        )
        story.append(p(f"<b>지지/저항</b>: {row.get('support', '')} / {row.get('resistance', '')}", body))
        story.append(Spacer(1, 6))

        charts = [chart_path(runs_dir, ticker, "market_structure"), chart_path(runs_dir, ticker, "momentum_volume")]
        image_cells = []
        for path in charts:
            if path:
                img = Image(str(path))
                img.drawWidth = 82 * mm
                img.drawHeight = 46 * mm
                image_cells.append(img)
        if image_cells:
            while len(image_cells) < 2:
                image_cells.append(p("차트 없음", small))
            chart_table = Table([image_cells], colWidths=[88 * mm, 88 * mm])
            chart_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.extend([chart_table, Spacer(1, 8)])

        story.append(Paragraph("주요 기사", h3))
        bullets = headline_items(str(row.get("news_headlines", "")))
        if not bullets:
            bullets = ["관련 기사 없음"]
        for item in bullets:
            story.append(p(f"• {item}", small))
        story.append(PageBreak())

    doc.build(story)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--top", type=int, default=6)
    args = parser.parse_args()
    print(build_pdf(Path(args.csv), Path(args.out), Path(args.runs_dir), args.top))


if __name__ == "__main__":
    main()
