# FX Research Pipeline

This repository is a working starter pipeline for researching the AMDX-style
Asian-range sweep → shallow closeback → rebreak continuation strategy.

## What it already does

- Loads canonical bid/ask CSV or Parquet data
- Converts UTC to Singapore time
- Assigns AMDX days beginning at 06:00 SGT
- Computes ATR(14)
- Builds signals sequentially with a state machine
- Applies pair-specific spread and stop caps
- Simulates side-correct long/short execution
- Applies a max-two-trades daily portfolio rule
- Applies the daily loss stop using exit-time-aware realised P&L
- Writes trades, candidate audit logs, metrics, and an equity curve

## Required input columns

```text
timestamp_utc
symbol
bid_open
bid_high
bid_low
bid_close
ask_open
ask_high
ask_low
ask_close
```

Example symbol values:

```text
EURUSD
GBPUSD
EURJPY
GBPJPY
```

## Setup

```bash
cd fx-research
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Install:

```bash
pip install -e .
```

Run tests:

```bash
pytest
```

Run research:

```bash
python run_research.py \
  --data data/normalized/fx_2021_2025.parquet \
  --config config/amdx_v1.yaml \
  --output reports/amdx_v1
```

## Output

```text
reports/amdx_v1/
├── candidate_audit.csv
├── trades.csv
├── metrics.json
└── equity_curve.png
```

## Important caveats

This is a research starter, not a claim that the published AMDX results have
been reproduced.

You still need to decide and document:

- whether midpoint invalidation uses wick or close
- exact sweep definition and any sweep buffer
- whether the entry bar may hit stop/target
- exact session-close handling
- news filtering
- commissions and empirical slippage
- same-bar stop/target ordering using tick data
- canonical 5-minute versus 15-minute version

The simulator currently uses a conservative stop-first assumption whenever
both stop and target are touched in the same bar.

## Recommended next step

Start with one pair and one year, inspect 20-30 generated setups manually,
then expand to all four pairs and 2021-2025.
