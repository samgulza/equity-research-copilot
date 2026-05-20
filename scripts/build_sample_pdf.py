from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    KeepTogether,
    ListFlowable,
    ListItem,
)
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "reports" / "NVDA_sample_report_polished.pdf"
CHART_DIR = ROOT / "examples" / "charts"
FONT_REG = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"

pdfmetrics.registerFont(TTFont("Nanum", FONT_REG))
pdfmetrics.registerFont(TTFont("Nanum-Bold", FONT_BOLD))

PAGE_W, PAGE_H = letter
MARGIN_X = 0.58 * inch
MARGIN_Y = 0.52 * inch

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="TitleKR", parent=styles["Title"], fontName="Nanum-Bold", fontSize=19, leading=24,
    alignment=TA_CENTER, spaceAfter=6,
))
styles.add(ParagraphStyle(
    name="SubtitleKR", parent=styles["Normal"], fontName="Nanum", fontSize=10.5, leading=14,
    alignment=TA_CENTER, textColor=colors.HexColor("#333333"), spaceAfter=14,
))
styles.add(ParagraphStyle(
    name="H1KR", parent=styles["Heading1"], fontName="Nanum-Bold", fontSize=14, leading=18,
    spaceBefore=12, spaceAfter=8,
))
styles.add(ParagraphStyle(
    name="H2KR", parent=styles["Heading2"], fontName="Nanum-Bold", fontSize=11.2, leading=15,
    spaceBefore=9, spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="BodyKR", parent=styles["BodyText"], fontName="Nanum", fontSize=8.6, leading=12.2,
    spaceAfter=6,
))
styles.add(ParagraphStyle(
    name="SmallKR", parent=styles["BodyText"], fontName="Nanum", fontSize=7.5, leading=10,
    spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="CalloutKR", parent=styles["BodyText"], fontName="Nanum", fontSize=8.5, leading=12,
    backColor=colors.HexColor("#F4F6F8"), borderColor=colors.HexColor("#D7DEE7"),
    borderWidth=0.6, borderPadding=6, spaceBefore=4, spaceAfter=8,
))
styles.add(ParagraphStyle(
    name="CellKR", parent=styles["BodyText"], fontName="Nanum", fontSize=7.3, leading=9.4,
))
styles.add(ParagraphStyle(
    name="CellBoldKR", parent=styles["BodyText"], fontName="Nanum-Bold", fontSize=7.3, leading=9.4,
))


def p(text: str, style: str = "BodyKR") -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), styles[style])


def bullet(items: list[str]) -> ListFlowable:
    return ListFlowable(
        [ListItem(p(item, "BodyKR"), bulletColor=colors.HexColor("#333333")) for item in items],
        bulletType="bullet", start="circle", leftIndent=16, bulletFontName="Nanum", bulletFontSize=6,
    )


def table(rows: list[list[str]], widths: list[float], header: bool = True) -> Table:
    converted = []
    for i, row in enumerate(rows):
        converted.append([p(cell, "CellBoldKR" if header and i == 0 else "CellKR") for cell in row])
    t = Table(converted, colWidths=widths, hAlign="LEFT", repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D7DE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2F7")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#7A869A")),
        ]
    t.setStyle(TableStyle(style))
    return t


def image(path: Path, width: float) -> Image:
    img = Image(str(path))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = width
    img.drawHeight = width * ratio
    return img


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Nanum", 7)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(MARGIN_X, 0.32 * inch, "Research-only sample - OpenBB + OpenClaw Equity Research Copilot")
    canvas.drawRightString(PAGE_W - MARGIN_X, 0.32 * inch, f"{doc.page}")
    canvas.restoreState()


def build() -> Path:
    doc = BaseDocTemplate(
        str(OUT),
        pagesize=letter,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_Y,
        bottomMargin=0.55 * inch,
        title="NVDA Sample Deep-Dive Research Report",
        author="OpenBB + OpenClaw Equity Research Copilot",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=header_footer)])

    w = doc.width
    story = []
    story += [
        p("NVDA Sample Deep-Dive Research Report", "TitleKR"),
        p("News-to-Catalyst + Annotated Technical Chart Pack | 2026-05-19 Asia/Seoul", "SubtitleKR"),
        p("주의: 이 문서는 리서치 코파일럿 산출물 예시다. 매수/매도 권유가 아니며, 차트 이미지는 실시간 OHLCV 접근 제한 때문에 synthetic OHLCV fixture로 만든 annotation demo다. 실제 운용 시 OpenBB OHLCV와 provider snapshot으로 재렌더링한다.", "CalloutKR"),
        p("1. Executive Summary", "H1KR"),
        table([
            ["항목", "판단"],
            ["Ticker", "NVDA"],
            ["Current quote anchor", "USD 222.32, latest trade May 19 00:15 UTC"],
            ["Overall label", "WATCH / Bullish catalyst, high event risk"],
            ["Time horizon", "5D event reaction + 20D swing"],
            ["Confidence", "0.58 / 1.00"],
            ["Key risk", "Earnings/guidance expectations already high; China/H200 approval uncertainty; event-volatility compression risk"],
        ], [1.55*inch, w-1.55*inch]),
        Spacer(1, 6),
        p("Thesis: NVDA still has a structurally bullish AI/data-center narrative, but the setup is not a clean low-risk entry. The next move is likely earnings-driven: headline beat alone may be insufficient because consensus expectations are already elevated. The most important variables are Q2 guidance, data-center trajectory, gross margin, and China/H200 commentary."),
        p("2. Source-Aware Context", "H1KR"),
        bullet([
            "NVIDIA reported Q4 FY2026 revenue of $68.1B, Data Center revenue of $62.3B, and FY2026 revenue of $215.9B.",
            "NVIDIA is scheduled to report Q1 FY2027 results on 2026-05-20 2:00 PM PT.",
            "Quote anchor: $222.32; intraday high $230.62; intraday low $218.55; volume 146.3M; market cap about $5.44T; P/E about 54.49.",
            "Consensus previews indicate high expectations: FactSet-based preview cited EPS $1.75 and revenue $78.85B, with current-quarter expectations around EPS $1.95 and revenue $87.09B.",
            "Reuters reported unresolved Chinese approval for H200 despite U.S. licenses, making China optionality material but not fully confirmed.",
        ]),
    ]

    story.append(KeepTogether([
        p("3. Annotated Chart Pack", "H1KR"),
        p("3.1 Daily Market Structure", "H2KR"),
        image(CHART_DIR / "nvda_daily_structure.png", w),
        p("차트 해석: record-high resistance는 $236.54, support/invalidation 관찰 구간은 $214-$218이다. 현재가가 이 구간 위에서 유지되면 constructive pullback으로 볼 수 있지만, 실적 이벤트 이후 $236.54를 거래량 동반으로 회복하지 못하면 good news priced-in 위험이 커진다."),
    ]))

    story.append(KeepTogether([
        p("3.2 Momentum and Participation", "H2KR"),
        image(CHART_DIR / "nvda_momentum_volume.png", w),
        p("차트 해석: RSI가 과열권에서 식는 것은 자체로 bearish가 아니다. 문제는 가격이 고점을 갱신하지 못하는 동안 RSI lower-high와 하락 거래량 증가가 동시에 나타나는 경우다. 이벤트 전후 volume expansion은 방향보다 정보 진단력이 더 크다."),
    ]))

    story.append(KeepTogether([
        p("3.3 Event Overlay", "H2KR"),
        image(CHART_DIR / "nvda_event_overlay.png", w),
        p("차트 해석: Q4 FY2026 실적은 data-center thesis를 검증했지만 이제는 상당 부분 기대에 편입되어 있다. 2026-05-18 China/H200 headline은 material optionality이나, approval uncertainty 때문에 full catalyst로 확정하기 어렵다."),
    ]))

    story += [
        p("4. Technical Analysis", "H1KR"),
        p("Market structure: constructive but extended. Broad trend is positive because price remains near record-high territory, but the pullback into an earnings event means the next impulse requires confirmation."),
        table([
            ["Level", "Type", "Why it matters"],
            ["$236.54", "Resistance / breakout trigger", "Recent record-high anchor. A clean break suggests repricing of guidance or China optionality."],
            ["$222.32", "Current quote zone", "Reference price; not a thesis level by itself."],
            ["$214-$218", "Support / failed-breakout test", "Prior breakout/support band. Loss weakens the swing setup."],
            ["<$214", "Invalidation", "Break below support implies bullish catalyst was priced-in or rejected."],
        ], [0.9*inch, 1.5*inch, w-2.4*inch]),
        p("Momentum: not broken, but no longer a clean chase setup. Bullish confirmation requires RSI reset without support loss, short-term momentum turning up after the event, and a volume-confirmed breakout above the prior high."),
        p("Volume: elevated participation makes the post-event move diagnostically valuable. A rally on high volume implies fresh buyers are willing to underwrite already-high expectations; a selloff despite good headline numbers implies priced-in risk."),
        p("5. News-to-Catalyst Analysis", "H1KR"),
    ]

    catalysts = [
        ("Q1 FY2027 earnings", "Mixed", "Revenue, margin, guidance", "0.90", "0.98", "High", "Highly material, but expectations are elevated. Beat alone may not be enough."),
        ("Data Center growth", "Positive", "AI infrastructure revenue", "0.40", "0.95", "High", "Validates long-term thesis, but largely known."),
        ("China/H200 reopening", "Positive optionality", "Incremental China revenue", "0.75", "0.80", "Medium", "U.S. license is constructive; Chinese approval uncertainty prevents full confirmation."),
        ("Options/event volatility", "Mixed", "Positioning and implied move", "0.65", "0.60", "Medium", "Raises two-sided event risk; useful for alerting, not enough for directional thesis."),
        ("Valuation", "Negative risk", "Multiple compression", "0.30", "0.75", "Medium", "High P/E raises bar for guidance and margin performance."),
    ]
    for cat in catalysts:
        story.append(KeepTogether([
            table([
                ["Catalyst", "Direction", "Driver", "Novelty", "Materiality", "Priced-in risk"],
                list(cat[:6]),
            ], [1.45*inch, 1.15*inch, 1.65*inch, 0.75*inch, 0.8*inch, 0.9*inch]),
            p(f"Interpretation: {cat[6]}", "SmallKR"),
            Spacer(1, 4),
        ]))

    story += [
        p("6. Combined Interpretation", "H1KR"),
        p("Integrated view: bullish narrative, but not asymmetric unless guidance exceeds expectations or price confirms with breakout. The technical side is constructive but vulnerable to failed-breakout behavior; the news side is strong but partly consensus; the price-reaction side says reclaiming $236.54 matters more than headline positivity."),
        p("7. Scenario Analysis", "H1KR"),
        table([
            ["Scenario", "Conditions", "Expected price behavior", "Confidence"],
            ["Bull case", "Q1 beat + Q2 guide materially above consensus + constructive China commentary + volume breakout", "Break above $236.54; continuation toward higher range", "0.32"],
            ["Base case", "Q1 beat but guide around consensus; China remains unresolved", "Chop between $214-$236; post-earnings fade possible", "0.43"],
            ["Bear case", "Guidance/margin disappointment or China commentary weak; support loss", "Break below $214-$218; failed-breakout risk", "0.25"],
        ], [0.9*inch, 2.35*inch, 2.3*inch, 0.75*inch]),
        p("8. Invalidation / Risk Controls", "H1KR"),
        bullet([
            "Price loses the $214-$218 support band after the print.",
            "Good headline results fail to generate sustained buying.",
            "Data-center growth or gross margin commentary disappoints relative to expectations.",
            "China/H200 commentary remains blocked or materially worsens.",
            "Broad AI trade reverses after Google I/O / NVDA earnings week.",
        ]),
        p("9. Watchpoints", "H1KR"),
        bullet([
            "Q1 FY2027 earnings release: 2026-05-20 2:00 PM PT.",
            "Q2 revenue guidance: whether the market reads it as merely good or actually better than expected.",
            "Data Center revenue and margin commentary.",
            "China/H200 approval and revenue contribution language.",
            "Breakout level: $236.54; support/invalidation: $214-$218.",
            "Volume confirmation on the first full session after earnings.",
        ]),
        p("10. Critic Memo", "H1KR"),
        p("Potential overclaim: the long-term AI thesis is well known, so the report should not treat familiar data-center growth as a new catalyst."),
        p("Evidence gap: actual OHLCV chart should be regenerated from OpenBB in production. This sample chart is an annotation demo."),
        p("Main uncertainty: whether high consensus and options positioning create a sell-the-news response despite strong reported numbers."),
        p("11. Research-Only Disclaimer", "H1KR"),
        p("This document is a research-assistance example. It is not investment advice, a recommendation, or an instruction to buy or sell securities."),
        p("12. Source Appendix", "H1KR"),
        bullet([
            "NVIDIA Newsroom: Q4 FY2026 and fiscal 2026 results, 2026-02-25.",
            "NVIDIA Investor Relations: Q1 FY2027 financial results event, 2026-05-20 2:00 PM PT.",
            "Market quote snapshot: NVDA, 2026-05-19 UTC.",
            "Investor's Business Daily: NVDA Q1 FY2027 earnings preview.",
            "Reuters: NVIDIA CEO on China market/H200 approval, 2026-05-18.",
        ]),
    ]

    doc.build(story)
    regular = ROOT / "examples" / "reports" / "NVDA_sample_report.pdf"
    if regular != OUT:
        regular.write_bytes(OUT.read_bytes())
    return OUT


if __name__ == "__main__":
    print(build())
