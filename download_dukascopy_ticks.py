from __future__ import annotations
import argparse, concurrent.futures as futures, hashlib, json, time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
BASE_URL = "https://datafeed.dukascopy.com/datafeed"
USER_AGENT = "fx-research/0.1"
@dataclass(frozen=True)
class Job:
    symbol: str
    ts: datetime
    path: Path
    @property
    def url(self) -> str:
        m = self.ts.month - 1
        return f"{BASE_URL}/{self.symbol}/{self.ts.year:04d}/{m:02d}/{self.ts.day:02d}/{self.ts.hour:02d}h_ticks.bi5"
def hours(start, end):
    cur = start
    while cur < end:
        yield cur
        cur += timedelta(hours=1)
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()
def fetch(job: Job, retries=4, timeout=30):
    job.path.parent.mkdir(parents=True, exist_ok=True)
    if job.path.exists() and job.path.stat().st_size > 0:
        return {"status":"cached","symbol":job.symbol,"hour":job.ts.isoformat(),"path":str(job.path),"bytes":job.path.stat().st_size,"sha256":sha256(job.path)}
    req = Request(job.url, headers={"User-Agent": USER_AGENT})
    err = ""
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=timeout) as r:
                data = r.read()
            if not data:
                return {"status":"empty","symbol":job.symbol,"hour":job.ts.isoformat(),"url":job.url}
            tmp = job.path.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(job.path)
            return {"status":"downloaded","symbol":job.symbol,"hour":job.ts.isoformat(),"path":str(job.path),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
        except HTTPError as e:
            if e.code == 404:
                return {"status":"missing","symbol":job.symbol,"hour":job.ts.isoformat(),"url":job.url,"http_code":404}
            err = f"HTTP {e.code}"
        except OSError as e:
            # OSError covers URLError, TimeoutError, ConnectionError, and
            # ssl.SSLError (including SSLWantReadError) -- i.e. essentially
            # every network/socket/TLS failure mode. A batch job with tens
            # of thousands of independent requests must never let one
            # connection glitch kill the whole run.
            err = repr(e)
        except Exception as e:
            # last-resort safety net: this script runs unattended for
            # hours, so ANY unexpected exception on a single job should be
            # recorded and skipped, never allowed to crash the batch.
            err = f"unexpected: {e!r}"
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    return {"status":"failed","symbol":job.symbol,"hour":job.ts.isoformat(),"url":job.url,"error":err}
def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--output", default="data/raw/dukascopy")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--retries", type=int, default=4)
    a = p.parse_args()
    start, end = parse_date(a.start), parse_date(a.end)
    root = Path(a.output)
    jobs = []
    for symbol in a.symbols:
        symbol = symbol.upper().replace("/","")
        for ts in hours(start, end):
            path = root/symbol/f"{ts.year:04d}"/f"{ts.month:02d}"/f"{ts.day:02d}"/f"{ts.hour:02d}h_ticks.bi5"
            jobs.append(Job(symbol, ts, path))
    manifest_dir = Path("data/manifests"); manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir/f"dukascopy_{'-'.join(a.symbols)}_{a.start}_{a.end}.jsonl"
    counts={}
    with manifest.open("a", encoding="utf-8") as out, futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        fetch_fn = lambda job: fetch(job, retries=a.retries, timeout=a.timeout)
        for i,res in enumerate(ex.map(fetch_fn,jobs),1):
            out.write(json.dumps(res)+"\n"); out.flush()
            counts[res["status"]] = counts.get(res["status"],0)+1
            if i % 50 == 0 or i == len(jobs): print(f"{i}/{len(jobs)} | {counts}")
    print("Manifest:", manifest)
    print("Summary:", counts)
if __name__ == "__main__":
    main()