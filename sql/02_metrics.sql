-- 02_metrics.sql  -  every definition, computed month by month from the same `lines` table.
-- Purchase line = product code, non-cancelled invoice, quantity > 0, price > 0.

-- ---------------------------------------------------------------- revenue
DROP TABLE IF EXISTS m_revenue;
CREATE TABLE m_revenue AS
SELECT l.month,
       SUM(line_value)                                                                                  AS r1,
       SUM(CASE WHEN is_product = 1 AND is_cancel = 0 AND qty > 0 AND price > 0 THEN line_value END)    AS r2,
       SUM(CASE WHEN is_product = 1 THEN line_value END)                                                AS r3,
       SUM(CASE WHEN is_product = 1 AND dup_rank = 1 THEN line_value END)                               AS r4,
       SUM(CASE WHEN is_product = 1 AND dup_rank = 1 AND customer_id IS NOT NULL THEN line_value END)   AS r5
FROM lines l GROUP BY l.month;

-- the gaps between the answers, one named cause per column (these reconcile exactly: see tests/)
DROP TABLE IF EXISTS m_bridge;
CREATE TABLE m_bridge AS
SELECT month,
       SUM(CASE WHEN is_product = 1 AND is_cancel = 0 AND qty > 0 AND price > 0 THEN line_value ELSE 0 END)           AS gross,
       SUM(CASE WHEN is_product = 1 AND NOT (is_cancel = 0 AND qty > 0 AND price > 0) THEN line_value ELSE 0 END)      AS returns_and_credits,
       SUM(CASE WHEN is_product = 1 AND dup_kind = 'repeat'      THEN line_value ELSE 0 END)                           AS dup_repeat,
       SUM(CASE WHEN is_product = 1 AND dup_kind = 'cross_sheet' THEN line_value ELSE 0 END)                           AS dup_cross_sheet,
       SUM(CASE WHEN is_product = 1 AND dup_rank = 1 AND customer_id IS NULL THEN line_value ELSE 0 END)              AS unidentified,
       SUM(CASE WHEN is_product = 0 THEN line_value ELSE 0 END)                                                       AS non_product
FROM lines GROUP BY month;

-- ---------------------------------------------------------------- active customers
DROP TABLE IF EXISTS purchase_days;
CREATE TABLE purchase_days AS
SELECT DISTINCT customer_id, day FROM lines
WHERE customer_id IS NOT NULL AND is_product = 1 AND is_cancel = 0 AND qty > 0 AND price > 0;
CREATE INDEX ix_pd_day ON purchase_days(day);

DROP TABLE IF EXISTS m_customers;
CREATE TABLE m_customers AS
WITH a1 AS (SELECT month, COUNT(DISTINCT customer_id) AS n FROM lines WHERE customer_id IS NOT NULL GROUP BY month),
a2 AS (SELECT month, COUNT(DISTINCT customer_id) AS n FROM lines
       WHERE customer_id IS NOT NULL AND is_product = 1 AND is_cancel = 0 AND qty > 0 AND price > 0 GROUP BY month),
a3 AS (SELECT month, COUNT(*) AS n FROM (
         SELECT month, customer_id, SUM(line_value) AS s FROM lines
         WHERE customer_id IS NOT NULL AND is_product = 1 AND dup_rank = 1
         GROUP BY month, customer_id HAVING SUM(line_value) > 0) GROUP BY month),
a4 AS (SELECT month, COUNT(DISTINCT CASE WHEN customer_id IS NULL THEN 'g' || invoice ELSE 'c' || customer_id END) AS n,
              COUNT(DISTINCT CASE WHEN customer_id IS NULL THEN invoice END) AS guest_invoices
       FROM lines WHERE is_product = 1 AND is_cancel = 0 AND qty > 0 AND price > 0 GROUP BY month),
a5 AS (SELECT m.month,
              CASE WHEN date(m.last_day, '-89 day') >= (SELECT MIN(day) FROM lines)
                   THEN (SELECT COUNT(DISTINCT p.customer_id) FROM purchase_days p
                         WHERE p.day BETWEEN date(m.last_day, '-89 day') AND m.last_day) END AS n
       FROM months m)
SELECT m.month,
       a1.n AS a1, a2.n AS a2, a3.n AS a3, a4.n AS a4, a5.n AS a5,
       a4.guest_invoices AS guest_invoices
FROM months m
LEFT JOIN a1 USING (month) LEFT JOIN a2 USING (month) LEFT JOIN a3 USING (month)
LEFT JOIN a4 USING (month) LEFT JOIN a5 USING (month);

-- ---------------------------------------------------------------- average order value
DROP TABLE IF EXISTS inv;
CREATE TABLE inv AS
SELECT invoice, substr(MIN(ts), 1, 7) AS month, MIN(customer_id) AS customer_id, MIN(day) AS day, SUM(line_value) AS gross
FROM lines
WHERE is_product = 1 AND is_cancel = 0 AND qty > 0 AND price > 0 AND dup_rank = 1
GROUP BY invoice;
CREATE INDEX ix_inv_month ON inv(month);

DROP TABLE IF EXISTS m_aov;
CREATE TABLE m_aov AS
WITH v1 AS (SELECT month, SUM(line_value) * 1.0 / COUNT(DISTINCT invoice) AS v, COUNT(DISTINCT invoice) AS n FROM lines GROUP BY month),
v2 AS (SELECT month, AVG(gross) AS v, COUNT(*) AS n FROM inv GROUP BY month),
v4 AS (SELECT month, AVG(gross) AS v FROM (
         SELECT month, gross, ROW_NUMBER() OVER (PARTITION BY month ORDER BY gross) AS rn,
                COUNT(*) OVER (PARTITION BY month) AS c FROM inv)
       WHERE rn IN ((c + 1) / 2, (c + 2) / 2) GROUP BY month),
v5 AS (SELECT month, SUM(line_value) * 1.0 /
              COUNT(DISTINCT CASE WHEN customer_id IS NULL THEN 'i' || invoice ELSE 'c' || customer_id || '|' || day END) AS v,
              COUNT(DISTINCT CASE WHEN customer_id IS NULL THEN 'i' || invoice ELSE 'c' || customer_id || '|' || day END) AS n
       FROM lines WHERE is_product = 1 AND is_cancel = 0 AND qty > 0 AND price > 0 AND dup_rank = 1 GROUP BY month)
SELECT m.month,
       v1.v AS v1, v2.v AS v2, m_revenue.r4 * 1.0 / v2.n AS v3, v4.v AS v4, v5.v AS v5,
       v1.n AS invoices_all, v2.n AS purchase_invoices, v5.n AS consolidated_orders
FROM months m
LEFT JOIN v1 USING (month) LEFT JOIN v2 USING (month) LEFT JOIN v4 USING (month) LEFT JOIN v5 USING (month)
LEFT JOIN m_revenue USING (month);

-- ---------------------------------------------------------------- one long table for everything downstream
DROP TABLE IF EXISTS metric_long;
CREATE TABLE metric_long AS
SELECT d.metric, d.def_id, d.name, d.governed, m.month, m.is_full, x.value
FROM definitions d
JOIN months m
JOIN (SELECT month, 'R1' AS def_id, r1 AS value FROM m_revenue UNION ALL SELECT month, 'R2', r2 FROM m_revenue
      UNION ALL SELECT month, 'R3', r3 FROM m_revenue UNION ALL SELECT month, 'R4', r4 FROM m_revenue
      UNION ALL SELECT month, 'R5', r5 FROM m_revenue
      UNION ALL SELECT month, 'A1', a1 FROM m_customers UNION ALL SELECT month, 'A2', a2 FROM m_customers
      UNION ALL SELECT month, 'A3', a3 FROM m_customers UNION ALL SELECT month, 'A4', a4 FROM m_customers
      UNION ALL SELECT month, 'A5', a5 FROM m_customers
      UNION ALL SELECT month, 'V1', v1 FROM m_aov UNION ALL SELECT month, 'V2', v2 FROM m_aov
      UNION ALL SELECT month, 'V3', v3 FROM m_aov UNION ALL SELECT month, 'V4', v4 FROM m_aov
      UNION ALL SELECT month, 'V5', v5 FROM m_aov) x
  ON x.def_id = d.def_id AND x.month = m.month;
CREATE INDEX ix_ml ON metric_long(metric, def_id, month);
