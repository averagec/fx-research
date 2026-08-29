"""
Checks every built M5 parquet against its own raw .bi5 inputs and flags
any parquet that is STALE -- i.e. built before all of its source .bi5
files finished downloading. This exact scenario silently corrupted a
month of data earlier: a parquet was built while a download was still
in progress, and every subsequent run kept skipping that month (since
the parquet already existed) even after the missing raw file arrived.

This does not fix anything by itself -- it only tells you which
symbol/month combos need a --force rebuild via build_m5_batch.py.

Usage:
    python check_stale_parquets.py --symbols GBPUSD EURUSD EURJPY GBPJPY --year 2021
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--input", default="data/raw/dukascopy")
    p.add_argument("--output", default="data/normalized/m5")
    args = p.parse_args()

    stale = []
    ok = []
    no_parquet = []

    for symbol in args.symbols:
        symbol = symbol.upper().replace("/", "")
        for month in range(1, 13):
            parquet_path = Path(args.output) / symbol / f"{args.year:04d}" / f"{month:02d}.parquet"
            raw_dir = Path(args.input) / symbol / f"{args.year:04d}" / f"{month:02d}"

            if not parquet_path.exists():
                continue  # nothing to compare -- build_m5_batch.py will handle this normally
            if not raw_dir.exists():
                continue

            raw_files = list(raw_dir.rglob("*.bi5"))
            if not raw_files:
                continue

            parquet_mtime = parquet_path.stat().st_mtime
            newest_raw = max(f.stat().st_mtime for f in raw_files)

            label = f"{symbol} {args.year:04d}-{month:02d}"
            if newest_raw > parquet_mtime:
                gap_hours = (newest_raw - parquet_mtime) / 3600
                stale.append((label, gap_hours))
            else:
                ok.append(label)

    print(f"Checked {len(ok) + len(stale)} symbol/month combos with both a parquet and raw data.\n")

    if stale:
        print(f"[STALE] {len(stale)} parquet(s) built BEFORE their raw data finished arriving:")
        for label, gap_hours in stale:
            print(f"  - {label}  (raw data arrived {gap_hours:.2f}h after the parquet was built)")
        print(f"\nRebuild these with:")
        symbols_str = " ".join(sorted(set(l.split()[0] for l, _ in stale)))
        print(f"  python build_m5_batch.py --symbols {symbols_str} --year {args.year} --force")
    else:
        print("[OK] No stale parquets found -- every parquet is newer than all of its raw inputs.")

    if ok:
        print(f"\n{len(ok)} combo(s) confirmed fresh: {', '.join(ok)}")


if __name__ == "__main__":
    main()