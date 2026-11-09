-- 04_drift.sql  -  does the gap between definitions stay constant?  (If it did, you could just rescale.)

DROP TABLE IF EXISTS drift;
CREATE TABLE drift AS
SELECT l.metric, l.def_id, l.month, l.value * 1.0 / g.value AS ratio
FROM metric_long l
JOIN metric_long g ON g.metric = l.metric AND g.month = l.month AND g.governed = 1
WHERE l.is_full = 1 AND l.governed = 0 AND l.value IS NOT NULL AND g.value IS NOT NULL AND g.value <> 0;

DROP TABLE IF EXISTS drift_summary;
CREATE TABLE drift_summary AS
SELECT d.metric, d.def_id, MIN(ratio) AS min_ratio, MAX(ratio) AS max_ratio, AVG(ratio) AS avg_ratio,
       MAX(ratio) - MIN(ratio) AS range_ratio,
       (SELECT month FROM drift x WHERE x.metric = d.metric AND x.def_id = d.def_id ORDER BY ABS(ratio - 1) DESC LIMIT 1) AS worst_month
FROM drift d GROUP BY d.metric, d.def_id;

-- the named causes behind the revenue gaps, as a share of net clean revenue
DROP TABLE IF EXISTS causes_monthly;
CREATE TABLE causes_monthly AS
SELECT b.month, r.r4 AS net_clean,
       -1.0 * b.returns_and_credits / b.gross     AS return_rate,
       1.0 * (b.dup_repeat + b.dup_cross_sheet) / r.r3 AS duplicate_share,
       1.0 * b.dup_cross_sheet / r.r3             AS cross_sheet_share,
       1.0 * b.unidentified / r.r4                AS unidentified_share,
       1.0 * b.non_product / r.r3                 AS non_product_share
FROM m_bridge b JOIN m_revenue r USING (month) JOIN months m USING (month) WHERE m.is_full = 1;

-- guest share of buyers by month (A4 vs A2 gap)
DROP TABLE IF EXISTS guest_share;
CREATE TABLE guest_share AS
SELECT c.month, c.guest_invoices, c.a4, 1.0 * c.guest_invoices / c.a4 AS guest_share
FROM m_customers c JOIN months m USING (month) WHERE m.is_full = 1;
