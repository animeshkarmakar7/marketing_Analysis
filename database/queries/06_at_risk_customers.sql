USE marketing_db;

WITH customer_percentiles AS (
    SELECT
        c.customer_id,
        c.age,
        c.education,
        c.marital_clean,
        c.income,
        s.total_spend,
        e.recency,
        cr.total_campaigns_accepted,
        cr.response,
        NTILE(4) OVER (ORDER BY s.total_spend DESC) AS spend_quartile
    FROM customers c
    JOIN customer_spending s
        ON c.customer_id = s.customer_id
    JOIN customer_engagement e
        ON c.customer_id = e.customer_id
    JOIN campaign_responses cr
        ON c.customer_id = cr.customer_id
)
SELECT
    customer_id,
    age,
    education,
    marital_clean,
    income,
    total_spend,
    recency,
    total_campaigns_accepted
FROM customer_percentiles
WHERE spend_quartile = 1
  AND recency > 60
  AND response = 0
ORDER BY total_spend DESC;
