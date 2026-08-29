from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import pandas as pd

from fxresearch.config import StrategyConfig
from fxresearch.models import SignalCandidate, Trade
from fxresearch.backtest.execution import simulate_trade


PAIR_PRIORITY = {"GBPUSD": 0, "EURUSD": 1, "EURJPY": 2, "GBPJPY": 3}


def run_portfolio(
    candidates: list[SignalCandidate],
    bars_by_symbol: dict[str, pd.DataFrame],
    cfg: StrategyConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = sorted(
        candidates,
        key=lambda c: (c.entry_time, PAIR_PRIORITY.get(c.symbol, 99)),
    )

    accepted: list[Trade] = []
    audit: list[dict] = []
    selected_by_day: defaultdict[str, int] = defaultdict(int)
    used_pairs_by_day: defaultdict[str, set[str]] = defaultdict(set)

    for candidate in candidates:
        realised_before = sum(
            t.r_multiple
            for t in accepted
            if t.amdx_day == candidate.amdx_day and t.exit_time <= candidate.entry_time
        )

        decision = "accepted"
        reason = ""

        if realised_before <= cfg.daily_realised_loss_stop_r:
            decision = "rejected"
            reason = "daily_loss_stop"
        elif selected_by_day[candidate.amdx_day] >= cfg.max_trades_per_day:
            decision = "rejected"
            reason = "daily_trade_cap"
        elif (
            cfg.one_trade_per_pair_per_day
            and candidate.symbol in used_pairs_by_day[candidate.amdx_day]
        ):
            decision = "rejected"
            reason = "duplicate_pair_day"

        if decision == "accepted":
            trade = simulate_trade(candidate, bars_by_symbol[candidate.symbol])
            if trade is None:
                decision = "rejected"
                reason = "no_future_bars"
            else:
                accepted.append(trade)
                selected_by_day[candidate.amdx_day] += 1
                used_pairs_by_day[candidate.amdx_day].add(candidate.symbol)

        audit.append(
            {
                **asdict(candidate),
                "realised_r_before": realised_before,
                "decision": decision,
                "reason": reason,
            }
        )

    trades_df = pd.DataFrame([asdict(t) for t in accepted])
    audit_df = pd.DataFrame(audit)
    return trades_df, audit_df
