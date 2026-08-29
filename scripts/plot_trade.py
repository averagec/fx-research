"""
Plot real M5 bars around a specific trade, for manual chart audit --
using the EXACT same data the backtest engine consumed (no need for a
separate charting platform, and no risk of a different broker's feed
showing a different wick).

Usage:
    python plot_trade.py --parquet data/normalized/m5/GBPUSD/2021/01.parquet \
                          --day 2021-01-28 --timezone Asia/Singapore \
                          --entry-time "2021-01-28 16:05:00" --side short \
                          --entry-price 1.36495 --stop-price 1.3663 \
                          --out trade_2021-01-28.png
"""
from __future__ import annotations

import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", required=True, nargs="+")
    p.add_argument("--day", required=True, help="AMDX day, e.g. 2021-01-28")
    p.add_argument("--timezone", default="Asia/Singapore")
    p.add_argument("--entry-time", help="e.g. '2021-01-28 16:05:00' (local tz)")
    p.add_argument("--side", choices=["long", "short"])
    p.add_argument("--entry-price", type=float)
    p.add_argument("--stop-price", type=float)
    p.add_argument("--target-price", type=float)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    frames = [pd.read_parquet(f) for f in args.parquet]
    df = pd.concat(frames, ignore_index=True)

    symbol = df["symbol"].iloc[0] if "symbol" in df.columns and df["symbol"].nunique() == 1 else "UNKNOWN"

    df["timestamp_sgt"] = df["timestamp_utc"].dt.tz_convert(args.timezone)
    df["mid_high"] = (df["ask_high"] + df["bid_high"]) / 2
    df["mid_low"] = (df["ask_low"] + df["bid_low"]) / 2
    df["mid_open"] = (df["ask_open"] + df["bid_open"]) / 2
    df["mid_close"] = (df["ask_close"] + df["bid_close"]) / 2

    day_start = pd.Timestamp(f"{args.day} 06:00:00").tz_localize(args.timezone)
    day_end = day_start + pd.Timedelta(hours=24)
    window = df[(df["timestamp_sgt"] >= day_start) & (df["timestamp_sgt"] < day_end)].sort_values("timestamp_sgt")

    if window.empty:
        raise SystemExit(f"No bars found for AMDX day {args.day} -- check the parquet covers this date")

    asian = window[window["timestamp_sgt"] < day_start + pd.Timedelta(hours=6)]
    asian_high = asian["mid_high"].max()
    asian_low = asian["mid_low"].min()
    midpoint = (asian_high + asian_low) / 2

    print(f"Symbol: {symbol}")
    print(f"AMDX day {args.day}: Asian high={asian_high:.5f} low={asian_low:.5f} mid={midpoint:.5f}")

    fig, ax = plt.subplots(figsize=(16, 7))
    for _, row in window.iterrows():
        t = row["timestamp_sgt"]
        color = "#2ca02c" if row["mid_close"] >= row["mid_open"] else "#d62728"
        ax.plot([t, t], [row["mid_low"], row["mid_high"]], color=color, linewidth=1)
        ax.plot([t, t], [row["mid_open"], row["mid_close"]], color=color, linewidth=3)

    ax.axhspan(asian_low, asian_high, color="grey", alpha=0.15, label="Asian range")
    ax.axhline(midpoint, color="grey", linestyle=":", linewidth=1, label="Asian midpoint")
    ax.axvspan(day_start, day_start + pd.Timedelta(hours=6), color="blue", alpha=0.05, label="Asian session")

    if args.entry_time:
        et = pd.Timestamp(args.entry_time).tz_localize(args.timezone)
        ax.axvline(et, color="black", linestyle="--", linewidth=1.5, label=f"entry ({args.side})")
    if args.entry_price:
        ax.axhline(args.entry_price, color="black", linewidth=0.8, alpha=0.6)
    if args.stop_price:
        ax.axhline(args.stop_price, color="red", linewidth=0.8, alpha=0.6, label="stop")
    if args.target_price:
        ax.axhline(args.target_price, color="green", linewidth=0.8, alpha=0.6, label="target")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=window["timestamp_sgt"].dt.tz))
    ax.set_title(f"{symbol} AMDX day {args.day} (SGT)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.2)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(args.out, dpi=130)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()