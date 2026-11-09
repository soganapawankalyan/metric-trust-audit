#!/usr/bin/env python3
"""Turns results/*.csv into plain-English findings (docs/findings.md) to paste into the README. Every figure is read from the results."""
import json, os
import pandas as pd

R = lambda n: pd.read_csv(f"results/{n}.csv")
meta = json.load(open("results/meta.json"))
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ml = lambda m: f"{MON[int(m[5:7]) - 1]} {m[:4]}"
gbp = lambda v: f"£{v/1e6:.2f}M" if abs(v) >= 1e6 else f"£{v/1e3:,.0f}K" if abs(v) >= 1e4 else f"£{v:,.0f}"
defs, mlong, months = R("definitions"), R("metric_long"), R("months")
full = months[months.is_full == 1].month.tolist(); latest = full[-1]
NAME = {"revenue": "Revenue", "customers": "Active customers", "aov": "Average order value"}
orlist = lambda xs: xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " or " + xs[-1]
out = []
if meta["source"] == "demo":
    out += ["> **These figures come from the synthetic demo data, not from the real file. Re-run the pipeline on the real data and regenerate this file before publishing.**", ""]
for metric in NAME:
    d = defs[defs.metric == metric].set_index("def_id")
    gid = d[d.governed == 1].index[0]
    v = mlong[(mlong.metric == metric) & (mlong.month == latest)].set_index("def_id").value
    lo, hi = v.idxmin(), v.idxmax()
    fmt = (lambda x: f"{x:,.0f}") if metric == "customers" else gbp
    ag = R("mom_agree"); ag = ag[ag.metric == metric]
    yoy = R("yoy"); yoy = yoy[yoy.metric == metric]
    best = R("best_month"); best = best[best.metric == metric]
    ymin, ymax = yoy.loc[yoy.yoy_pct.idxmin()], yoy.loc[yoy.yoy_pct.idxmax()]
    sign_split = (yoy.yoy_pct > 0).any() and (yoy.yoy_pct < 0).any()
    out += [f"### {NAME[metric]}",
            f"- In {ml(latest)} the five definitions give **{fmt(v[lo])} ({d.loc[lo, 'name']}) to {fmt(v[hi])} ({d.loc[hi, 'name']})**, a {v[hi]/v[lo]-1:.0%} spread. The governed definition ({d.loc[gid, 'name']}) gives {fmt(v[gid])}.",
            f"- In **{int(ag.flip.sum())} of {len(ag)} comparable months** one definition moved up by 1% or more while another moved down by 1% or more.",
            f"- Year on year (last 12 full months against the 12 before) the answers run from **{ymin.yoy_pct:+.1%} ({d.loc[ymin.def_id, 'name']}) to {ymax.yoy_pct:+.1%} ({d.loc[ymax.def_id, 'name']})**" + (", so the sign of growth depends on the definition." if sign_split else "."),
            f"- The best month on record is {orlist(sorted({ml(m) for m in best.best}))}" + (" depending on the definition." if best.best.nunique() > 1 else " under every definition."), ""]
t = R("trust_tests"); rd = R("analysis_ready").iloc[0]; q = R("quality_monthly").sort_values("dup_pct", ascending=False).iloc[0]
out += ["### Data trust",
        f"- {rd.pct_ready:.1%} of {int(rd.rows_total):,} rows pass every row-level rule; {int((t.severity == 'high').sum())} of {len(t)} automated tests fail at high severity.",
        f"- Duplicate lines peak in {ml(q.month)} at {q.dup_pct:.1%} of that month's rows ({q.cross_sheet_pct:.1%} are present on both sheets of the source workbook).", ""]
os.makedirs("docs", exist_ok=True)
open("docs/findings.md", "w").write("\n".join(out))
print("\n".join(out))
