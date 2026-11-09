# Metric dictionary

Generated from `sql/01_definitions.sql` by `build_dashboard.py`. The governed definition is the one every dashboard reads.

## Revenue (monthly)

| Id | Definition | Governed | Usually used by | Rule | Where it goes wrong |
|---|---|---|---|---|---|
| R1 | Ledger total |  | Whoever sums the table first | SUM(quantity x price) over every row in the file. | Mixes product sales with postage, bank charges, manual entries, bad-debt adjustments and test items. |
| R2 | Gross sales |  | Sales and marketing | Product lines on non-cancelled invoices, positive quantity and price. Duplicates kept. | Ignores returns, so it only ever looks better than the cash that stays. |
| R3 | Net sales |  | Finance, quick version | All product lines including cancellation credits, dated when the credit was issued. Duplicates kept. | Duplicate lines (including the sheet overlap) still inflate it; returns hit the month they are credited, not the month of the sale. |
| R4 | Net clean revenue | yes | Governed definition | R3 after removing exact duplicate lines (same invoice, item, quantity, price, timestamp, customer). | A true repeat scan on one invoice is indistinguishable from a duplicate, so this can undercount slightly. |
| R5 | Identified-customer revenue |  | CRM and lifecycle marketing | R4 restricted to rows with a Customer ID. | Silently drops guest checkouts, so it shrinks whenever guest share grows. |

## Active customers (monthly)

| Id | Definition | Governed | Usually used by | Rule | Where it goes wrong |
|---|---|---|---|---|---|
| A1 | Any record |  | Data warehouse default | Distinct Customer IDs on any row in the month, including returns and fees. | A customer who only returned something, or only paid a fee, counts as active. |
| A2 | Purchasing customers | yes | Governed definition | Distinct Customer IDs with at least one purchase line (product, non-cancelled, positive quantity and price) in the month. | Guest checkouts have no ID and are not counted here; the dictionary reports them next to it. |
| A3 | Net-positive customers |  | Finance | Distinct Customer IDs whose net clean spend in the month is above zero. | A customer who buys and returns the same value in a month disappears. |
| A4 | Buyers incl. guests |  | E-commerce operations | A2 plus one buyer for every distinct guest invoice. | A guest who orders three times is three buyers, so the count drifts up as guest checkout grows. |
| A5 | Trailing 90-day active |  | Retention and CRM | Distinct Customer IDs with a purchase in the 90 days up to month end. Needs 90 days of history, so the first months are blank. | Smooth by construction: it reacts to a change about three months late. |

## Average order value (monthly)

| Id | Definition | Governed | Usually used by | Rule | Where it goes wrong |
|---|---|---|---|---|---|
| V1 | Ledger per invoice |  | Whoever divides the table first | R1 divided by every distinct invoice number, including cancellations and fee-only invoices. | Cancellation invoices lower the numerator and add to the denominator at the same time. |
| V2 | Clean gross per invoice | yes | Governed definition | Gross product value of purchase invoices (duplicates removed) divided by the count of those invoices. | One invoice is one order, so a customer who splits a basket looks like two smaller orders. |
| V3 | Net per invoice |  | Finance, quick version | R4 (net of returns) divided by the count of purchase invoices. | Numerator subtracts returns, denominator ignores the matching invoices, so the ratio is biased down. |
| V4 | Median invoice value |  | Analysts who distrust outliers | Median gross product value of purchase invoices. | Hides wholesale orders, which is where most of the money is. |
| V5 | Value per consolidated order |  | Customer analytics | Clean gross value divided by orders, where one order is one customer on one day (one invoice for guests). | Merges real separate orders placed on the same day. |

## Shared rules

- A product line has a stock code of five digits (optionally followed by letters) or starting with DCGS. Everything else (POST, DOT, M, BANK CHARGES, ADJUST, TEST, GIFT_ and similar) is not product revenue.
- A purchase line is a product line on a non-cancelled invoice with quantity > 0 and price > 0.
- Two lines are duplicates when invoice, stock code, quantity, price, timestamp, customer and country all match. The first is kept.
- A month is compared only when the file covers every day of it.
- Revenue is in pounds as recorded in the file.
