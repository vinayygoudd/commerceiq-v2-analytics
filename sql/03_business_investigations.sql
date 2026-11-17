-- ============================================================================
-- CommerceIQ v2 — 10 Core Analytical SQL Queries Across All Business Domains
-- ============================================================================

-- Q1: Monthly Revenue, Net Contribution Margin & Refund Impact
SELECT
    order_year_month,
    COUNT(DISTINCT order_id) AS orders_count,
    COUNT(*) AS line_items_count,
    ROUND(SUM(gross_item_revenue_brl), 2) AS gross_revenue_brl,
    ROUND(SUM(unit_cogs_brl), 2) AS total_cogs_brl,
    ROUND(SUM(return_refund_brl), 2) AS return_refunds_brl,
    ROUND(SUM(cancel_refund_brl), 2) AS cancel_refunds_brl,
    ROUND(SUM(net_contribution_brl), 2) AS net_contribution_brl,
    ROUND(100.0 * SUM(net_contribution_brl) / NULLIF(SUM(gross_item_revenue_brl), 0), 2) AS net_margin_pct
FROM vw_fact_order_items
GROUP BY order_year_month
ORDER BY order_year_month;

-- Q2: Category Unit Economics & Return Rate Ranking
SELECT
    product_category_english,
    COUNT(*) AS units_sold,
    ROUND(SUM(gross_item_revenue_brl), 2) AS gross_revenue_brl,
    ROUND(SUM(net_contribution_brl), 2) AS net_contribution_brl,
    ROUND(100.0 * SUM(net_contribution_brl) / NULLIF(SUM(gross_item_revenue_brl), 0), 2) AS net_margin_pct,
    ROUND(100.0 * SUM(has_return) / NULLIF(SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END), 0), 2) AS delivered_return_rate_pct
FROM vw_fact_order_items
GROUP BY product_category_english
HAVING COUNT(*) >= 100
ORDER BY net_contribution_brl DESC;

-- Q3: Customer Acquisition Cohort Repeat Purchase Rate & LTV Analysis
SELECT
    acquisition_cohort_ym,
    COUNT(*) AS cohort_customers,
    SUM(is_repeat_customer) AS repeat_customers,
    ROUND(100.0 * SUM(is_repeat_customer) / NULLIF(COUNT(*), 0), 2) AS repeat_purchase_rate_pct,
    ROUND(AVG(lifetime_payment_brl), 2) AS avg_ltv_brl,
    ROUND(AVG(customer_acquisition_cost_brl), 2) AS avg_cac_brl,
    ROUND(AVG(avg_customer_review_score), 2) AS avg_review_score,
    ROUND(100.0 * AVG(ever_had_late_delivery), 2) AS late_delivery_exposure_pct
FROM vw_customer_summary
GROUP BY acquisition_cohort_ym
ORDER BY acquisition_cohort_ym;

-- Q4: Marketing Channel Effectiveness & ROAS Comparison
SELECT
    marketing_channel,
    COUNT(*) AS campaigns_count,
    ROUND(SUM(actual_spend_brl), 2) AS total_spend_brl,
    SUM(acquired_customers) AS acquired_customers,
    ROUND(SUM(attributed_gmv_brl), 2) AS attributed_gmv_brl,
    CASE WHEN SUM(actual_spend_brl) > 0 THEN ROUND(SUM(attributed_gmv_brl) / SUM(actual_spend_brl), 2) ELSE NULL END AS channel_roas,
    ROUND(100.0 * SUM(repeat_customers) / NULLIF(SUM(acquired_customers), 0), 2) AS cohort_repeat_rate_pct
FROM vw_marketing_roas
GROUP BY marketing_channel
ORDER BY attributed_gmv_brl DESC;

-- Q5: Multi-Session Funnel Stage Progression (Order Placement vs Delivery)
SELECT
    funnel_exit_stage,
    COUNT(*) AS sessions_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM commerceiq_customer_sessions_funnel), 2) AS share_of_sessions_pct,
    ROUND(AVG(session_duration_seconds), 1) AS avg_duration_sec,
    ROUND(AVG(page_views), 2) AS avg_page_views,
    SUM(CASE WHEN order_placed = 1 THEN 1 ELSE 0 END) AS orders_placed,
    SUM(CASE WHEN order_delivered = 1 THEN 1 ELSE 0 END) AS orders_delivered
FROM commerceiq_customer_sessions_funnel
GROUP BY funnel_exit_stage
ORDER BY sessions_count DESC;

-- Q6: Carrier Performance & Freight Margin (Delivered Orders Only)
SELECT
    carrier_name,
    service_tier,
    COUNT(*) AS delivered_shipments,
    ROUND(100.0 * AVG(CASE WHEN is_late_delivery = 1 THEN 1.0 ELSE 0.0 END), 2) AS late_delivery_pct,
    ROUND(AVG(delivery_variance_days), 2) AS avg_delivery_variance_days,
    ROUND(AVG(freight_margin_brl), 2) AS avg_freight_margin_brl,
    ROUND(AVG(avg_review_score), 2) AS avg_review_score
FROM vw_carrier_performance
GROUP BY carrier_name, service_tier
ORDER BY delivered_shipments DESC;

-- Q7: Post-Delivery Product Returns Breakdown by Reason & Disposition
SELECT
    return_reason,
    item_inspection_disposition,
    COUNT(*) AS return_items,
    ROUND(SUM(refunded_amount_brl), 2) AS total_refunded_brl,
    ROUND(SUM(reverse_logistics_cost_brl), 2) AS total_reverse_shipping_brl
FROM commerceiq_returns_refunds
GROUP BY return_reason, item_inspection_disposition
ORDER BY return_items DESC;

-- Q8: Pre- vs Post-Shipment Cancellations & Refund Impact
SELECT
    cancellation_stage,
    cancellation_reason,
    COUNT(*) AS cancellation_records,
    COUNT(DISTINCT order_id) AS distinct_orders,
    ROUND(SUM(eligible_payment_brl), 2) AS eligible_payment_brl,
    ROUND(SUM(refunded_amount_brl), 2) AS refunded_amount_brl,
    ROUND(SUM(intercept_or_restocking_cost_brl), 2) AS intercept_cost_brl
FROM commerceiq_cancellations_refunds
GROUP BY cancellation_stage, cancellation_reason
ORDER BY cancellation_records DESC;

-- Q9: Multi-Period Historical Inventory Movement & Stockout Trends
SELECT
    snapshot_date,
    COUNT(*) AS active_sku_seller_pairs,
    SUM(opening_stock_units) AS total_opening_units,
    SUM(stock_received_units) AS total_received_units,
    SUM(units_sold_in_period) AS total_sold_units,
    SUM(closing_stock_units) AS total_closing_units,
    SUM(CASE WHEN stockout_occurred = 1 THEN 1 ELSE 0 END) AS stockout_events,
    ROUND(SUM(inventory_valuation_cogs_brl), 2) AS ending_inventory_cogs_brl
FROM commerceiq_inventory_snapshots
GROUP BY snapshot_date
ORDER BY snapshot_date;

-- Q10: Support Ticket SLA Breaches & Post-Ticket CSAT by Issue Category
SELECT
    issue_category,
    COUNT(*) AS tickets_count,
    ROUND(AVG(first_response_time_minutes), 1) AS avg_first_response_min,
    ROUND(AVG(resolution_time_hours), 2) AS avg_resolution_hours,
    ROUND(100.0 * AVG(CASE WHEN sla_breached = 1 THEN 1.0 ELSE 0.0 END), 2) AS sla_breach_pct,
    ROUND(AVG(post_ticket_csat_score), 2) AS avg_csat_score
FROM commerceiq_customer_support_tickets
GROUP BY issue_category
ORDER BY tickets_count DESC;
