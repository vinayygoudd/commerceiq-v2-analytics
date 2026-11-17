# CommerceIQ v2 — Synthetic Dataset Data Dictionary

This data dictionary documents all **9 synthetic CSV tables** (`585,568` total records) in **CommerceIQ v2**, extending the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Every record carries `is_synthetic = True` and `data_source` (`CommerceIQ_Synthetic_v1` for preserved baseline tables or `CommerceIQ_Synthetic_v2` for upgraded/new v2 tables).

## Summary of Synthetic Tables (`v2`)

| File Name | Business Domain | Rows | Columns | Primary Key | Foreign Keys / Join Keys |
| :--- | :--- | ---: | ---: | :--- | :--- |
| `commerceiq_marketing_campaigns.csv` | Marketing Spend & Channel Attribution | 90 | 14 | `campaign_id` | Referenced by Acquisition & Sessions |
| `commerceiq_customer_acquisition_attribution.csv` | Customer Acquisition, CAC, Cohort & Churn Risk | 96,096 | 15 | `customer_unique_id` | `customer_unique_id`, `first_order_id`, `first_touch_campaign_id`, `last_touch_campaign_id` |
| `commerceiq_product_costs_pricing.csv` | Product COGS, MSRP, Commissions & Unit Economics | 32,951 | 13 | `product_id` | `product_id` (`olist_products_dataset.csv`) |
| `commerceiq_returns_refunds.csv` | Post-Delivery Product Returns & RMA Ledger | 7,616 | 17 | `return_id` | `(order_id, order_item_id)`, `product_id`, `seller_id`, `customer_id` |
| `commerceiq_cancellations_refunds.csv` | Pre- & Post-Shipment Order Cancellations & Refunds | 706 | 18 | `cancellation_id` | `order_id`, `order_item_id` (nullable), `product_id`, `seller_id`, `customer_id` |
| `commerceiq_shipment_tracking_logistics.csv` | Plausible Carrier Shipments, Freight Margin & Exceptions | 97,658 | 21 | `shipment_id` | `order_id` (Unique), `primary_seller_id` |
| `commerceiq_customer_sessions_funnel.csv` | Multi-Session Browsing Funnel & Order Placement | 145,458 | 18 | `session_id` | `customer_unique_id`, `order_id` (nullable), `campaign_id` |
| `commerceiq_inventory_snapshots.csv` | Multi-Period Historical Warehouse Stock Movement | 137,792 | 19 | `inventory_record_id` | `(snapshot_date, seller_id, product_id)` (Composite Unique) |
| `commerceiq_customer_support_tickets.csv` | Omnichannel Support SLAs & CSAT Scores | 17,201 | 15 | `ticket_id` | `order_id`, `customer_unique_id` |

## 1. `commerceiq_marketing_campaigns.csv` (90 rows, 14 columns)
Quarterly performance marketing, CRM, affiliate, and organic campaigns across `2016-09-01` to `2018-10-31`.

| Column Name | Data Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `campaign_id` | `string` | No | **PK** | Unique campaign identifier (e.g., `CMP-2017Q4-046`). |
| `campaign_name` | `string` | No | Unique | Descriptive label combining quarter, ad platform, and audience segment. |
| `marketing_channel` | `string` | No | Categorical | Channel (`Paid Search`, `Paid Social`, `Affiliate`, `CRM / Email`, `Price Comparison`, `Display / Retargeting`, `Influencer / Content`, `Organic / SEO`). |
| `ad_platform` | `string` | No | Categorical | Executing ad network (`Google Ads`, `Meta Ads`, `Instagram Shopping`, `Awin Brazil`, `RD Station`, `Buscape / Zoom`, `Criteo`, `YouTube Creators BR`, `Organic Search`). |
| `cost_model` | `string` | No | Categorical | Billing mechanism (`CPC`, `CPM`, `CPA`, `Fixed`, `Organic`). |
| `target_audience_segment` | `string` | No | Categorical | Target buyer cohort. |
| `start_date` | `string (YYYY-MM-DD)` | No | `<= end_date` | Campaign start date. |
| `end_date` | `string (YYYY-MM-DD)` | No | `>= start_date` | Campaign end date. |
| `planned_budget_brl` | `float64` | No | `>= 0.0` | Allocated budget in BRL (`0.0` for organic). |
| `actual_spend_brl` | `float64` | No | `<= planned_budget_brl` | Realized media spend in BRL reconciled with attributed CAC. |
| `impressions` | `int64` | No | `> 0` | Total ad or organic search impressions delivered. |
| `clicks` | `int64` | No | `<= impressions` | Total clicks generated. |
| `is_synthetic` | `bool` | No | Always `True` | Synthetic provenance indicator. |
| `data_source` | `string` | No | Constant | `'CommerceIQ_Synthetic_v1'`. |

## 2. `commerceiq_customer_acquisition_attribution.csv` (96,096 rows, 15 columns)
Customer-level attribution, Customer Acquisition Cost (CAC), loyalty tier, and churn risk (`1:1` on `customer_unique_id`).

| Column Name | Data Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `customer_unique_id` | `string` | No | **PK**, **FK** | References `olist_customers_dataset.customer_unique_id`. |
| `first_order_id` | `string` | No | **FK** | Chronologically earliest `order_id` placed by this customer. |
| `acquisition_timestamp` | `string (datetime)` | No | `<= first_order_timestamp` | Timestamp of first customer acquisition touchpoint within campaign window. |
| `first_order_timestamp` | `string (datetime)` | No | Matches Olist | Exact `order_purchase_timestamp` of first order. |
| `first_touch_campaign_id` | `string` | No | **FK** | Initial discovery campaign (`commerceiq_marketing_campaigns.campaign_id`). |
| `last_touch_campaign_id` | `string` | No | **FK** | Converting campaign (`commerceiq_marketing_campaigns.campaign_id`). |
| `acquisition_channel` | `string` | No | Categorical | Marketing channel of `last_touch_campaign_id`. |
| `primary_device_type` | `string` | No | Categorical | Primary device (`Mobile Web`, `Desktop Web`, `Android App`, `iOS App`). |
| `customer_acquisition_cost_brl` | `float64` | No | `>= 0.0` | Attributed CAC in BRL (`0.0` for `Organic / SEO`). |
| `lifetime_orders_count` | `int64` | No | `>= 1` | Total historical orders placed by this `customer_unique_id`. |
| `loyalty_tier` | `string` | No | Categorical | `Standard` (1 order), `Silver` (2 orders), or `Gold` (3+ orders). |
| `marketing_email_opt_in` | `bool` | No | Boolean | Lifecycle email consent flag. |
| `predicted_churn_probability` | `float64` | No | `[0.0, 1.0]` | Modeled 12-month churn probability. |
| `is_synthetic` | `bool` | No | Always `True` | Synthetic provenance indicator. |
| `data_source` | `string` | No | Constant | `'CommerceIQ_Synthetic_v1'`. |

## 3. `commerceiq_product_costs_pricing.csv` (32,951 rows, 13 columns)
Unit cost economics, MSRP, marketplace commission rates, and ICMS tax rates (`1:1` on `product_id`).

| Column Name | Data Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `product_id` | `string` | No | **PK**, **FK** | References `olist_products_dataset.product_id`. |
| `product_category_english` | `string` | No | Non-null | English category name (including `gaming_pc` and `kitchen_portables_and_food_preparers`). |
| `msrp_list_price_brl` | `float64` | No | `>= max_historical_price` | Manufacturer Suggested Retail Price in BRL. |
| `min_historical_selling_price_brl` | `float64` | No | Matches Olist | Minimum observed item `price` in Olist. |
| `median_historical_selling_price_brl` | `float64` | No | Matches Olist | Median observed item `price` in Olist. |
| `max_historical_selling_price_brl` | `float64` | No | Matches Olist | Maximum observed item `price` in Olist. |
| `unit_cogs_brl` | `float64` | No | `<= min_historical_price` | Unit Cost of Goods Sold (COGS) in BRL. |
| `packaging_handling_cost_brl` | `float64` | No | `>= 1.20` | Fulfillment packaging & handling cost per unit in BRL. |
| `olist_marketplace_commission_pct` | `float64` | No | `[0.10, 0.17]` | Marketplace commission take-rate fraction. |
| `max_allowed_discount_pct` | `float64` | No | `[0.0, 1.0)` | Maximum promotional discount vs. MSRP. |
| `tax_icms_rate_pct` | `float64` | No | `{0.07, 0.12, 0.17, 0.18}` | Applicable Brazilian ICMS state VAT rate. |
| `is_synthetic` | `bool` | No | Always `True` | Synthetic provenance indicator. |
| `data_source` | `string` | No | Constant | `'CommerceIQ_Synthetic_v1'`. |

## 4. `commerceiq_returns_refunds.csv` (7,616 rows, 17 columns — Upgraded in v2)
Tracks post-delivery product returns (RMAs) strictly for **delivered** order items (`order_status == 'delivered'`). Zero canceled orders appear in this table.

| Column Name | Data Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `return_id` | `string` | No | **PK** | Unique RMA identifier (`RMA-000001` to `RMA-007616`). |
| `order_id` | `string` | No | **FK**, Composite Unique | References `olist_order_items_dataset.order_id` (delivered orders only). |
| `order_item_id` | `int64` | No | **FK**, Composite Unique | References `olist_order_items_dataset.order_item_id`. |
| `product_id` | `string` | No | **FK** | References `olist_products_dataset.product_id`. |
| `seller_id` | `string` | No | **FK** | References `olist_sellers_dataset.seller_id`. |
| `customer_id` | `string` | No | **FK** | References `olist_customers_dataset.customer_id`. |
| `return_request_timestamp` | `string (datetime)` | No | `> delivered_customer_date` | Timestamp when customer initiated post-delivery RMA. |
| `refund_processed_timestamp` | `string (datetime)` | No | `>= return_request_timestamp` | Timestamp when return resolution was settled. |
| `return_reason` | `string` | No | Categorical | `Defective_or_Damaged_Item`, `Wrong_Item_Sent`, `Not_As_Described`, `Late_Delivery_Regret`, `Buyer_Remorse_7Day_CDC`. |
| `resolution_outcome` | `string` | No | Categorical | `Full_Refund`, `Partial_Refund_Keep_Item`, `Exchange_Replacement`, `Rejected_Policy_Violation`. |
| `item_inspection_disposition` | `string` | No | Categorical | `Restocked_Sellable`, `Damaged_WriteOff`, `Retained_by_Customer`. |
| `original_item_price_brl` | `float64` | No | Matches Olist | Exact `price` from `olist_order_items_dataset.csv`. |
| `original_freight_value_brl` | `float64` | No | Matches Olist | Exact `freight_value` from `olist_order_items_dataset.csv`. |
| `refunded_amount_brl` | `float64` | No | `<= price + freight` | Total BRL refunded to customer (`0.0` for exchanges or rejected claims). |
| `reverse_logistics_cost_brl` | `float64` | No | `>= 0.0` | Return shipping cost incurred in BRL. |
| `is_synthetic` | `bool` | No | Always `True` | Synthetic provenance indicator. |
| `data_source` | `string` | No | Constant | `'CommerceIQ_Synthetic_v2'`. |

## 5. `commerceiq_cancellations_refunds.csv` (706 rows, 18 columns — New in v2)
Dedicated cancellation and refund ledger covering all `625` canceled orders in `olist_orders_dataset.csv` (`461` itemized canceled orders yielding `542` item-level rows + `164` order-level canceled orders without rows in `olist_order_items_dataset.csv`).

| Column Name | Data Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `cancellation_id` | `string` | No | **PK** | Unique cancellation identifier (`CXL-000001` to `CXL-000706`). |
| `order_id` | `string` | No | **FK** | References `olist_orders_dataset.order_id` (`order_status == 'canceled'`). |
| `order_item_id` | `Int64` | Yes | **FK** (when itemized) | References `olist_order_items_dataset.order_item_id`; `<NA>` for the `164` order-level cancellations without line items. |
| `product_id` | `string` | Yes | **FK** (when itemized) | References `olist_products_dataset.product_id`; null when `order_item_id` is null. |
| `seller_id` | `string` | Yes | **FK** (when itemized) | References `olist_sellers_dataset.seller_id`; null when `order_item_id` is null. |
| `customer_id` | `string` | No | **FK** | References `olist_customers_dataset.customer_id`. |
| `cancellation_stage` | `string` | No | Categorical | `Cancelled_Before_Shipment` (`621` rows) or `Cancelled_After_Shipment` (`85` rows). |
| `cancellation_reason` | `string` | No | Categorical | Root-cause reason (`Customer_Changed_Mind_Pre_Ship`, `Seller_Out_Of_Stock_Cancel`, `SLA_Dispatch_Timeout`, `Payment_Gateway_Timeout`, `Customer_Refused_Delivery`, `Carrier_Transit_Loss_Damage`, etc.). |
| `cancellation_timestamp` | `string (datetime)` | No | `>= purchase_timestamp` | Timestamp when order cancellation was triggered. |
| `refund_processed_timestamp` | `string (datetime)` | No | `>= cancellation_timestamp` | Timestamp when cancellation refund was processed. |
| `original_item_price_brl` | `float64` | Yes | Matches Olist | Item `price` (null for itemless order-level cancellations). |
| `original_freight_value_brl` | `float64` | Yes | Matches Olist | Item `freight_value` (null for itemless order-level cancellations). |
| `eligible_payment_brl` | `float64` | No | Reconciled to Payments | Maximum refundable amount capped by actual captured `payment_value` in `olist_order_payments_dataset.csv`. |
| `refunded_amount_brl` | `float64` | No | `<= eligible_payment_brl` | Actual BRL refunded to customer (`100%` of eligible payment pre-shipment; `85%–100%` post-shipment). |
| `intercept_or_restocking_cost_brl` | `float64` | No | `>= 0.0` | Carrier intercept/return fee (`0.0` for pre-shipment cancellations). |
| `refund_status` | `string` | No | Categorical | `Refunded_To_Original_Payment` or `No_Payment_Captured`. |
| `is_synthetic` | `bool` | No | Always `True` | Synthetic provenance indicator. |
| `data_source` | `string` | No | Constant | `'CommerceIQ_Synthetic_v2'`. |

## 6. `commerceiq_shipment_tracking_logistics.csv` (97,658 rows, 21 columns — Upgraded in v2)
Contains **only plausible shipments** (orders handed off to a carrier or having valid delivery confirmation), excluding `1,783` unshipped or pre-shipment canceled orders. Delivery timestamps and delivery variance metrics are populated **strictly** for `Delivered` orders (`96,470` rows) and set to null (`NaN`) for `In_Transit` (`1,113` rows) and `Cancelled_After_Shipment` (`75` rows).

| Column Name | Data Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `shipment_id` | `string` | No | **PK** | Unique shipment identifier (`SHP-000001` to `SHP-097658`). |
| `order_id` | `string` | No | **FK**, Unique | References `olist_orders_dataset.order_id`. |
| `primary_seller_id` | `string` | No | **FK** | References `olist_sellers_dataset.seller_id`. |
| `fulfillment_state` | `string` | No | Categorical | `Delivered` (`96,470`), `In_Transit` (`1,113`), or `Cancelled_After_Shipment` (`75`). |
| `origin_state` | `string` | No | State Code | Seller origin Brazilian state. |
| `destination_state` | `string` | No | State Code | Customer destination Brazilian state. |
| `is_interstate_shipment` | `bool` | No | `origin != destination` | `True` for cross-state shipments. |
| `carrier_name` | `string` | No | Categorical | `Correios PAC`, `Correios SEDEX`, `Jadlog`, `Total Express`, `Azul Cargo Express`, `Loggi`. |
| `service_tier` | `string` | No | Categorical | `Standard` or `Express`. |
| `customer_freight_charged_brl` | `float64` | No | Matches Olist | Sum of `freight_value` on the order. |
| `actual_carrier_cost_brl` | `float64` | No | `>= 6.50` | Actual carrier invoice cost in BRL. |
| `freight_margin_brl` | `float64` | No | `charged - actual_cost` | Net shipping margin (`customer_freight_charged_brl - actual_carrier_cost_brl`). |
| `carrier_handoff_timestamp` | `string (datetime)` | Yes | Matches Olist | Mirrors `order_delivered_carrier_date`. |
| `actual_delivery_timestamp` | `string (datetime)` | Yes | Populated iff `Delivered` | Mirrors `order_delivered_customer_date` (`NaN` for `In_Transit` and `Cancelled_After_Shipment`). |
| `estimated_delivery_date` | `string (YYYY-MM-DD)` | No | Matches Olist | Mirrors `order_estimated_delivery_date`. |
| `delivery_variance_days` | `float64` | Yes | Populated iff `Delivered` | Signed days vs. estimated delivery (`NaN` for non-delivered shipments). |
| `is_late_delivery` | `boolean` | Yes | Populated iff `Delivered` | `True`/`False` for `Delivered` orders; `<NA>` for non-delivered shipments. |
| `delivery_attempts_count` | `int64` | No | `0` if non-delivered | Number of delivery attempts (`0` for `In_Transit` and `Cancelled_After_Shipment`). |
| `delivery_exception_code` | `string` | No | Categorical | `None_On_Time`, `Hub_Congestion_Delay`, `Weather_Route_Delay`, `Recipient_Absent_Retry`, `Customs_State_Border_Hold`, `Active_In_Transit_Awaiting_Delivery`, `Cancelled_After_Carrier_Handoff`. |
| `is_synthetic` | `bool` | No | Always `True` | Synthetic provenance indicator. |
| `data_source` | `string` | No | Constant | `'CommerceIQ_Synthetic_v2'`. |

## 7. `commerceiq_customer_sessions_funnel.csv` (145,458 rows, 18 columns — Upgraded in v2)
Models realistic multi-session customer journeys without forcing a `1:1` session-per-order relationship:
* `73,461` tracked converting sessions (`order_placed == True`, `funnel_exit_stage == 'Order_Placed'`), while `25,980` Olist orders occurred via direct/partner checkout without a web funnel session.
* `43,701` customers have multiple sessions (pre-purchase research, cart abandonment, and repeat visits), and `6,631` customers have browsing/abandonment sessions with zero converted web sessions.
* Separates **order placement** (`order_placed`) from **physical delivery** (`order_delivered`).

| Column Name | Data Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `session_id` | `string` | No | **PK** | Unique session ID (`SES-ORD-...`, `SES-PRE-...`, `SES-BRW-...`). |
| `customer_unique_id` | `string` | No | **FK** | References `olist_customers_dataset.customer_unique_id`. |
| `order_id` | `string` | Yes | **FK** (iff `order_placed`) | References `olist_orders_dataset.order_id` when `order_placed == True`; `NaN` otherwise. |
| `campaign_id` | `string` | No | **FK** | Attributed campaign active during session (`commerceiq_marketing_campaigns.campaign_id`). |
| `session_start_timestamp` | `string (datetime)` | No | `>= acquisition_timestamp` | Session start timestamp. |
| `session_end_timestamp` | `string (datetime)` | No | `<= order_purchase_timestamp` | Session end timestamp (equals `order_purchase_timestamp` when `order_placed == True`). |
| `session_duration_seconds` | `int64` | No | `> 0` | Elapsed session duration in seconds. |
| `device_type` | `string` | No | Categorical | `Mobile Web`, `Desktop Web`, `Android App`, `iOS App`. |
| `product_viewed` | `bool` | No | Funnel Step 1 | `True` if at least one product page was viewed. |
| `page_views` | `int64` | No | `>= 1` | Total page views in session. |
| `products_viewed` | `int64` | No | `>= 0` | Distinct product detail views in session. |
| `added_to_cart` | `bool` | No | Funnel Step 2 | `True` if item added to cart (requires `product_viewed`). |
| `checkout_initiated` | `bool` | No | Funnel Step 3 | `True` if checkout started (requires `added_to_cart`). |
| `order_placed` | `bool` | No | Funnel Step 4 | `True` if order was submitted (`funnel_exit_stage == 'Order_Placed'`). |
| `order_delivered` | `bool` | No | Post-Order Outcome | `True` only when `order_placed == True` AND the linked Olist order achieved confirmed delivery (`71,237` rows). |
| `funnel_exit_stage` | `string` | No | Categorical | `Bounce_Landing`, `Product_Browse_Exit`, `Cart_Abandonment`, `Checkout_Dropoff`, `Order_Placed`. |
| `is_synthetic` | `bool` | No | Always `True` | Synthetic provenance indicator. |
| `data_source` | `string` | No | Constant | `'CommerceIQ_Synthetic_v2'`. |

## 8. `commerceiq_inventory_snapshots.csv` (137,792 rows, 19 columns — Upgraded Option A in v2)
Historical monthly warehouse inventory ledger spanning **4 monthly snapshots** (`2018-07-01`, `2018-08-01`, `2018-09-01`, `2018-10-01`) across all `34,448` active `(seller_id, product_id)` pairs with exact stock accounting conservation (`opening_stock_units + stock_received_units - units_sold_in_period == closing_stock_units`).

| Column Name | Data Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `inventory_record_id` | `string` | No | **PK** | Unique snapshot row ID (`INV-000001` to `INV-137792`). |
| `snapshot_date` | `string (YYYY-MM-DD)` | No | Composite Unique | Monthly checkpoint date (`2018-07-01`, `2018-08-01`, `2018-09-01`, `2018-10-01`). |
| `seller_id` | `string` | No | **FK**, Composite Unique | References `olist_sellers_dataset.seller_id`. |
| `product_id` | `string` | No | **FK**, Composite Unique | References `olist_products_dataset.product_id`. |
| `warehouse_region_state` | `string` | No | State Code | Seller fulfillment warehouse state. |
| `opening_stock_units` | `int64` | No | `== prev closing_stock` | Beginning physical stock at start of period. |
| `stock_received_units` | `int64` | No | `>= 0` | Replenishment units received during period. |
| `units_sold_in_period` | `int64` | No | Driven by Olist sales | Units fulfilled in the preceding calendar month (`2018-06` through `2018-09`). |
| `closing_stock_units` | `int64` | No | `opening + received - sold` | Ending physical stock at snapshot date. |
| `reserved_quantity` | `int64` | No | `<= closing_stock_units` | Units committed to pending orders. |
| `available_quantity` | `int64` | No | `closing - reserved >= 0` | Net sellable units available. |
| `safety_stock_units` | `int64` | No | `>= 2` | Buffer stock threshold. |
| `reorder_point_units` | `int64` | No | `> safety_stock_units` | Replenishment trigger threshold. |
| `supplier_lead_time_days` | `int64` | No | `[3, 24]` | Supplier restock lead time in days. |
| `stockout_occurred` | `bool` | No | Boolean | `True` if closing stock hit `0` or period demand exceeded available supply. |
| `inventory_valuation_cogs_brl` | `float64` | No | `closing * unit_cogs` | Ending inventory book value at unit COGS in BRL. |
| `stock_health_status` | `string` | No | Categorical | `Healthy_In_Stock`, `Low_Stock_Reorder`, or `Out_of_Stock`. |
| `is_synthetic` | `bool` | No | Always `True` | Synthetic provenance indicator. |
| `data_source` | `string` | No | Constant | `'CommerceIQ_Synthetic_v2'`. |

## 9. `commerceiq_customer_support_tickets.csv` (17,201 rows, 15 columns — Synchronized in v2)
Omnichannel customer support inquiries synchronized with separated product returns (`Product_Return_RMA_Inquiry`) and order cancellations (`Order_Cancellation_Refund_Inquiry`).

| Column Name | Data Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `ticket_id` | `string` | No | **PK** | Unique ticket identifier (`TKT-000001` to `TKT-017201`). |
| `order_id` | `string` | No | **FK** | References `olist_orders_dataset.order_id`. |
| `customer_unique_id` | `string` | No | **FK** | References `olist_customers_dataset.customer_unique_id`. |
| `ticket_channel` | `string` | No | Categorical | `Web_Help_Center`, `Email`, `WhatsApp_Bot`, `Phone_Support`, `Marketplace_Chat`. |
| `issue_category` | `string` | No | Categorical | `Order_Cancellation_Refund_Inquiry`, `Product_Return_RMA_Inquiry`, `Where_Is_My_Order_WISMO`, `Product_Quality_or_Defect`, `Payment_or_Boleto_Issue`, `Address_or_Invoice_Change`, `Seller_Communication_Delay`. |
| `priority_level` | `string` | No | Categorical | `Low`, `Medium`, `High`, `Urgent`. |
| `ticket_created_timestamp` | `string (datetime)` | No | `>= purchase_timestamp` | Ticket creation timestamp (strictly `< actual_delivery_timestamp` for WISMO tickets). |
| `ticket_resolved_timestamp` | `string (datetime)` | No | `>= created_timestamp` | Ticket resolution timestamp. |
| `first_response_time_minutes` | `int64` | No | `[2, 720]` | Minutes elapsed before first agent/bot response. |
| `resolution_time_hours` | `float64` | No | `[0.5, 120.0]` | Total hours to resolution. |
| `sla_breached` | `bool` | No | `resolution_hours > 48` | `True` if resolution exceeded 48-hour SLA (`12.4%` breach rate). |
| `agent_interactions_count` | `int64` | No | `[1, 6]` | Number of support interactions. |
| `post_ticket_csat_score` | `int64` | No | `[1, 5]` | Post-resolution CSAT survey score (`1` to `5`). |
| `is_synthetic` | `bool` | No | Always `True` | Synthetic provenance indicator. |
| `data_source` | `string` | No | Constant | `'CommerceIQ_Synthetic_v2'`. |
