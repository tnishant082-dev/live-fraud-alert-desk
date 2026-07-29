-- Reconciliation / quality checks vs Excel KPI pack

-- Row counts
SELECT 'transactions' AS entity, COUNT(*) AS n FROM transactions
UNION ALL
SELECT 'alerts', COUNT(*) FROM fact_alerts
UNION ALL
SELECT 'disputes', COUNT(*) FROM disputes;

-- Amount at risk should match mart_daily sum
SELECT
  ROUND(SUM(amount_inr), 2) AS fact_amount_at_risk,
  (SELECT ROUND(SUM(amount_at_risk), 2) FROM mart_daily_alerts) AS mart_amount_at_risk
FROM fact_alerts;

-- Block rate sanity
SELECT
  SUM(is_blocked) AS blocked,
  COUNT(*) AS alerts,
  ROUND(1.0 * SUM(is_blocked) / COUNT(*), 4) AS block_rate
FROM fact_alerts;

-- No null keys
SELECT
  SUM(CASE WHEN alert_id IS NULL THEN 1 ELSE 0 END) AS null_alert_id,
  SUM(CASE WHEN txn_id IS NULL THEN 1 ELSE 0 END) AS null_txn_id,
  SUM(CASE WHEN amount_inr < 0 THEN 1 ELSE 0 END) AS neg_amount
FROM fact_alerts;
