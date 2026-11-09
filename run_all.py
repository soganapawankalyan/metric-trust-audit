#!/usr/bin/env python3
"""Load the CSV into SQLite, run sql/*.sql in order, export every results table to results/*.csv.
   python3 run_all.py            (reads data/raw/online_retail_ii.csv, writes work/audit.db and results/)"""
import glob, json, os, sqlite3, sys, time
import pandas as pd

CSV, DB = "data/raw/online_retail_ii.csv", "work/audit.db"
EXPORT = ["definitions", "months", "m_revenue", "m_bridge", "m_customers", "m_aov", "metric_long"]


def main(extra_export=()):
    if not os.path.exists(CSV):
        sys.exit(f"{CSV} not found. Run: python3 01_get_data.py   (or add --demo for synthetic data)")
    os.makedirs("work", exist_ok=True); os.makedirs("results", exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    t = time.time()
    n = 0
    for chunk in pd.read_csv(CSV, dtype={"Invoice": str, "StockCode": str, "Customer ID": str, "Sheet": str}, keep_default_na=False, chunksize=200_000):
        chunk.to_sql("raw", con, if_exists="append", index=False)
        n += len(chunk)
    print(f"loaded {n:,} rows into raw ({time.time()-t:.0f}s)")
    for f in sorted(glob.glob("sql/*.sql")):
        t = time.time()
        con.executescript(open(f).read())
        print(f"  ran {os.path.basename(f)} ({time.time()-t:.0f}s)")
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('raw','lines','purchase_days','inv','sqlite_sequence') ORDER BY name")]
    for tname in tables:
        pd.read_sql(f"SELECT * FROM {tname}", con).to_csv(f"results/{tname}.csv", index=False)
    src = open("data/raw/_source.txt").read().strip() if os.path.exists("data/raw/_source.txt") else "unknown"
    meta = {"source": src, "rows": n,
            "first_day": con.execute("SELECT MIN(day) FROM lines").fetchone()[0],
            "last_day": con.execute("SELECT MAX(day) FROM lines").fetchone()[0]}
    json.dump(meta, open("results/meta.json", "w"))
    print(f"exported {len(tables)} tables to results/  | source = {src}")
    con.close()


if __name__ == "__main__":
    main()
