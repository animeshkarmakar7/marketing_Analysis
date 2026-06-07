USE marketing_db;

WITH rfm_base AS (
    SELECT
        c.customer_id,
        e.recency,
        s.total_purchases AS frequency,
        s.total_spend AS monetary
    FROM customers c
    JOIN customer_engagement e
        ON c.customer_id = e.customer_id
    JOIN customer_spending s
        ON c.customer_id = s.customer_id
),
rfm_scored AS (
    SELECT
        customer_id,
        recency,
        frequency,
        monetary,
        6 - NTILE(5) OVER (ORDER BY recency ASC) AS r_score,
        6 - NTILE(5) OVER (ORDER BY frequency DESC) AS f_score,
        6 - NTILE(5) OVER (ORDER BY monetary DESC) AS m_score
    FROM rfm_base
)
SELECT
    customer_id,
    recency,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    r_score + f_score + m_score AS rfm_total
FROM rfm_scored
ORDER BY rfm_total DESC, monetary DESC;
