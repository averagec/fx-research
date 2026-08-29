from __future__ import annotations

from enum import Enum, auto
import pandas as pd

from fxresearch.config import StrategyConfig
from fxresearch.models import Side, SignalCandidate


class SetupState(Enum):
    WAITING_FOR_SWEEP = auto()
    WAITING_FOR_CLOSEBACK = auto()
    WAITING_FOR_REBREAK = auto()
    DONE = auto()
    INVALID = auto()


def _time_mask(ts: pd.Series, start: str, end: str) -> pd.Series:
    t = ts.dt.strftime("%H:%M")
    return (t >= start) & (t < end)


def generate_candidates_for_day(
    day_df: pd.DataFrame,
    cfg: StrategyConfig,
    symbol: str,
) -> list[SignalCandidate]:
    if day_df.empty:
        return []

    rule = cfg.pair_rules[symbol]
    day_df = day_df.sort_values("timestamp_sgt").reset_index(drop=True)

    asian = day_df[_time_mask(day_df["timestamp_sgt"], cfg.asian_start, cfg.asian_end)]
    trade = day_df[
        (day_df["timestamp_sgt"].dt.strftime("%H:%M") >= cfg.asian_end)
        & (day_df["timestamp_sgt"].dt.strftime("%H:%M") <= cfg.trading_end)
    ]

    if asian.empty or trade.empty:
        return []

    # CRITICAL: asian/trade are boolean-mask slices of day_df, so they keep
    # day_df's original row labels (e.g. 72, 73, 74...), not 0..len-1.
    # The loop below uses `i` from iterrows() together with `trade.iloc[i+1]`,
    # which requires `i` to be a POSITION, not a label. Reset it here so the
    # two stay consistent.
    trade = trade.reset_index(drop=True)

    asian_high = float(asian["mid_high"].max())
    asian_low = float(asian["mid_low"].min())
    asian_range = asian_high - asian_low
    if asian_range <= 0:
        return []

    midpoint = (asian_high + asian_low) / 2
    state = SetupState.WAITING_FOR_SWEEP
    side: Side | None = None
    sweep_time: pd.Timestamp | None = None
    candidates: list[SignalCandidate] = []

    for i, row in trade.iterrows():
        now = row["timestamp_sgt"]

        if state in {SetupState.DONE, SetupState.INVALID}:
            break

        if state is SetupState.WAITING_FOR_SWEEP:
            if row["mid_high"] > asian_high:
                side = Side.LONG
                sweep_time = now
                state = SetupState.WAITING_FOR_CLOSEBACK
            elif row["mid_low"] < asian_low:
                side = Side.SHORT
                sweep_time = now
                state = SetupState.WAITING_FOR_CLOSEBACK
            continue

        assert side is not None and sweep_time is not None

        if now - sweep_time > pd.Timedelta(minutes=cfg.setup_expiry_minutes):
            state = SetupState.INVALID
            break

        if state is SetupState.WAITING_FOR_CLOSEBACK:
            if side is Side.LONG and row["mid_close"] < asian_high:
                depth = asian_high - row["mid_close"]
                fraction = depth / asian_range
                if fraction <= cfg.closeback_max_fraction and row["mid_close"] > midpoint:
                    state = SetupState.WAITING_FOR_REBREAK
                else:
                    state = SetupState.INVALID
            elif side is Side.SHORT and row["mid_close"] > asian_low:
                depth = row["mid_close"] - asian_low
                fraction = depth / asian_range
                if fraction <= cfg.closeback_max_fraction and row["mid_close"] < midpoint:
                    state = SetupState.WAITING_FOR_REBREAK
                else:
                    state = SetupState.INVALID
            continue

        if state is SetupState.WAITING_FOR_REBREAK:
            if cfg.midpoint_reclaim_invalidates:
                if side is Side.LONG and row["mid_low"] <= midpoint:
                    state = SetupState.INVALID
                    break
                if side is Side.SHORT and row["mid_high"] >= midpoint:
                    state = SetupState.INVALID
                    break

            rebreak = (
                side is Side.LONG and row["mid_close"] > asian_high
            ) or (
                side is Side.SHORT and row["mid_close"] < asian_low
            )
            if not rebreak:
                continue

            if i + 1 >= len(trade):
                break

            next_row = trade.iloc[i + 1]
            atr = row["atr"]
            if pd.isna(atr):
                state = SetupState.INVALID
                break

            entry = float(next_row["ask_open"] if side is Side.LONG else next_row["bid_open"])
            spread_pips = float((next_row["ask_open"] - next_row["bid_open"]) / rule.pip_size)
            stop_distance = float(cfg.atr_multiplier * atr)
            stop_pips = stop_distance / rule.pip_size

            if spread_pips > rule.spread_max_pips or stop_pips > rule.max_stop_pips:
                state = SetupState.INVALID
                break

            if side is Side.LONG:
                stop = entry - stop_distance
                target = entry + cfg.target_r * stop_distance
            else:
                stop = entry + stop_distance
                target = entry - cfg.target_r * stop_distance

            candidates.append(
                SignalCandidate(
                    symbol=symbol,
                    side=side,
                    signal_time=now,
                    entry_time=next_row["timestamp_sgt"],
                    entry_price=entry,
                    stop_price=float(stop),
                    target_price=float(target),
                    stop_distance=stop_distance,
                    spread_pips=spread_pips,
                    amdx_day=str(next_row["amdx_day"]),
                )
            )
            state = SetupState.DONE

    return candidates