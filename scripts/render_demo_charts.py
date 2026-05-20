from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples" / "data" / "nvda_synthetic_ohlcv.csv"
OUT = ROOT / "examples" / "charts"
OUT.mkdir(parents=True, exist_ok=True)


def _load() -> pd.DataFrame:
    df = pd.read_csv(DATA, parse_dates=["date"])
    return df


def _candles(ax, data: pd.DataFrame, width: float = 0.65) -> None:
    xs = mdates.date2num(data["date"].dt.to_pydatetime())
    for x, o, h, l, c in zip(xs, data["open"], data["high"], data["low"], data["close"]):
        up = c >= o
        color = "#2ca02c" if up else "#d62728"
        ax.vlines(x, l, h, color=color, linewidth=0.8, alpha=0.85)
        ax.add_patch(
            Rectangle(
                (x - width / 2, min(o, c)),
                width,
                max(abs(c - o), 0.25),
                facecolor=color,
                edgecolor=color,
                alpha=0.72,
            )
        )
    ax.xaxis_date()
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.grid(True, alpha=0.22)


def market_structure(df: pd.DataFrame) -> None:
    peak_ix = int(df["close"].idxmax())
    fig, ax = plt.subplots(figsize=(13, 7.3), dpi=180)
    _candles(ax, df)
    ax.plot(df["date"], df["sma20"], linewidth=1.5, label="20D SMA")
    ax.plot(df["date"], df["sma50"], linewidth=1.5, label="50D SMA")
    ax.axhline(236.54, linestyle="--", linewidth=1.0, color="#6e6e6e")
    ax.axhspan(214, 218, alpha=0.16, color="#9ecae1")
    ax.axhline(222.32, linestyle=":", linewidth=1.2, color="#1f77b4")
    ax.set_ylim(140, 251)
    ax.annotate(
        "Record-high resistance\n$236.54",
        xy=(df["date"].iloc[peak_ix], 236.54),
        xytext=(df["date"].iloc[peak_ix - 14], 247.0),
        arrowprops={"arrowstyle": "->", "lw": 1.0},
        fontsize=9,
        ha="center",
        bbox={"boxstyle": "round,pad=0.22", "fc": "white", "ec": "#cccccc", "alpha": 0.85},
    )
    ax.annotate(
        "Pullback into event risk\ncurrent quote area: $222.32",
        xy=(df["date"].iloc[-1], 222.32),
        xytext=(df["date"].iloc[-36], 229),
        arrowprops={"arrowstyle": "->", "lw": 1.0},
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.22", "fc": "white", "ec": "#cccccc", "alpha": 0.85},
    )
    ax.annotate(
        "Prior breakout / support zone\n$214-$218",
        xy=(df["date"].iloc[-24], 216),
        xytext=(df["date"].iloc[-65], 205),
        arrowprops={"arrowstyle": "->", "lw": 1.0},
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.22", "fc": "white", "ec": "#cccccc", "alpha": 0.85},
    )
    ax.set_title("NVDA - Market Structure Demo: resistance, pullback, support retest", fontsize=12, weight="bold", pad=14)
    ax.set_ylabel("Price, USD")
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT / "nvda_daily_structure.png")
    plt.close(fig)


def momentum_volume(df: pd.DataFrame) -> None:
    peak_ix = int(df["close"].idxmax())
    fig = plt.figure(figsize=(13, 9), dpi=180)
    grid = fig.add_gridspec(3, 1, height_ratios=[2.15, 1.1, 1.0], hspace=0.08)
    ax1 = fig.add_subplot(grid[0])
    ax2 = fig.add_subplot(grid[1], sharex=ax1)
    ax3 = fig.add_subplot(grid[2], sharex=ax1)
    ax1.plot(df["date"], df["close"], label="Close", linewidth=1.5)
    ax1.plot(df["date"], df["sma20"], label="20D SMA", linewidth=1.2)
    ax1.plot(df["date"], df["sma50"], label="50D SMA", linewidth=1.2)
    ax1.axhline(236.54, linestyle="--", linewidth=0.9, color="#6e6e6e")
    ax1.annotate("Higher high into event", xy=(df["date"].iloc[peak_ix], 236.54), xytext=(df["date"].iloc[peak_ix-22], 244), arrowprops={"arrowstyle":"->", "lw":0.9}, fontsize=8.5)
    ax2.plot(df["date"], df["rsi14"], linewidth=1.4)
    ax2.axhline(70, linestyle="--", linewidth=0.9, color="#6e6e6e")
    ax2.axhline(30, linestyle="--", linewidth=0.9, color="#6e6e6e")
    ax2.annotate("RSI cool-down; watch for\nconfirmed lower-high", xy=(df["date"].iloc[-1], df["rsi14"].iloc[-1]), xytext=(df["date"].iloc[-44], 48), arrowprops={"arrowstyle":"->", "lw":0.9}, fontsize=8.5)
    colors = ["#2ca02c" if c >= o else "#d62728" for o, c in zip(df["open"], df["close"])]
    ax3.bar(df["date"], df["volume"] / 1e6, color=colors, alpha=0.62)
    ax3.axhline(df["volume"].rolling(20).mean().iloc[-1] / 1e6, linestyle=":", linewidth=1.0, color="#6e6e6e")
    ax3.annotate("Event-volume expansion", xy=(df["date"].iloc[-1], df["volume"].iloc[-1] / 1e6), xytext=(df["date"].iloc[-56], 130), arrowprops={"arrowstyle":"->", "lw":0.9}, fontsize=8.5)
    for ax in [ax1, ax2, ax3]:
        ax.grid(True, alpha=0.22)
    ax1.legend(loc="upper left")
    ax2.set_ylabel("RSI")
    ax3.set_ylabel("Vol, M")
    ax3.xaxis.set_major_locator(mdates.MonthLocator())
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    fig.suptitle("NVDA - Momentum/Participation Demo: RSI reset + volume confirmation", fontsize=12, weight="bold", y=0.985)
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(OUT / "nvda_momentum_volume.png")
    plt.close(fig)


def event_overlay(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 7.3), dpi=180)
    ax.plot(df["date"], df["close"], linewidth=1.7, label="Close")
    ax.fill_between(df["date"], df["low"], df["high"], alpha=0.12)
    ax.axhline(236.54, linestyle="--", color="#6e6e6e", linewidth=0.9)
    ax.axhspan(214, 218, alpha=0.16, color="#9ecae1")
    event_specs = [
        ("2026-02-25", "Q4 FY26 results", 181, "left"),
        ("2026-03-17", "GTC analyst Q&A", 199, "right"),
        ("2026-05-18", "China/H200 headline", 226, "left"),
        ("2026-05-20", "Q1 FY27 results\nfuture event", 238, "right"),
    ]
    for d, label, y, side in event_specs:
        ts = pd.Timestamp(d)
        ax.axvline(ts, linestyle="--", linewidth=0.9, color="#6e6e6e", alpha=0.65)
        x_text = ts + pd.Timedelta(days=8 if side == "left" else -8)
        ha = "left" if side == "left" else "right"
        ax.annotate(
            label,
            xy=(ts, y),
            xytext=(x_text, y + 8),
            arrowprops={"arrowstyle":"->", "lw":0.85},
            fontsize=8.5,
            ha=ha,
            bbox={"boxstyle":"round,pad=0.22", "fc":"white", "ec":"#cccccc", "alpha":0.86},
        )
    ax.annotate(
        "Interpret event by combining:\nnovelty + price reaction + volume",
        xy=(pd.Timestamp("2026-05-18"), 222.32),
        xytext=(pd.Timestamp("2026-03-24"), 205),
        arrowprops={"arrowstyle": "->", "lw": 1.0},
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#cccccc", "alpha": 0.88},
    )
    ax.set_xlim(df["date"].iloc[0], pd.Timestamp("2026-05-24"))
    ax.set_ylim(140, 252)
    ax.set_title("NVDA - Event Overlay Demo: connect catalysts to price reaction", fontsize=12, weight="bold", pad=14)
    ax.set_ylabel("Price, USD")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.22)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT / "nvda_event_overlay.png")
    plt.close(fig)


def main() -> None:
    df = _load()
    market_structure(df)
    momentum_volume(df)
    event_overlay(df)
    print("Rendered demo charts to", OUT)


if __name__ == "__main__":
    main()
