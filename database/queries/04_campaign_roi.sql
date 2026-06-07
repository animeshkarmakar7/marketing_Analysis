USE marketing_db;

WITH campaign_performance AS (
    SELECT 'Campaign 1' AS campaign_name, SUM(campaign_1) AS accepted, COUNT(*) AS contacted FROM campaign_responses
    UNION ALL
    SELECT 'Campaign 2', SUM(campaign_2), COUNT(*) FROM campaign_responses
    UNION ALL
    SELECT 'Campaign 3', SUM(campaign_3), COUNT(*) FROM campaign_responses
    UNION ALL
    SELECT 'Campaign 4', SUM(campaign_4), COUNT(*) FROM campaign_responses
    UNION ALL
    SELECT 'Campaign 5', SUM(campaign_5), COUNT(*) FROM campaign_responses
),
unit_economics AS (
    SELECT
        MAX(z_revenue) AS revenue_per_conversion,
        MAX(z_cost_contact) AS cost_per_contact
    FROM campaign_responses
)
SELECT
    cp.campaign_name,
    cp.contacted,
    cp.accepted,
    ROUND(cp.accepted * 100.0 / cp.contacted, 2) AS acceptance_rate_pct,
    cp.accepted * ue.revenue_per_conversion AS revenue,
    cp.contacted * ue.cost_per_contact AS cost,
    (cp.accepted * ue.revenue_per_conversion) - (cp.contacted * ue.cost_per_contact) AS net_profit,
    ROUND(
        ((cp.accepted * ue.revenue_per_conversion) - (cp.contacted * ue.cost_per_contact))
        * 100.0 / NULLIF(cp.contacted * ue.cost_per_contact, 0),
        2
    ) AS roi_pct
FROM campaign_performance cp
CROSS JOIN unit_economics ue
ORDER BY roi_pct DESC;
