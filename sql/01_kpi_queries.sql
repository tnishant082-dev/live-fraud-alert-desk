-- Live Fraud Alert Desk — KPI queries
-- Source: cleaned alert / transaction facts (Jul 15 – Aug 13, 2025)

-- 1) Headline KPIs
SELECT
  COUNT(*)                                                    AS alerts,
  SUM(CASE WHEN severity IN ('High','Critical') THEN 1 ELSE 0 END) AS high_risk,
  SUM(is_blocked)                                             AS blocked,
  ROUND(100.0 * SUM(is_blocked) / COUNT(*), 2)                AS block_rate_pct,
  SUM(is_false_positive)                                      AS false_positive_proxy,
  ROUND(100.0 * SUM(is_false_positive) / COUNT(*), 2)         AS fp_rate_pct,
  ROUND(SUM(amount_inr), 2)                                   AS amount_at_risk_inr,
  ROUND(AVG(fraud_score), 3)                                  AS avg_fraud_score
FROM fact_alerts;

-- 2) Alerts per day
SELECT
  alert_date,
  COUNT(*)                         AS alerts,
  SUM(CASE WHEN severity IN ('High','Critical') THEN 1 ELSE 0 END) AS high_risk,
  SUM(is_blocked)                  AS blocked,
  ROUND(SUM(amount_inr), 2)        AS amount_at_risk
FROM fact_alerts
GROUP BY alert_date
ORDER BY alert_date;

-- 3) Channel mix
SELECT
  channel,
  COUNT(*)                         AS alerts,
  ROUND(SUM(amount_inr), 2)        AS amount_at_risk,
  SUM(is_blocked)                  AS blocked,
  ROUND(AVG(fraud_score), 3)       AS avg_score
FROM fact_alerts
GROUP BY channel
ORDER BY alerts DESC;

-- 4) Rule hit performance
SELECT
  rule_hit,
  COUNT(*)                         AS alerts,
  SUM(is_blocked)                  AS blocked,
  SUM(is_false_positive)           AS false_positives,
  ROUND(100.0 * SUM(is_false_positive) / COUNT(*), 1) AS fp_rate_pct,
  ROUND(SUM(amount_inr), 2)        AS amount_at_risk
FROM fact_alerts
GROUP BY rule_hit
ORDER BY alerts DESC;
