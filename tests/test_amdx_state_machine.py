"""
Synthetic ground-truth tests for the AMDX state machine.

Philosophy: real market data can never prove the ABSENCE of a look-ahead or
indexing bug, because we don't independently know the "correct" answer.
These tests hand-construct tiny bar sequences where the correct output is
known by construction, so any deviation is unambiguously a bug.

NOTE: adjust the import paths below to match your actual package layout
(assumed here: fxresearch.strategies.amdx / fxresearch.config / fxresearch.models).
"""
from __future__ import annotations

import pandas as pd
import pytest

from fxresearch.strategies.amdx import generate_candidates_for_day
from fxresearch.config import StrategyConfig, PairRule
from fxresearch.models import Side


SYMBOL = "TESTPAIR"


def make_cfg(
    closeback_max_fraction: float = 0.5,
    midpoint_reclaim_invalidates: bool = True,
    setup_expiry_minutes: int = 60,
    spread_max_pips: float = 5.0,
    max_stop_pips: float = 200.0,
) -> StrategyConfig:
    return StrategyConfig(
        name="test",
        timezone="Asia/Singapore",
        day_start="06:00",
        asian_start="06:00",
        asian_end="06:30",
        trading_end="08:00",
        closeback_max_fraction=closeback_max_fraction,
        midpoint_reclaim_invalidates=midpoint_reclaim_invalidates,
        setup_expiry_minutes=setup_expiry_minutes,
        atr_period=14,
        atr_multiplier=2.0,
        target_r=1.5,
        max_trades_per_day=2,
        daily_realised_loss_stop_r=-1.0,
        one_trade_per_pair_per_day=True,
        pair_rules={
            SYMBOL: PairRule(
                spread_max_pips=spread_max_pips,
                max_stop_pips=max_stop_pips,
                pip_size=0.0001,
            )
        },
    )


def bar(ts, mid_high, mid_low, mid_close, ask_open=None, bid_open=None, atr=0.0010, day="2024-01-02"):
    """One synthetic 5-minute bar. ask/bid default to mid +/- half a pip spread."""
    if ask_open is None:
        ask_open = mid_close + 0.00005
    if bid_open is None:
        bid_open = mid_close - 0.00005
    return {
        "timestamp_sgt": pd.Timestamp(f"2024-01-02 {ts}:00"),
        "mid_high": mid_high,
        "mid_low": mid_low,
        "mid_close": mid_close,
        "ask_open": ask_open,
        "bid_open": bid_open,
        "atr": atr,
        "amdx_day": day,
    }


def make_day_df(extra_asian_bars: int = 0) -> pd.DataFrame:
    """
    Builds: N flat Asian bars (06:00-06:25) establishing range [1.0985, 1.1010],
    then a trade window 06:30-07:25 containing:
      06:30 normal / 06:35 sweep / 06:40 closeback / 06:45 rebreak / 06:50 true-next-bar
    `extra_asian_bars` inflates the Asian session so the trade window's row
    LABELS start at a large, nonzero offset -- this is what exposes the
    iloc/label bug, since a small offset can accidentally look correct.
    """
    rows = []
    # Asian session: alternate two flat bars to pad to any length while
    # keeping high/low fixed at 1.1010 / 1.0985.
    base_asian = [
        bar("06:00", 1.1005, 1.0990, 1.1000),
        bar("06:05", 1.1010, 1.0985, 1.1000),  # sets the range
        bar("06:10", 1.1000, 1.0995, 1.0998),
        bar("06:15", 1.1000, 1.0995, 1.0998),
        bar("06:20", 1.1000, 1.0995, 1.0998),
        bar("06:25", 1.1000, 1.0995, 1.0998),
    ]
    rows.extend(base_asian)
    # pad further if requested, all inside the same range so it doesn't change asian_high/low
    for extra in range(extra_asian_bars):
        minute = 25 - 5 * (extra + 1)
        # only used for large offset tests; keep simple and inside range
        rows.append(bar(f"06:{minute:02d}" if minute >= 0 else "06:00", 1.1000, 1.0995, 1.0998))

    rows += [
        bar("06:30", 1.1000, 1.0995, 1.0998),               # normal bar, no sweep
        bar("06:35", 1.1020, 1.0995, 1.1005),                # SWEEP (high > 1.1010)
        bar("06:40", 1.1008, 1.0999, 1.1000),                # CLOSEBACK (close 1.1000 < 1.1010, > midpoint 1.09975)
        bar("06:45", 1.1012, 1.1000, 1.1015),                # REBREAK (close 1.1015 > 1.1010)
        bar("06:50", 1.1016, 1.1010, 1.1016,
            ask_open=1.10165, bid_open=1.10155),              # TRUE next bar -> should be entry bar
        bar("06:55", 1.1030, 1.1020, 1.1025),
        bar("07:00", 1.1030, 1.1020, 1.1025),
        bar("07:05", 1.1030, 1.1020, 1.1025),
        bar("07:10", 1.1030, 1.1020, 1.1025),
        bar("07:15", 1.1030, 1.1020, 1.1025),
        bar("07:20", 1.1030, 1.1020, 1.1025),
        bar("07:25", 1.1030, 1.1020, 1.1025),
    ]
    return pd.DataFrame(rows)


def test_entry_is_the_immediate_next_bar_after_rebreak():
    """
    Regression test for the trade.iloc[i+1] label/position bug.
    With the Asian session inflated to 6 bars (nonzero label offset for the
    trade window), the entry MUST still be the bar at 06:50 -- exactly one
    bar after the 06:45 rebreak confirmation -- not some bar hours later.
    """
    day_df = make_day_df()
    cfg = make_cfg()

    candidates = generate_candidates_for_day(day_df, cfg, SYMBOL)

    assert len(candidates) == 1, f"expected exactly one signal, got {len(candidates)}"
    c = candidates[0]
    assert c.entry_time == pd.Timestamp("2024-01-02 06:50:00"), (
        f"entry landed on {c.entry_time}, expected 06:50 "
        "(this is the iloc[i+1] label/position bug if it fails)"
    )
    assert c.side is Side.LONG
    assert c.entry_price == pytest.approx(1.10165)


def test_deep_closeback_invalidates_setup():
    """Closeback deeper than closeback_max_fraction must produce NO candidate."""
    day_df = make_day_df()
    # tighten the allowed closeback fraction well below what the fixture bar produces
    cfg = make_cfg(closeback_max_fraction=0.05)

    candidates = generate_candidates_for_day(day_df, cfg, SYMBOL)
    assert candidates == [], "deep closeback should invalidate the setup, but a signal fired"


def test_midpoint_reclaim_invalidates_pending_rebreak():
    """
    If price reclaims the Asian midpoint while WAITING_FOR_REBREAK and
    midpoint_reclaim_invalidates=True, no candidate should be produced --
    even if a rebreak-looking close happens on the very next bar.
    """
    rows = [
        bar("06:00", 1.1005, 1.0990, 1.1000),
        bar("06:05", 1.1010, 1.0985, 1.1000),
        bar("06:10", 1.1000, 1.0995, 1.0998),
        bar("06:15", 1.1000, 1.0995, 1.0998),
        bar("06:20", 1.1000, 1.0995, 1.0998),
        bar("06:25", 1.1000, 1.0995, 1.0998),
        bar("06:30", 1.1000, 1.0995, 1.0998),
        bar("06:35", 1.1020, 1.0995, 1.1005),   # sweep
        bar("06:40", 1.1008, 1.0999, 1.1000),   # closeback (shallow, valid)
        bar("06:45", 1.0990, 1.0980, 1.0995),   # low dips to 1.0980, BELOW midpoint 1.09975 -> invalidate
        bar("06:50", 1.1020, 1.1010, 1.1020),   # would look like a rebreak if not already invalidated
    ]
    day_df = pd.DataFrame(rows)
    cfg = make_cfg()

    candidates = generate_candidates_for_day(day_df, cfg, SYMBOL)
    assert candidates == [], "midpoint reclaim should invalidate the setup before rebreak is checked"


def test_setup_expiry_invalidates_stale_rebreak():
    """A rebreak arriving after setup_expiry_minutes from the sweep must not fire."""
    rows = [
        bar("06:00", 1.1005, 1.0990, 1.1000),
        bar("06:05", 1.1010, 1.0985, 1.1000),
        bar("06:10", 1.1000, 1.0995, 1.0998),
        bar("06:15", 1.1000, 1.0995, 1.0998),
        bar("06:20", 1.1000, 1.0995, 1.0998),
        bar("06:25", 1.1000, 1.0995, 1.0998),
        bar("06:30", 1.1000, 1.0995, 1.0998),
        bar("06:35", 1.1020, 1.0995, 1.1005),   # sweep at 06:35
        bar("06:40", 1.1008, 1.0999, 1.1000),   # closeback, valid
        # stall inside the range for a long time (no rebreak) past expiry
        bar("06:45", 1.1005, 1.1000, 1.1002),
        bar("06:50", 1.1005, 1.1000, 1.1002),
        bar("06:55", 1.1005, 1.1000, 1.1002),
        bar("07:00", 1.1005, 1.1000, 1.1002),
        bar("07:05", 1.1005, 1.1000, 1.1002),
        bar("07:10", 1.1005, 1.1000, 1.1002),
        bar("07:15", 1.1005, 1.1000, 1.1002),
        bar("07:20", 1.1005, 1.1000, 1.1002),
        bar("07:25", 1.1020, 1.1010, 1.1020),   # "rebreak" but way past expiry
    ]
    day_df = pd.DataFrame(rows)
    cfg = make_cfg(setup_expiry_minutes=30)  # expires 30 min after 06:35 sweep -> 07:05

    candidates = generate_candidates_for_day(day_df, cfg, SYMBOL)
    assert candidates == [], "rebreak arriving after setup_expiry_minutes should not produce a signal"


def test_no_lookahead_past_the_entry_decision_bar():
    """
    Two days identical up through the rebreak+entry bar, differing ONLY in
    what happens afterward, must produce IDENTICAL candidates. If they
    differ, the engine is using information beyond the entry decision point.
    """
    day_df_a = make_day_df()

    day_df_b = day_df_a.copy()
    # mutate bars strictly after the entry bar (06:50) to something wildly different
    future_mask = day_df_b["timestamp_sgt"] > pd.Timestamp("2024-01-02 06:50:00")
    day_df_b.loc[future_mask, ["mid_high", "mid_low", "mid_close"]] = [0.5, 0.4, 0.45]

    cfg = make_cfg()
    cands_a = generate_candidates_for_day(day_df_a, cfg, SYMBOL)
    cands_b = generate_candidates_for_day(day_df_b, cfg, SYMBOL)

    assert len(cands_a) == 1 and len(cands_b) == 1
    assert cands_a[0].entry_time == cands_b[0].entry_time
    assert cands_a[0].entry_price == cands_b[0].entry_price
    assert cands_a[0].stop_price == cands_b[0].stop_price


def test_at_most_one_candidate_per_symbol_per_day():
    """The state machine should stop (state=DONE) after the first valid entry."""
    day_df = make_day_df()
    cfg = make_cfg()
    candidates = generate_candidates_for_day(day_df, cfg, SYMBOL)
    assert len(candidates) <= 1
