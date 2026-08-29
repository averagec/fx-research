from __future__ import annotations
import argparse, lzma
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

DTYPE = np.dtype([
    ("millisecond", ">u4"),
    ("ask_raw", ">u4"),
    ("bid_raw", ">u4"),
    ("ask_volume", ">f4"),
    ("bid_volume", ">f4"),
])
SCALE = {"EURUSD":100000,"GBPUSD":100000,"EURJPY":1000,"GBPJPY":1000}

def hour_from_path(path: Path):
    year=int(path.parents[2].name); month=int(path.parents[1].name); day=int(path.parent.name)
    hour=int(path.name[:2])
    return datetime(year,month,day,hour,tzinfo=timezone.utc)

def decode(path: Path, symbol: str):
    raw=lzma.decompress(path.read_bytes())
    if len(raw)%20: raise ValueError(f"Bad record size: {path}")
    arr=np.frombuffer(raw,dtype=DTYPE)
    base=pd.Timestamp(hour_from_path(path))
    scale=SCALE[symbol]
    return pd.DataFrame({
        "timestamp_utc": base + pd.to_timedelta(arr["millisecond"],unit="ms"),
        "ask": arr["ask_raw"].astype("float64")/scale,
        "bid": arr["bid_raw"].astype("float64")/scale,
        "ask_volume": arr["ask_volume"].astype("float64"),
        "bid_volume": arr["bid_volume"].astype("float64"),
    })

def to_m5(ticks, symbol):
    ticks=ticks.sort_values("timestamp_utc").drop_duplicates(["timestamp_utc","bid","ask"]).set_index("timestamp_utc")
    bid=ticks["bid"].resample("5min").ohlc(); ask=ticks["ask"].resample("5min").ohlc()
    cnt=ticks["bid"].resample("5min").count()
    bars=pd.DataFrame({
        "bid_open":bid["open"],"bid_high":bid["high"],"bid_low":bid["low"],"bid_close":bid["close"],
        "ask_open":ask["open"],"ask_high":ask["high"],"ask_low":ask["low"],"ask_close":ask["close"],
        "tick_count":cnt,
    }).dropna().reset_index()
    bars.insert(1,"symbol",symbol)
    return bars

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--symbol",required=True)
    p.add_argument("--year",type=int,required=True)
    p.add_argument("--month",type=int,required=True)
    p.add_argument("--input",default="data/raw/dukascopy")
    p.add_argument("--output",default="data/normalized/m5")
    a=p.parse_args()
    symbol=a.symbol.upper().replace("/","")
    src=Path(a.input)/symbol/f"{a.year:04d}"/f"{a.month:02d}"
    files=sorted(src.rglob("*h_ticks.bi5"))
    if not files: raise SystemExit(f"No files under {src}")
    frames=[]; failures=[]
    for i,path in enumerate(files,1):
        try: frames.append(decode(path,symbol))
        except Exception as e: failures.append(f"{path}: {e}")
        if i%100==0 or i==len(files): print(f"Decoded {i}/{len(files)}")
    ticks=pd.concat(frames,ignore_index=True)
    bars=to_m5(ticks,symbol)
    out=Path(a.output)/symbol/f"{a.year:04d}"/f"{a.month:02d}.parquet"
    out.parent.mkdir(parents=True,exist_ok=True); bars.to_parquet(out,index=False)
    q=Path("data/quality_reports"); q.mkdir(parents=True,exist_ok=True)
    report=q/f"{symbol}_{a.year:04d}_{a.month:02d}.txt"
    report.write_text("\n".join([
        f"symbol={symbol}",f"source_files={len(files)}",f"tick_rows={len(ticks)}",f"m5_rows={len(bars)}",
        f"first_tick={ticks['timestamp_utc'].min()}",f"last_tick={ticks['timestamp_utc'].max()}",
        f"negative_spreads={(ticks['ask']<ticks['bid']).sum()}",f"decode_failures={len(failures)}",*failures
    ]),encoding="utf-8")
    print("Wrote:",out); print("Quality:",report)

if __name__=="__main__":
    main()
