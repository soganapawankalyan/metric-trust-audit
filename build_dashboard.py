#!/usr/bin/env python3
"""Build dashboard/index.html from results/*.csv.  python3 build_dashboard.py
Every sentence on the page that states a finding is written here from the numbers, so a new dataset gets true headlines."""
import json, math
import pandas as pd

R = lambda n: pd.read_csv(f"results/{n}.csv")
meta = json.load(open("results/meta.json"))
demo = meta["source"] == "demo"

months = R("months")
full = months[months.is_full == 1].month.tolist()
latest = full[-1]
ml, defs = R("metric_long"), R("definitions")
MN = {"revenue": "Revenue", "customers": "Active customers", "aov": "Average order value"}
UNIT = {"revenue": "money", "customers": "count", "aov": "money"}
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
mlabel = lambda m: f"{MON[int(m[5:7]) - 1]} {m[:4]}"


def money(v):
    a = abs(v)
    s = f"£{a/1e6:.2f}M" if a >= 1e6 else f"£{a/1e3:.0f}K" if a >= 1e4 else f"£{a:,.0f}"
    return ("-" if v < 0 else "") + s


def num(v):
    return f"{v:,.0f}"


val = lambda metric, v: money(v) if UNIT[metric] == "money" else num(v)
clean = lambda v: None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)

# ------------------------------------------------------------ definitions + colour slots (governed = slot 1 on every metric)
D = []
for metric in MN:
    sub = defs[defs.metric == metric].sort_values("def_id")
    slot = 2
    for _, r in sub.iterrows():
        if r.governed == 1:
            s = 1
        else:
            s, slot = slot, slot + 1
        D.append(dict(metric=metric, id=r.def_id, name=r["name"], owner=r.typical_owner, rule=r.rule, pitfall=r.pitfall, governed=int(r.governed), slot=s))

series = {m: {} for m in MN}
for metric in MN:
    for did in [d["id"] for d in D if d["metric"] == metric]:
        s = ml[(ml.def_id == did) & (ml.is_full == 1)].set_index("month").value.reindex(full)
        series[metric][did] = [clean(x) for x in s]

# ------------------------------------------------------------ decisions
mom = R("mom"); agree = R("mom_agree"); best = R("best_month"); yoy = R("yoy"); ttm = R("ttm"); lat = R("latest_mom")
cr = R("country_rank")
dec = {}
for metric in MN:
    ids = [d["id"] for d in D if d["metric"] == metric]
    e = dict(best={}, latest_mom={}, yoy={}, ttm={}, second_country={})
    for i in ids:
        e["best"][i] = best[best.def_id == i].best.iloc[0]
        x = lat[lat.def_id == i]; e["latest_mom"][i] = clean(x.mom_pct.iloc[0]) if len(x) else None
        x = yoy[yoy.def_id == i]; e["yoy"][i] = clean(x.yoy_pct.iloc[0]) if len(x) else None
        e["ttm"][i] = clean(ttm[ttm.def_id == i].value.iloc[0])
    if metric == "revenue":
        for k, i in zip(["k1", "k2", "k3", "k4", "k5"], ids):
            e["second_country"][i] = cr[cr[k] == 2].country.iloc[0] if (cr[k] == 2).any() else None
    a = agree[agree.metric == metric].sort_values("month")
    e["flips"] = [dict(month=r.month, flip=int(r.flip), disagree=int(r.disagree), range=clean(r.mom_range)) for r in a.itertuples()]
    e["n_flip"], e["n_cmp"], e["n_disagree"] = int(a.flip.sum()), len(a), int(a.disagree.sum())
    e["mom"] = {m: {r.def_id: clean(r.mom_pct) for r in mom[(mom.metric == metric) & (mom.month == m)].itertuples()} for m in a.month}
    dec[metric] = e

drift = R("drift")
dr = {m: {i: [clean(x) for x in drift[(drift.metric == m) & (drift.def_id == i)].set_index("month").ratio.reindex(full)]
          for i in [d["id"] for d in D if d["metric"] == m and not d["governed"]]} for m in MN}

# ------------------------------------------------------------ bridge, histogram, trust
bridge = {r.month: dict(gross=r.gross, returns=r.returns_and_credits, dup_repeat=r.dup_repeat, dup_cross=r.dup_cross_sheet,
                        unidentified=r.unidentified, non_product=r.non_product) for r in R("m_bridge").itertuples() if r.month in full}
cust_extra = {r.month: dict(guests=int(r.guest_invoices)) for r in R("m_customers").itertuples() if r.month in full}
hist = R("inv_hist"); hist = hist[(hist.n_invoices > 0) | (hist.b <= hist[hist.n_invoices > 0].b.max())]
hist = hist[hist.b >= hist[hist.n_invoices > 0].b.min()]
istats = R("inv_stats").iloc[0]
tests = R("trust_tests"); ready = R("analysis_ready").iloc[0]; quality = R("quality_monthly"); guest = R("guest_share")
npc = R("non_product_codes")
sev_rank = {"high": 0, "medium": 1, "low": 2, "pass": 3}
tests["sr"] = tests.severity.map(sev_rank)

# ------------------------------------------------------------ headlines written from the numbers
H = {}
for metric in MN:
    vals = {d["id"]: series[metric][d["id"]][full.index(latest)] for d in D if d["metric"] == metric}
    vv = {k: v for k, v in vals.items() if v is not None}
    lo, hi = min(vv.values()), max(vv.values())
    H[metric] = dict(spread=hi / lo - 1, lo=lo, hi=hi)
sp = {m: pd.DataFrame(series[m]).dropna() for m in MN}
widest = {}
for m in MN:
    df = sp[m]; s = (df.max(axis=1) / df.min(axis=1) - 1)
    widest[m] = dict(month=full[int(s.reset_index(drop=True).idxmax())] if False else df.index.map(lambda i: full[i])[int(s.values.argmax())], spread=float(s.max()))

pooled = pd.DataFrame(bridge).T
tot = pooled.sum()
pool = dict(returns=-tot.returns / tot.gross, dups=(tot.dup_repeat + tot.dup_cross) / tot.gross, guests=-tot.unidentified / tot.gross if False else tot.unidentified / tot.gross, non_product=tot.non_product)
cross_total = int(tests[tests.test_id == "U2"].rows_failing.iloc[0])
qm = quality.sort_values("dup_pct", ascending=False).iloc[0]

DATA = dict(
    meta=dict(source=meta["source"], demo=demo, rows=meta["rows"], first=meta["first_day"], last=meta["last_day"], latest=latest, n_months=len(full), first_full=full[0]),
    months=full, labels=[mlabel(m) for m in full],
    defs=D, series=series, dec=dec, drift=dr, H=H, widest=widest,
    bridge=bridge, cust_extra=cust_extra,
    pool=dict(returns=float(pool["returns"]), dups=float(pool["dups"]), guests=float(pool["guests"]), non_product=float(pool["non_product"])),
    hist=[dict(lo=r.lo, hi=r.hi, n=int(r.n_invoices), si=float(r.share_invoices), sv=float(r.share_value)) for r in hist.itertuples()],
    istats=dict(mean=float(istats["mean"]), median=float(istats["median"]), top10=float(istats.top10_share), n=int(istats.n_invoices)),
    tests=[dict(id=r.test_id, dim=r.dimension, test=r.test, tested=int(r.rows_tested), failing=int(r.rows_failing), pr=float(r.pct_rows), pv=float(r.pct_value),
                sev=r.severity, handling=r.handling) for r in tests.sort_values(["sr", "pct_rows"], ascending=[True, False]).itertuples()],
    ready=dict(total=int(ready.rows_total), ok=int(ready.rows_ready), pct=float(ready.pct_ready)),
    quality=[dict(month=r.month, dup=float(r.dup_pct), cross=float(r.cross_sheet_pct), nonprod=float(r.non_product_pct), nocust=float(r.no_customer_pct), cancel=float(r.cancel_pct)) for r in quality.sort_values("month").itertuples()],
    guest=[dict(month=r.month, share=float(r.guest_share)) for r in guest.sort_values("month").itertuples()],
    nonprod=[dict(code=r.stock_code, desc=r.description, lines=int(r.lines), net=float(r.net_value)) for r in npc.head(6).itertuples()],
    cross_total=cross_total, worst_dup=dict(month=qm.month, pct=float(qm.dup_pct), cross=float(qm.cross_sheet_pct)),
)
tpl = open("dashboard/template.html").read()
html = tpl.replace("/*DATA*/null", json.dumps(DATA, default=lambda o: None if (isinstance(o, float) and math.isnan(o)) else float(o) if hasattr(o, "item") else str(o), separators=(",", ":")))
open("dashboard/index.html", "w").write(html)
print(f"dashboard/index.html  {len(html)/1024:.0f} KB   latest full month {latest}   demo={demo}")
for m in MN:
    print(f"  {m:10s} spread {H[m]['spread']:.1%}   flips {dec[m]['n_flip']}/{dec[m]['n_cmp']}   widest {widest[m]['month']} {widest[m]['spread']:.1%}")

import os
os.makedirs("docs", exist_ok=True)
lines = ["# Metric dictionary", "", "Generated from `sql/01_definitions.sql` by `build_dashboard.py`. The governed definition is the one every dashboard reads.", ""]
for metric, title in [("revenue", "Revenue (monthly)"), ("customers", "Active customers (monthly)"), ("aov", "Average order value (monthly)")]:
    lines += [f"## {title}", "", "| Id | Definition | Governed | Usually used by | Rule | Where it goes wrong |", "|---|---|---|---|---|---|"]
    for d in [x for x in D if x["metric"] == metric]:
        lines.append(f"| {d['id']} | {d['name']} | {'yes' if d['governed'] else ''} | {d['owner']} | {d['rule']} | {d['pitfall']} |")
    lines.append("")
lines += ["## Shared rules", "",
          "- A product line has a stock code of five digits (optionally followed by letters) or starting with DCGS. Everything else (POST, DOT, M, BANK CHARGES, ADJUST, TEST, GIFT_ and similar) is not product revenue.",
          "- A purchase line is a product line on a non-cancelled invoice with quantity > 0 and price > 0.",
          "- Two lines are duplicates when invoice, stock code, quantity, price, timestamp, customer and country all match. The first is kept.",
          "- A month is compared only when the file covers every day of it.",
          "- Revenue is in pounds as recorded in the file."]
open("docs/metric_dictionary.md", "w").write("\n".join(lines) + "\n")
print("docs/metric_dictionary.md")
