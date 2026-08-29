from __future__ import annotations

import pandas as pd


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    out = df.copy()
    prev_close = out["mid_close"].shift(1)
    tr = pd.concat(
        [
            out["mid_high"] - out["mid_low"],
            (out["mid_high"] - prev_close).abs(),
            (out["mid_low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return out
