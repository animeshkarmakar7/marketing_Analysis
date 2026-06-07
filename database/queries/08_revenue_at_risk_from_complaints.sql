USE marketing_db;

SELECT
    c.complain,
    COUNT(*) AS customers,
    ROUND(AVG(s.total_spend), 2) AS avg_spend,
    SUM(s.total_spend) AS historical_revenue_at_risk,
    ROUND(AVG(cr.response) * 100, 2) AS conversion_rate_pct
FROM customers c
JOIN customer_spending s
    ON c.customer_id = s.customer_id
JOIN campaign_responses cr
    ON c.customer_id = cr.customer_id
GROUP BY c.complain
ORDER BY c.complain DESC;
