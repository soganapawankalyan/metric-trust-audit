-- 06_governed_layer.sql  -  the answer to "which number do we use?": one table per metric, built from the chosen definition.
-- Dashboards, notebooks and finance all read these tables and nothing else.

DROP TABLE IF EXISTS gov_monthly;
CREATE TABLE gov_monthly AS
SELECT m.month, m.is_full,
       (SELECT value FROM metric_long WHERE metric = 'revenue'   AND governed = 1 AND month = m.month) AS revenue_net_clean,
       (SELECT value FROM metric_long WHERE metric = 'customers' AND governed = 1 AND month = m.month) AS active_customers,
       (SELECT value FROM metric_long WHERE metric = 'aov'       AND governed = 1 AND month = m.month) AS aov,
       c.guest_invoices                                                                                 AS guest_buyers,
       a.purchase_invoices, a.consolidated_orders
FROM months m JOIN m_customers c USING (month) JOIN m_aov a USING (month);

DROP TABLE IF EXISTS metric_dictionary;
CREATE TABLE metric_dictionary AS
SELECT d.metric, d.def_id, d.name, d.governed, d.typical_owner, d.rule, d.pitfall,
       CASE d.metric WHEN 'revenue' THEN 'GBP, month, net of returns' WHEN 'customers' THEN 'customers, month' ELSE 'GBP per order, month' END AS unit_and_grain
FROM definitions d;
