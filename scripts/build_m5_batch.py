"""
Batch-runs build_m5_from_bi5.py across every symbol x month combination
for a given year, so you don't have to type 48 commands by hand.

Skips a symbol/month combo if the output parquet already exists (so it's
safe to re-run after adding more symbols/years later, or after a partial
run). Continues past individual failures (e.g. a month with no raw data
yet) rather than aborting the whole batch, and prints a summary at the end.

Usage:
    python build_m5_batch.py --symbols GBPUSD EURUSD EURJPY GBPJPY --year 2021
    python build_m5_batch.py --symbols GBPUSD --year 2021 --months 1 2 3
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--months", type=int, nargs="+", default=list(range(1, 13)))
    p.add_argument("--input", default="data/raw/dukascopy")
    p.add_argument("--output", default="data/normalized/m5")
    p.add_argument("--force", action="store_true",
                    help="rebuild even if the output parquet already exists")
    args = p.parse_args()

    results = {"built": [], "skipped_exists": [], "skipped_no_data": [], "failed": []}

    for symbol in args.symbols:
        symbol = symbol.upper().replace("/", "")
        for month in args.months:
            out_path = Path(args.output) / symbol / f"{args.year:04d}" / f"{month:02d}.parquet"
            src_path = Path(args.input) / symbol / f"{args.year:04d}" / f"{month:02d}"
            label = f"{symbol} {args.year:04d}-{month:02d}"

            if out_path.exists() and not args.force:
                print(f"[skip: exists] {label}")
                results["skipped_exists"].append(label)
                continue

            if not src_path.exists() or not any(src_path.rglob("*.bi5")):
                print(f"[skip: no raw data] {label} -- {src_path} has no .bi5 files")
                results["skipped_no_data"].append(label)
                continue

            print(f"[building] {label} ...")
            proc = subprocess.run(
                [sys.executable, "build_m5_from_bi5.py",
                 "--symbol", symbol, "--year", str(args.year), "--month", str(month)],
                capture_output=True, text=True,
            )
            if proc.returncode == 0:
                print(f"[ok] {label}")
                results["built"].append(label)
            else:
                print(f"[FAILED] {label}\n{proc.stderr.strip()[-500:]}")
                results["failed"].append(label)

    print("\n" + "=" * 50)
    print(f"Built: {len(results['built'])}")
    print(f"Skipped (already exists): {len(results['skipped_exists'])}")
    print(f"Skipped (no raw data yet): {len(results['skipped_no_data'])}")
    print(f"Failed: {len(results['failed'])}")
    if results["failed"]:
        print("\nFailed combos (re-run individually to see full error):")
        for f in results["failed"]:
            print(f"  - {f}")
    if results["skipped_no_data"]:
        print("\nSkipped, no raw data yet (probably still downloading or not started):")
        for s in results["skipped_no_data"]:
            print(f"  - {s}")


if __name__ == "__main__":
    main()