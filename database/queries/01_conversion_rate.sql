USE marketing_db;

SELECT
    COUNT(*) AS total_customers,
    SUM(response) AS total_conversions,
    ROUND(SUM(response) * 100.0 / COUNT(*), 2) AS conversion_rate_pct
FROM campaign_responses;
