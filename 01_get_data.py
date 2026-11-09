#!/usr/bin/env python3
"""
Project: "One metric, five answers" - get the data.

Real data:  UCI "Online Retail II" (a UK online gift-ware wholesaler, Dec 2009 - Dec 2011, ~1.07M invoice lines).
            python3 01_get_data.py                  downloads it from the UCI repository
            python3 01_get_data.py --file PATH      use a copy you downloaded yourself (.zip, .xlsx or .csv)
Demo data:  python3 01_get_data.py --demo           synthetic data with the same columns and the same kinds of mess,
                                                    so the whole pipeline can run offline. Everything downstream labels it as demo.

Writes data/raw/online_retail_ii.csv and data/raw/_source.txt.   Needs: pandas, numpy, openpyxl (xlsx only).
"""
import argparse, io, os, sys, urllib.request, zipfile
import numpy as np
import pandas as pd

URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
PAGE = "https://archive.ics.uci.edu/dataset/502/online+retail+ii"
OUT = "data/raw/online_retail_ii.csv"
COLS = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]
OUTCOLS = COLS + ["Sheet"]


def normalize(df):
    df = df.rename(columns={c: c.strip() for c in df.columns})
    alias = {"CustomerID": "Customer ID", "Customer_ID": "Customer ID", "UnitPrice": "Price", "Unit Price": "Price"}
    df = df.rename(columns=alias)
    miss = [c for c in COLS if c not in df.columns]
    if miss:
        sys.exit(f"Missing columns {miss}. Found: {list(df.columns)}")
    if "Sheet" not in df.columns:
        df["Sheet"] = "unknown"
    df = df[OUTCOLS].copy()
    df["Invoice"] = df["Invoice"].astype(str).str.strip()
    df["StockCode"] = df["StockCode"].astype(str).str.strip().str.upper()
    df["Quantity"] = pd.to_numeric(df["Quantity"])
    df["Price"] = pd.to_numeric(df["Price"])
    cid = pd.to_numeric(df["Customer ID"], errors="coerce")
    df["Customer ID"] = cid.map(lambda v: "" if pd.isna(v) else str(int(v)))
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def from_path(path):
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.lower().endswith((".xlsx", ".csv"))]
            if not names:
                sys.exit(f"No .xlsx or .csv inside {path}: {z.namelist()}")
            data = z.read(names[0])
            return from_bytes(names[0], data)
    with open(path, "rb") as f:
        return from_bytes(path, f.read())


def from_bytes(name, data):
    if name.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
    print("  reading the Excel file (about a minute)...")
    sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, dtype={"Customer ID": "float64", "Invoice": str, "StockCode": str})
    print("  sheets:", {k: len(v) for k, v in sheets.items()})
    return pd.concat([v.assign(Sheet=k) for k, v in sheets.items()], ignore_index=True)


def download():
    print(f"Downloading {URL} ...")
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "portfolio-metric-audit/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            blob = r.read()
    except Exception as e:
        sys.exit(f"Download failed ({e}).\nOpen {PAGE} in a browser, download the zip, then run:\n  python3 01_get_data.py --file ~/Downloads/online_retail_ii.zip")
    print(f"  {len(blob)/1e6:.1f} MB")
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = [n for n in z.namelist() if n.lower().endswith((".xlsx", ".csv"))]
        return from_bytes(names[0], z.read(names[0]))


def demo(seed=7):
    """Synthetic retailer with the same kinds of mess as the real file, plus four PLANTED effects the audit must find:
       1. Dec 1-9 2010 appears on both sheets (cross-sheet duplicates)
       2. returns spike in Jan 2011
       3. guest checkout share climbs from Mar 2011 (identified-customer metrics diverge from all-buyer metrics)
       4. a handful of very large wholesale invoices in Oct 2010 (mean vs median order value)
       Not real data. Every output built from it is labelled DEMO."""
    rng = np.random.default_rng(seed)
    days = pd.date_range("2009-12-01", "2011-12-09")
    n_cust = 4200
    cust_country = rng.choice(["United Kingdom", "Germany", "France", "EIRE", "Spain", "Netherlands", "Belgium", "Switzerland", "Portugal", "Australia"], n_cust,
                              p=[.905, .018, .017, .016, .008, .008, .008, .006, .006, .008])
    cust_ids = rng.choice(np.arange(12346, 18287), n_cust, replace=False)
    catalog = sorted({f"{rng.integers(10000, 99999)}{rng.choice(['', '', '', 'A', 'B', 'P'])}" for _ in range(900)})
    price_of = {c: round(float(np.clip(rng.lognormal(1.0, .7), 0.2, 60)), 2) for c in catalog}
    desc_of = {c: f"ITEM {c}" for c in catalog}
    bought, rows, inv_no = {}, [], 490000
    for d in days:
        if d.weekday() == 5:
            continue
        season = 1 + 0.9 * np.exp(-((d.dayofyear - 320) / 40.0) ** 2) + 0.35 * (d.year - 2009) / 2
        p_guest = 0.20 if d < pd.Timestamp("2011-03-01") else min(0.45, 0.20 + 0.25 * (d - pd.Timestamp("2011-03-01")).days / 275)
        p_cancel = 0.40 if (d.year == 2010 and d.month == 12) else 0.04
        n_inv = rng.poisson(24 * season)
        for _ in range(n_inv):
            inv_no += 1
            guest = rng.random() < p_guest
            ci = rng.integers(0, n_cust)
            cid = "" if guest else str(cust_ids[ci])
            ctry = "United Kingdom" if guest else cust_country[ci]
            ts = d + pd.Timedelta(minutes=int(rng.integers(8 * 60, 18 * 60)))
            n_l = int(np.clip(rng.geometric(0.11), 1, 60))
            inv = str(inv_no)
            for sc in rng.choice(catalog, n_l, replace=False):
                q = int(np.clip(rng.geometric(0.18), 1, 120))
                rows.append((inv, sc, desc_of[sc], q, ts, price_of[sc], cid, ctry))
                if cid:
                    bought.setdefault(cid, []).append((sc, price_of[sc], q))
            if rng.random() < 0.08:
                rows.append((inv, "POST", "POSTAGE", 1, ts, float(rng.choice([18, 18, 30, 60])), cid, ctry))
            if rng.random() < 0.004:
                rows.append((inv, "DOT", "DOTCOM POSTAGE", 1, ts, round(float(rng.uniform(100, 900)), 2), cid, ctry))
            if rng.random() < 0.003:
                rows.append((inv, "M", "Manual", 1, ts, round(float(rng.uniform(5, 400)), 2), cid, ctry))
            if rng.random() < 0.002:
                rows.append((inv, "BANK CHARGES", "Bank Charges", 1, ts, 15.0, cid, ctry))
            if rng.random() < 0.003:
                rows.append((inv, "TEST001", "This is a test product.", 1, ts, 4.5, cid, ctry))
            if rng.random() < 0.006:
                rows.append((inv, rng.choice(catalog), "damaged", int(rng.integers(1, 20)), ts, 0.0, cid, ctry))
            if cid and rng.random() < p_cancel and bought.get(cid):
                inv_no += 1
                cinv = f"C{inv_no}"
                pick = [bought[cid][i] for i in rng.integers(0, len(bought[cid]), int(rng.integers(1, 5)))]
                for sc, p, q in pick:
                    rows.append((cinv, sc, desc_of[sc], -int(max(1, q * rng.uniform(0.3, 1.0))), ts + pd.Timedelta(days=int(rng.integers(1, 30))), p, cid, ctry))
                if rng.random() < 0.06:
                    rows.append((cinv, "D", "Discount", -1, ts, round(float(rng.uniform(3, 60)), 2), cid, ctry))
            if rng.random() < 0.0012:
                inv_no += 1
                rows.append((f"A{inv_no}", "B", "Adjust bad debt", 1, ts, -round(float(rng.uniform(100, 12000)), 2), "", "United Kingdom"))
        if d.year == 2010 and d.month == 10 and d.day in (5, 12, 19, 21, 26, 28):      # planted: whale invoices
            inv_no += 1
            ci = rng.integers(0, n_cust)
            ts = d + pd.Timedelta(hours=11)
            for sc in rng.choice(catalog, 14, replace=False):
                rows.append((str(inv_no), sc, desc_of[sc], int(rng.integers(150, 400)), ts, price_of[sc], str(cust_ids[ci]), cust_country[ci]))
    df = pd.DataFrame(rows, columns=["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"])
    df = df[df.InvoiceDate <= pd.Timestamp("2011-12-09 12:00")]
    df = pd.concat([df, df.sample(frac=0.003, random_state=1)])                         # within-sheet repeat lines
    s1_end, s2_start = pd.Timestamp("2010-12-10"), pd.Timestamp("2010-12-01")
    sheet1 = df[df.InvoiceDate < s1_end].assign(Sheet="Year 2009-2010")
    sheet2 = df[df.InvoiceDate >= s2_start].assign(Sheet="Year 2010-2011")             # planted: 9-day overlap on both sheets
    df = pd.concat([sheet1, sheet2]).sort_values(["InvoiceDate", "Sheet"], kind="stable").reset_index(drop=True)
    df["InvoiceDate"] = df["InvoiceDate"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    os.makedirs("data/raw", exist_ok=True)
    if a.demo:
        print("Generating DEMO data (synthetic, same schema as the real file)...")
        df, src = demo(), "demo"
    else:
        df, src = (normalize(from_path(a.file)) if a.file else normalize(download())), "real"
    df[OUTCOLS].to_csv(OUT, index=False)
    open("data/raw/_source.txt", "w").write(src)
    d = pd.to_datetime(df["InvoiceDate"])
    print(f"\nWrote {OUT}: {len(df):,} rows, {d.min().date()} to {d.max().date()}  (source: {src})")
    print("customer id missing:", f"{(df['Customer ID'].astype(str)=='').mean():.1%}", "| countries:", df["Country"].nunique(), "| invoices:", df["Invoice"].nunique())
    print("cancellation invoices:", df[df["Invoice"].astype(str).str.startswith("C")]["Invoice"].nunique())


if __name__ == "__main__":
    main()
