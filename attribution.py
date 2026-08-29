"""
Attribution analysis for a trades.csv -- slices results by pair, direction,
and time period, mirroring the "Pair and Direction Attribution" and
"Drawdown and Regime Analysis" structure from the original research reports.
This is where real edges (or concentration risk) actually get identified --
a single aggregate win-rate/PF number can hide that 80% of the R comes from
one pair or one direction.

Usage:
    python attribution.py --trades data/results/2021_full/trades.csv
"""
from __future__ import annotations

import argparse
import pandas as pd


def pct(n: int, total: int) -> str:
    return f"{100*n/total:.1f}%" if total else "0.0%"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--trades", required=True)
    args = p.parse_args()

    df = pd.read_csv(args.trades, parse_dates=["entry_time", "exit_time"])
    if df.empty:
        print("No trades in file.")
        return

    df["year"] = df["entry_time"].dt.year
    df["month"] = df["entry_time"].dt.to_period("M")
    df["dow"] = df["entry_time"].dt.day_name()
    total_r = df["r_multiple"].sum()
    total_trades = len(df)

    print(f"Total: {total_trades} trades, {total_r:+.2f}R, "
          f"{df['symbol'].nunique()} symbol(s), "
          f"{df['entry_time'].dt.date.min()} to {df['entry_time'].dt.date.max()}\n")

    print("=" * 60)
    print("BY PAIR")
    print("=" * 60)
    by_pair = df.groupby("symbol").agg(
        trades=("r_multiple", "count"),
        total_r=("r_multiple", "sum"),
        avg_r=("r_multiple", "mean"),
        win_rate=("r_multiple", lambda x: (x > 0).mean()),
    ).sort_values("total_r", ascending=False)

    # share-of-total-R (pair_r / total_r * 100) is only guaranteed to stay in
    # a sane, interpretable range when no single contributor's magnitude
    # exceeds the grand total's magnitude. If one pair's |R| is bigger than
    # the |total|, it means other pairs partially cancelled it out, and the
    # resulting percentage can exceed 100% or flip sign for reasons that
    # have nothing to do with real concentration. Mixed signs among
    # contributors are normal on their own and don't cause this by
    # themselves -- only this magnitude condition does.
    shares_are_stable = abs(total_r) > 1e-9 and (by_pair["total_r"].abs() <= abs(total_r) + 1e-9).all()
    if shares_are_stable:
        by_pair["share_of_total_r"] = (by_pair["total_r"] / total_r * 100).round(1)
        print(by_pair.round(3).to_string())
    else:
        print(by_pair.round(3).to_string())
        print(f"\n[NOTE] total_r ({total_r:+.2f}R) is smaller in magnitude than "
              f"at least one individual pair's contribution -- pairs are "
              f"partially cancelling each other out, so '% of total' can "
              f"exceed 100% or flip sign. Read the raw total_r column above "
              f"instead of a percentage.")
    print()

    print("=" * 60)
    print("BY DIRECTION")
    print("=" * 60)
    by_side = df.groupby("side").agg(
        trades=("r_multiple", "count"),
        total_r=("r_multiple", "sum"),
        avg_r=("r_multiple", "mean"),
        win_rate=("r_multiple", lambda x: (x > 0).mean()),
    )
    side_shares_stable = abs(total_r) > 1e-9 and (by_side["total_r"].abs() <= abs(total_r) + 1e-9).all()
    if side_shares_stable:
        by_side["share_of_total_r"] = (by_side["total_r"] / total_r * 100).round(1)
    print(by_side.round(3).to_string())
    print()

    print("=" * 60)
    print("BY PAIR x DIRECTION (where concentration usually hides)")
    print("=" * 60)
    by_pair_side = df.groupby(["symbol", "side"]).agg(
        trades=("r_multiple", "count"),
        total_r=("r_multiple", "sum"),
        avg_r=("r_multiple", "mean"),
    ).sort_values("total_r", ascending=False)
    print(by_pair_side.round(3).to_string())
    print()

    print("=" * 60)
    print("BY YEAR")
    print("=" * 60)
    by_year = df.groupby("year").agg(
        trades=("r_multiple", "count"),
        total_r=("r_multiple", "sum"),
        avg_r=("r_multiple", "mean"),
        win_rate=("r_multiple", lambda x: (x > 0).mean()),
    )
    print(by_year.round(3).to_string())
    print()

    print("=" * 60)
    print("BY MONTH (positive vs negative months)")
    print("=" * 60)
    by_month = df.groupby("month")["r_multiple"].sum()
    pos_months = (by_month > 0).sum()
    neg_months = (by_month < 0).sum()
    print(f"Positive months: {pos_months} | Negative months: {neg_months} | "
          f"Flat: {(by_month == 0).sum()}")
    print(by_month.round(3).to_string())
    print()

    print("=" * 60)
    print("BY DAY OF WEEK (worth checking given the ATR weekend-gap finding)")
    print("=" * 60)
    by_dow = df.groupby("dow").agg(
        trades=("r_multiple", "count"),
        total_r=("r_multiple", "sum"),
        avg_r=("r_multiple", "mean"),
    ).reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    print(by_dow.round(3).to_string())
    print()

    print("=" * 60)
    print("CONCENTRATION FLAGS")
    print("=" * 60)
    if not shares_are_stable:
        print("[SKIPPED] Pair-concentration % check skipped -- at least one pair's "
              "contribution is larger in magnitude than the total (pairs are "
              "partially cancelling each other out), so a percentage isn't "
              "meaningful here. See raw total_r per pair above instead.")
    else:
        top_pair_share = by_pair["share_of_total_r"].abs().max()
        if top_pair_share > 60:
            top_pair = by_pair["share_of_total_r"].abs().idxmax()
            print(f"[FLAG] {top_pair} alone accounts for {top_pair_share:.1f}% of total R -- "
                  f"edge may be pair-concentrated, not diversified.")
        elif top_pair_share <= 60:
            print("No pair-concentration flag at the >60% threshold.")
    if side_shares_stable:
        top_side_share = by_side["share_of_total_r"].abs().max()
        if top_side_share > 65:
            top_side = by_side["share_of_total_r"].abs().idxmax()
            print(f"[FLAG] {top_side} trades alone account for {top_side_share:.1f}% of total R -- "
                  f"edge may be direction-concentrated.")
    if neg_months > 0:
        print(f"[NOTE] {neg_months} negative month(s) -- if a prior claim says "
              f"'no negative months', that claim does not hold here.")


if __name__ == "__main__":
    main()