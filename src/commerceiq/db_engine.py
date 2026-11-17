import os
import time
import json
import sqlite3
import numpy as np
import pandas as pd

OLIST_TABLES = {
    "olist_customers_dataset": "olist_customers_dataset.csv",
    "olist_geolocation_dataset": "olist_geolocation_dataset.csv",
    "olist_order_items_dataset": "olist_order_items_dataset.csv",
    "olist_order_payments_dataset": "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset": "olist_order_reviews_dataset.csv",
    "olist_orders_dataset": "olist_orders_dataset.csv",
    "olist_products_dataset": "olist_products_dataset.csv",
    "olist_sellers_dataset": "olist_sellers_dataset.csv",
    "product_category_name_translation": "product_category_name_translation.csv",
}

SYNTHETIC_V2_TABLES = {
    "commerceiq_marketing_campaigns": "commerceiq_marketing_campaigns.csv",
    "commerceiq_customer_acquisition_attribution": "commerceiq_customer_acquisition_attribution.csv",
    "commerceiq_product_costs_pricing": "commerceiq_product_costs_pricing.csv",
    "commerceiq_returns_refunds": "commerceiq_returns_refunds.csv",
    "commerceiq_cancellations_refunds": "commerceiq_cancellations_refunds.csv",
    "commerceiq_shipment_tracking_logistics": "commerceiq_shipment_tracking_logistics.csv",
    "commerceiq_customer_sessions_funnel": "commerceiq_customer_sessions_funnel.csv",
    "commerceiq_inventory_snapshots": "commerceiq_inventory_snapshots.csv",
    "commerceiq_customer_support_tickets": "commerceiq_customer_support_tickets.csv",
}


class CommerceIQWarehouse:
    def __init__(self, platform_root: str, olist_dir: str, synth_dir: str, db_path: str = None):
        self.platform_root = platform_root
        self.olist_dir = olist_dir
        self.synth_dir = synth_dir
        self.db_path = db_path or os.path.join(platform_root, "data", "commerceiq_warehouse.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.kpi_registry_path = os.path.join(platform_root, "config", "kpi_registry.json")
        self.views_sql_path = os.path.join(platform_root, "sql", "02_analytical_views.sql")

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=MEMORY;")
        conn.execute("PRAGMA synchronous=OFF;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-128000;")
        return conn

    def load_kpi_registry(self) -> dict:
        with open(self.kpi_registry_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def build_warehouse(self, include_full_geolocation: bool = False) -> dict:
        t0 = time.time()
        stats = {"original_tables": {}, "synthetic_tables": {}, "views": []}
        dfs = {}

        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

        conn = self.get_connection()
        try:
            for tname, fname in OLIST_TABLES.items():
                fpath = os.path.join(self.olist_dir, fname)
                df = pd.read_csv(fpath, low_memory=False)
                stats["original_tables"][tname] = len(df)
                if tname == "olist_geolocation_dataset" and not include_full_geolocation:
                    geo_dedup = df.groupby("geolocation_zip_code_prefix", as_index=False).agg(
                        geolocation_lat=("geolocation_lat", "median"),
                        geolocation_lng=("geolocation_lng", "median"),
                        geolocation_city=("geolocation_city", "first"),
                        geolocation_state=("geolocation_state", "first"),
                    )
                    geo_dedup.to_sql("olist_geolocation_zip_dedup", conn, if_exists="replace", index=False)
                    geo_dedup.to_sql(tname, conn, if_exists="replace", index=False)
                    dfs[tname] = geo_dedup
                    print(f"  -> Loaded {tname} (dedup: {len(geo_dedup):,} rows)", flush=True)
                else:
                    df.to_sql(tname, conn, if_exists="replace", index=False)
                    dfs[tname] = df
                    print(f"  -> Loaded {tname} ({len(df):,} rows)", flush=True)

            for tname, fname in SYNTHETIC_V2_TABLES.items():
                fpath = os.path.join(self.synth_dir, fname)
                df = pd.read_csv(fpath, low_memory=False)
                for bcol in df.columns:
                    if str(df[bcol].dtype) in ("bool", "boolean"):
                        df[bcol] = df[bcol].astype("int64")
                df.to_sql(tname, conn, if_exists="replace", index=False)
                dfs[tname] = df
                stats["synthetic_tables"][tname] = len(df)
                print(f"  -> Loaded {tname} ({len(df):,} rows)", flush=True)

            print("  -> Computing analytical views in Pandas (vectorized hash merges)...", flush=True)

            oi = dfs["olist_order_items_dataset"]
            o = dfs["olist_orders_dataset"]
            c = dfs["olist_customers_dataset"]
            s = dfs["olist_sellers_dataset"]
            pay = dfs["olist_order_payments_dataset"]
            rev = dfs["olist_order_reviews_dataset"]
            pc = dfs["commerceiq_product_costs_pricing"]
            stl = dfs["commerceiq_shipment_tracking_logistics"]
            rr = dfs["commerceiq_returns_refunds"]
            cxl = dfs["commerceiq_cancellations_refunds"]
            caa = dfs["commerceiq_customer_acquisition_attribution"]
            tkt = dfs["commerceiq_customer_support_tickets"]
            mc = dfs["commerceiq_marketing_campaigns"]

            # 1. Pre-aggregations at order / item level
            ic = oi.groupby("order_id", as_index=False).size().rename(columns={"size": "order_item_count"})

            cxl_items = cxl[cxl["order_item_id"].notna()].copy()
            if not cxl_items.empty:
                cxl_items["order_item_id"] = cxl_items["order_item_id"].astype(oi["order_item_id"].dtype)
                cxl_agg = cxl_items.groupby(["order_id", "order_item_id"], as_index=False).agg(
                    cancel_refund_brl=("refunded_amount_brl", "sum"),
                    cancel_intercept_cost_brl=("intercept_or_restocking_cost_brl", "sum"),
                )
                cxl_agg["has_item_cancellation"] = 1
            else:
                cxl_agg = pd.DataFrame(
                    columns=["order_id", "order_item_id", "cancel_refund_brl", "cancel_intercept_cost_brl", "has_item_cancellation"]
                )

            rr_sub = rr[["order_id", "order_item_id", "return_id", "refunded_amount_brl", "reverse_logistics_cost_brl"]].copy()
            rr_sub["order_item_id"] = rr_sub["order_item_id"].astype(oi["order_item_id"].dtype)

            # Build vw_fact_order_items
            fact = (
                oi[["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"]]
                .merge(o[["order_id", "customer_id", "order_status", "order_purchase_timestamp"]], on="order_id", how="inner")
                .merge(c[["customer_id", "customer_unique_id", "customer_state"]], on="customer_id", how="inner")
                .merge(s[["seller_id", "seller_state"]], on="seller_id", how="inner")
                .merge(ic, on="order_id", how="inner")
                .merge(
                    pc[
                        [
                            "product_id",
                            "product_category_english",
                            "unit_cogs_brl",
                            "packaging_handling_cost_brl",
                            "olist_marketplace_commission_pct",
                            "tax_icms_rate_pct",
                        ]
                    ],
                    on="product_id",
                    how="left",
                )
                .merge(stl[["order_id", "actual_carrier_cost_brl"]], on="order_id", how="left")
                .merge(rr_sub, on=["order_id", "order_item_id"], how="left")
                .merge(cxl_agg, on=["order_id", "order_item_id"], how="left")
            )

            fact["product_category_english"] = fact["product_category_english"].fillna("uncategorized")
            fact["order_year_month"] = fact["order_purchase_timestamp"].astype(str).str.slice(0, 7)
            fact["item_price_brl"] = fact["price"]
            fact["item_freight_brl"] = fact["freight_value"]
            fact["gross_item_revenue_brl"] = (fact["price"] + fact["freight_value"]).round(2)

            raw_comm = fact["price"] * fact["olist_marketplace_commission_pct"]
            raw_icms = fact["price"] * fact["tax_icms_rate_pct"]
            raw_alloc_carrier = fact["actual_carrier_cost_brl"].fillna(0.0) / fact["order_item_count"]

            fact["marketplace_commission_brl"] = raw_comm.round(2)
            fact["icms_tax_brl"] = raw_icms.round(2)
            fact["allocated_carrier_cost_brl"] = raw_alloc_carrier.round(2)

            fact["has_return"] = np.where(fact["return_id"].notna(), 1, 0)
            fact["return_refund_brl"] = fact["refunded_amount_brl"].fillna(0.0)
            fact["reverse_logistics_cost_brl"] = fact["reverse_logistics_cost_brl"].fillna(0.0)

            fact["has_item_cancellation"] = fact["has_item_cancellation"].fillna(0).astype(int)
            fact["cancel_refund_brl"] = fact["cancel_refund_brl"].fillna(0.0)
            fact["cancel_intercept_cost_brl"] = fact["cancel_intercept_cost_brl"].fillna(0.0)

            fact["net_contribution_brl"] = (
                (fact["price"] + fact["freight_value"])
                - raw_icms
                - raw_comm
                - fact["unit_cogs_brl"]
                - fact["packaging_handling_cost_brl"]
                - raw_alloc_carrier
                - fact["return_refund_brl"]
                - fact["reverse_logistics_cost_brl"]
                - fact["cancel_refund_brl"]
                - fact["cancel_intercept_cost_brl"]
            ).round(2)

            fact_cols = [
                "order_id",
                "order_item_id",
                "customer_id",
                "customer_unique_id",
                "customer_state",
                "product_id",
                "product_category_english",
                "seller_id",
                "seller_state",
                "order_status",
                "order_purchase_timestamp",
                "order_year_month",
                "item_price_brl",
                "item_freight_brl",
                "gross_item_revenue_brl",
                "unit_cogs_brl",
                "packaging_handling_cost_brl",
                "marketplace_commission_brl",
                "icms_tax_brl",
                "allocated_carrier_cost_brl",
                "has_return",
                "return_refund_brl",
                "reverse_logistics_cost_brl",
                "has_item_cancellation",
                "cancel_refund_brl",
                "cancel_intercept_cost_brl",
                "net_contribution_brl",
            ]
            fact_df = fact[fact_cols]
            fact_df.to_sql("_mat_vw_fact_order_items", conn, if_exists="replace", index=False)
            conn.execute("CREATE VIEW IF NOT EXISTS vw_fact_order_items AS SELECT * FROM _mat_vw_fact_order_items;")
            stats["views"].append({"view_name": "vw_fact_order_items", "rows": int(len(fact_df))})
            print(f"  -> Materialized view vw_fact_order_items ({len(fact_df):,} rows)", flush=True)

            # 2. Build vw_customer_summary
            op = pay.groupby("order_id", as_index=False)["payment_value"].sum().rename(columns={"payment_value": "order_payment_brl"})
            orev = rev.groupby("order_id", as_index=False)["review_score"].mean().rename(columns={"review_score": "avg_review_score"})

            co_base = (
                c[["customer_id", "customer_unique_id", "customer_state"]]
                .merge(o[["order_id", "customer_id", "order_status", "order_purchase_timestamp"]], on="customer_id", how="inner")
                .merge(op, on="order_id", how="left")
                .merge(orev, on="order_id", how="left")
            )
            co_base["order_payment_brl"] = co_base["order_payment_brl"].fillna(0.0)
            co_base["is_delivered"] = (co_base["order_status"] == "delivered").astype(int)
            co_base["is_canceled"] = (co_base["order_status"] == "canceled").astype(int)

            co = co_base.groupby("customer_unique_id", as_index=False).agg(
                customer_state=("customer_state", "min"),
                total_orders=("order_id", "nunique"),
                delivered_orders=("is_delivered", "sum"),
                canceled_orders=("is_canceled", "sum"),
                first_order_ts=("order_purchase_timestamp", "min"),
                last_order_ts=("order_purchase_timestamp", "max"),
                lifetime_payment_brl=("order_payment_brl", "sum"),
                avg_customer_review_score=("avg_review_score", "mean"),
            )
            co["acquisition_cohort_ym"] = co["first_order_ts"].astype(str).str.slice(0, 7)
            co["lifetime_payment_brl"] = co["lifetime_payment_brl"].round(2)
            co["avg_customer_review_score"] = co["avg_customer_review_score"].round(3)
            co["is_repeat_customer"] = np.where(co["total_orders"] >= 2, 1, 0)

            stl_deliv = stl[stl["fulfillment_state"] == "Delivered"][["order_id", "is_late_delivery", "delivery_variance_days"]].copy()
            stl_deliv["is_late_flag"] = np.where(stl_deliv["is_late_delivery"] == 1, 1, 0)
            cl_base = (
                c[["customer_id", "customer_unique_id"]]
                .merge(o[["order_id", "customer_id"]], on="customer_id", how="inner")
                .merge(stl_deliv, on="order_id", how="inner")
            )
            cl = cl_base.groupby("customer_unique_id", as_index=False).agg(
                ever_had_late_delivery=("is_late_flag", "max"),
                avg_delivery_variance_days=("delivery_variance_days", "mean"),
            )
            cl["avg_delivery_variance_days"] = cl["avg_delivery_variance_days"].round(2)

            tkt_copy = tkt[["customer_unique_id", "sla_breached"]].copy()
            tkt_copy["sla_flag"] = np.where(tkt_copy["sla_breached"] == 1, 1, 0)
            ct = tkt_copy.groupby("customer_unique_id", as_index=False).agg(
                support_tickets_count=("sla_flag", "count"),
                ever_had_sla_breach=("sla_flag", "max"),
            )

            cust_sum = (
                co.merge(
                    caa[
                        [
                            "customer_unique_id",
                            "first_touch_campaign_id",
                            "last_touch_campaign_id",
                            "acquisition_channel",
                            "primary_device_type",
                            "customer_acquisition_cost_brl",
                            "loyalty_tier",
                            "predicted_churn_probability",
                        ]
                    ],
                    on="customer_unique_id",
                    how="left",
                )
                .merge(cl, on="customer_unique_id", how="left")
                .merge(ct, on="customer_unique_id", how="left")
            )
            cust_sum["ever_had_late_delivery"] = cust_sum["ever_had_late_delivery"].fillna(0).astype(int)
            cust_sum["support_tickets_count"] = cust_sum["support_tickets_count"].fillna(0).astype(int)
            cust_sum["ever_had_sla_breach"] = cust_sum["ever_had_sla_breach"].fillna(0).astype(int)

            cust_cols = [
                "customer_unique_id",
                "customer_state",
                "acquisition_cohort_ym",
                "first_order_ts",
                "last_order_ts",
                "total_orders",
                "delivered_orders",
                "canceled_orders",
                "is_repeat_customer",
                "lifetime_payment_brl",
                "avg_customer_review_score",
                "first_touch_campaign_id",
                "last_touch_campaign_id",
                "acquisition_channel",
                "primary_device_type",
                "customer_acquisition_cost_brl",
                "loyalty_tier",
                "predicted_churn_probability",
                "ever_had_late_delivery",
                "avg_delivery_variance_days",
                "support_tickets_count",
                "ever_had_sla_breach",
            ]
            cust_df = cust_sum[cust_cols]
            cust_df.to_sql("_mat_vw_customer_summary", conn, if_exists="replace", index=False)
            conn.execute("CREATE VIEW IF NOT EXISTS vw_customer_summary AS SELECT * FROM _mat_vw_customer_summary;")
            stats["views"].append({"view_name": "vw_customer_summary", "rows": int(len(cust_df))})
            print(f"  -> Materialized view vw_customer_summary ({len(cust_df):,} rows)", flush=True)

            # 3. Build vw_marketing_roas
            cc = (
                cust_df.groupby("last_touch_campaign_id", as_index=False)
                .agg(
                    acquired_customers=("customer_unique_id", "count"),
                    total_cohort_orders=("total_orders", "sum"),
                    repeat_customers=("is_repeat_customer", "sum"),
                    attributed_gmv_brl=("lifetime_payment_brl", "sum"),
                    attributed_cac_brl=("customer_acquisition_cost_brl", "sum"),
                )
                .rename(columns={"last_touch_campaign_id": "campaign_id"})
            )
            cc["attributed_gmv_brl"] = cc["attributed_gmv_brl"].round(2)
            cc["attributed_cac_brl"] = cc["attributed_cac_brl"].round(2)

            roas_df = mc[
                [
                    "campaign_id",
                    "campaign_name",
                    "marketing_channel",
                    "ad_platform",
                    "cost_model",
                    "start_date",
                    "end_date",
                    "planned_budget_brl",
                    "actual_spend_brl",
                    "impressions",
                    "clicks",
                ]
            ].merge(cc, on="campaign_id", how="left")

            roas_df["acquired_customers"] = roas_df["acquired_customers"].fillna(0).astype(int)
            roas_df["total_cohort_orders"] = roas_df["total_cohort_orders"].fillna(0).astype(int)
            roas_df["repeat_customers"] = roas_df["repeat_customers"].fillna(0).astype(int)
            roas_df["attributed_gmv_brl"] = roas_df["attributed_gmv_brl"].fillna(0.0).round(2)
            roas_df["attributed_cac_brl"] = roas_df["attributed_cac_brl"].fillna(0.0).round(2)
            roas_df["campaign_roas"] = np.where(
                roas_df["actual_spend_brl"] > 0,
                (roas_df["attributed_gmv_brl"] / roas_df["actual_spend_brl"]).round(2),
                np.nan,
            )

            roas_df.to_sql("_mat_vw_marketing_roas", conn, if_exists="replace", index=False)
            conn.execute("CREATE VIEW IF NOT EXISTS vw_marketing_roas AS SELECT * FROM _mat_vw_marketing_roas;")
            stats["views"].append({"view_name": "vw_marketing_roas", "rows": int(len(roas_df))})
            print(f"  -> Materialized view vw_marketing_roas ({len(roas_df):,} rows)", flush=True)

            # 4. Build vw_carrier_performance
            carrier_df = (
                stl[stl["fulfillment_state"] == "Delivered"][
                    [
                        "shipment_id",
                        "order_id",
                        "primary_seller_id",
                        "fulfillment_state",
                        "origin_state",
                        "destination_state",
                        "is_interstate_shipment",
                        "carrier_name",
                        "service_tier",
                        "customer_freight_charged_brl",
                        "actual_carrier_cost_brl",
                        "freight_margin_brl",
                        "delivery_variance_days",
                        "is_late_delivery",
                        "delivery_attempts_count",
                        "delivery_exception_code",
                    ]
                ]
                .merge(orev, on="order_id", how="left")
            )
            carrier_df.to_sql("_mat_vw_carrier_performance", conn, if_exists="replace", index=False)
            conn.execute("CREATE VIEW IF NOT EXISTS vw_carrier_performance AS SELECT * FROM _mat_vw_carrier_performance;")
            stats["views"].append({"view_name": "vw_carrier_performance", "rows": int(len(carrier_df))})
            print(f"  -> Materialized view vw_carrier_performance ({len(carrier_df):,} rows)", flush=True)

            print("  -> Creating indexes and running ANALYZE...", flush=True)
            for stmt in [
                "CREATE INDEX IF NOT EXISTS idx_ord_id ON olist_orders_dataset(order_id);",
                "CREATE INDEX IF NOT EXISTS idx_ord_cust ON olist_orders_dataset(customer_id);",
                "CREATE INDEX IF NOT EXISTS idx_cust_id ON olist_customers_dataset(customer_id);",
                "CREATE INDEX IF NOT EXISTS idx_cust_uid ON olist_customers_dataset(customer_unique_id);",
                "CREATE INDEX IF NOT EXISTS idx_oi_ord ON olist_order_items_dataset(order_id);",
                "CREATE INDEX IF NOT EXISTS idx_oi_prod ON olist_order_items_dataset(product_id);",
                "CREATE INDEX IF NOT EXISTS idx_oi_sell ON olist_order_items_dataset(seller_id);",
                "CREATE INDEX IF NOT EXISTS idx_prod_id ON olist_products_dataset(product_id);",
                "CREATE INDEX IF NOT EXISTS idx_sell_id ON olist_sellers_dataset(seller_id);",
                "CREATE INDEX IF NOT EXISTS idx_pay_ord ON olist_order_payments_dataset(order_id);",
                "CREATE INDEX IF NOT EXISTS idx_rev_ord ON olist_order_reviews_dataset(order_id);",
                "CREATE INDEX IF NOT EXISTS idx_pc_id ON commerceiq_product_costs_pricing(product_id);",
                "CREATE INDEX IF NOT EXISTS idx_stl_ord ON commerceiq_shipment_tracking_logistics(order_id);",
                "CREATE INDEX IF NOT EXISTS idx_rr_ord_item ON commerceiq_returns_refunds(order_id, order_item_id);",
                "CREATE INDEX IF NOT EXISTS idx_cxl_ord ON commerceiq_cancellations_refunds(order_id);",
                "CREATE INDEX IF NOT EXISTS idx_caa_uid ON commerceiq_customer_acquisition_attribution(customer_unique_id);",
                "CREATE INDEX IF NOT EXISTS idx_tkt_uid ON commerceiq_customer_support_tickets(customer_unique_id);",
                "CREATE INDEX IF NOT EXISTS idx_tkt_ord ON commerceiq_customer_support_tickets(order_id);",
                "CREATE INDEX IF NOT EXISTS idx_foi_ord ON _mat_vw_fact_order_items(order_id);",
                "CREATE INDEX IF NOT EXISTS idx_foi_cat ON _mat_vw_fact_order_items(product_category_english);",
                "CREATE INDEX IF NOT EXISTS idx_foi_ym ON _mat_vw_fact_order_items(order_year_month);",
                "CREATE INDEX IF NOT EXISTS idx_cs_uid ON _mat_vw_customer_summary(customer_unique_id);",
                "CREATE INDEX IF NOT EXISTS idx_cs_coh ON _mat_vw_customer_summary(acquisition_cohort_ym);",
                "CREATE INDEX IF NOT EXISTS idx_cp_car ON _mat_vw_carrier_performance(carrier_name);",
            ]:
                conn.execute(stmt)
            conn.execute("ANALYZE;")

            conn.commit()
            print(f"  -> Warehouse build complete in {time.time() - t0:.1f}s!", flush=True)
        finally:
            conn.close()
        return stats

    def query_df(self, sql: str, params: tuple = None) -> pd.DataFrame:
        conn = self.get_connection()
        try:
            return pd.read_sql_query(sql, conn, params=params)
        finally:
            conn.close()

    def get_schema_catalog(self) -> list:
        conn = self.get_connection()
        try:
            objs = pd.read_sql_query(
                "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE '_mat_%' AND name NOT LIKE 'sqlite_%' ORDER BY type, name",
                conn,
            )
            catalog = []
            for row in objs.itertuples():
                cols = pd.read_sql_query(f"PRAGMA table_info({row.name})", conn)
                catalog.append({
                    "name": row.name,
                    "type": row.type,
                    "columns": [{"name": r.name, "dtype": r.type} for r in cols.itertuples()],
                })
            return catalog
        finally:
            conn.close()