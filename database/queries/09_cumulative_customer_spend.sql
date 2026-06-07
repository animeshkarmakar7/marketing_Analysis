USE marketing_db;

SELECT
    c.customer_id,
    c.dt_customer,
    s.total_spend,
    SUM(s.total_spend) OVER (
        ORDER BY c.dt_customer, c.customer_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_historical_spend
FROM customers c
JOIN customer_spending s
    ON c.customer_id = s.customer_id
ORDER BY c.dt_customer, c.customer_id;
