# Dukascopy tick-data setup

Copy both `.py` files into the root of `fx-research`.

## Download GBPUSD January 2021

```powershell
python download_dukascopy_ticks.py `
  --symbols GBPUSD `
  --start 2021-01-01 `
  --end 2021-02-01 `
  --workers 6
```

The end date is exclusive. The command is resume-safe.

## Build M5 bid/ask bars

```powershell
python build_m5_from_bi5.py `
  --symbol GBPUSD `
  --year 2021 `
  --month 1
```

Outputs:

```text
data/normalized/m5/GBPUSD/2021/01.parquet
data/quality_reports/GBPUSD_2021_01.txt
```

Inspect the quality report before scaling to more months or symbols.
