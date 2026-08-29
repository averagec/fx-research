"""
Ground-truth test for the exact 'Notebook 4' defect described in the audit
report: a portfolio engine that uses a trade's EVENTUAL outcome to gate a
later trade's entry, even though that outcome isn't known yet at decision
time. portfolio.py's `realised_before` filter (t.exit_time <= entry_time)
is supposed to prevent this -- this test proves it with a constructed case
where getting it wrong changes the accept/reject decision.
"""
from __future__ import annotations

import pandas as pd
import pytest

from fxresearch.backtest.portfolio import run_portfolio
from fxresearch.config import StrategyConfig, PairRule
from fxresearch.models import Side, SignalCandidate

SYMBOL = "TESTPAIR"


def make_cfg(daily_realised_loss_stop_r=-1.0, max_trades_per_day=2):
    return StrategyConfig(
        name="test", timezone="Asia/Singapore", day_start="06:00",
        asian_start="06:00", asian_end="06:30", trading_end="08:00",
        closeback_max_fraction=0.5, midpoint_reclaim_invalidates=True,
        setup_expiry_minutes=60, atr_period=14, atr_multiplier=2.0,
        target_r=1.5, max_trades_per_day=max_trades_per_day,
        daily_realised_loss_stop_r=daily_realised_loss_stop_r,
        one_trade_per_pair_per_day=False,
        pair_rules={SYMBOL: PairRule(spread_max_pips=5.0, max_stop_pips=200.0, pip_size=0.0001)},
    )


def candidate(entry_time, side, entry_price, stop_price, target_price, day="2024-01-02"):
    stop_distance = abs(entry_price - stop_price)
    return SignalCandidate(
        symbol=SYMBOL, side=side, signal_time=entry_time, entry_time=entry_time,
        entry_price=entry_price, stop_price=stop_price, target_price=target_price,
        stop_distance=stop_distance, spread_pips=1.0, amdx_day=day,
    )


def bars_open_then_stop(start, price_open, stop_price, stop_after_minutes, minutes=120):
    """
    Bars for a LONG that stay safely inside [stop, target] on the entry bar
    itself (so the trade is genuinely still OPEN right after entry), then
    hit the stop `stop_after_minutes` later.
    """
    ts0 = pd.Timestamp(start)
    rows = [{
        "timestamp_sgt": ts0, "bid_low": price_open - 0.0002, "bid_high": price_open + 0.0002,
        "ask_low": price_open - 0.0002, "ask_high": price_open + 0.0002,
        "bid_close": price_open, "ask_close": price_open + 0.0001,
    }]
    for m in range(5, minutes, 5):
        ts = ts0 + pd.Timedelta(minutes=m)
        if m < stop_after_minutes:
            rows.append({
                "timestamp_sgt": ts, "bid_low": price_open - 0.0002, "bid_high": price_open + 0.0002,
                "ask_low": price_open - 0.0002, "ask_high": price_open + 0.0002,
                "bid_close": price_open, "ask_close": price_open + 0.0001,
            })
        else:
            rows.append({
                "timestamp_sgt": ts, "bid_low": stop_price - 0.0002, "bid_high": stop_price + 0.0002,
                "ask_low": stop_price - 0.0002, "ask_high": stop_price + 0.0002,
                "bid_close": stop_price, "ask_close": stop_price + 0.0001,
            })
    return pd.DataFrame(rows)


def test_second_entry_uses_only_already_realised_pnl_not_future_outcome():
    """
    Trade A: enters 06:35, hits its stop (-1R) at 06:40.
    Trade B: enters 06:38 (BEFORE trade A's 06:40 exit is known).

    daily_realised_loss_stop_r = -1.0. If the engine were future-peeking
    (the audited defect), trade B could be wrongly rejected using A's
    not-yet-realised -1R outcome. The correct, causal behavior is that B
    is evaluated with realised_before = 0.0 (A hasn't exited yet), so B
    should be ACCEPTED.
    """
    cand_a = candidate(pd.Timestamp("2024-01-02 06:35:00"), Side.LONG,
                        entry_price=1.1000, stop_price=1.0990, target_price=1.1015)
    cand_b = candidate(pd.Timestamp("2024-01-02 06:38:00"), Side.LONG,
                        entry_price=1.1002, stop_price=1.0992, target_price=1.1017)

    # A stays open through its entry bar and hits its stop 10 minutes later
    # (06:45) -- i.e. AFTER B's 06:38 entry. B must NOT see A's loss yet.
    bars_a = bars_open_then_stop("2024-01-02 06:35:00", 1.1000, 1.0990, stop_after_minutes=10)
    bars_b = bars_open_then_stop("2024-01-02 06:38:00", 1.1002, 1.0992, stop_after_minutes=60)

    trades_df, audit_df = run_portfolio(
        [cand_a, cand_b],
        bars_by_symbol={SYMBOL: pd.concat([bars_a, bars_b]).sort_values("timestamp_sgt")},
        cfg=make_cfg(),
    )

    b_row = audit_df[audit_df["entry_time"] == cand_b.entry_time].iloc[0]
    assert b_row["decision"] == "accepted", (
        f"trade B was rejected ({b_row['reason']}) using an outcome from trade A "
        "that had not been realised yet at B's entry time -- this is the future-path defect."
    )
    assert b_row["realised_r_before"] == 0.0, (
        "realised_before should be 0.0 for B since A had not exited by B's entry time"
    )
