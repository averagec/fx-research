from __future__ import annotations

from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt

from fxresearch.backtest.metrics import calculate_metrics


def write_report(trades: pd.DataFrame, output_dir: str | Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = calculate_metrics(trades)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    trades.to_csv(output_dir / "trades.csv", index=False)

    if not trades.empty:
        ordered = trades.sort_values("exit_time").copy()
        ordered["equity_r"] = ordered["r_multiple"].cumsum()

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(ordered["exit_time"], ordered["equity_r"])
        ax.set_title("Cumulative R")
        ax.set_xlabel("Exit time")
        ax.set_ylabel("R")
        fig.tight_layout()
        fig.savefig(output_dir / "equity_curve.png", dpi=150)
        plt.close(fig)

    return metrics
