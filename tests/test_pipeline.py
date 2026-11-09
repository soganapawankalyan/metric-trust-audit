#!/usr/bin/env python3
"""Checks that the SQL results are right. Run after run_all.py:   python3 -I tests/test_pipeline.py
1. Reconciliation: the gaps between definitions add up exactly (to the penny).
2. Cross-engine: R4 and A2 recomputed in pandas straight from the CSV must equal the SQL answers.
3. Logic: orderings that must hold (A4 >= A2 >= A3, partial month excluded, ...).
Exit code 1 if anything fails."""
import sqlite3, sys
import pandas as pd

con = sqlite3.connect("work/audit.db")
fails, passed = [], 0


def check(name, ok, detail=""):
    global passed
    if ok:
        passed += 1
        print(f"  ok    {name}")
    else:
        fails.append(name)
        print(f"  FAIL  {name}  {detail}")


q = lambda s: pd.read_sql(s, con)

print("1. reconciliation")
r = q("SELECT SUM(r1) r1, SUM(r2) r2, SUM(r3) r3, SUM(r4) r4, SUM(r5) r5 FROM m_revenue").iloc[0]
b = q("SELECT SUM(gross) g, SUM(returns_and_credits) rc, SUM(dup_repeat) dr, SUM(dup_cross_sheet) dc, SUM(unidentified) u, SUM(non_product) n FROM m_bridge").iloc[0]
check("ledger = net sales + non-product lines", abs(r.r1 - r.r3 - b.n) < 0.01, r.r1 - r.r3 - b.n)
check("gross sales + returns/credits = net sales", abs(b.g + b.rc - r.r3) < 0.01, b.g + b.rc - r.r3)
check("bridge gross matches R2", abs(b.g - r.r2) < 0.01)
check("net sales - duplicates = net clean", abs(r.r3 - b.dr - b.dc - r.r4) < 0.01)
check("net clean - unidentified = identified-customer revenue", abs(r.r4 - b.u - r.r5) < 0.01)
lines = q("SELECT COUNT(*) n, SUM(line_value) s FROM lines").iloc[0]
raw = q("SELECT COUNT(*) n, SUM(Quantity*Price) s FROM raw").iloc[0]
check("no rows lost between raw and lines", lines.n == raw.n)
check("ledger total equals raw sum of quantity x price", abs(lines.s - raw.s) < 0.01 and abs(lines.s - r.r1) < 0.01)

print("2. cross-engine (pandas from the CSV)")
df = pd.read_csv("data/raw/online_retail_ii.csv", dtype={"Invoice": str, "StockCode": str, "Customer ID": str}, keep_default_na=False)
df["sc"] = df.StockCode.str.upper().str.strip()
df["month"] = df.InvoiceDate.str[:7]
df["v"] = df.Quantity * df.Price
df["cid"] = df["Customer ID"].replace("", pd.NA)
df["prod"] = df.sc.str.match(r"^\d{5}") | df.sc.str.startswith("DCGS")
key = ["Invoice", "sc", "Quantity", "Price", "InvoiceDate", "Customer ID", "Country"]
df["first"] = ~df.duplicated(key, keep="first")
p4 = df[df["prod"] & df["first"]].groupby("month").v.sum()
s4 = q("SELECT month, r4 FROM m_revenue").set_index("month").r4
check("R4 by month matches pandas", (p4.reindex(s4.index).fillna(0) - s4.fillna(0)).abs().max() < 0.01, (p4.reindex(s4.index).fillna(0) - s4.fillna(0)).abs().max())
buy = df[df["prod"] & ~df.Invoice.str.startswith("C") & (df.Quantity > 0) & (df.Price > 0) & df.cid.notna()]
pa2 = buy.groupby("month").cid.nunique()
sa2 = q("SELECT month, a2 FROM m_customers").set_index("month").a2
check("A2 by month matches pandas", (pa2.reindex(sa2.index).fillna(0) - sa2.fillna(0)).abs().max() == 0)
gbuy = df[df["prod"] & ~df.Invoice.str.startswith("C") & (df.Quantity > 0) & (df.Price > 0) & df.first]
pv2 = gbuy.groupby(["month", "Invoice"]).v.sum().groupby("month").mean()
sv2 = q("SELECT month, v2 FROM m_aov").set_index("month").v2
check("V2 by month matches pandas", (pv2.reindex(sv2.index) - sv2).abs().max() < 0.01)
pv4 = gbuy.groupby(["month", "Invoice"]).v.sum().groupby("month").median()
sv4 = q("SELECT month, v4 FROM m_aov").set_index("month").v4
check("V4 (median) by month matches pandas", (pv4.reindex(sv4.index) - sv4).abs().max() < 0.01)

print("3. logic")
c = q("SELECT c.*, m.is_full FROM m_customers c JOIN months m USING(month)")
check("A4 >= A2 in every month", (c.a4 >= c.a2).all())
check("A1 >= A2 in every month", (c.a1 >= c.a2).all())
check("A2 >= A3 in every month", (c.a2 >= c.a3).all())
check("trailing-90 is blank only where history is short", c[c.a5.isna()].month.max() <= "2010-02" if c.a5.isna().any() else True)
m = q("SELECT month, is_full FROM months ORDER BY month")
check("last month of the file is flagged partial", m.iloc[-1].is_full == 0 and m.iloc[:-1].is_full.min() == 1)
ml = q("SELECT COUNT(*) n FROM metric_long WHERE is_full=1 AND value IS NULL AND def_id <> 'A5'").n[0]
check("no missing values in full months (except A5 warm-up)", ml == 0, ml)
check("each metric has exactly one governed definition", (q("SELECT metric, SUM(governed) g FROM definitions GROUP BY metric").g == 1).all())
dup = q("SELECT COUNT(*) n FROM (SELECT 1 FROM lines WHERE dup_rank = 1 GROUP BY invoice, stock_code, qty, price, ts, COALESCE(customer_id,''), country HAVING COUNT(*) > 1)").n[0]
check("after dedupe no identical line remains", dup == 0)

src = open("data/raw/_source.txt").read().strip()
if src == "demo":
    print("4. planted effects must be found (demo data only)")
    cs = q("SELECT month, COUNT(*) n FROM lines WHERE dup_kind='cross_sheet' GROUP BY month")
    check("sheet overlap detected, and only in Dec 2010", list(cs.month) == ["2010-12"], list(cs.month))
    g = q("SELECT guest_share FROM guest_share ORDER BY month").guest_share
    check("guest share rises over 2011", g.iloc[-1] > g.iloc[0] + 0.15)
    a = q("SELECT v2, v4 FROM m_aov WHERE month = '2010-10'").iloc[0]
    check("Oct 2010 wholesale invoices pull mean AOV far above median", a.v2 > 2 * a.v4)
    rr = q("SELECT month, return_rate FROM causes_monthly ORDER BY return_rate DESC LIMIT 1").iloc[0]
    check("returns spike lands in Jan 2011", rr.month == "2011-01", rr.month)

print(f"\n{passed} passed, {len(fails)} failed")
sys.exit(1 if fails else 0)
