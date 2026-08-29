from __future__ import annotations

import pandas as pd


def normalize_market_data(df: pd.DataFrame, timezone: str) -> pd.DataFrame:
    out = df.copy()
    out["timestamp_sgt"] = out["timestamp_utc"].dt.tz_convert(timezone)
    out["spread_open"] = out["ask_open"] - out["bid_open"]
    out["mid_open"] = (out["ask_open"] + out["bid_open"]) / 2
    out["mid_high"] = (out["ask_high"] + out["bid_high"]) / 2
    out["mid_low"] = (out["ask_low"] + out["bid_low"]) / 2
    out["mid_close"] = (out["ask_close"] + out["bid_close"]) / 2
    return out


def assign_amdx_day(df: pd.DataFrame, day_start_hour: int = 6) -> pd.DataFrame:
    out = df.copy()
    shifted = out["timestamp_sgt"] - pd.Timedelta(hours=day_start_hour)
    out["amdx_day"] = shifted.dt.date.astype(str)
    return out
