# CommerceIQ v2 — Integrated Entity-Relationship & Join Architecture Guide

This guide documents how the 9 original tables from the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) connect to the **9 synthetic CommerceIQ v2 tables** (`585,568` total synthetic records).

## 1. Integrated Entity-Relationship Topology (`v2`)

```text
                        +---------------------------------------------+
                        |    commerceiq_marketing_campaigns (SYNTH)   |
                        | PK: campaign_id (90 rows)                   |
                        +----------------------+----------------------+
                                               |
                   +---------------------------+---------------------------+
                   | (1:N on first/last_touch_campaign_id)                 | (1:N on campaign_id)
                   v                                                       v
+---------------------------------------------+         +---------------------------------------------+
| commerceiq_customer_acquisition_attribution |         |  commerceiq_customer_sessions_funnel (SYNTH)|
| PK/FK: customer_unique_id (96,096 rows)     |         | PK: session_id (145,458 rows)               |
| FK: first_order_id -> olist_orders          |         | FK: customer_unique_id, order_id (nullable) |
+----------------------+----------------------+         +----------------------+----------------------+
                       | (1:1 on customer_unique_id)                           |
                       v                                                       |
+---------------------------------------------+                                |
|       olist_customers_dataset (ORIG)        |                                |
| PK: customer_id (99,441 rows)               |                                |
| Index: customer_unique_id (96,096 unique)   |                                |
| FK: customer_zip_code_prefix -> geolocation |                                |
+----------------------+----------------------+                                |
                       | (1:1 on customer_id)                                  | (0..1:1 on tracked Order_Placed)
                       v                                                       |
+---------------------------------------------+                                |
|         olist_orders_dataset (ORIG)         |<-------------------------------+
| PK: order_id (99,441 rows)                  |
| FK: customer_id                             |
+----+-----------+---------------+------------+--------------------+--------------------------+
     |           |               |                                 |                          |
     | (1:N)     | (1:N)         | (0..1:1 on plausible shipments) | (0..N:1 on canceled)     | (0..N:1)
     v           v               v                                 v                          v
+----------+ +----------+ +------------------------------+ +------------------------------+ +-----------------------+
| payments | | reviews  | | commerceiq_shipment_         | | commerceiq_cancellations_    | | commerceiq_customer_  |
| (ORIG)   | | (ORIG)   | | tracking_logistics (SYNTH)   | | refunds (NEW SYNTH v2)       | | support_tickets       |
| 103,886  | | 99,224   | | PK: shipment_id (97,658)     | | PK: cancellation_id (706)    | | PK: ticket_id (17,201)|
+----------+ +----------+ | UK/FK: order_id              | | FK: order_id, order_item_id, | +-----------------------+
                          | FK: primary_seller_id        | |     product_id, seller_id,   |
                          +------------------------------+ |     customer_id              |
                                                           +------------------------------+
       | (1:N on order_id)
       v
+---------------------------------------------+         +---------------------------------------------+
|      olist_order_items_dataset (ORIG)       |-------->|     commerceiq_returns_refunds (SYNTH)      |
| PK: (order_id, order_item_id) (112,650 rows)| (0..1:1)| PK: return_id (7,616 rows — Delivered ONLY) |
| FK: product_id, seller_id                   |         | UK/FK: (order_id, order_item_id)            |
+--------------+-----------------------+------+         | FK: product_id, seller_id, customer_id      |
               |                       |                +---------------------------------------------+
               | (N:1 on product_id)   | (N:1 on seller_id)
               v                       v
+-----------------------------+ +-----------------------------+
| olist_products (ORIG)       | | olist_sellers (ORIG)        |
| PK: product_id (32,951)     | | PK: seller_id (3,095)       |
+--------------+--------------+ +--------------+--------------+
               |                               |
               | (1:1 on product_id)           | (1:N on seller_id)
               v                               v
+-----------------------------+ +---------------------------------------------+
| commerceiq_product_costs_   | |   commerceiq_inventory_snapshots (SYNTH)    |
| pricing (SYNTH)             |<| PK: inventory_record_id (137,792 rows)      |
| PK/FK: product_id (32,951)  | | UK/FK: (snapshot_date, seller_id, product_id)|
+-----------------------------+ +---------------------------------------------+
```

## 2. Complete Relational Mapping Table (`v2`)

| Child Table | Child Foreign Key(s) | Parent Table | Parent Key | Cardinality & Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `commerceiq_customer_acquisition_attribution.csv` | `customer_unique_id` | `olist_customers_dataset.csv` | `customer_unique_id` | `1:1` (`96,096` / `96,096` unique customers) |
| `commerceiq_customer_acquisition_attribution.csv` | `first_order_id` | `olist_orders_dataset.csv` | `order_id` | `1:1` (`96,096` earliest orders) |
| `commerceiq_customer_acquisition_attribution.csv` | `first_touch_campaign_id`, `last_touch_campaign_id` | `commerceiq_marketing_campaigns.csv` | `campaign_id` | `N:1` (`100%` of `96,096` rows) |
| `commerceiq_product_costs_pricing.csv` | `product_id` | `olist_products_dataset.csv` | `product_id` | `1:1` (`32,951` / `32,951` products) |
| `commerceiq_returns_refunds.csv` | `(order_id, order_item_id)` | `olist_order_items_dataset.csv` | `(order_id, order_item_id)` | `0..1:1` (`7,616` delivered items; `0` canceled orders) |
| `commerceiq_cancellations_refunds.csv` | `order_id`, `order_item_id` (nullable) | `olist_orders_dataset.csv` / `olist_order_items_dataset.csv` | `order_id` / `(order_id, order_item_id)` | `0..N:1` (`706` rows covering all `625` canceled orders) |
| `commerceiq_shipment_tracking_logistics.csv` | `order_id` | `olist_orders_dataset.csv` | `order_id` | `0..1:1` (`97,658` plausible shipments; excludes `1,783` unshipped/pre-ship canceled orders) |
| `commerceiq_shipment_tracking_logistics.csv` | `primary_seller_id` | `olist_sellers_dataset.csv` | `seller_id` | `N:1` (`100%` of `97,658` shipments) |
| `commerceiq_customer_sessions_funnel.csv` | `customer_unique_id`, `order_id` (nullable), `campaign_id` | `olist_customers_dataset.csv` / `olist_orders_dataset.csv` / `commerceiq_marketing_campaigns.csv` | `customer_unique_id` / `order_id` / `campaign_id` | `N:1` (`145,458` total sessions; `73,461` tracked `Order_Placed` sessions) |
| `commerceiq_inventory_snapshots.csv` | `(snapshot_date, seller_id, product_id)` | `olist_sellers_dataset.csv` & `olist_products_dataset.csv` | `seller_id`, `product_id` | `4:1` (`4` monthly snapshots x `34,448` active pairs = `137,792` rows) |
| `commerceiq_customer_support_tickets.csv` | `order_id`, `customer_unique_id` | `olist_orders_dataset.csv` / `olist_customers_dataset.csv` | `order_id` / `customer_unique_id` | `N:1` (`17,201` support tickets) |

## 3. Recommended Analytical Join Patterns (`v2`)

### Pattern A: Net Order-Item Contribution Margin (Separating Returns vs. Cancellations)
```python
item_econ = (
    items.merge(orders[["order_id", "customer_id", "order_status"]], on="order_id", how="inner")
    .merge(product_costs[["product_id", "product_category_english", "unit_cogs_brl", "packaging_handling_cost_brl", "olist_marketplace_commission_pct", "tax_icms_rate_pct"]], on="product_id", how="inner")
    .merge(logistics[["order_id", "fulfillment_state", "carrier_name", "actual_carrier_cost_brl", "freight_margin_brl", "is_late_delivery"]], on="order_id", how="left")
    .merge(returns[["order_id", "order_item_id", "refunded_amount_brl", "reverse_logistics_cost_brl"]].rename(columns={"refunded_amount_brl": "return_refund_brl"}), on=["order_id", "order_item_id"], how="left")
    .merge(cancellations[["order_id", "order_item_id", "refunded_amount_brl", "intercept_or_restocking_cost_brl"]].dropna(subset=["order_item_id"]).rename(columns={"refunded_amount_brl": "cancel_refund_brl"}), on=["order_id", "order_item_id"], how="left")
)
```

### Pattern B: Delivery Performance KPIs (Strictly Excluding Non-Delivered Shipments)
```python
delivered_shipments = logistics[logistics["fulfillment_state"] == "Delivered"].copy()
carrier_kpis = delivered_shipments.groupby("carrier_name", as_index=False).agg(
    delivered_orders=("shipment_id", "count"),
    late_rate=("is_late_delivery", "mean"),
    avg_variance_days=("delivery_variance_days", "mean"),
    avg_freight_margin_brl=("freight_margin_brl", "mean"),
)
```
