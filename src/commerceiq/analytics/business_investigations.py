#!/usr/bin/env python3
"""
CommerceIQ — Pillar 1 & 2: Data & Business Analytics Engine
===========================================================
Executes comprehensive SQL and Python business investigations across all 9 domains:
  1. Revenue & Profitability Waterfall Analysis
  2. Customer Retention, Repeat Purchase & Cohort Analysis
  3. Customer Acquisition & Multi-Session Funnel Conversion Analysis
  4. Product & Category Unit Economics Analysis
  5. Marketing Channel Effectiveness & ROAS Analysis
  6. Post-Delivery Returns vs. Pre-/Post-Shipment Cancellations & Refunds Analysis
  7. Carrier Logistics, Interstate Shipping & Delivery SLA Analysis
  8. Multi-Period Historical Inventory Movement & Stockout Analysis
  9. Root-Cause Investigations & Evidence-Backed Business Recommendations

Also exports clean Power BI Star-Schema tables (`bi/powerbi_star_schema/`) so BI
dashboards share the exact same verified KPI definitions and underlying numbers.
"""

import os
import json
import numpy as np
import pandas as pd
from commerceiq.db_engine import CommerceIQWarehouse


def run_all_business_investigations(warehouse: CommerceIQWarehouse, output_dir: str, bi_mart_dir: str) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(bi_mart_dir, exist_ok=True)

    # 1. Revenue & Profitability Waterfall
    rev_summary = warehouse.query_df(
        """
        SELECT
            COUNT(DISTINCT order_id) AS itemized_orders,
            COUNT(*) AS total_line_items,
            ROUND(SUM(item_price_brl), 2) AS total_item_price_brl,
            ROUND(SUM(item_freight_brl), 2) AS total_freight_charged_brl,
            ROUND(SUM(gross_item_revenue_brl), 2) AS gross_merchandise_value_brl,
            ROUND(SUM(icms_tax_brl), 2) AS total_icms_tax_brl,
            ROUND(SUM(marketplace_commission_brl), 2) AS total_olist_commission_brl,
            ROUND(SUM(unit_cogs_brl), 2) AS total_unit_cogs_brl,
            ROUND(SUM(packaging_handling_cost_brl), 2) AS total_packaging_cost_brl,
            ROUND(SUM(allocated_carrier_cost_brl), 2) AS total_carrier_cost_brl,
            ROUND(SUM(return_refund_brl), 2) AS total_return_refunds_brl,
            ROUND(SUM(reverse_logistics_cost_brl), 2) AS total_reverse_shipping_brl,
            ROUND(SUM(cancel_refund_brl), 2) AS total_item_cancel_refunds_brl,
            ROUND(SUM(cancel_intercept_cost_brl), 2) AS total_cancel_intercept_brl,
            ROUND(SUM(net_contribution_brl), 2) AS total_net_contribution_brl,
            ROUND(100.0 * SUM(net_contribution_brl) / NULLIF(SUM(gross_item_revenue_brl), 0), 2) AS net_contribution_margin_pct
        FROM vw_fact_order_items
        """
    ).iloc[0].to_dict()

    monthly_trends = warehouse.query_df(
        """
        SELECT
            order_year_month,
            COUNT(DISTINCT order_id) AS orders_count,
            ROUND(SUM(gross_item_revenue_brl), 2) AS gmv_brl,
            ROUND(SUM(net_contribution_brl), 2) AS net_contribution_brl,
            ROUND(100.0 * SUM(net_contribution_brl) / NULLIF(SUM(gross_item_revenue_brl), 0), 2) AS net_margin_pct
        FROM vw_fact_order_items
        WHERE order_year_month BETWEEN '2017-01' AND '2018-08'
        GROUP BY order_year_month
        ORDER BY order_year_month
        """
    )

    # 2. Customer Retention & Cohort Analysis (including Repeat Purchase Decline investigation)
    cohort_retention = warehouse.query_df(
        """
        SELECT
            acquisition_cohort_ym,
            COUNT(*) AS cohort_customers,
            SUM(is_repeat_customer) AS repeat_customers,
            ROUND(100.0 * SUM(is_repeat_customer) / NULLIF(COUNT(*), 0), 2) AS repeat_rate_pct,
            ROUND(AVG(lifetime_payment_brl), 2) AS avg_ltv_brl,
            ROUND(AVG(customer_acquisition_cost_brl), 2) AS avg_cac_brl,
            ROUND(AVG(avg_customer_review_score), 2) AS avg_review_score,
            ROUND(100.0 * AVG(ever_had_late_delivery), 2) AS late_delivery_pct
        FROM vw_customer_summary
        WHERE acquisition_cohort_ym BETWEEN '2017-01' AND '2018-08'
        GROUP BY acquisition_cohort_ym
        ORDER BY acquisition_cohort_ym
        """
    )

    overall_retention = warehouse.query_df(
        """
        SELECT
            COUNT(*) AS unique_customers,
            SUM(is_repeat_customer) AS repeat_customers,
            ROUND(100.0 * SUM(is_repeat_customer) / COUNT(*), 2) AS repeat_purchase_rate_pct,
            ROUND(AVG(CASE WHEN is_repeat_customer = 1 THEN lifetime_payment_brl END), 2) AS repeat_customer_avg_ltv_brl,
            ROUND(AVG(CASE WHEN is_repeat_customer = 0 THEN lifetime_payment_brl END), 2) AS one_time_customer_avg_ltv_brl
        FROM vw_customer_summary
        """
    ).iloc[0].to_dict()

    # 3. Acquisition & Multi-Session Funnel Analysis
    funnel_stages = warehouse.query_df(
        """
        SELECT
            funnel_exit_stage,
            COUNT(*) AS sessions_count,
            ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM commerceiq_customer_sessions_funnel), 2) AS pct_of_sessions,
            ROUND(AVG(session_duration_seconds), 1) AS avg_duration_sec,
            ROUND(AVG(page_views), 2) AS avg_page_views,
            SUM(CASE WHEN order_placed = 1 THEN 1 ELSE 0 END) AS orders_placed_count,
            SUM(CASE WHEN order_delivered = 1 THEN 1 ELSE 0 END) AS orders_delivered_count
        FROM commerceiq_customer_sessions_funnel
        GROUP BY funnel_exit_stage
        ORDER BY sessions_count DESC
        """
    )

    # 4. Product & Category Unit Economics
    category_performance = warehouse.query_df(
        """
        SELECT
            product_category_english,
            COUNT(*) AS units_sold,
            ROUND(SUM(gross_item_revenue_brl), 2) AS gmv_brl,
            ROUND(SUM(net_contribution_brl), 2) AS net_contribution_brl,
            ROUND(100.0 * SUM(net_contribution_brl) / NULLIF(SUM(gross_item_revenue_brl), 0), 2) AS net_margin_pct,
            ROUND(100.0 * SUM(has_return) / NULLIF(SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END), 0), 2) AS delivered_return_rate_pct
        FROM vw_fact_order_items
        GROUP BY product_category_english
        HAVING COUNT(*) >= 200
        ORDER BY gmv_brl DESC
        LIMIT 15
        """
    )

    # 5. Marketing Channel Effectiveness
    marketing_channels = warehouse.query_df(
        """
        SELECT
            marketing_channel,
            COUNT(*) AS campaigns_count,
            ROUND(SUM(actual_spend_brl), 2) AS actual_spend_brl,
            SUM(acquired_customers) AS acquired_customers,
            ROUND(SUM(attributed_gmv_brl), 2) AS attributed_gmv_brl,
            CASE WHEN SUM(actual_spend_brl) > 0 THEN ROUND(SUM(attributed_gmv_brl) / SUM(actual_spend_brl), 2) ELSE NULL END AS roas_x,
            CASE WHEN SUM(acquired_customers) > 0 THEN ROUND(SUM(actual_spend_brl) / SUM(acquired_customers), 2) ELSE 0.0 END AS effective_cac_brl,
            ROUND(100.0 * SUM(repeat_customers) / NULLIF(SUM(acquired_customers), 0), 2) AS repeat_rate_pct
        FROM vw_marketing_roas
        GROUP BY marketing_channel
        ORDER BY attributed_gmv_brl DESC
        """
    )

    # 6. Returns vs. Cancellations & Refunds
    returns_breakdown = warehouse.query_df(
        """
        SELECT
            return_reason,
            resolution_outcome,
            COUNT(*) AS return_items,
            ROUND(SUM(refunded_amount_brl), 2) AS refunded_brl,
            ROUND(SUM(reverse_logistics_cost_brl), 2) AS reverse_shipping_brl
        FROM commerceiq_returns_refunds
        GROUP BY return_reason, resolution_outcome
        ORDER BY return_items DESC
        """
    )

    cancellations_breakdown = warehouse.query_df(
        """
        SELECT
            cancellation_stage,
            cancellation_reason,
            COUNT(*) AS cancellation_rows,
            COUNT(DISTINCT order_id) AS canceled_orders,
            ROUND(SUM(eligible_payment_brl), 2) AS eligible_payment_brl,
            ROUND(SUM(refunded_amount_brl), 2) AS refunded_brl,
            ROUND(SUM(intercept_or_restocking_cost_brl), 2) AS intercept_cost_brl
        FROM commerceiq_cancellations_refunds
        GROUP BY cancellation_stage, cancellation_reason
        ORDER BY cancellation_rows DESC
        """
    )

    # 7. Delivery & Carrier Logistics (Delivered Orders Only vs Fulfillment States)
    fulfillment_states = warehouse.query_df(
        """
        SELECT
            fulfillment_state,
            COUNT(*) AS shipments_count,
            ROUND(SUM(customer_freight_charged_brl), 2) AS freight_charged_brl,
            ROUND(SUM(actual_carrier_cost_brl), 2) AS carrier_cost_brl,
            ROUND(SUM(freight_margin_brl), 2) AS freight_margin_brl
        FROM commerceiq_shipment_tracking_logistics
        GROUP BY fulfillment_state
        ORDER BY shipments_count DESC
        """
    )

    carrier_kpis = warehouse.query_df(
        """
        SELECT
            carrier_name,
            service_tier,
            COUNT(*) AS delivered_shipments,
            ROUND(100.0 * AVG(CASE WHEN is_late_delivery = 1 THEN 1.0 ELSE 0.0 END), 2) AS late_delivery_pct,
            ROUND(AVG(delivery_variance_days), 2) AS avg_variance_days,
            ROUND(AVG(freight_margin_brl), 2) AS avg_freight_margin_brl,
            ROUND(AVG(avg_review_score), 2) AS avg_review_score
        FROM vw_carrier_performance
        GROUP BY carrier_name, service_tier
        ORDER BY delivered_shipments DESC
        """
    )

    # 8. Multi-Period Inventory Movement & Stockouts
    inventory_trends = warehouse.query_df(
        """
        SELECT
            snapshot_date,
            COUNT(*) AS active_sku_seller_pairs,
            SUM(opening_stock_units) AS opening_units,
            SUM(stock_received_units) AS received_units,
            SUM(units_sold_in_period) AS sold_units,
            SUM(closing_stock_units) AS closing_units,
            SUM(available_quantity) AS available_units,
            SUM(CASE WHEN stockout_occurred = 1 THEN 1 ELSE 0 END) AS stockout_skus,
            ROUND(SUM(inventory_valuation_cogs_brl), 2) AS ending_valuation_cogs_brl
        FROM commerceiq_inventory_snapshots
        GROUP BY snapshot_date
        ORDER BY snapshot_date
        """
    )

    # 9. Customer Support Experience
    support_summary = warehouse.query_df(
        """
        SELECT
            issue_category,
            COUNT(*) AS tickets_count,
            ROUND(AVG(first_response_time_minutes), 1) AS avg_first_response_min,
            ROUND(AVG(resolution_time_hours), 2) AS avg_resolution_hours,
            ROUND(100.0 * AVG(CASE WHEN sla_breached = 1 THEN 1.0 ELSE 0.0 END), 2) AS sla_breach_pct,
            ROUND(AVG(post_ticket_csat_score), 2) AS avg_csat_score
        FROM commerceiq_customer_support_tickets
        GROUP BY issue_category
        ORDER BY tickets_count DESC
        """
    )

    # Export Power BI Star-Schema Marts (Dim + Fact + Pre-Aggregated KPI Marts)
    monthly_trends.to_csv(os.path.join(bi_mart_dir, "mart_monthly_financials.csv"), index=False)
    cohort_retention.to_csv(os.path.join(bi_mart_dir, "mart_customer_cohorts.csv"), index=False)
    funnel_stages.to_csv(os.path.join(bi_mart_dir, "mart_session_funnel.csv"), index=False)
    category_performance.to_csv(os.path.join(bi_mart_dir, "mart_category_unit_economics.csv"), index=False)
    marketing_channels.to_csv(os.path.join(bi_mart_dir, "mart_marketing_roas.csv"), index=False)
    carrier_kpis.to_csv(os.path.join(bi_mart_dir, "mart_carrier_performance.csv"), index=False)
    inventory_trends.to_csv(os.path.join(bi_mart_dir, "mart_inventory_snapshots.csv"), index=False)
    support_summary.to_csv(os.path.join(bi_mart_dir, "mart_support_sla_csat.csv"), index=False)

    results = {
        "revenue_profitability_summary": rev_summary,
        "overall_retention_summary": overall_retention,
        "monthly_trends": monthly_trends.to_dict("records"),
        "cohort_retention": cohort_retention.to_dict("records"),
        "funnel_stages": funnel_stages.to_dict("records"),
        "top_categories": category_performance.to_dict("records"),
        "marketing_channels": marketing_channels.to_dict("records"),
        "returns_breakdown": returns_breakdown.to_dict("records"),
        "cancellations_breakdown": cancellations_breakdown.to_dict("records"),
        "fulfillment_states": fulfillment_states.to_dict("records"),
        "carrier_kpis": carrier_kpis.to_dict("records"),
        "inventory_trends": inventory_trends.to_dict("records"),
        "support_summary": support_summary.to_dict("records"),
    }

    with open(os.path.join(output_dir, "business_investigations_results.json"), "w") as f:
        json.dump(results, f, indent=2)

    return results
