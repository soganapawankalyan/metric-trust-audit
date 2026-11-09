# One metric, five answers

**A metric trust audit.** Ask five analysts for last month's revenue, active customers or average order value and you get five different numbers, all defensible. This project measures how far apart they land, whether the gap changes decisions, and what a governed metric layer fixes.

> Independent portfolio project on public data. It has no connection to the retailer in the data, the data publisher or any employer. The definitions are examples, not claims about how any real company counts.

**Live dashboard:** https://soganapawankalyan.github.io/metric-trust-audit/dashboard/

## The question

Companies that run on dashboards keep hitting the same problem: two reports that should agree do not. The cause is rarely a bug. It is usually that "revenue" has five reasonable meanings and nobody wrote down which one is in use. This audit takes one real transaction file, writes down five definitions each for three common metrics, and answers four things:

1. **How big is the gap?** Same question, same month, five answers.
2. **Does it change decisions?** Best month, direction of the last month, year-on-year growth, biggest markets.
3. **Why do they differ?** A reconciliation that adds up to the penny, one named cause at a time.
4. **Which numbers can you trust?** Fourteen automated data tests, with severity by rule.

## What is in the dashboard

- **The tape.** Revenue is five yes-or-no rules (add postage and fees, net off returns, drop repeated lines, drop lines on both sheets, drop guest orders). Switch them on and off on a calculation tape and the total recomputes, exactly, from the data. Five of the 32 combinations are named definitions; the page tells you which one you built and how far it is from the governed number.
- **All 32 ways to count revenue** for the month, on one axis. Click any dot to load its rules.
- **Your rules against the governed number** over time, and which business answers change (best month, latest change, year-on-year, months called the opposite way).
- **One ruler.** All three metrics on the same scale, each definition as a multiple of the governed one.
- **Over time**, by definition or relative to the governed one, with a table view of every chart.
- **Decisions.** A flip grid for all three metrics (when does one definition say up while another says down?) and a matrix of the same questions asked of each definition.
- **Why they differ** for customers and order value, a data-trust scorecard with the month the duplicates arrived, and the governed metric layer with its dictionary.

## Data

UCI **Online Retail II**: every transaction of a UK-based online gift-ware retailer from 1 Dec 2009 to 9 Dec 2011, 1,067,371 invoice lines in one Excel workbook (Chen, D. (2012), https://doi.org/10.24432/C5CG6D, licensed CC BY 4.0). The loader reads every sheet and tags each row with its sheet name, so the audit can tell whether any lines appear on more than one sheet. The file has the mess a real extract has: cancellation invoices, about 23% of rows with no customer ID, postage and fee lines in the stock-code column, zero and negative prices, and duplicate lines.

The raw data is not committed. The first script downloads it.

## The fifteen definitions

| Metric | Governed definition | The four alternatives |
|---|---|---|
| Revenue | **R4 Net clean revenue** | Ledger total, gross sales, net sales, identified-customer revenue |
| Active customers | **A2 Purchasing customers** | Any record, net-positive, buyers incl. guests, trailing 90-day |
| Average order value | **V2 Clean gross per invoice** | Ledger per invoice, net per invoice, median invoice, per consolidated order |

Full rules, usual owners and failure modes: [docs/metric_dictionary.md](docs/metric_dictionary.md).

## Run it

Needs Python 3 with SQLite 3.28 or newer (check: `python3 -c "import sqlite3; print(sqlite3.sqlite_version)"`).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 01_get_data.py            # downloads the UCI file and writes data/raw/online_retail_ii.csv
python3 run_all.py                # loads it into SQLite, runs sql/*.sql, writes results/*.csv
python3 tests/test_pipeline.py    # reconciliation and cross-engine checks
python3 build_dashboard.py        # writes dashboard/index.html and docs/metric_dictionary.md
python3 make_findings.py          # writes docs/findings.md, plain-English results
```

If the download is blocked, get the zip from https://archive.ics.uci.edu/dataset/502/online+retail+ii and run `python3 01_get_data.py --file ~/Downloads/online_retail_ii.zip`.

No internet or just trying it out: `python3 01_get_data.py --demo` generates synthetic data with the same columns and four planted traps. Every figure built from it is labelled demo on the page.

## How the numbers are checked

`tests/test_pipeline.py` fails the run if any of these break:
- Ledger total = net sales + non-product lines. Gross + returns = net sales. Net sales - duplicates = net clean. Net clean - guest orders = identified-customer revenue. All to the penny.
- Net clean revenue, purchasing customers, clean order value and the median order value are recomputed in pandas straight from the CSV and must equal the SQL results.
- A4 >= A2 >= A3, the last month is flagged partial, every metric has exactly one governed definition.
- On demo data, the four planted traps must be found.

## Repository map

```
01_get_data.py          download or generate the data
run_all.py              load CSV into SQLite, run the SQL, export results
sql/00_staging.sql      one tidy lines table; flags rows instead of deleting them
sql/01_definitions.sql  the fifteen definitions as data (seed of the dictionary)
sql/02_metrics.sql      every definition, month by month, plus the reconciliation columns
sql/03_decisions.sql    do the answers change decisions?
sql/04_drift.sql        does the gap stay constant?
sql/05_trust_tests.sql  fourteen data tests, severity by rule
sql/06_governed_layer.sql  the one table dashboards read
sql/07_dashboard_extracts.sql  small summaries for the charts
build_dashboard.py      results to a self-contained HTML page
make_findings.py        results to plain-English findings
dashboard/              template, built page, design notes
docs/                   metric dictionary, findings
tests/                  reconciliation and cross-engine checks
```

## Findings

Measured on the real file (UCI Online Retail II, 24 full months, Dec 2009 to Nov 2011; the partial Dec 2011 is excluded).

| Metric | Nov 2011, lowest to highest answer | Governed | Months where definitions moved in opposite directions (1% or more) | Year on year, across definitions |
|---|---|---|---|---|
| Revenue | £1.11M to £1.46M (31% spread) | £1.43M | 1 of 23 | -2.1% to +6.7% |
| Active customers | 1,653 to 2,833 (71%) | 1,660 | 4 of 21 | -2.5% to -0.5% |
| Average order value | £298 to £582 (96%) | £528 | 10 of 23 | +0.6% to +17.4% |

What stands out:
- **The damage depends on the metric.** Revenue definitions mostly agree on direction (1 flip in 23 months) but differ in level and in the sign of year-on-year growth: identified-customer revenue says -2.1%, gross sales says +6.7%. Average order value is the worst case: 10 flips, and four different "best months" depending on the definition.
- **Customers look dramatic for a structural reason.** The 71% spread is mostly the trailing 90-day count, which answers a different question (who bought lately) from the monthly count. The monthly definitions sit within about 1% of each other (1,653 to 1,660) before guest checkouts are added.
- **The source file contains a data-quality trap.** Duplicate lines peak in Dec 2010 at 35.4% of that month's rows, and 34.6% are present on both sheets of the workbook. Every definition that does not remove exact duplicates counts those lines twice, which is why the widest gaps in all three metrics fall in Dec 2010.
- **4 of 14 automated tests fail at high severity**, and 95.7% of the 1,067,371 rows pass every row-level rule.

Per-month detail, the 32-way comparison and the full test list are in the dashboard.


## Limits

- One retailer and one two-year file. The pattern is general, the sizes are not.
- No ground truth. A repeated line may be two real scans, so the cleaned definition can undercount slightly.
- The five definitions are a sample of what a real team would argue about, chosen by judgment.
- Revenue is in pounds as recorded. The file does not say how VAT or inflation are treated.
- The trailing 90-day customer count needs 90 days of history, so its first months are blank.
- The last month in the file is partial and is excluded from every comparison.
