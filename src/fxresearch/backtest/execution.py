from __future__ import annotations

import pandas as pd

from fxresearch.models import SignalCandidate, Side, Trade


def simulate_trade(
    candidate: SignalCandidate,
    bars: pd.DataFrame,
    conservative_same_bar: bool = True,
) -> Trade | None:
    future = bars[bars["timestamp_sgt"] >= candidate.entry_time].sort_values("timestamp_sgt")
    if future.empty:
        return None

    for _, row in future.iterrows():
        if candidate.side is Side.LONG:
            stop_hit = row["bid_low"] <= candidate.stop_price
            target_hit = row["bid_high"] >= candidate.target_price
        else:
            stop_hit = row["ask_high"] >= candidate.stop_price
            target_hit = row["ask_low"] <= candidate.target_price

        if not stop_hit and not target_hit:
            continue

        if stop_hit and target_hit:
            stop_first = conservative_same_bar
        else:
            stop_first = stop_hit

        if stop_first:
            exit_price = candidate.stop_price
            r = -1.0
            reason = "stop"
        else:
            exit_price = candidate.target_price
            r = 1.5
            reason = "target"

        return Trade(
            symbol=candidate.symbol,
            side=candidate.side,
            entry_time=candidate.entry_time,
            exit_time=row["timestamp_sgt"],
            entry_price=candidate.entry_price,
            exit_price=float(exit_price),
            stop_price=candidate.stop_price,
            target_price=candidate.target_price,
            r_multiple=r,
            exit_reason=reason,
            amdx_day=candidate.amdx_day,
        )

    last = future.iloc[-1]
    if candidate.side is Side.LONG:
        exit_price = float(last["bid_close"])
        r = (exit_price - candidate.entry_price) / candidate.stop_distance
    else:
        exit_price = float(last["ask_close"])
        r = (candidate.entry_price - exit_price) / candidate.stop_distance

    return Trade(
        symbol=candidate.symbol,
        side=candidate.side,
        entry_time=candidate.entry_time,
        exit_time=last["timestamp_sgt"],
        entry_price=candidate.entry_price,
        exit_price=exit_price,
        stop_price=candidate.stop_price,
        target_price=candidate.target_price,
        r_multiple=float(r),
        exit_reason="session_close",
        amdx_day=candidate.amdx_day,
    )
