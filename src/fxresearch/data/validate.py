from __future__ import annotations

import pandas as pd


def validate_market_data(df: pd.DataFrame) -> dict[str, int]:
    issues: dict[str, int] = {}
    issues["duplicates"] = int(df.duplicated(["symbol", "timestamp_utc"]).sum())
    issues["negative_spread"] = int((df["ask_open"] < df["bid_open"]).sum())
    issues["bad_bid_ohlc"] = int(
        ((df["bid_high"] < df[["bid_open", "bid_close"]].max(axis=1)) |
         (df["bid_low"] > df[["bid_open", "bid_close"]].min(axis=1))).sum()
    )
    issues["bad_ask_ohlc"] = int(
        ((df["ask_high"] < df[["ask_open", "ask_close"]].max(axis=1)) |
         (df["ask_low"] > df[["ask_open", "ask_close"]].min(axis=1))).sum()
    )
    return issues
