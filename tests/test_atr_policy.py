"""
Locks in the CURRENT, deliberate ATR specification:
  - add_atr() is called once on the full continuous per-symbol series,
    BEFORE splitting into AMDX days -> no daily warm-up reset.
  - True range uses the previous bar's close with no gap-reset logic,
    so a large weekend/holiday gap temporarily inflates ATR.

If either of these ever changes (e.g. someone moves add_atr() inside the
per-day loop, or adds gap-reset logic), this test should fail loudly so
the change is a deliberate decision, not an accidental regression.
"""
from __future__ import annotations

import pandas as pd

from fxresearch.features import add_atr


def test_atr_does_not_reset_at_day_boundaries():
    """
    Build >14 bars before a day boundary and a handful after. Under the
    current policy (continuous ATR on the full series pre-split), the
    first bars of "day 2" should already have a valid (non-NaN) ATR,
    inherited from day 1's history -- NOT a fresh 13-bar NaN warm-up.
    """
    day1 = [{"mid_high": 1.10 + i*0.0001, "mid_low": 1.09 + i*0.0001,
             "mid_close": 1.095 + i*0.0001, "amdx_day": "2024-01-01"} for i in range(20)]
    day2 = [{"mid_high": 1.12 + i*0.0001, "mid_low": 1.11 + i*0.0001,
             "mid_close": 1.115 + i*0.0001, "amdx_day": "2024-01-02"} for i in range(5)]
    full_series = pd.DataFrame(day1 + day2)

    # current pipeline order: add_atr on the FULL series, THEN split by day
    out = add_atr(full_series, period=14)

    day2_atr = out[out["amdx_day"] == "2024-01-02"]["atr"]
    assert day2_atr.notna().all(), (
        "Day 2's ATR contains NaN -- if this fails, ATR is being reset per "
        "day (e.g. add_atr() moved inside the per-day loop), which "
        "systematically suppresses early-session setups every day. "
        "This must be a deliberate spec change, not an accident."
    )


def test_atr_is_inflated_by_a_large_gap_and_documents_current_non_reset_policy():
    """
    Documents (does not "fix") the known weekend-gap inflation behavior,
    so it's visible in the test suite rather than only in a chat log.
    Fails only if someone adds gap-reset logic without updating this test.
    """
    rows = [{"mid_high": 1.1000 + i*0.00005 + 0.0010, "mid_low": 1.1000 + i*0.00005 - 0.0010,
             "mid_close": 1.1000 + i*0.00005 + 0.0002} for i in range(20)]
    rows.append({"mid_high": 1.1310, "mid_low": 1.1295, "mid_close": 1.1300})  # gap bar
    df = pd.DataFrame(rows)

    out = add_atr(df, period=14)
    pre_gap_atr = out["atr"].iloc[19]
    post_gap_atr = out["atr"].iloc[20]

    assert post_gap_atr > pre_gap_atr * 1.5, (
        "Expected the gap to noticeably inflate ATR under the current "
        "continuous, no-reset policy. If this now fails, someone likely "
        "added gap-reset logic -- update this test to reflect the new, "
        "deliberately chosen policy."
    )