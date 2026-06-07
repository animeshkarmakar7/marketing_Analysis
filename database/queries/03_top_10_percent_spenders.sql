USE marketing_db;

WITH spend_ranked AS (
    SELECT
        c.customer_id,
        c.age,
        c.education,
        c.marital_clean,
        c.income,
        s.total_spend,
        NTILE(10) OVER (ORDER BY s.total_spend DESC) AS spend_decile
    FROM customers c
    JOIN customer_spending s
        ON c.customer_id = s.customer_id
)
SELECT
    customer_id,
    age,
    education,
    marital_clean,
    income,
    total_spend
FROM spend_ranked
WHERE spend_decile = 1
ORDER BY total_spend DESC;
