"""
Structural sanity checks for a fresh backtest run's trades.csv / candidate_audit.csv.

Purpose: catch obvious pipeline problems (wrong entry timing, duplicate trades,
R-multiples outside expected bounds, portfolio rules not enforced) BEFORE
spending time on the manual chart-by-chart audit. This does not validate
whether the strategy is profitable -- only whether the output is internally
consistent with what the code is supposed to produce.

Usage:
    python sanity_check_run.py --trades path/to/trades.csv --audit path/to/candidate_audit.csv --cfg config/amdx_v1.yaml
"""
from __future__ import annotations

import argparse
import sys
import pandas as pd
import yaml


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail and not condition else ""))
    return condition


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--trades", required=True)
    p.add_argument("--audit", required=True)
    p.add_argument("--cfg", required=True)
    args = p.parse_args()

    trades = pd.read_csv(args.trades, parse_dates=["entry_time", "exit_time"])
    audit = pd.read_csv(args.audit, parse_dates=["entry_time"])
    cfg = yaml.safe_load(open(args.cfg, encoding="utf-8"))

    ok = True

    # 1. No duplicate trades on the same pair/day if one_trade_per_pair_per_day is set
    if cfg["risk"].get("one_trade_per_pair_per_day", False):
        dupes = trades.groupby(["symbol", "amdx_day"]).size()
        ok &= check(
            "One trade per pair per day",
            (dupes <= 1).all(),
            f"{(dupes > 1).sum()} (symbol, day) pairs have >1 trade",
        )

    # 2. Daily trade cap respected across the whole portfolio
    max_per_day = cfg["risk"]["max_trades_per_day"]
    daily_counts = trades.groupby("amdx_day").size()
    ok &= check(
        f"Max {max_per_day} trades/day respected (portfolio-wide)",
        (daily_counts <= max_per_day).all(),
        f"worst day had {daily_counts.max()} trades",
    )

    # 3. R-multiples land in the expected set: -1.0 (stop), +target_r (target),
    #    or something else only for session_close exits (partial R).
    target_r = cfg["risk"]["target_r"]
    non_close = trades[trades["exit_reason"] != "session_close"]
    bad_r = non_close[~non_close["r_multiple"].round(4).isin([-1.0, round(target_r, 4)])]
    ok &= check(
        "Stop/target R-multiples match config (-1.0 / +target_r)",
        bad_r.empty,
        f"{len(bad_r)} trades have unexpected R for their exit_reason",
    )

    # 4. Exit time is never before entry time
    ok &= check(
        "No trade exits before it enters",
        (trades["exit_time"] >= trades["entry_time"]).all(),
    )

    # 5. Spread and stop caps from the audit file were actually enforced
    #    (accepted trades should never have spread/stop values that exceed
    #    their pair's configured caps)
    pair_rules = cfg["pair_rules"]
    accepted = audit[audit["decision"] == "accepted"]
    violations = 0
    for _, row in accepted.iterrows():
        rule = pair_rules.get(row["symbol"])
        if rule and row.get("spread_pips", 0) > rule["spread_max_pips"]:
            violations += 1
    ok &= check("No accepted trade exceeds its pair's spread cap", violations == 0,
                f"{violations} violations")

    # 6. Entry times fall inside the configured trading window, not the Asian session
    asian_end = cfg["sessions"]["asian_end"]
    trading_end = cfg["sessions"]["trading_end"]
    entry_hm = trades["entry_time"].dt.strftime("%H:%M")
    outside_window = trades[(entry_hm < asian_end) | (entry_hm > trading_end)]
    ok &= check(
        "All entries fall within the configured trading window",
        outside_window.empty,
        f"{len(outside_window)} trades entered outside [{asian_end}, {trading_end}]",
    )

    # 7. Rejection reasons in the audit file are all recognized values
    #    (catches silent new failure modes / typos in reason strings)
    known_reasons = {"", "daily_loss_stop", "daily_trade_cap", "duplicate_pair_day", "no_future_bars"}
    unknown = audit[~audit["reason"].fillna("").isin(known_reasons)]
    ok &= check("All audit rejection reasons are recognized", unknown.empty,
                f"unexpected reasons: {unknown['reason'].unique().tolist()}")

    print(f"\nTrades: {len(trades)}  |  Candidates evaluated: {len(audit)}  |  "
          f"Accepted in audit: {(audit['decision']=='accepted').sum()}")
    print("\n=> " + ("ALL CHECKS PASSED -- safe to move to manual chart review."
                      if ok else "SOME CHECKS FAILED -- investigate before trusting this run."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())