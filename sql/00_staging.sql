-- 00_staging.sql  -  one tidy `lines` table with every flag the metric definitions need.
-- Nothing is deleted here. Rows are FLAGGED, and each metric definition decides what to include.
-- Input: table `raw` (loaded by run_all.py straight from data/raw/online_retail_ii.csv).

DROP TABLE IF EXISTS lines;
CREATE TABLE lines AS
WITH base AS (
  SELECT rowid                                   AS raw_id,
         TRIM(Invoice)                           AS invoice,
         UPPER(TRIM(StockCode))                  AS stock_code,
         NULLIF(TRIM(Description), '')           AS description,
         Quantity                                AS qty,
         Price                                   AS price,
         InvoiceDate                             AS ts,
         NULLIF(TRIM("Customer ID"), '')         AS customer_id,
         Country                                 AS country,
         COALESCE(NULLIF(TRIM(Sheet), ''), 'unknown') AS sheet
  FROM raw
),
flagged AS (
  SELECT b.*,
         substr(ts, 1, 10)                       AS day,
         substr(ts, 1, 7)                        AS month,
         qty * price                             AS line_value,
         CASE WHEN invoice LIKE 'C%' THEN 1 ELSE 0 END AS is_cancel,
         -- a real product has a 5-digit stock code (optionally with a letter suffix) or a DCGS web-shop code;
         -- everything else (POST, DOT, M, BANK CHARGES, ADJUST, TEST001, GIFT_..., etc.) is not a product sale
         CASE WHEN stock_code GLOB '[0-9][0-9][0-9][0-9][0-9]*' OR stock_code LIKE 'DCGS%' THEN 1 ELSE 0 END AS is_product,
         ROW_NUMBER() OVER (k ORDER BY sheet, raw_id)        AS dup_rank,
         FIRST_VALUE(sheet) OVER (k ORDER BY sheet, raw_id)  AS first_sheet
  FROM base b
  WINDOW k AS (PARTITION BY invoice, stock_code, qty, price, ts, COALESCE(customer_id, ''), country)
)
SELECT raw_id, invoice, stock_code, description, qty, price, ts, day, month, customer_id, country, sheet,
       line_value, is_cancel, is_product, dup_rank,
       CASE WHEN dup_rank = 1 THEN NULL
            WHEN sheet <> first_sheet THEN 'cross_sheet'
            ELSE 'repeat' END                    AS dup_kind
FROM flagged;

CREATE INDEX ix_lines_month    ON lines(month);
CREATE INDEX ix_lines_day      ON lines(day);
CREATE INDEX ix_lines_cust_sc  ON lines(customer_id, stock_code);
CREATE INDEX ix_lines_invoice  ON lines(invoice);

-- calendar of months; a month is "full" only if the data covers every day of it
DROP TABLE IF EXISTS months;
CREATE TABLE months AS
SELECT month,
       month || '-01'                                      AS first_day,
       date(month || '-01', '+1 month', '-1 day')          AS last_day,
       CASE WHEN date(month || '-01', '+1 month', '-1 day') <= (SELECT MAX(day) FROM lines)
             AND month || '-01' >= (SELECT MIN(day) FROM lines) THEN 1 ELSE 0 END AS is_full
FROM (SELECT DISTINCT month FROM lines);
