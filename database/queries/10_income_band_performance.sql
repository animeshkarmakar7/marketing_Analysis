USE marketing_db;

SELECT
    CASE
        WHEN c.income < 30000 THEN 'Low (<30K)'
        WHEN c.income < 60000 THEN 'Mid (30K-60K)'
        WHEN c.income < 90000 THEN 'High (60K-90K)'
        ELSE 'Very High (>90K)'
    END AS income_band,
    COUNT(*) AS customers,
    ROUND(AVG(c.income), 2) AS avg_income,
    ROUND(AVG(s.total_spend), 2) AS avg_spend,
    ROUND(AVG(cr.response) * 100, 2) AS conversion_rate_pct
FROM customers c
JOIN customer_spending s
    ON c.customer_id = s.customer_id
JOIN campaign_responses cr
    ON c.customer_id = cr.customer_id
GROUP BY income_band
ORDER BY avg_spend DESC;
