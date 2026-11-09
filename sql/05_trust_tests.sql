-- 05_trust_tests.sql  -  automated data tests, the kind a data-quality job runs on every load.
-- Severity is a rule, not an opinion:  high >= 5% of rows or of money, medium >= 0.5%, low > 0, otherwise pass.

DROP TABLE IF EXISTS trust_tests_raw;
CREATE TABLE trust_tests_raw (test_id TEXT, dimension TEXT, test TEXT, rows_tested INTEGER, rows_failing INTEGER, abs_value_failing REAL, handling TEXT);

INSERT INTO trust_tests_raw
SELECT 'C1', 'Completeness', 'Customer ID is present', COUNT(*), SUM(customer_id IS NULL),
       SUM(CASE WHEN customer_id IS NULL THEN ABS(line_value) ELSE 0 END),
       'Kept in revenue. Excluded from customer counts, reported as guest buyers.' FROM lines;
INSERT INTO trust_tests_raw
SELECT 'C2', 'Completeness', 'Description is present', COUNT(*), SUM(description IS NULL),
       SUM(CASE WHEN description IS NULL THEN ABS(line_value) ELSE 0 END),
       'No metric depends on it. Logged only.' FROM lines;
INSERT INTO trust_tests_raw
SELECT 'U1', 'Uniqueness', 'No repeated line inside one sheet', COUNT(*), SUM(dup_kind = 'repeat'),
       SUM(CASE WHEN dup_kind = 'repeat' THEN ABS(line_value) ELSE 0 END),
       'Removed in R4 and everything built on it. Could be a genuine double scan, so it is flagged, not deleted.' FROM lines;
INSERT INTO trust_tests_raw
SELECT 'U2', 'Uniqueness', 'No line present on both sheets', COUNT(*), SUM(dup_kind = 'cross_sheet'),
       SUM(CASE WHEN dup_kind = 'cross_sheet' THEN ABS(line_value) ELSE 0 END),
       'Removed in R4. The two sheets cover an overlapping stretch of days.' FROM lines;
INSERT INTO trust_tests_raw
SELECT 'V1', 'Validity', 'Stock code is a real product', COUNT(*), SUM(is_product = 0),
       SUM(CASE WHEN is_product = 0 THEN ABS(line_value) ELSE 0 END),
       'Postage, fees, manual lines, adjustments and test items are not product revenue. Excluded from R2 to R5.' FROM lines;
INSERT INTO trust_tests_raw
SELECT 'V2', 'Validity', 'Price is above zero', COUNT(*), SUM(price <= 0), SUM(CASE WHEN price <= 0 THEN ABS(line_value) ELSE 0 END),
       'Zero-price lines add no revenue but do add to invoice and customer counts. Purchase definitions require price > 0.' FROM lines;
INSERT INTO trust_tests_raw
SELECT 'V3', 'Validity', 'Quantity is not zero', COUNT(*), SUM(qty = 0), SUM(CASE WHEN qty = 0 THEN ABS(line_value) ELSE 0 END),
       'None expected. Fails the load if any appear.' FROM lines;
INSERT INTO trust_tests_raw
SELECT 'V4', 'Validity', 'Unit price is within 10x of the item average', COUNT(*), SUM(price > 10 * a.avg_price),
       SUM(CASE WHEN price > 10 * a.avg_price THEN ABS(line_value) ELSE 0 END),
       'Possible keying error. Reviewed, not removed.'
FROM lines l JOIN (SELECT stock_code, AVG(price) AS avg_price FROM lines WHERE is_product = 1 AND price > 0 GROUP BY stock_code) a USING (stock_code)
WHERE l.is_product = 1 AND l.price > 0;
INSERT INTO trust_tests_raw
SELECT 'K1', 'Consistency', 'Cancellation invoices carry negative quantities', COUNT(*), SUM(qty > 0),
       SUM(CASE WHEN qty > 0 THEN ABS(line_value) ELSE 0 END),
       'Cancellation prefix and sign should agree.' FROM lines WHERE is_cancel = 1;
INSERT INTO trust_tests_raw
SELECT 'K2', 'Consistency', 'Non-cancellation invoices carry positive quantities', COUNT(*), SUM(qty < 0),
       SUM(CASE WHEN qty < 0 THEN ABS(line_value) ELSE 0 END),
       'Stock write-offs and adjustments hide here. Counted as credits in R3 and R4.' FROM lines WHERE is_cancel = 0;
INSERT INTO trust_tests_raw
SELECT 'K3', 'Consistency', 'Every return follows an earlier purchase of that item by that customer', COUNT(*),
       SUM(NOT EXISTS (SELECT 1 FROM lines p WHERE p.customer_id = r.customer_id AND p.stock_code = r.stock_code
                         AND p.is_cancel = 0 AND p.qty > 0 AND p.ts < r.ts)),
       SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM lines p WHERE p.customer_id = r.customer_id AND p.stock_code = r.stock_code
                         AND p.is_cancel = 0 AND p.qty > 0 AND p.ts < r.ts) THEN ABS(line_value) ELSE 0 END),
       'Mostly purchases made before the file starts. Returns still count in the month they are credited.'
FROM lines r WHERE r.is_cancel = 1 AND r.is_product = 1 AND r.customer_id IS NOT NULL;
INSERT INTO trust_tests_raw
SELECT 'K4', 'Consistency', 'One invoice belongs to one customer', COUNT(*),
       SUM(invoice IN (SELECT invoice FROM lines GROUP BY invoice HAVING COUNT(DISTINCT COALESCE(customer_id, '')) > 1)),
       SUM(CASE WHEN invoice IN (SELECT invoice FROM lines GROUP BY invoice HAVING COUNT(DISTINCT COALESCE(customer_id, '')) > 1) THEN ABS(line_value) ELSE 0 END),
       'Would break order-level metrics. None expected.' FROM lines;
INSERT INTO trust_tests_raw
SELECT 'K5', 'Consistency', 'One stock code has one description', COUNT(*),
       SUM(stock_code IN (SELECT stock_code FROM lines WHERE description IS NOT NULL GROUP BY stock_code HAVING COUNT(DISTINCT description) > 1)),
       SUM(CASE WHEN stock_code IN (SELECT stock_code FROM lines WHERE description IS NOT NULL GROUP BY stock_code HAVING COUNT(DISTINCT description) > 1) THEN ABS(line_value) ELSE 0 END),
       'Product-name rollups must group by stock code, not by description.' FROM lines WHERE is_product = 1;
INSERT INTO trust_tests_raw
SELECT 'T1', 'Timeliness', 'Row falls in a fully covered month', COUNT(*), SUM(m.is_full = 0),
       SUM(CASE WHEN m.is_full = 0 THEN ABS(line_value) ELSE 0 END),
       'Partial months are loaded but never compared.' FROM lines l JOIN months m USING (month);

DROP TABLE IF EXISTS trust_tests;
CREATE TABLE trust_tests AS
SELECT t.*, 1.0 * rows_failing / rows_tested AS pct_rows,
       abs_value_failing / (SELECT SUM(ABS(line_value)) FROM lines) AS pct_value,
       CASE WHEN rows_failing = 0 THEN 'pass'
            WHEN MAX(1.0 * rows_failing / rows_tested, abs_value_failing / (SELECT SUM(ABS(line_value)) FROM lines)) >= 0.05  THEN 'high'
            WHEN MAX(1.0 * rows_failing / rows_tested, abs_value_failing / (SELECT SUM(ABS(line_value)) FROM lines)) >= 0.005 THEN 'medium'
            ELSE 'low' END AS severity
FROM trust_tests_raw t;
DROP TABLE trust_tests_raw;

-- share of rows that survive every row-level rule
DROP TABLE IF EXISTS analysis_ready;
CREATE TABLE analysis_ready AS
SELECT COUNT(*) AS rows_total,
       SUM(is_product = 1 AND dup_rank = 1 AND price > 0 AND qty <> 0) AS rows_ready,
       1.0 * SUM(is_product = 1 AND dup_rank = 1 AND price > 0 AND qty <> 0) / COUNT(*) AS pct_ready
FROM lines;

-- which non-product codes carry the money
DROP TABLE IF EXISTS non_product_codes;
CREATE TABLE non_product_codes AS
SELECT stock_code, MAX(description) AS description, COUNT(*) AS lines, SUM(line_value) AS net_value, SUM(ABS(line_value)) AS abs_value
FROM lines WHERE is_product = 0 GROUP BY stock_code ORDER BY abs_value DESC LIMIT 12;

-- data quality by month: where did the mess arrive?
DROP TABLE IF EXISTS quality_monthly;
CREATE TABLE quality_monthly AS
SELECT l.month, COUNT(*) AS rows,
       1.0 * SUM(dup_rank > 1) / COUNT(*)            AS dup_pct,
       1.0 * SUM(dup_kind = 'cross_sheet') / COUNT(*) AS cross_sheet_pct,
       1.0 * SUM(is_product = 0) / COUNT(*)          AS non_product_pct,
       1.0 * SUM(customer_id IS NULL) / COUNT(*)     AS no_customer_pct,
       1.0 * SUM(is_cancel = 1) / COUNT(*)           AS cancel_pct
FROM lines l JOIN months m USING (month) WHERE m.is_full = 1 GROUP BY l.month;
