-- ============================================================================
-- CommerceIQ v2 — Unified Analytical Views (ANSI SQL: PostgreSQL & SQLite)
-- ============================================================================

DROP VIEW IF EXISTS vw_fact_order_items;
CREATE VIEW vw_fact_order_items AS
WITH item_counts AS (
    SELECT order_id, COUNT(*) AS order_item_count
    FROM olist_order_items_dataset
    GROUP BY order_id
),
cxl_item_agg AS (
    SELECT
        order_id,
        order_item_id,
        SUM(refunded_amount_brl) AS cancel_refund_brl,
        SUM(intercept_or_restocking_cost_brl) AS cancel_intercept_cost_brl
    FROM commerceiq_cancellations_refunds
    WHERE order_item_id IS NOT NULL
    GROUP BY order_id, order_item_id
)
SELECT
    oi.order_id,
    oi.order_item_id,
    o.customer_id,
    c.customer_unique_id,
    c.customer_state,
    oi.product_id,
    COALESCE(pc.product_category_english, 'uncategorized') AS product_category_english,
    oi.seller_id,
    s.seller_state,
    o.order_status,
    o.order_purchase_timestamp,
    SUBSTR(o.order_purchase_timestamp, 1, 7) AS order_year_month,
    oi.price AS item_price_brl,
    oi.freight_value AS item_freight_brl,
    ROUND(oi.price + oi.freight_value, 2) AS gross_item_revenue_brl,
    pc.unit_cogs_brl,
    pc.packaging_handling_cost_brl,
    ROUND(oi.price * pc.olist_marketplace_commission_pct, 2) AS marketplace_commission_brl,
    ROUND(oi.price * pc.tax_icms_rate_pct, 2) AS icms_tax_brl,
    ROUND(COALESCE(stl.actual_carrier_cost_brl, 0.0) / ic.order_item_count, 2) AS allocated_carrier_cost_brl,
    CASE WHEN rr.return_id IS NOT NULL THEN 1 ELSE 0 END AS has_return,
    COALESCE(rr.refunded_amount_brl, 0.0) AS return_refund_brl,
    COALESCE(rr.reverse_logistics_cost_brl, 0.0) AS reverse_logistics_cost_brl,
    CASE WHEN cxl.order_id IS NOT NULL THEN 1 ELSE 0 END AS has_item_cancellation,
    COALESCE(cxl.cancel_refund_brl, 0.0) AS cancel_refund_brl,
    COALESCE(cxl.cancel_intercept_cost_brl, 0.0) AS cancel_intercept_cost_brl,
    ROUND(
        (oi.price + oi.freight_value)
        - (oi.price * pc.tax_icms_rate_pct)
        - (oi.price * pc.olist_marketplace_commission_pct)
        - pc.unit_cogs_brl
        - pc.packaging_handling_cost_brl
        - (COALESCE(stl.actual_carrier_cost_brl, 0.0) / ic.order_item_count)
        - COALESCE(rr.refunded_amount_brl, 0.0)
        - COALESCE(rr.reverse_logistics_cost_brl, 0.0)
        - COALESCE(cxl.cancel_refund_brl, 0.0)
        - COALESCE(cxl.cancel_intercept_cost_brl, 0.0),
        2
    ) AS net_contribution_brl
FROM olist_order_items_dataset oi
JOIN olist_orders_dataset o ON oi.order_id = o.order_id
JOIN olist_customers_dataset c ON o.customer_id = c.customer_id
JOIN olist_sellers_dataset s ON oi.seller_id = s.seller_id
JOIN item_counts ic ON oi.order_id = ic.order_id
LEFT JOIN commerceiq_product_costs_pricing pc ON oi.product_id = pc.product_id
LEFT JOIN commerceiq_shipment_tracking_logistics stl ON oi.order_id = stl.order_id
LEFT JOIN commerceiq_returns_refunds rr ON oi.order_id = rr.order_id AND oi.order_item_id = rr.order_item_id
LEFT JOIN cxl_item_agg cxl ON oi.order_id = cxl.order_id AND oi.order_item_id = cxl.order_item_id;

DROP VIEW IF EXISTS vw_customer_summary;
CREATE VIEW vw_customer_summary AS
WITH order_pay AS (
    SELECT order_id, SUM(payment_value) AS order_payment_brl
    FROM olist_order_payments_dataset
    GROUP BY order_id
),
order_rev AS (
    SELECT order_id, AVG(review_score) AS avg_review_score
    FROM olist_order_reviews_dataset
    GROUP BY order_id
),
cust_orders AS (
    SELECT
        c.customer_unique_id,
        MIN(c.customer_state) AS customer_state,
        COUNT(DISTINCT o.order_id) AS total_orders,
        SUM(CASE WHEN o.order_status = 'delivered' THEN 1 ELSE 0 END) AS delivered_orders,
        SUM(CASE WHEN o.order_status = 'canceled' THEN 1 ELSE 0 END) AS canceled_orders,
        MIN(o.order_purchase_timestamp) AS first_order_ts,
        MAX(o.order_purchase_timestamp) AS last_order_ts,
        SUBSTR(MIN(o.order_purchase_timestamp), 1, 7) AS acquisition_cohort_ym,
        ROUND(SUM(COALESCE(op.order_payment_brl, 0.0)), 2) AS lifetime_payment_brl,
        ROUND(AVG(orev.avg_review_score), 3) AS avg_customer_review_score
    FROM olist_customers_dataset c
    JOIN olist_orders_dataset o ON c.customer_id = o.customer_id
    LEFT JOIN order_pay op ON o.order_id = op.order_id
    LEFT JOIN order_rev orev ON o.order_id = orev.order_id
    GROUP BY c.customer_unique_id
),
cust_logistics AS (
    SELECT
        c.customer_unique_id,
        MAX(CASE WHEN stl.is_late_delivery = 1 THEN 1 ELSE 0 END) AS ever_had_late_delivery,
        AVG(stl.delivery_variance_days) AS avg_delivery_variance_days
    FROM olist_customers_dataset c
    JOIN olist_orders_dataset o ON c.customer_id = o.customer_id
    JOIN commerceiq_shipment_tracking_logistics stl ON o.order_id = stl.order_id
    WHERE stl.fulfillment_state = 'Delivered'
    GROUP BY c.customer_unique_id
),
cust_tickets AS (
    SELECT
        customer_unique_id,
        COUNT(*) AS support_tickets_count,
        MAX(CASE WHEN sla_breached = 1 THEN 1 ELSE 0 END) AS ever_had_sla_breach
    FROM commerceiq_customer_support_tickets
    GROUP BY customer_unique_id
)
SELECT
    co.customer_unique_id,
    co.customer_state,
    co.acquisition_cohort_ym,
    co.first_order_ts,
    co.last_order_ts,
    co.total_orders,
    co.delivered_orders,
    co.canceled_orders,
    CASE WHEN co.total_orders >= 2 THEN 1 ELSE 0 END AS is_repeat_customer,
    co.lifetime_payment_brl,
    co.avg_customer_review_score,
    caa.first_touch_campaign_id,
    caa.last_touch_campaign_id,
    caa.acquisition_channel,
    caa.primary_device_type,
    caa.customer_acquisition_cost_brl,
    caa.loyalty_tier,
    caa.predicted_churn_probability,
    COALESCE(cl.ever_had_late_delivery, 0) AS ever_had_late_delivery,
    ROUND(cl.avg_delivery_variance_days, 2) AS avg_delivery_variance_days,
    COALESCE(ct.support_tickets_count, 0) AS support_tickets_count,
    COALESCE(ct.ever_had_sla_breach, 0) AS ever_had_sla_breach
FROM cust_orders co
LEFT JOIN commerceiq_customer_acquisition_attribution caa ON co.customer_unique_id = caa.customer_unique_id
LEFT JOIN cust_logistics cl ON co.customer_unique_id = cl.customer_unique_id
LEFT JOIN cust_tickets ct ON co.customer_unique_id = ct.customer_unique_id;

DROP VIEW IF EXISTS vw_marketing_roas;
CREATE VIEW vw_marketing_roas AS
WITH camp_cust AS (
    SELECT
        last_touch_campaign_id AS campaign_id,
        COUNT(*) AS acquired_customers,
        SUM(total_orders) AS total_cohort_orders,
        SUM(CASE WHEN is_repeat_customer = 1 THEN 1 ELSE 0 END) AS repeat_customers,
        ROUND(SUM(lifetime_payment_brl), 2) AS attributed_gmv_brl,
        ROUND(SUM(customer_acquisition_cost_brl), 2) AS attributed_cac_brl
    FROM vw_customer_summary
    GROUP BY last_touch_campaign_id
)
SELECT
    mc.campaign_id,
    mc.campaign_name,
    mc.marketing_channel,
    mc.ad_platform,
    mc.cost_model,
    mc.start_date,
    mc.end_date,
    mc.planned_budget_brl,
    mc.actual_spend_brl,
    mc.impressions,
    mc.clicks,
    COALESCE(cc.acquired_customers, 0) AS acquired_customers,
    COALESCE(cc.total_cohort_orders, 0) AS total_cohort_orders,
    COALESCE(cc.repeat_customers, 0) AS repeat_customers,
    COALESCE(cc.attributed_gmv_brl, 0.0) AS attributed_gmv_brl,
    COALESCE(cc.attributed_cac_brl, 0.0) AS attributed_cac_brl,
    CASE
        WHEN mc.actual_spend_brl > 0 THEN ROUND(COALESCE(cc.attributed_gmv_brl, 0.0) / mc.actual_spend_brl, 2)
        ELSE NULL
    END AS campaign_roas
FROM commerceiq_marketing_campaigns mc
LEFT JOIN camp_cust cc ON mc.campaign_id = cc.campaign_id;

DROP VIEW IF EXISTS vw_carrier_performance;
CREATE VIEW vw_carrier_performance AS
WITH order_rev AS (
    SELECT order_id, AVG(review_score) AS avg_review_score
    FROM olist_order_reviews_dataset
    GROUP BY order_id
)
SELECT
    stl.shipment_id,
    stl.order_id,
    stl.primary_seller_id,
    stl.fulfillment_state,
    stl.origin_state,
    stl.destination_state,
    stl.is_interstate_shipment,
    stl.carrier_name,
    stl.service_tier,
    stl.customer_freight_charged_brl,
    stl.actual_carrier_cost_brl,
    stl.freight_margin_brl,
    stl.delivery_variance_days,
    stl.is_late_delivery,
    stl.delivery_attempts_count,
    stl.delivery_exception_code,
    orev.avg_review_score
FROM commerceiq_shipment_tracking_logistics stl
LEFT JOIN order_rev orev ON stl.order_id = orev.order_id
WHERE stl.fulfillment_state = 'Delivered';
