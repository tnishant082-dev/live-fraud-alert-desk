-- Live Fraud Alert Desk — drill-down queries

-- 1) City hotspots
SELECT
  city,
  COUNT(*) AS alerts,
  SUM(CASE WHEN severity IN ('High','Critical') THEN 1 ELSE 0 END) AS high_risk,
  SUM(is_blocked) AS blocked,
  ROUND(SUM(amount_inr), 2) AS amount_at_risk
FROM fact_alerts
GROUP BY city
ORDER BY alerts DESC;

-- 2) Merchant category risk
SELECT
  merchant_category,
  COUNT(*) AS alerts,
  ROUND(AVG(fraud_score), 3) AS avg_score,
  SUM(is_blocked) AS blocked,
  ROUND(SUM(amount_inr), 2) AS amount_at_risk
FROM fact_alerts
GROUP BY merchant_category
ORDER BY amount_at_risk DESC;

-- 3) Merchant hotspots (top 25)
SELECT
  merchant_id,
  merchant_category,
  city,
  COUNT(*) AS alerts,
  SUM(CASE WHEN severity IN ('High','Critical') THEN 1 ELSE 0 END) AS high_risk,
  ROUND(AVG(fraud_score), 3) AS avg_score,
  ROUND(SUM(amount_inr), 2) AS amount_at_risk
FROM fact_alerts
GROUP BY merchant_id, merchant_category, city
ORDER BY alerts DESC
LIMIT 25;

-- 4) Analyst queue (open / investigating / escalated)
SELECT
  alert_id,
  alert_ts,
  channel,
  city,
  merchant_category,
  amount_inr,
  fraud_score,
  rule_hit,
  severity,
  status
FROM fact_alerts
WHERE analyst_queue = 'Queue'
ORDER BY
  CASE severity
    WHEN 'Critical' THEN 1
    WHEN 'High' THEN 2
    WHEN 'Medium' THEN 3
    ELSE 4
  END,
  alert_ts
LIMIT 100;

-- 5) Night-window concentration
SELECT
  CASE WHEN CAST(strftime('%H', alert_ts) AS INT) < 5
            OR CAST(strftime('%H', alert_ts) AS INT) >= 23
       THEN 'Night' ELSE 'Day' END AS daypart,
  channel,
  COUNT(*) AS alerts,
  ROUND(SUM(amount_inr), 2) AS amount_at_risk,
  ROUND(AVG(fraud_score), 3) AS avg_score
FROM fact_alerts
GROUP BY 1, 2
ORDER BY 1, alerts DESC;

-- 6) Dispute join sample (txn → dispute)
SELECT
  d.dispute_id,
  d.opened_ts,
  d.dispute_type,
  d.status AS dispute_status,
  d.amount_inr,
  d.channel,
  d.city,
  a.alert_id,
  a.severity,
  a.rule_hit
FROM disputes d
LEFT JOIN fact_alerts a ON d.txn_id = a.txn_id
ORDER BY d.opened_ts DESC
LIMIT 50;
