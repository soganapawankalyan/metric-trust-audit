-- 03_decisions.sql  -  do the five answers lead to different decisions?
-- Only FULL months are compared (the last month of the file is partial and excluded).

DROP TABLE IF EXISTS mom;
CREATE TABLE mom AS
SELECT metric, def_id, month, value,
       LAG(value) OVER (PARTITION BY metric, def_id ORDER BY month) AS prev,
       value * 1.0 / LAG(value) OVER (PARTITION BY metric, def_id ORDER BY month) - 1 AS mom_pct
FROM metric_long
WHERE is_full = 1 AND value IS NOT NULL;

-- month-by-month: do all five definitions agree on direction?  (only months where all five exist)
-- disagree = signs differ at all; flip = they differ by at least one percent in opposite directions
DROP TABLE IF EXISTS mom_agree;
CREATE TABLE mom_agree AS
SELECT metric, month,
       COUNT(*)                                       AS n_defs,
       SUM(mom_pct > 0)                               AS n_up,
       SUM(mom_pct < 0)                               AS n_down,
       CASE WHEN SUM(mom_pct > 0) BETWEEN 1 AND COUNT(*) - 1 THEN 1 ELSE 0 END AS disagree,
       SUM(mom_pct >=  0.01)                          AS n_up_material,
       SUM(mom_pct <= -0.01)                          AS n_down_material,
       -- a real flip: at least one definition says up by 1% or more while another says down by 1% or more
       CASE WHEN SUM(mom_pct >= 0.01) >= 1 AND SUM(mom_pct <= -0.01) >= 1 THEN 1 ELSE 0 END AS flip,
       MAX(mom_pct) - MIN(mom_pct)                    AS mom_range
FROM mom WHERE mom_pct IS NOT NULL
GROUP BY metric, month
HAVING COUNT(*) = 5;

-- best month, per definition
DROP TABLE IF EXISTS best_month;
CREATE TABLE best_month AS
SELECT metric, def_id, month AS best, value
FROM (SELECT metric, def_id, month, value,
             ROW_NUMBER() OVER (PARTITION BY metric, def_id ORDER BY value DESC) AS rn
      FROM metric_long WHERE is_full = 1 AND value IS NOT NULL)
WHERE rn = 1;

-- latest full month vs the one before
DROP TABLE IF EXISTS latest_mom;
CREATE TABLE latest_mom AS
SELECT m.metric, m.def_id, m.month, m.value, m.prev, m.mom_pct
FROM mom m WHERE m.month = (SELECT MAX(month) FROM months WHERE is_full = 1);

-- year on year, over the last 12 full months, matched month to the same month a year earlier
DROP TABLE IF EXISTS yoy;
CREATE TABLE yoy AS
WITH cur AS (SELECT * FROM metric_long WHERE is_full = 1 AND value IS NOT NULL),
last12 AS (SELECT month FROM months WHERE is_full = 1 ORDER BY month DESC LIMIT 12),
pairs AS (
  SELECT c.metric, c.def_id, c.month, c.value AS v_now, p.value AS v_prev
  FROM cur c JOIN cur p ON p.metric = c.metric AND p.def_id = c.def_id
                       AND p.month = substr(date(c.month || '-01', '-12 month'), 1, 7)
  WHERE c.month IN (SELECT month FROM last12))
SELECT metric, def_id, COUNT(*) AS n_pairs, SUM(v_now) * 1.0 / SUM(v_prev) - 1 AS yoy_pct
FROM pairs GROUP BY metric, def_id;

-- trailing twelve full months: revenue is summed, the other two are monthly averages
DROP TABLE IF EXISTS ttm;
CREATE TABLE ttm AS
SELECT metric, def_id,
       CASE WHEN metric = 'revenue' THEN SUM(value) ELSE AVG(value) END AS value,
       COUNT(*) AS n_months
FROM metric_long
WHERE is_full = 1 AND value IS NOT NULL AND month IN (SELECT month FROM months WHERE is_full = 1 ORDER BY month DESC LIMIT 12)
GROUP BY metric, def_id;

-- how far apart are the answers, month by month
DROP TABLE IF EXISTS spread_monthly;
CREATE TABLE spread_monthly AS
SELECT metric, month, MIN(value) AS lo, MAX(value) AS hi, MAX(value) * 1.0 / MIN(value) - 1 AS spread_pct, COUNT(*) AS n_defs
FROM metric_long WHERE is_full = 1 AND value IS NOT NULL AND value > 0
GROUP BY metric, month HAVING COUNT(*) = 5;

-- country ranking under each revenue definition (full months pooled)
DROP TABLE IF EXISTS country_rank;
CREATE TABLE country_rank AS
WITH c AS (
  SELECT country,
         SUM(line_value)                                                                                 AS r1,
         SUM(CASE WHEN is_product = 1 AND is_cancel = 0 AND qty > 0 AND price > 0 THEN line_value END)   AS r2,
         SUM(CASE WHEN is_product = 1 THEN line_value END)                                               AS r3,
         SUM(CASE WHEN is_product = 1 AND dup_rank = 1 THEN line_value END)                              AS r4,
         SUM(CASE WHEN is_product = 1 AND dup_rank = 1 AND customer_id IS NOT NULL THEN line_value END)  AS r5
  FROM lines JOIN months USING (month) WHERE is_full = 1 GROUP BY country),
r AS (SELECT *, RANK() OVER (ORDER BY r1 DESC) AS k1, RANK() OVER (ORDER BY r2 DESC) AS k2,
                RANK() OVER (ORDER BY r3 DESC) AS k3, RANK() OVER (ORDER BY r4 DESC) AS k4,
                RANK() OVER (ORDER BY r5 DESC) AS k5 FROM c)
SELECT *, MAX(k1, k2, k3, k4, k5) - MIN(k1, k2, k3, k4, k5) AS rank_spread FROM r ORDER BY r4 DESC;

-- product ranking: gross vs net clean (returns and duplicates change who the best sellers are)
DROP TABLE IF EXISTS product_rank;
CREATE TABLE product_rank AS
WITH p AS (
  SELECT stock_code, MAX(description) AS description,
         SUM(CASE WHEN is_cancel = 0 AND qty > 0 AND price > 0 THEN line_value END)  AS gross,
         SUM(CASE WHEN dup_rank = 1 THEN line_value END)                              AS net_clean,
         SUM(CASE WHEN dup_rank = 1 AND NOT (is_cancel = 0 AND qty > 0 AND price > 0) THEN line_value END) AS returns
  FROM lines JOIN months USING (month) WHERE is_full = 1 AND is_product = 1 GROUP BY stock_code),
r AS (SELECT *, RANK() OVER (ORDER BY gross DESC) AS rank_gross, RANK() OVER (ORDER BY net_clean DESC) AS rank_net,
                -1.0 * returns / gross AS return_rate FROM p)
SELECT * FROM r WHERE rank_gross <= 100 OR rank_net <= 100 ORDER BY rank_gross;
