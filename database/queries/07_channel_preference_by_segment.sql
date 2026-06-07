USE marketing_db;

WITH rfm_base AS (
    SELECT
        c.customer_id,
        e.recency,
        s.total_purchases,
        s.total_spend,
        s.num_web_purchases,
        s.num_catalog_purchases,
        s.num_store_purchases
    FROM customers c
    JOIN customer_engagement e
        ON c.customer_id = e.customer_id
    JOIN customer_spending s
        ON c.customer_id = s.customer_id
),
segmented AS (
    SELECT
        customer_id,
        CASE
            WHEN recency <= 30 AND total_spend >= 1000 AND total_purchases >= 10 THEN 'VIP'
            WHEN recency <= 60 AND total_spend >= 400 THEN 'Loyal'
            WHEN recency > 60 AND total_spend >= 400 THEN 'At Risk'
            ELSE 'New'
        END AS business_segment,
        num_web_purchases,
        num_catalog_purchases,
        num_store_purchases
    FROM rfm_base
)
SELECT
    business_segment,
    COUNT(*) AS customers,
    ROUND(AVG(num_web_purchases), 2) AS avg_web_purchases,
    ROUND(AVG(num_catalog_purchases), 2) AS avg_catalog_purchases,
    ROUND(AVG(num_store_purchases), 2) AS avg_store_purchases
FROM segmented
GROUP BY business_segment
ORDER BY customers DESC;
