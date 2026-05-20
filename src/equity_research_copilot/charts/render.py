from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle


def render_structure_chart(df: pd.DataFrame, out_path: str | Path, title: str = "Structure Chart") -> Path:
    path = Path(out_path)
    fig, ax = plt.subplots(figsize=(12, 7), dpi=150)
    ax.plot(pd.to_datetime(df["date"]), df["close"], label="Close")
    for col in ["sma20", "sma50"]:
        if col in df:
            ax.plot(pd.to_datetime(df["date"]), df[col], label=col.upper())
    ax.set_title(title)
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.25)
    ax.legend()
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def _candles(ax, df: pd.DataFrame, width: float = 0.65) -> None:
    dates = pd.to_datetime(df["date"])
    xs = mdates.date2num(dates.dt.to_pydatetime())
    for x, row in zip(xs, df.itertuples(index=False)):
        up = row.close >= row.open
        color = "#1f8a4c" if up else "#c23b3b"
        ax.vlines(x, row.low, row.high, color=color, linewidth=0.8, alpha=0.85)
        ax.add_patch(
            Rectangle(
                (x - width / 2, min(row.open, row.close)),
                width,
                max(abs(row.close - row.open), 0.01),
                facecolor=color,
                edgecolor=color,
                alpha=0.72,
            )
        )
    ax.xaxis_date()


def render_market_structure_chart(df: pd.DataFrame, out_path: str | Path, symbol: str) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    recent = df.tail(120).copy()
    current = float(recent["close"].iloc[-1])
    high = float(recent["high"].max())
    low = float(recent["low"].min())
    support = float(recent["low"].tail(60).quantile(0.2))
    resistance = float(recent["high"].tail(60).quantile(0.8))

    fig, ax = plt.subplots(figsize=(13, 7.3), dpi=160)
    _candles(ax, recent)
    for col, label in [("sma20", "20D SMA"), ("sma50", "50D SMA"), ("sma100", "100D SMA")]:
        if col in recent:
            ax.plot(pd.to_datetime(recent["date"]), recent[col], linewidth=1.2, label=label)
    ax.axhline(current, linestyle=":", linewidth=1.1, color="#1f77b4", label=f"Last close {current:.2f}")
    ax.axhspan(support * 0.995, support * 1.005, alpha=0.18, color="#9ecae1", label="Support watch zone")
    ax.axhline(resistance, linestyle="--", linewidth=1.0, color="#6e6e6e", label="Resistance watch")
    ax.annotate(
        f"Resistance watch\n{resistance:.2f}",
        xy=(pd.to_datetime(recent["date"]).iloc[-10], resistance),
        xytext=(pd.to_datetime(recent["date"]).iloc[max(0, len(recent) - 45)], high),
        arrowprops={"arrowstyle": "->", "lw": 0.9},
        fontsize=8.5,
        bbox={"boxstyle": "round,pad=0.22", "fc": "white", "ec": "#cccccc", "alpha": 0.88},
    )
    ax.annotate(
        f"Support/invalidation area\n~{support:.2f}",
        xy=(pd.to_datetime(recent["date"]).iloc[-20], support),
        xytext=(pd.to_datetime(recent["date"]).iloc[max(0, len(recent) - 65)], low + (high - low) * 0.15),
        arrowprops={"arrowstyle": "->", "lw": 0.9},
        fontsize=8.5,
        bbox={"boxstyle": "round,pad=0.22", "fc": "white", "ec": "#cccccc", "alpha": 0.88},
    )
    ax.set_title(f"{symbol.upper()} - Market Structure", fontsize=12, weight="bold", pad=14)
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.22)
    ax.legend(loc="upper left", fontsize=8)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def render_momentum_volume_chart(df: pd.DataFrame, out_path: str | Path, symbol: str) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    recent = df.tail(120).copy()
    dates = pd.to_datetime(recent["date"])
    fig = plt.figure(figsize=(13, 9), dpi=160)
    grid = fig.add_gridspec(3, 1, height_ratios=[2.1, 1.0, 1.0], hspace=0.08)
    ax1 = fig.add_subplot(grid[0])
    ax2 = fig.add_subplot(grid[1], sharex=ax1)
    ax3 = fig.add_subplot(grid[2], sharex=ax1)
    ax1.plot(dates, recent["close"], label="Close", linewidth=1.4)
    for col, label in [("sma20", "20D SMA"), ("sma50", "50D SMA")]:
        if col in recent:
            ax1.plot(dates, recent[col], label=label, linewidth=1.1)
    ax2.plot(dates, recent["rsi14"], linewidth=1.3, color="#9467bd")
    ax2.axhline(70, linestyle="--", linewidth=0.9, color="#6e6e6e")
    ax2.axhline(30, linestyle="--", linewidth=0.9, color="#6e6e6e")
    colors = ["#1f8a4c" if c >= o else "#c23b3b" for o, c in zip(recent["open"], recent["close"])]
    ax3.bar(dates, recent["volume"] / 1e6, color=colors, alpha=0.62)
    if "volume_20d" in recent:
        ax3.plot(dates, recent["volume_20d"] / 1e6, color="#333333", linestyle=":", linewidth=1.0, label="20D avg")
    for ax in [ax1, ax2, ax3]:
        ax.grid(True, alpha=0.22)
    ax1.legend(loc="upper left", fontsize=8)
    ax2.set_ylabel("RSI")
    ax3.set_ylabel("Volume, M")
    ax3.xaxis.set_major_locator(mdates.MonthLocator())
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    fig.suptitle(f"{symbol.upper()} - Momentum and Participation", fontsize=12, weight="bold", y=0.985)
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(path)
    plt.close(fig)
    return path


def render_event_overlay_chart(df: pd.DataFrame, out_path: str | Path, symbol: str) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    recent = df.tail(120).copy()
    dates = pd.to_datetime(recent["date"])
    current = float(recent["close"].iloc[-1])
    high = float(recent["high"].tail(60).max())
    support = float(recent["low"].tail(60).quantile(0.2))

    fig, ax = plt.subplots(figsize=(13, 7.3), dpi=160)
    ax.plot(dates, recent["close"], linewidth=1.7, label="Close")
    ax.fill_between(dates, recent["low"], recent["high"], alpha=0.12)
    ax.axhline(high, linestyle="--", color="#6e6e6e", linewidth=0.9, label="60D high")
    ax.axhline(current, linestyle=":", color="#1f77b4", linewidth=1.1, label="Last close")
    ax.axhspan(support * 0.995, support * 1.005, alpha=0.16, color="#9ecae1", label="Support watch")
    ax.annotate(
        "Use fresh news/filings here\nwhen catalyst adapter is configured",
        xy=(dates.iloc[-1], current),
        xytext=(dates.iloc[max(0, len(dates) - 55)], current),
        arrowprops={"arrowstyle": "->", "lw": 0.9},
        fontsize=8.5,
        bbox={"boxstyle": "round,pad=0.22", "fc": "white", "ec": "#cccccc", "alpha": 0.88},
    )
    ax.set_title(f"{symbol.upper()} - Price Reaction / Event Overlay Scaffold", fontsize=12, weight="bold", pad=14)
    ax.set_ylabel("Price")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.22)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def render_chart_pack(df: pd.DataFrame, out_dir: str | Path, symbol: str) -> dict[str, Path]:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    sym = symbol.lower()
    return {
        "market_structure": render_market_structure_chart(df, root / f"{sym}_market_structure.png", symbol),
        "momentum_volume": render_momentum_volume_chart(df, root / f"{sym}_momentum_volume.png", symbol),
        "event_overlay": render_event_overlay_chart(df, root / f"{sym}_event_overlay.png", symbol),
    }
