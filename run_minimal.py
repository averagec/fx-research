"""
Minimal end-to-end runner: normalized M5 parquet(s) -> trades.csv / candidate_audit.csv.

Handles multiple symbols in one call: each symbol is normalized, day-assigned,
and given its own continuous ATR pass independently, then ALL candidates
across ALL symbols are combined into a single run_portfolio() call -- this is
what actually exercises cross-pair rules (max_trades_per_day, pair priority,
daily loss stop), which a single-symbol run never touches.

--parquet accepts either explicit file paths OR glob patterns (any argument
that isn't an existing file is treated as a glob pattern and expanded).

Usage:
    # explicit paths (original behavior, still works)
    python run_minimal.py --parquet data/normalized/m5/GBPUSD/2021/01.parquet \
                           data/normalized/m5/EURUSD/2021/01.parquet \
                           --cfg config/amdx_v1.yaml --out data/results/2021_01

    # glob pattern -- e.g. every pair, every month of 2021
    python run_minimal.py --parquet "data/normalized/m5/*/2021/*.parquet" \
                           --cfg config/amdx_v1.yaml --out data/results/2021_full
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import pandas as pd

from fxresearch.config import load_config
from fxresearch.features import add_atr
from fxresearch.data.normalize import normalize_market_data, assign_amdx_day
from fxresearch.strategies.amdx import generate_candidates_for_day
from fxresearch.backtest.portfolio import run_portfolio
from fxresearch.backtest.metrics import calculate_metrics


def resolve_parquet_paths(patterns: list[str]) -> list[str]:
    resolved: list[str] = []
    for pattern in patterns:
        if Path(pattern).is_file():
            resolved.append(pattern)
            continue
        matches = sorted(glob.glob(pattern))
        if not matches:
            raise SystemExit(f"No files matched: {pattern!r} (not a literal file, and glob found nothing)")
        resolved.extend(matches)
    seen = set()
    deduped = []
    for r in resolved:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", required=True, nargs="+",
                    help="one or more normalized M5 parquet files or glob patterns")
    p.add_argument("--cfg", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    parquet_files = resolve_parquet_paths(args.parquet)
    print(f"Resolved {len(parquet_files)} parquet file(s) from {len(args.parquet)} argument(s)")

    cfg = load_config(args.cfg)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = [pd.read_parquet(f) for f in parquet_files]
    raw = pd.concat(frames, ignore_index=True)

    symbols = sorted(raw["symbol"].unique())
    print(f"Loaded {len(raw)} M5 bars across {len(symbols)} symbol(s): {symbols}")

    all_candidates = []
    bars_by_symbol = {}

    for symbol in symbols:
        df = raw[raw["symbol"] == symbol].copy()

        df = normalize_market_data(df, cfg.timezone)
        df = assign_amdx_day(df, day_start_hour=int(cfg.day_start.split(":")[0]))
        df = add_atr(df, cfg.atr_period)
        df = df.sort_values("timestamp_sgt").reset_index(drop=True)

        print(f"  {symbol}: {df['amdx_day'].nunique()} AMDX days, "
              f"{df['atr'].isna().sum()} rows still in ATR warm-up")

        symbol_candidates = []
        for day, day_df in df.groupby("amdx_day"):
            symbol_candidates.extend(generate_candidates_for_day(day_df, cfg, symbol))

        print(f"  {symbol}: {len(symbol_candidates)} raw candidates before portfolio rules")

        all_candidates.extend(symbol_candidates)
        bars_by_symbol[symbol] = df

    print(f"\nTotal raw candidates across all symbols: {len(all_candidates)}")

    trades_df, audit_df = run_portfolio(all_candidates, bars_by_symbol, cfg)

    trades_path = out_dir / "trades.csv"
    audit_path = out_dir / "candidate_audit.csv"
    trades_df.to_csv(trades_path, index=False)
    audit_df.to_csv(audit_path, index=False)

    metrics = calculate_metrics(trades_df)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"\nWrote {trades_path}")
    print(f"Wrote {audit_path}")
    print(f"\nMetrics: {json.dumps(metrics, indent=2)}")

    if trades_df.empty:
        return
    print("\nTrades per symbol:")
    print(trades_df["symbol"].value_counts().to_string())
    if len(symbols) > 1:
        rejected = audit_df[audit_df["decision"] == "rejected"]
        print("\nRejections by reason (evidence cross-pair rules actually fired):")
        print(rejected["reason"].value_counts().to_string() if not rejected.empty else "  (none rejected)")


if __name__ == "__main__":
    main()