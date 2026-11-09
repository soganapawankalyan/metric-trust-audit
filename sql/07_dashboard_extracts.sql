-- 07_dashboard_extracts.sql  -  small summary tables the dashboard draws from (no row-level data leaves the database).

-- how invoice values are spread over the last 12 full months, on a log-style ladder of bins
DROP TABLE IF EXISTS inv_hist;
CREATE TABLE inv_hist AS
WITH recent AS (SELECT month FROM months WHERE is_full = 1 ORDER BY month DESC LIMIT 12),
edges(b, lo, hi) AS (VALUES (0,1,10),(1,10,20),(2,20,30),(3,30,50),(4,50,75),(5,75,100),(6,100,150),(7,150,200),(8,200,300),
                            (9,300,500),(10,500,750),(11,750,1000),(12,1000,1500),(13,1500,2500),(14,2500,5000),(15,5000,10000),(16,10000,1000000)),
t AS (SELECT gross, (SELECT b FROM edges WHERE gross >= lo AND gross < hi OR (gross < 1 AND b = 0) ORDER BY b LIMIT 1) AS b
      FROM inv WHERE month IN (SELECT month FROM recent))
SELECT e.b, e.lo, e.hi, COUNT(t.gross) AS n_invoices, COALESCE(SUM(t.gross), 0) AS value,
       1.0 * COUNT(t.gross) / (SELECT COUNT(*) FROM t) AS share_invoices,
       COALESCE(SUM(t.gross), 0) / (SELECT SUM(gross) FROM t) AS share_value
FROM edges e LEFT JOIN t ON t.b = e.b GROUP BY e.b ORDER BY e.b;

DROP TABLE IF EXISTS inv_stats;
CREATE TABLE inv_stats AS
WITH recent AS (SELECT month FROM months WHERE is_full = 1 ORDER BY month DESC LIMIT 12),
t AS (SELECT gross, ROW_NUMBER() OVER (ORDER BY gross) AS rn, COUNT(*) OVER () AS c FROM inv WHERE month IN (SELECT month FROM recent))
SELECT COUNT(*) AS n_invoices, AVG(gross) AS mean, 
       (SELECT AVG(gross) FROM t WHERE rn IN ((c + 1) / 2, (c + 2) / 2)) AS median,
       (SELECT SUM(gross) FROM t WHERE rn > 0.9 * c) * 1.0 / SUM(gross) AS top10_share
FROM t;
