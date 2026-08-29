from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_metrics(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "avg_r": 0.0,
            "total_r": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_r": 0.0,
        }

    r = trades.sort_values("exit_time")["r_multiple"].astype(float)
    equity = r.cumsum()
    equity0 = pd.concat([pd.Series([0.0]), equity.reset_index(drop=True)], ignore_index=True)
    drawdown = equity0 - equity0.cummax()

    gross_win = r[r > 0].sum()
    gross_loss = abs(r[r < 0].sum())
    pf = float(gross_win / gross_loss) if gross_loss > 0 else float("inf")

    return {
        "trades": int(len(r)),
        "win_rate": float((r > 0).mean()),
        "avg_r": float(r.mean()),
        "total_r": float(r.sum()),
        "profit_factor": pf,
        "max_drawdown_r": float(drawdown.min()),
    }
