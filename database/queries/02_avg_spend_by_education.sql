USE marketing_db;

SELECT
    c.education,
    COUNT(*) AS customer_count,
    ROUND(AVG(s.total_spend), 2) AS avg_total_spend,
    ROUND(AVG(c.income), 2) AS avg_income
FROM customers c
JOIN customer_spending s
    ON c.customer_id = s.customer_id
GROUP BY c.education
ORDER BY avg_total_spend DESC;
