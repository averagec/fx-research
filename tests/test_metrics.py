import pandas as pd
from fxresearch.backtest.metrics import calculate_metrics


def test_metrics_basic():
    trades = pd.DataFrame(
        {
            "r_multiple": [1.5, -1.0, 1.5, -1.0],
            "exit_time": pd.date_range("2025-01-01", periods=4, freq="h", tz="UTC"),
        }
    )
    m = calculate_metrics(trades)
    assert m["trades"] == 4
    assert m["total_r"] == 1.0
    assert m["win_rate"] == 0.5
