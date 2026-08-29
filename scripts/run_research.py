from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

from fxresearch.config import load_config
from fxresearch.data.io import load_market_data, save_parquet
from fxresearch.data.normalize import normalize_market_data, assign_amdx_day
from fxresearch.data.validate import validate_market_data
from fxresearch.features import add_atr
from fxresearch.strategies.amdx import generate_candidates_for_day
from fxresearch.backtest.portfolio import run_portfolio
from fxresearch.reporting.report import write_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="CSV or Parquet with canonical bid/ask columns")
    parser.add_argument("--config", default="config/amdx_v1.yaml")
    parser.add_argument("--output", default="reports/latest")
    args = parser.parse_args()

    cfg = load_config(args.config)
    df = load_market_data(args.data)
    print("Data quality:", validate_market_data(df))

    df = normalize_market_data(df, cfg.timezone)
    df = assign_amdx_day(df, day_start_hour=int(cfg.day_start.split(":")[0]))

    bars_by_symbol: dict[str, pd.DataFrame] = {}
    candidates = []

    for symbol, symbol_df in df.groupby("symbol"):
        symbol_df = add_atr(symbol_df, cfg.atr_period)
        bars_by_symbol[symbol] = symbol_df

        for _, day_df in symbol_df.groupby("amdx_day"):
            candidates.extend(generate_candidates_for_day(day_df, cfg, symbol))

    trades, audit = run_portfolio(candidates, bars_by_symbol, cfg)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output / "candidate_audit.csv", index=False)
    metrics = write_report(trades, output)
    print(metrics)


if __name__ == "__main__":
    main()
