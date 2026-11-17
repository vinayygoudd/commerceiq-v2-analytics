#!/usr/bin/env python3
"""
CommerceIQ v2.0 — Olist Dataset Augmentation & Incremental Synthetic Data Generator
===================================================================================
Upgrades the CommerceIQ synthetic layer to v2.0 while preserving the 9 original Olist CSVs
byte-for-byte unchanged and preserving the 3 already-validated baseline synthetic tables:
  - Preserved Synthetic Tables (unchanged if present):
      1. `commerceiq_marketing_campaigns.csv` (90 rows)
      2. `commerceiq_customer_acquisition_attribution.csv` (96,096 rows)
      3. `commerceiq_product_costs_pricing.csv` (32,951 rows)
  - Upgraded / New v2 Synthetic Tables:
      4. `commerceiq_returns_refunds.csv` (delivered-item product returns only; zero canceled orders)
      5. `commerceiq_cancellations_refunds.csv` [NEW] (cancellation refunds linked to order_id & order_item_id)
      6. `commerceiq_shipment_tracking_logistics.csv` (plausible shipments only; explicit fulfillment_state;
         no delivery timestamps or delivery metrics for non-delivered orders)
      7. `commerceiq_customer_sessions_funnel.csv` (multi-session customer journeys; removes forced 1:1
         session-per-order lock; uses `Order_Placed` stage and separate `order_delivered` boolean)
      8. `commerceiq_inventory_snapshots.csv` (4 monthly historical snapshots: 2018-07-01, 2018-08-01,
         2018-09-01, 2018-10-01 with exact opening + received - sold = closing stock conservation)
      9. `commerceiq_customer_support_tickets.csv` (synchronized with separated returns & cancellations)

Synthetic Behavioural Design Assumptions (explicitly documented, not independent discoveries):
  - Late deliveries -> higher probability of lower Olist review scores & WISMO inquiries
  - Lower review scores -> higher probability of post-delivery product returns
  - SLA breaches (>48h) -> lower post-ticket CSAT scores
  - Returns & cancellations -> higher probability of customer support ticket creation
"""

import os
import hashlib
import numpy as np
import pandas as pd


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_marketing_and_acquisition(
    olist_dir: str,
    output_dir: str,
    orders_cust: pd.DataFrame,
    rng: np.random.Generator,
    force_regenerate: bool = False,
):
    camp_path = os.path.join(output_dir, "commerceiq_marketing_campaigns.csv")
    acq_path = os.path.join(output_dir, "commerceiq_customer_acquisition_attribution.csv")
    if (not force_regenerate) and os.path.exists(camp_path) and os.path.exists(acq_path):
        print("  -> Preserving existing validated commerceiq_marketing_campaigns.csv & commerceiq_customer_acquisition_attribution.csv")
        return pd.read_csv(camp_path, low_memory=False), pd.read_csv(acq_path, low_memory=False)

    channels = [
        ("Paid Search", "Google Ads", "CPC", 28.0),
        ("Paid Social", "Meta Ads", "CPM", 22.0),
        ("Paid Social", "Instagram Shopping", "CPC", 24.0),
        ("Affiliate", "Awin Brazil", "CPA", 19.0),
        ("CRM / Email", "RD Station", "Fixed", 11.0),
        ("Price Comparison", "Buscape / Zoom", "CPC", 21.0),
        ("Display / Retargeting", "Criteo", "CPM", 25.0),
        ("Influencer / Content", "YouTube Creators BR", "Fixed", 32.0),
        ("Organic / SEO", "Organic Search", "Organic", 0.0),
    ]
    quarters = [
        ("2016-Q3", "2016-09-01", "2016-09-30"),
        ("2016-Q4", "2016-10-01", "2016-12-31"),
        ("2017-Q1", "2017-01-01", "2017-03-31"),
        ("2017-Q2", "2017-04-01", "2017-06-30"),
        ("2017-Q3", "2017-07-01", "2017-09-30"),
        ("2017-Q4", "2017-10-01", "2017-12-31"),
        ("2018-Q1", "2018-01-01", "2018-03-31"),
        ("2018-Q2", "2018-04-01", "2018-06-30"),
        ("2018-Q3", "2018-07-01", "2018-09-30"),
        ("2018-Q4", "2018-10-01", "2018-10-31"),
    ]
    target_segments = [
        "New Buyer Acquisition",
        "High-AOV Home & Tech",
        "Beauty & Lifestyle Repeat",
        "Black Friday / Seasonal Promo",
        "Cart Abandonment Retargeting",
        "Reactivation Win-Back",
    ]

    campaign_meta = []
    camp_idx = 1
    for q_label, q_start, q_end in quarters:
        for ch_name, platform, cost_model, base_cac in channels:
            camp_id = f"CMP-{q_label.replace('-', '')}-{camp_idx:03d}"
            seg = target_segments[(camp_idx - 1) % len(target_segments)]
            campaign_meta.append(
                {
                    "campaign_id": camp_id,
                    "quarter_label": q_label,
                    "campaign_name": f"{q_label} {platform} - {seg}",
                    "marketing_channel": ch_name,
                    "ad_platform": platform,
                    "cost_model": cost_model,
                    "target_audience_segment": seg,
                    "start_date": q_start,
                    "end_date": q_end,
                    "base_cac_brl": base_cac,
                }
            )
            camp_idx += 1

    df_camp_meta = pd.DataFrame(campaign_meta)
    df_camp_meta["start_dt"] = pd.to_datetime(df_camp_meta["start_date"])
    df_camp_meta["end_dt"] = pd.to_datetime(df_camp_meta["end_date"]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    earliest_orders = (
        orders_cust.sort_values(["order_purchase_timestamp", "order_id"])
        .groupby("customer_unique_id", as_index=False)
        .first()[["customer_unique_id", "order_id", "order_purchase_timestamp", "customer_state"]]
    )
    order_counts = orders_cust.groupby("customer_unique_id")["order_id"].count().rename("lifetime_orders")
    cust_base = earliest_orders.merge(order_counts, on="customer_unique_id", how="left")

    q_period = cust_base["order_purchase_timestamp"].dt.to_period("Q").astype(str)
    q_formatted = q_period.str.slice(0, 4) + "-" + q_period.str.slice(4, 6)
    quarter_to_camps = {ql: grp.to_dict("records") for ql, grp in df_camp_meta.groupby("quarter_label")}

    n_cust = len(cust_base)
    channel_weights = np.array([0.24, 0.16, 0.10, 0.08, 0.09, 0.08, 0.07, 0.04, 0.14])
    channel_weights = channel_weights / channel_weights.sum()

    ft_indices = rng.choice(len(channels), size=n_cust, p=channel_weights)
    lt_indices = np.where(rng.random(n_cust) < 0.74, ft_indices, rng.choice(len(channels), size=n_cust, p=channel_weights))

    first_touch_camps, last_touch_camps, acq_channels, cac_vals, camp_start_bounds = [], [], [], [], []
    q_vals = q_formatted.values
    for i in range(n_cust):
        c_list = quarter_to_camps[q_vals[i]]
        ft_c = c_list[ft_indices[i]]
        lt_c = c_list[lt_indices[i]]
        first_touch_camps.append(ft_c["campaign_id"])
        last_touch_camps.append(lt_c["campaign_id"])
        acq_channels.append(lt_c["marketing_channel"])
        camp_start_bounds.append(lt_c["start_dt"])
        if lt_c["marketing_channel"] == "Organic / SEO":
            cac_vals.append(0.0)
        else:
            mean_cac = lt_c["base_cac_brl"]
            cac_vals.append(round(float(rng.gamma(shape=4.0, scale=mean_cac / 4.0)), 2))

    camp_start_series = pd.Series(camp_start_bounds)
    max_lead_secs = (cust_base["order_purchase_timestamp"] - camp_start_series).dt.total_seconds().clip(lower=0).values
    desired_lead_secs = rng.integers(3600, 10 * 86400, size=n_cust)
    actual_lead_secs = np.minimum(desired_lead_secs, max_lead_secs)
    acq_ts = cust_base["order_purchase_timestamp"] - pd.to_timedelta(actual_lead_secs, unit="s")

    df_acquisition = pd.DataFrame(
        {
            "customer_unique_id": cust_base["customer_unique_id"],
            "first_order_id": cust_base["order_id"],
            "acquisition_timestamp": acq_ts.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "first_order_timestamp": cust_base["order_purchase_timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "first_touch_campaign_id": first_touch_camps,
            "last_touch_campaign_id": last_touch_camps,
            "acquisition_channel": acq_channels,
            "primary_device_type": rng.choice(["Mobile Web", "Desktop Web", "Android App", "iOS App"], size=n_cust, p=[0.46, 0.34, 0.14, 0.06]),
            "customer_acquisition_cost_brl": cac_vals,
            "lifetime_orders_count": cust_base["lifetime_orders"],
            "loyalty_tier": np.where(cust_base["lifetime_orders"] >= 3, "Gold", np.where(cust_base["lifetime_orders"] == 2, "Silver", "Standard")),
            "marketing_email_opt_in": rng.choice([True, False], size=n_cust, p=[0.68, 0.32]),
            "predicted_churn_probability": np.where(
                cust_base["lifetime_orders"] >= 2,
                np.round(rng.beta(2.2, 4.5, size=n_cust), 3),
                np.round(rng.beta(5.2, 2.3, size=n_cust), 3),
            ),
            "is_synthetic": True,
            "data_source": "CommerceIQ_Synthetic_v1",
        }
    )

    camp_cac_agg = (
        df_acquisition.groupby("last_touch_campaign_id", as_index=False)
        .agg(attributed_customers=("customer_unique_id", "count"), attributed_cac_sum=("customer_acquisition_cost_brl", "sum"))
        .rename(columns={"last_touch_campaign_id": "campaign_id"})
    )
    df_camp_full = df_camp_meta.merge(camp_cac_agg, on="campaign_id", how="left")
    df_camp_full["attributed_customers"] = df_camp_full["attributed_customers"].fillna(0).astype(int)
    df_camp_full["attributed_cac_sum"] = df_camp_full["attributed_cac_sum"].fillna(0.0)

    budgets, spends, impressions_list, clicks_list = [], [], [], []
    for row in df_camp_full.itertuples():
        if row.cost_model == "Organic":
            budgets.append(0.0)
            spends.append(0.0)
            base_clicks = max(120, int(row.attributed_customers * rng.uniform(18, 32)))
            impr = int(base_clicks / rng.uniform(0.028, 0.052))
            clicks_list.append(base_clicks)
            impressions_list.append(impr)
        else:
            actual_spend = round(row.attributed_cac_sum * float(rng.uniform(1.18, 1.42)), 2) if row.attributed_customers > 0 else round(float(rng.uniform(35.0, 95.0)), 2)
            planned_budget = round(actual_spend * float(rng.uniform(1.03, 1.18)), 2)
            clicks = max(25, int(actual_spend / float(rng.uniform(0.75, 1.85))))
            impr = max(clicks * 10, int(clicks / float(rng.uniform(0.014, 0.038))))
            budgets.append(planned_budget)
            spends.append(actual_spend)
            clicks_list.append(clicks)
            impressions_list.append(impr)

    df_campaigns_out = pd.DataFrame(
        {
            "campaign_id": df_camp_full["campaign_id"],
            "campaign_name": df_camp_full["campaign_name"],
            "marketing_channel": df_camp_full["marketing_channel"],
            "ad_platform": df_camp_full["ad_platform"],
            "cost_model": df_camp_full["cost_model"],
            "target_audience_segment": df_camp_full["target_audience_segment"],
            "start_date": df_camp_full["start_date"],
            "end_date": df_camp_full["end_date"],
            "planned_budget_brl": budgets,
            "actual_spend_brl": spends,
            "impressions": impressions_list,
            "clicks": clicks_list,
            "is_synthetic": True,
            "data_source": "CommerceIQ_Synthetic_v1",
        }
    )
    df_campaigns_out.to_csv(camp_path, index=False)
    df_acquisition.to_csv(acq_path, index=False)
    return df_campaigns_out, df_acquisition


def generate_product_costs(
    output_dir: str,
    products: pd.DataFrame,
    translations: pd.DataFrame,
    items: pd.DataFrame,
    rng: np.random.Generator,
    force_regenerate: bool = False,
):
    cost_path = os.path.join(output_dir, "commerceiq_product_costs_pricing.csv")
    if (not force_regenerate) and os.path.exists(cost_path):
        print("  -> Preserving existing validated commerceiq_product_costs_pricing.csv")
        return pd.read_csv(cost_path, low_memory=False)

    prod_price_stats = (
        items.groupby("product_id", as_index=False)
        .agg(
            min_observed_price_brl=("price", "min"),
            median_observed_price_brl=("price", "median"),
            max_observed_price_brl=("price", "max"),
            units_sold_count=("order_item_id", "count"),
        )
    )
    prod_merged = products[["product_id", "product_category_name", "product_weight_g"]].merge(
        translations, on="product_category_name", how="left"
    ).merge(prod_price_stats, on="product_id", how="left")

    manual_trans = {
        "pc_gamer": "gaming_pc",
        "portateis_cozinha_e_preparadores_de_alimentos": "kitchen_portables_and_food_preparers",
    }
    prod_merged["product_category_name_english"] = prod_merged["product_category_name_english"].fillna(
        prod_merged["product_category_name"].map(manual_trans)
    ).fillna("uncategorized")

    n_prod = len(prod_merged)
    cogs_ratio = rng.uniform(0.42, 0.66, size=n_prod)
    raw_cogs = np.round(prod_merged["median_observed_price_brl"] * cogs_ratio, 2)
    unit_cogs = np.maximum(0.50, np.minimum(raw_cogs, np.round(prod_merged["min_observed_price_brl"] * 0.92, 2)))
    msrp_brl = np.round(prod_merged["max_observed_price_brl"] * rng.uniform(1.06, 1.26, size=n_prod), 2)
    weight_kg = prod_merged["product_weight_g"].fillna(500.0) / 1000.0

    df_product_costs = pd.DataFrame(
        {
            "product_id": prod_merged["product_id"],
            "product_category_english": prod_merged["product_category_name_english"],
            "msrp_list_price_brl": msrp_brl,
            "min_historical_selling_price_brl": np.round(prod_merged["min_observed_price_brl"], 2),
            "median_historical_selling_price_brl": np.round(prod_merged["median_observed_price_brl"], 2),
            "max_historical_selling_price_brl": np.round(prod_merged["max_observed_price_brl"], 2),
            "unit_cogs_brl": unit_cogs,
            "packaging_handling_cost_brl": np.round(np.clip(1.20 + weight_kg * 0.42, 1.20, 16.50), 2),
            "olist_marketplace_commission_pct": np.round(rng.uniform(0.10, 0.17, size=n_prod), 4),
            "max_allowed_discount_pct": np.round(1.0 - (prod_merged["min_observed_price_brl"] / msrp_brl), 4),
            "tax_icms_rate_pct": rng.choice([0.07, 0.12, 0.17, 0.18], size=n_prod, p=[0.15, 0.25, 0.20, 0.40]),
            "is_synthetic": True,
            "data_source": "CommerceIQ_Synthetic_v1",
        }
    )
    df_product_costs.to_csv(cost_path, index=False)
    return df_product_costs


def generate_v2_dataset(
    olist_dir: str,
    output_dir: str,
    seed: int = 42,
    force_regenerate_all: bool = False,
) -> dict:
    rng = np.random.default_rng(seed)
    os.makedirs(output_dir, exist_ok=True)

    print("[1/9] Loading original Olist tables (strictly read-only)...")
    customers = pd.read_csv(os.path.join(olist_dir, "olist_customers_dataset.csv"), low_memory=False)
    orders = pd.read_csv(os.path.join(olist_dir, "olist_orders_dataset.csv"), low_memory=False)
    items = pd.read_csv(os.path.join(olist_dir, "olist_order_items_dataset.csv"), low_memory=False)
    payments = pd.read_csv(os.path.join(olist_dir, "olist_order_payments_dataset.csv"), low_memory=False)
    reviews = pd.read_csv(os.path.join(olist_dir, "olist_order_reviews_dataset.csv"), low_memory=False)
    products = pd.read_csv(os.path.join(olist_dir, "olist_products_dataset.csv"), low_memory=False)
    sellers = pd.read_csv(os.path.join(olist_dir, "olist_sellers_dataset.csv"), low_memory=False)
    translations = pd.read_csv(os.path.join(olist_dir, "product_category_name_translation.csv"), low_memory=False)

    orders_ts = orders.copy()
    for col in [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]:
        orders_ts[col] = pd.to_datetime(orders_ts[col], errors="coerce")

    orders_cust = orders_ts.merge(
        customers[["customer_id", "customer_unique_id", "customer_state"]],
        on="customer_id",
        how="left",
    )

    print("[2/9] Preserving/loading baseline Marketing, Acquisition & Product Cost tables...")
    df_campaigns, df_acquisition = generate_marketing_and_acquisition(
        olist_dir, output_dir, orders_cust, rng, force_regenerate=force_regenerate_all
    )
    df_product_costs = generate_product_costs(
        output_dir, products, translations, items, rng, force_regenerate=force_regenerate_all
    )

    # -------------------------------------------------------------------------
    # CORRECTION 1: Separate Product Returns vs. Cancellations & Refunds
    # -------------------------------------------------------------------------
    print("[3/9] Generating Table 4 (Upgraded): commerceiq_returns_refunds.csv (Delivered items ONLY)...")
    order_min_review = reviews.groupby("order_id", as_index=False)["review_score"].min()
    items_full = (
        items.merge(
            orders_ts[["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_delivered_customer_date"]],
            on="order_id",
            how="left",
        )
        .merge(order_min_review, on="order_id", how="left")
    )
    items_full["review_score"] = items_full["review_score"].fillna(4)

    # STRICT v2 RULE: Only genuinely delivered items (`order_status == 'delivered'` & delivered timestamp present)
    # are eligible for product returns. Zero canceled orders may appear here.
    delivered_items_pool = items_full[
        (items_full["order_status"] == "delivered") & (items_full["order_delivered_customer_date"].notna())
    ].copy().reset_index(drop=True)

    # Synthetic behavioral assumption: lower review scores correlate with higher post-delivery return propensity
    ret_prob = np.where(
        delivered_items_pool["review_score"] == 1,
        0.38,
        np.where(
            delivered_items_pool["review_score"] == 2,
            0.22,
            np.where(delivered_items_pool["review_score"] == 3, 0.08, 0.015),
        ),
    )
    ret_items = delivered_items_pool[rng.random(len(delivered_items_pool)) < ret_prob].copy().reset_index(drop=True)
    n_ret = len(ret_items)

    return_req_ts = (
        ret_items["order_delivered_customer_date"]
        + pd.to_timedelta(rng.integers(1, 15, size=n_ret), unit="D")
        + pd.to_timedelta(rng.integers(3600, 86400, size=n_ret), unit="s")
    )
    refund_proc_ts = return_req_ts + pd.to_timedelta(rng.integers(2, 10, size=n_ret), unit="D")

    reasons = rng.choice(
        [
            "Defective_or_Damaged_Item",
            "Wrong_Item_Sent",
            "Not_As_Described",
            "Late_Delivery_Regret",
            "Buyer_Remorse_7Day_CDC",
        ],
        size=n_ret,
        p=[0.32, 0.16, 0.22, 0.14, 0.16],
    )
    resolution_types = rng.choice(
        ["Full_Refund", "Partial_Refund_Keep_Item", "Exchange_Replacement", "Rejected_Policy_Violation"],
        size=n_ret,
        p=[0.74, 0.12, 0.09, 0.05],
    )
    item_gross_total = ret_items["price"] + ret_items["freight_value"]
    refund_amt = np.where(
        resolution_types == "Full_Refund",
        np.round(item_gross_total, 2),
        np.where(
            resolution_types == "Partial_Refund_Keep_Item",
            np.round(ret_items["price"] * rng.uniform(0.30, 0.60, size=n_ret), 2),
            0.0,
        ),
    )
    reverse_ship_cost = np.where(
        (resolution_types == "Partial_Refund_Keep_Item") | (resolution_types == "Rejected_Policy_Violation"),
        0.0,
        np.round(ret_items["freight_value"] * rng.uniform(0.85, 1.15, size=n_ret), 2),
    )
    inspection_disposition = np.where(
        resolution_types == "Partial_Refund_Keep_Item",
        "Retained_by_Customer",
        np.where(reasons == "Defective_or_Damaged_Item", "Damaged_WriteOff", "Restocked_Sellable"),
    )

    df_returns = pd.DataFrame(
        {
            "return_id": [f"RMA-{i:06d}" for i in range(1, n_ret + 1)],
            "order_id": ret_items["order_id"],
            "order_item_id": ret_items["order_item_id"],
            "product_id": ret_items["product_id"],
            "seller_id": ret_items["seller_id"],
            "customer_id": ret_items["customer_id"],
            "return_request_timestamp": return_req_ts.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "refund_processed_timestamp": refund_proc_ts.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "return_reason": reasons,
            "resolution_outcome": resolution_types,
            "item_inspection_disposition": inspection_disposition,
            "original_item_price_brl": np.round(ret_items["price"], 2),
            "original_freight_value_brl": np.round(ret_items["freight_value"], 2),
            "refunded_amount_brl": refund_amt,
            "reverse_logistics_cost_brl": reverse_ship_cost,
            "is_synthetic": True,
            "data_source": "CommerceIQ_Synthetic_v2",
        }
    )

    print("[4/9] Generating Table 5 (NEW): commerceiq_cancellations_refunds.csv...")
    # Covers all 625 canceled orders in olist_orders_dataset.csv:
    # - 461 canceled orders with line items -> item-level rows linked to (order_id, order_item_id)
    # - 164 canceled orders without line items -> order-level rows (order_item_id = NaN) reconciled to olist_order_payments_dataset
    canceled_orders = orders_ts[orders_ts["order_status"] == "canceled"].copy()
    pay_by_order = payments.groupby("order_id", as_index=False)["payment_value"].sum().rename(columns={"payment_value": "order_payment_total_brl"})
    canceled_orders = canceled_orders.merge(pay_by_order, on="order_id", how="left")
    canceled_orders["order_payment_total_brl"] = canceled_orders["order_payment_total_brl"].fillna(0.0)

    canceled_with_items = canceled_orders.merge(items, on="order_id", how="inner")
    # Compute item share of order payment so multi-item canceled orders never exceed order_payment_total_brl
    ord_item_gross = canceled_with_items.groupby("order_id", as_index=False).apply(
        lambda g: pd.Series({"ord_gross_sum": float((g["price"] + g["freight_value"]).sum())}),
        include_groups=False,
    )
    canceled_with_items = canceled_with_items.merge(ord_item_gross, on="order_id", how="left")
    item_gross = canceled_with_items["price"] + canceled_with_items["freight_value"]
    share = np.where(canceled_with_items["ord_gross_sum"] > 0, item_gross / canceled_with_items["ord_gross_sum"], 0.0)
    canceled_with_items["eligible_payment_brl"] = np.round(
        np.minimum(item_gross, canceled_with_items["order_payment_total_brl"] * share), 2
    )
    canceled_with_items["cancellation_stage"] = np.where(
        canceled_with_items["order_delivered_carrier_date"].notna(),
        "Cancelled_After_Shipment",
        "Cancelled_Before_Shipment",
    )

    canceled_no_items = canceled_orders[~canceled_orders["order_id"].isin(canceled_with_items["order_id"])].copy()
    canceled_no_items["order_item_id"] = np.nan
    canceled_no_items["product_id"] = np.nan
    canceled_no_items["seller_id"] = np.nan
    canceled_no_items["price"] = np.nan
    canceled_no_items["freight_value"] = np.nan
    canceled_no_items["eligible_payment_brl"] = np.round(canceled_no_items["order_payment_total_brl"], 2)
    canceled_no_items["cancellation_stage"] = "Cancelled_Before_Shipment"

    cols_keep = [
        "order_id", "order_item_id", "product_id", "seller_id", "customer_id",
        "order_purchase_timestamp", "order_delivered_carrier_date",
        "cancellation_stage", "price", "freight_value", "eligible_payment_brl",
    ]
    canc_all = pd.concat([canceled_with_items[cols_keep], canceled_no_items[cols_keep]], ignore_index=True)
    n_canc = len(canc_all)

    canc_base_ts = canc_all["order_delivered_carrier_date"].fillna(canc_all["order_purchase_timestamp"])
    canc_req_ts = canc_base_ts + pd.to_timedelta(rng.integers(900, 172800, size=n_canc), unit="s")
    canc_ref_ts = canc_req_ts + pd.to_timedelta(rng.integers(1, 7, size=n_canc), unit="D")

    canc_initiator = np.where(
        canc_all["order_item_id"].isna(),
        rng.choice(["Payment_Gateway_Timeout", "Seller_Stock_Unavailable", "Customer_Cancelled_Pre_Approval"], size=n_canc, p=[0.45, 0.30, 0.25]),
        np.where(
            canc_all["cancellation_stage"] == "Cancelled_After_Shipment",
            rng.choice(["Customer_Refused_Delivery", "Carrier_Transit_Loss_Damage", "Customer_In_Transit_Cancel"], size=n_canc, p=[0.50, 0.25, 0.25]),
            rng.choice(["Customer_Changed_Mind_Pre_Ship", "Seller_Out_Of_Stock_Cancel", "SLA_Dispatch_Timeout"], size=n_canc, p=[0.52, 0.30, 0.18]),
        ),
    )

    # For pre-shipment cancellations, 100% of eligible_payment_brl is refunded;
    # for post-shipment cancellations, either 100% or item-only (excluding outbound freight) is refunded.
    refund_pct = np.where(
        canc_all["cancellation_stage"] == "Cancelled_Before_Shipment",
        1.0,
        rng.choice([1.0, 0.85], size=n_canc, p=[0.78, 0.22]),
    )
    canc_refund_brl = np.round(canc_all["eligible_payment_brl"] * refund_pct, 2)
    restocking_or_intercept_fee = np.where(
        canc_all["cancellation_stage"] == "Cancelled_After_Shipment",
        np.round(canc_all["freight_value"].fillna(12.0) * rng.uniform(0.50, 0.90, size=n_canc), 2),
        0.0,
    )

    df_cancellations = pd.DataFrame(
        {
            "cancellation_id": [f"CXL-{i:06d}" for i in range(1, n_canc + 1)],
            "order_id": canc_all["order_id"],
            "order_item_id": canc_all["order_item_id"].astype("Int64"),
            "product_id": canc_all["product_id"],
            "seller_id": canc_all["seller_id"],
            "customer_id": canc_all["customer_id"],
            "cancellation_stage": canc_all["cancellation_stage"],
            "cancellation_reason": canc_initiator,
            "cancellation_timestamp": canc_req_ts.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "refund_processed_timestamp": canc_ref_ts.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "original_item_price_brl": np.round(canc_all["price"], 2),
            "original_freight_value_brl": np.round(canc_all["freight_value"], 2),
            "eligible_payment_brl": canc_all["eligible_payment_brl"],
            "refunded_amount_brl": canc_refund_brl,
            "intercept_or_restocking_cost_brl": restocking_or_intercept_fee,
            "refund_status": np.where(canc_all["eligible_payment_brl"] > 0, "Refunded_To_Original_Payment", "No_Payment_Captured"),
            "is_synthetic": True,
            "data_source": "CommerceIQ_Synthetic_v2",
        }
    )

    # -------------------------------------------------------------------------
    # CORRECTION 2: Shipment & Logistics Eligibility (Plausible Shipments Only)
    # -------------------------------------------------------------------------
    print("[5/9] Generating Table 6 (Upgraded): commerceiq_shipment_tracking_logistics.csv...")
    order_item_ship = (
        items.groupby("order_id", as_index=False)
        .agg(
            primary_seller_id=("seller_id", "first"),
            total_freight_charged_brl=("freight_value", "sum"),
            items_count=("order_item_id", "count"),
        )
    )
    ship_candidates = orders_cust.merge(order_item_ship, on="order_id", how="inner").merge(
        sellers[["seller_id", "seller_state"]], left_on="primary_seller_id", right_on="seller_id", how="left"
    )

    # Plausible shipment filter: order must have been handed off to carrier (`order_delivered_carrier_date.notna()`)
    # OR have status in ['shipped', 'delivered'] with a valid carrier/delivery event.
    # Excludes all 550 Cancelled_Before_Shipment orders and all processing/invoiced/unavailable/created/approved orders.
    plausible_mask = (
        ship_candidates["order_delivered_carrier_date"].notna()
        | (
            ship_candidates["order_status"].isin(["shipped", "delivered"])
            & ship_candidates["order_delivered_customer_date"].notna()
        )
    )
    ship_orders = ship_candidates[plausible_mask].copy().reset_index(drop=True)
    n_ship = len(ship_orders)

    fulfillment_state = np.where(
        ship_orders["order_status"] == "canceled",
        "Cancelled_After_Shipment",
        np.where(
            (ship_orders["order_status"] == "delivered") & (ship_orders["order_delivered_customer_date"].notna()),
            "Delivered",
            "In_Transit",
        ),
    )
    has_valid_delivery = fulfillment_state == "Delivered"

    is_interstate = ship_orders["customer_state"] != ship_orders["seller_state"]
    carriers = rng.choice(
        ["Correios PAC", "Correios SEDEX", "Jadlog", "Total Express", "Azul Cargo Express", "Loggi"],
        size=n_ship,
        p=[0.42, 0.24, 0.14, 0.10, 0.05, 0.05],
    )
    service_tier = np.where(np.isin(carriers, ["Correios SEDEX", "Azul Cargo Express", "Loggi"]), "Express", "Standard")

    carrier_cost_ratio = np.where(
        is_interstate,
        rng.normal(loc=0.95, scale=0.07, size=n_ship),
        rng.normal(loc=0.86, scale=0.06, size=n_ship),
    )
    carrier_cost_ratio = np.clip(carrier_cost_ratio, 0.72, 1.18)
    actual_carrier_cost = np.round(np.maximum(6.50, ship_orders["total_freight_charged_brl"] * carrier_cost_ratio), 2)
    freight_margin = np.round(ship_orders["total_freight_charged_brl"] - actual_carrier_cost, 2)

    # Strictly null out delivery timestamps and delivery performance metrics for non-Delivered orders
    actual_deliv_ts = ship_orders["order_delivered_customer_date"].where(has_valid_delivery, pd.NaT)
    deliv_delay_days = np.where(
        has_valid_delivery,
        np.round((actual_deliv_ts - ship_orders["order_estimated_delivery_date"]).dt.total_seconds() / 86400.0, 2),
        np.nan,
    )
    is_late_series = pd.Series(
        np.where(has_valid_delivery, deliv_delay_days > 0, pd.NA),
        dtype="boolean",
    )

    exception_codes = np.where(
        fulfillment_state == "Cancelled_After_Shipment",
        "Cancelled_After_Carrier_Handoff",
        np.where(
            fulfillment_state == "In_Transit",
            "Active_In_Transit_Awaiting_Delivery",
            np.where(
                deliv_delay_days > 0,
                rng.choice(["Hub_Congestion_Delay", "Weather_Route_Delay", "Recipient_Absent_Retry", "Customs_State_Border_Hold"], size=n_ship, p=[0.45, 0.20, 0.25, 0.10]),
                "None_On_Time",
            ),
        ),
    )
    delivery_attempts = np.where(
        fulfillment_state == "Cancelled_After_Shipment",
        0,
        np.where(
            fulfillment_state == "In_Transit",
            0,
            np.where(exception_codes == "Recipient_Absent_Retry", rng.integers(2, 4, size=n_ship), 1),
        ),
    )

    df_logistics = pd.DataFrame(
        {
            "shipment_id": [f"SHP-{i:06d}" for i in range(1, n_ship + 1)],
            "order_id": ship_orders["order_id"],
            "primary_seller_id": ship_orders["primary_seller_id"],
            "fulfillment_state": fulfillment_state,
            "origin_state": ship_orders["seller_state"],
            "destination_state": ship_orders["customer_state"],
            "is_interstate_shipment": is_interstate,
            "carrier_name": carriers,
            "service_tier": service_tier,
            "customer_freight_charged_brl": np.round(ship_orders["total_freight_charged_brl"], 2),
            "actual_carrier_cost_brl": actual_carrier_cost,
            "freight_margin_brl": freight_margin,
            "carrier_handoff_timestamp": ship_orders["order_delivered_carrier_date"].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "actual_delivery_timestamp": actual_deliv_ts.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "estimated_delivery_date": ship_orders["order_estimated_delivery_date"].dt.strftime("%Y-%m-%d"),
            "delivery_variance_days": deliv_delay_days,
            "is_late_delivery": is_late_series,
            "delivery_attempts_count": delivery_attempts,
            "delivery_exception_code": exception_codes,
            "is_synthetic": True,
            "data_source": "CommerceIQ_Synthetic_v2",
        }
    )

    # -------------------------------------------------------------------------
    # CORRECTION 3: Multi-Session Customer Journeys (No Forced 1:1 Per Order)
    # -------------------------------------------------------------------------
    print("[6/9] Generating Table 7 (Upgraded): commerceiq_customer_sessions_funnel.csv...")
    cust_acq_map = df_acquisition.set_index("customer_unique_id")[
        ["first_order_id", "last_touch_campaign_id", "primary_device_type", "acquisition_timestamp"]
    ]
    orders_with_acq = orders_cust.merge(cust_acq_map, on="customer_unique_id", how="left")
    orders_with_acq["acq_dt"] = pd.to_datetime(orders_with_acq["acquisition_timestamp"])

    df_camp_lookup = df_campaigns.copy()
    df_camp_lookup["start_dt"] = pd.to_datetime(df_camp_lookup["start_date"])
    df_camp_lookup["end_dt"] = pd.to_datetime(df_camp_lookup["end_date"]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    df_camp_lookup["quarter_label"] = df_camp_lookup["campaign_name"].str.slice(0, 7)
    quarter_to_camps = {ql: grp.to_dict("records") for ql, grp in df_camp_lookup.groupby("quarter_label")}
    camp_lookup_by_id = df_camp_lookup.set_index("campaign_id").to_dict("index")

    channel_weights = np.array([0.24, 0.16, 0.10, 0.08, 0.09, 0.08, 0.07, 0.04, 0.14])
    channel_weights = channel_weights / channel_weights.sum()

    # ~74% of orders have a tracked web/app converting session (`Order_Placed`);
    # ~26% of orders occur via direct/partner API checkout without a tracked web funnel session.
    tracked_order_mask = rng.random(len(orders_with_acq)) < 0.74
    tracked_orders = orders_with_acq[tracked_order_mask].copy().reset_index(drop=True)
    n_conv = len(tracked_orders)

    ord_q_period = tracked_orders["order_purchase_timestamp"].dt.to_period("Q").astype(str)
    ord_q_fmt = ord_q_period.str.slice(0, 4) + "-" + ord_q_period.str.slice(4, 6)
    is_first_ord = tracked_orders["order_id"] == tracked_orders["first_order_id"]
    repeat_camp_indices = rng.choice(len(quarter_to_camps["2017-Q1"]), size=n_conv, p=channel_weights)

    conv_camp_ids, conv_c_starts, conv_c_ends = [], [], []
    for i in range(n_conv):
        if is_first_ord.iloc[i]:
            cid = tracked_orders["last_touch_campaign_id"].iloc[i]
        else:
            cid = quarter_to_camps[ord_q_fmt.iloc[i]][repeat_camp_indices[i]]["campaign_id"]
        c_info = camp_lookup_by_id[cid]
        conv_camp_ids.append(cid)
        conv_c_starts.append(c_info["start_dt"])
        conv_c_ends.append(c_info["end_dt"])

    conv_dur = np.clip(rng.lognormal(mean=6.4, sigma=0.55, size=n_conv).astype(int), 120, 3600)
    raw_conv_start = tracked_orders["order_purchase_timestamp"] - pd.to_timedelta(conv_dur, unit="s")
    lower_conv = np.maximum(pd.Series(conv_c_starts), tracked_orders["acq_dt"])
    conv_start = raw_conv_start.where(raw_conv_start >= lower_conv, lower_conv)
    conv_dur_adj = np.maximum(1, (tracked_orders["order_purchase_timestamp"] - conv_start).dt.total_seconds().astype(int))
    conv_delivered = (tracked_orders["order_status"] == "delivered") & (tracked_orders["order_delivered_customer_date"].notna())

    df_conv_sessions = pd.DataFrame(
        {
            "session_id": [f"SES-ORD-{i:06d}" for i in range(1, n_conv + 1)],
            "customer_unique_id": tracked_orders["customer_unique_id"].values,
            "order_id": tracked_orders["order_id"].values,
            "campaign_id": conv_camp_ids,
            "session_start_timestamp": conv_start.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "session_end_timestamp": tracked_orders["order_purchase_timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "session_duration_seconds": conv_dur_adj,
            "device_type": tracked_orders["primary_device_type"].values,
            "product_viewed": True,
            "page_views": np.clip(rng.lognormal(mean=2.3, sigma=0.45, size=n_conv).astype(int), 4, 35),
            "products_viewed": np.clip(rng.lognormal(mean=1.5, sigma=0.50, size=n_conv).astype(int), 1, 18),
            "added_to_cart": True,
            "checkout_initiated": True,
            "order_placed": True,
            "order_delivered": conv_delivered.values,
            "funnel_exit_stage": "Order_Placed",
            "is_synthetic": True,
            "data_source": "CommerceIQ_Synthetic_v2",
        }
    )

    # Multi-session pre-purchase journeys (0, 1, 2, or 3 prior browsing/abandonment sessions before Order_Placed)
    # plus general non-converting browsing sessions across all customers (including customers with 0 converted sessions)
    n_pre_conv = 42_000
    pre_idx = rng.choice(n_conv, size=n_pre_conv, replace=True)
    pre_base = tracked_orders.iloc[pre_idx].reset_index(drop=True)
    pre_cids = [conv_camp_ids[j] for j in pre_idx]
    pre_c_starts = pd.Series([camp_lookup_by_id[c]["start_dt"] for c in pre_cids])
    pre_lower = np.maximum(pre_c_starts, pre_base["acq_dt"])
    pre_upper = pd.Series(pd.to_datetime(df_conv_sessions["session_start_timestamp"].iloc[pre_idx].values) - pd.Timedelta(minutes=15))

    # Only keep rows where pre_upper > pre_lower + 60s
    valid_pre = (pre_upper - pre_lower).dt.total_seconds() > 120
    pre_base = pre_base[valid_pre].reset_index(drop=True)
    pre_cids = [c for c, ok in zip(pre_cids, valid_pre) if ok]
    pre_lower = pre_lower[valid_pre].reset_index(drop=True)
    pre_upper = pre_upper[valid_pre].reset_index(drop=True)
    n_pre_valid = len(pre_base)

    pre_dur = np.clip(rng.lognormal(mean=5.4, sigma=0.75, size=n_pre_valid).astype(int), 30, 1800)
    avail_span = np.maximum(10, ((pre_upper - pre_lower).dt.total_seconds() - pre_dur - 5).astype(int))
    pre_start = pre_lower + pd.to_timedelta((rng.random(n_pre_valid) * avail_span).astype(int), unit="s")
    pre_end = pre_start + pd.to_timedelta(pre_dur, unit="s")

    pre_stages = rng.choice(
        ["Product_Browse_Exit", "Cart_Abandonment", "Checkout_Dropoff"],
        size=n_pre_valid,
        p=[0.48, 0.35, 0.17],
    )

    df_pre_sessions = pd.DataFrame(
        {
            "session_id": [f"SES-PRE-{i:06d}" for i in range(1, n_pre_valid + 1)],
            "customer_unique_id": pre_base["customer_unique_id"].values,
            "order_id": np.nan,
            "campaign_id": pre_cids,
            "session_start_timestamp": pre_start.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "session_end_timestamp": pre_end.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "session_duration_seconds": pre_dur,
            "device_type": pre_base["primary_device_type"].values,
            "product_viewed": True,
            "page_views": np.clip(rng.lognormal(mean=1.9, sigma=0.45, size=n_pre_valid).astype(int), 2, 22),
            "products_viewed": np.clip(rng.lognormal(mean=1.2, sigma=0.45, size=n_pre_valid).astype(int), 1, 14),
            "added_to_cart": np.isin(pre_stages, ["Cart_Abandonment", "Checkout_Dropoff"]),
            "checkout_initiated": pre_stages == "Checkout_Dropoff",
            "order_placed": False,
            "order_delivered": False,
            "funnel_exit_stage": pre_stages,
            "is_synthetic": True,
            "data_source": "CommerceIQ_Synthetic_v2",
        }
    )

    # General non-converting sessions across all customers (including untracked-order customers)
    n_gen_nc = 30_000
    gen_cust_idx = rng.choice(len(df_acquisition), size=n_gen_nc, replace=True)
    gen_cust = df_acquisition.iloc[gen_cust_idx].reset_index(drop=True)
    gen_cids = gen_cust["last_touch_campaign_id"].values
    gen_c_starts = pd.Series([camp_lookup_by_id[c]["start_dt"] for c in gen_cids])
    gen_c_ends = pd.Series([camp_lookup_by_id[c]["end_dt"] for c in gen_cids])
    gen_lower = np.maximum(gen_c_starts, pd.to_datetime(gen_cust["acquisition_timestamp"]))

    gen_dur = np.clip(rng.lognormal(mean=4.9, sigma=0.85, size=n_gen_nc).astype(int), 15, 1500)
    gen_span = np.maximum(10, ((gen_c_ends - gen_lower).dt.total_seconds() - gen_dur - 5).astype(int))
    gen_start = gen_lower + pd.to_timedelta((rng.random(n_gen_nc) * gen_span).astype(int), unit="s")
    gen_end = gen_start + pd.to_timedelta(gen_dur, unit="s")

    gen_stages = rng.choice(
        ["Bounce_Landing", "Product_Browse_Exit", "Cart_Abandonment", "Checkout_Dropoff"],
        size=n_gen_nc,
        p=[0.30, 0.40, 0.20, 0.10],
    )
    gen_prod_viewed = gen_stages != "Bounce_Landing"

    df_gen_sessions = pd.DataFrame(
        {
            "session_id": [f"SES-BRW-{i:06d}" for i in range(1, n_gen_nc + 1)],
            "customer_unique_id": gen_cust["customer_unique_id"].values,
            "order_id": np.nan,
            "campaign_id": gen_cids,
            "session_start_timestamp": gen_start.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "session_end_timestamp": gen_end.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "session_duration_seconds": gen_dur,
            "device_type": gen_cust["primary_device_type"].values,
            "product_viewed": gen_prod_viewed,
            "page_views": np.where(gen_stages == "Bounce_Landing", 1, np.clip(rng.lognormal(mean=1.6, sigma=0.5, size=n_gen_nc).astype(int), 2, 18)),
            "products_viewed": np.where(gen_stages == "Bounce_Landing", 0, np.clip(rng.lognormal(mean=1.0, sigma=0.5, size=n_gen_nc).astype(int), 1, 10)),
            "added_to_cart": np.isin(gen_stages, ["Cart_Abandonment", "Checkout_Dropoff"]),
            "checkout_initiated": gen_stages == "Checkout_Dropoff",
            "order_placed": False,
            "order_delivered": False,
            "funnel_exit_stage": gen_stages,
            "is_synthetic": True,
            "data_source": "CommerceIQ_Synthetic_v2",
        }
    )

    df_sessions = pd.concat([df_conv_sessions, df_pre_sessions, df_gen_sessions], ignore_index=True)

    # -------------------------------------------------------------------------
    # CORRECTION 4 (Option A): Multi-Period Historical Inventory Snapshots
    # 4 Monthly Snapshots: 2018-07-01, 2018-08-01, 2018-09-01, 2018-10-01
    # Exact Stock Flow Conservation: opening + received - sold = closing
    # -------------------------------------------------------------------------
    print("[7/9] Generating Table 8 (Upgraded Option A): commerceiq_inventory_snapshots.csv...")
    items_with_month = items.merge(orders_ts[["order_id", "order_purchase_timestamp"]], on="order_id", how="left")
    items_with_month["ym"] = items_with_month["order_purchase_timestamp"].dt.to_period("M").astype(str)

    # Prior calendar month sales feeding each snapshot date:
    # 2018-07-01 reflects 2018-06 activity, 2018-08-01 -> 2018-07, 2018-09-01 -> 2018-08, 2018-10-01 -> 2018-09
    snapshot_specs = [
        ("2018-07-01", "2018-06"),
        ("2018-08-01", "2018-07"),
        ("2018-09-01", "2018-08"),
        ("2018-10-01", "2018-09"),
    ]

    seller_prod = (
        items.groupby(["seller_id", "product_id"], as_index=False)
        .agg(total_olist_units_sold=("order_item_id", "count"))
        .merge(sellers[["seller_id", "seller_state"]], on="seller_id", how="left")
        .merge(df_product_costs[["product_id", "unit_cogs_brl"]], on="product_id", how="left")
    )
    n_sp = len(seller_prod)
    avg_monthly_vel = np.round(np.maximum(0.5, seller_prod["total_olist_units_sold"] / 6.0), 2)
    lead_time_days = rng.integers(3, 25, size=n_sp)
    safety_stock = np.maximum(2, np.ceil(avg_monthly_vel * (lead_time_days / 30.0) * 0.6).astype(int))
    reorder_point = safety_stock + np.maximum(2, np.ceil(avg_monthly_vel * (lead_time_days / 30.0)).astype(int))

    # Initialize opening stock prior to June 2018
    running_stock = np.maximum(1, reorder_point + rng.integers(0, 28, size=n_sp))
    inv_frames = []
    rec_counter = 1

    for snap_date, sales_ym in snapshot_specs:
        m_sales = (
            items_with_month[items_with_month["ym"] == sales_ym]
            .groupby(["seller_id", "product_id"], as_index=False)["order_item_id"]
            .count()
            .rename(columns={"order_item_id": "actual_olist_sales"})
        )
        sp_m = seller_prod.merge(m_sales, on=["seller_id", "product_id"], how="left")
        actual_demand = sp_m["actual_olist_sales"].fillna(0).astype(int).values

        opening_stock = running_stock.copy()
        # Replenish when opening stock is at or below reorder point
        needs_replenish = opening_stock <= reorder_point
        replenish_qty = np.where(
            needs_replenish,
            np.maximum(reorder_point * 2 - opening_stock, rng.integers(4, 24, size=n_sp)),
            0,
        )
        available_for_sale = opening_stock + replenish_qty
        units_sold = np.minimum(actual_demand, available_for_sale)
        unmet_demand = actual_demand - units_sold
        closing_stock = available_for_sale - units_sold

        reserved_qty = np.minimum(closing_stock, rng.integers(0, 4, size=n_sp))
        available_qty = closing_stock - reserved_qty
        stockout_flag = (closing_stock == 0) | (unmet_demand > 0)

        inv_status = np.where(
            available_qty == 0,
            "Out_of_Stock",
            np.where(available_qty <= reorder_point, "Low_Stock_Reorder", "Healthy_In_Stock"),
        )

        inv_frames.append(
            pd.DataFrame(
                {
                    "inventory_record_id": [f"INV-{i:06d}" for i in range(rec_counter, rec_counter + n_sp)],
                    "snapshot_date": snap_date,
                    "seller_id": seller_prod["seller_id"].values,
                    "product_id": seller_prod["product_id"].values,
                    "warehouse_region_state": seller_prod["seller_state"].values,
                    "opening_stock_units": opening_stock,
                    "stock_received_units": replenish_qty,
                    "units_sold_in_period": units_sold,
                    "closing_stock_units": closing_stock,
                    "reserved_quantity": reserved_qty,
                    "available_quantity": available_qty,
                    "safety_stock_units": safety_stock,
                    "reorder_point_units": reorder_point,
                    "supplier_lead_time_days": lead_time_days,
                    "stockout_occurred": stockout_flag,
                    "inventory_valuation_cogs_brl": np.round(closing_stock * seller_prod["unit_cogs_brl"].values, 2),
                    "stock_health_status": inv_status,
                    "is_synthetic": True,
                    "data_source": "CommerceIQ_Synthetic_v2",
                }
            )
        )
        rec_counter += n_sp
        running_stock = closing_stock

    df_inventory = pd.concat(inv_frames, ignore_index=True)

    # -------------------------------------------------------------------------
    # TABLE 9: commerceiq_customer_support_tickets.csv (Synchronized with v2)
    # -------------------------------------------------------------------------
    print("[8/9] Generating Table 9 (Synchronized): commerceiq_customer_support_tickets.csv...")
    ret_order_ids = set(df_returns["order_id"].unique())
    canc_order_ids = set(df_cancellations["order_id"].unique())
    late_order_ids = set(df_logistics.loc[df_logistics["is_late_delivery"].fillna(False), "order_id"].unique())

    orders_ticket_pool = orders_cust.merge(order_min_review, on="order_id", how="left")
    orders_ticket_pool["review_score"] = orders_ticket_pool["review_score"].fillna(5)
    orders_ticket_pool["has_return"] = orders_ticket_pool["order_id"].isin(ret_order_ids)
    orders_ticket_pool["has_cancel"] = orders_ticket_pool["order_id"].isin(canc_order_ids)
    orders_ticket_pool["is_late"] = orders_ticket_pool["order_id"].isin(late_order_ids)

    ticket_prob = np.where(
        orders_ticket_pool["has_return"] | orders_ticket_pool["has_cancel"],
        0.85,
        np.where(
            orders_ticket_pool["review_score"] <= 2,
            0.75,
            np.where(orders_ticket_pool["is_late"], 0.45, 0.03),
        ),
    )
    t_orders = orders_ticket_pool[rng.random(len(orders_ticket_pool)) < ticket_prob].copy().reset_index(drop=True)
    n_tickets = len(t_orders)

    issue_cats = np.where(
        t_orders["has_cancel"],
        "Order_Cancellation_Refund_Inquiry",
        np.where(
            t_orders["has_return"],
            "Product_Return_RMA_Inquiry",
            np.where(
                t_orders["is_late"],
                "Where_Is_My_Order_WISMO",
                rng.choice(
                    ["Product_Quality_or_Defect", "Payment_or_Boleto_Issue", "Address_or_Invoice_Change", "Seller_Communication_Delay"],
                    size=n_tickets,
                    p=[0.35, 0.25, 0.20, 0.20],
                ),
            ),
        ),
    )

    raw_t_created = t_orders["order_purchase_timestamp"] + pd.to_timedelta(rng.integers(3600, 18 * 86400, size=n_tickets), unit="s")
    is_wismo = issue_cats == "Where_Is_My_Order_WISMO"
    has_deliv = t_orders["order_delivered_customer_date"].notna()
    wismo_max_ts = t_orders["order_delivered_customer_date"] - pd.to_timedelta(rng.integers(3600, 72 * 3600, size=n_tickets), unit="s")
    wismo_clamped = np.maximum(
        t_orders["order_purchase_timestamp"] + pd.Timedelta(minutes=30),
        np.minimum(raw_t_created, wismo_max_ts),
    )
    t_created = pd.to_datetime(np.where(is_wismo & has_deliv, wismo_clamped, raw_t_created))

    t_channels = rng.choice(["Web_Help_Center", "Email", "WhatsApp_Bot", "Phone_Support", "Marketplace_Chat"], size=n_tickets, p=[0.34, 0.26, 0.18, 0.10, 0.12])
    priorities = np.where(
        t_orders["review_score"] == 1,
        rng.choice(["High", "Urgent"], size=n_tickets, p=[0.65, 0.35]),
        rng.choice(["Low", "Medium", "High"], size=n_tickets, p=[0.30, 0.50, 0.20]),
    )

    resp_mu = np.where(t_channels == "WhatsApp_Bot", 1.8, np.where(t_channels == "Phone_Support", 2.5, 4.1))
    first_resp_mins = np.clip(rng.lognormal(mean=resp_mu, sigma=0.75, size=n_tickets).astype(int), 2, 720)
    res_mu = np.where(np.isin(priorities, ["Urgent", "High"]), 2.8, 3.1)
    res_hours = np.clip(rng.lognormal(mean=res_mu, sigma=0.80, size=n_tickets), 0.5, 120.0)
    t_resolved = t_created + pd.to_timedelta(first_resp_mins, unit="m") + pd.to_timedelta(res_hours, unit="h")

    sla_breached = res_hours > 48.0
    csat_scores = np.where(
        sla_breached,
        rng.choice([1, 2, 3], size=n_tickets, p=[0.50, 0.35, 0.15]),
        np.where(
            t_orders["review_score"] <= 2,
            rng.choice([2, 3, 4], size=n_tickets, p=[0.25, 0.45, 0.30]),
            rng.choice([4, 5], size=n_tickets, p=[0.38, 0.62]),
        ),
    )

    df_tickets = pd.DataFrame(
        {
            "ticket_id": [f"TKT-{i:06d}" for i in range(1, n_tickets + 1)],
            "order_id": t_orders["order_id"],
            "customer_unique_id": t_orders["customer_unique_id"],
            "ticket_channel": t_channels,
            "issue_category": issue_cats,
            "priority_level": priorities,
            "ticket_created_timestamp": t_created.strftime("%Y-%m-%d %H:%M:%S"),
            "ticket_resolved_timestamp": t_resolved.strftime("%Y-%m-%d %H:%M:%S"),
            "first_response_time_minutes": first_resp_mins,
            "resolution_time_hours": np.round(res_hours, 2),
            "sla_breached": sla_breached,
            "agent_interactions_count": rng.integers(1, 7, size=n_tickets),
            "post_ticket_csat_score": csat_scores,
            "is_synthetic": True,
            "data_source": "CommerceIQ_Synthetic_v2",
        }
    )

    print("[9/9] Writing updated v2 synthetic CSV files...")
    updated_tables = {
        "commerceiq_returns_refunds.csv": df_returns,
        "commerceiq_cancellations_refunds.csv": df_cancellations,
        "commerceiq_shipment_tracking_logistics.csv": df_logistics,
        "commerceiq_customer_sessions_funnel.csv": df_sessions,
        "commerceiq_inventory_snapshots.csv": df_inventory,
        "commerceiq_customer_support_tickets.csv": df_tickets,
    }
    all_tables = {
        "commerceiq_marketing_campaigns.csv": df_campaigns,
        "commerceiq_customer_acquisition_attribution.csv": df_acquisition,
        "commerceiq_product_costs_pricing.csv": df_product_costs,
        **updated_tables,
    }

    for fname, df in updated_tables.items():
        out_path = os.path.join(output_dir, fname)
        df.to_csv(out_path, index=False)

    summary_stats = {}
    for fname, df in all_tables.items():
        out_path = os.path.join(output_dir, fname)
        summary_stats[fname] = {
            "rows": len(df),
            "cols": len(df.columns),
            "sha256": compute_sha256(out_path),
        }
        print(f"  -> {fname}: {df.shape[0]:,} rows x {df.shape[1]} cols")

    return summary_stats


if __name__ == "__main__":
    OLIST_SOURCE_DIR = "/working_dir/c_3555ef631fbfd05e/user_uploaded_files/ttl=63d/user_uploaded"
    OUTPUT_DIR = "/working_dir/c_3555ef631fbfd05e/artifacts/file_generation/ttl=63d/output"
    generate_v2_dataset(OLIST_SOURCE_DIR, OUTPUT_DIR, seed=42, force_regenerate_all=False)
