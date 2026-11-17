# CommerceIQ v2 — Original Olist Authenticity Audit & Synthetic Data Validation Report

## 1. Executive Audit Summary

All 9 uploaded CSV files were audited against the canonical [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) release (`olistbr/brazilian-ecommerce`, v2) and preserved without modification. Subsequently, **9 non-redundant synthetic tables** (`585,568` total synthetic records across 150 total columns) were built and validated via `validate_commerceiq_dataset.py` (`v2.0`).

* **Passed Validation Checks:** `46 / 46` (100% pass rate across original file SHA-256 preservation, v2 schema & composite key uniqueness, separation of returns vs. cancellations, plausible shipment eligibility, multi-session funnel behavior, 4-period stock accounting conservation, foreign-key referential integrity, and synthetic assumption verification).
* **Failed Validation Checks:** `0`
* **Baseline Warnings Documented:** `3` (all 3 are documented structural nuances inherent to the original public Olist dataset and are preserved untouched).

## 2. Original Olist Dataset Verification & Authenticity Audit

### 2.1 File Inventory, Row Counts, Primary Keys & SHA-256 Checksums

| Original File Name | Rows | Columns | Primary / Unique Key | Exact Duplicates | Verified SHA-256 Checksum | Status |
| :--- | ---: | ---: | :--- | ---: | :--- | :--- |
| `olist_customers_dataset.csv` | 99,441 | 5 | `customer_id` (96,096 unique `customer_unique_id`) | 0 | `983a422239e1712d...26883d2` | **VERIFIED** |
| `olist_orders_dataset.csv` | 99,441 | 8 | `order_id` | 0 | `8df58ef3d2d7e994...5ef9ecf` | **VERIFIED** |
| `olist_order_items_dataset.csv` | 112,650 | 7 | `(order_id, order_item_id)` | 0 | `0bc4d068c4fe38cb...1c3e279` | **VERIFIED** |
| `olist_order_payments_dataset.csv` | 103,886 | 5 | `(order_id, payment_sequential)` | 0 | `4f713964f2815dbb...6de3cc0` | **VERIFIED** |
| `olist_order_reviews_dataset.csv` | 99,224 | 7 | `(review_id, order_id)` (98,410 unique `review_id`) | 0 | `012b61c7593e34f5...fc797d7` | **VERIFIED** |
| `olist_products_dataset.csv` | 32,951 | 9 | `product_id` | 0 | `3e6569628a17fbc7...c58aa9cc` | **VERIFIED** |
| `olist_sellers_dataset.csv` | 3,095 | 4 | `seller_id` | 0 | `1f643d2b950373b8...0846a0e` | **VERIFIED** |
| `product_category_name_translation.csv` | 71 | 2 | `product_category_name` | 0 | `a81f0d1f27b27e72...8586278` | **VERIFIED** |
| `olist_geolocation_dataset.csv` | 1,000,163 | 5 | None (19,015 unique `geolocation_zip_code_prefix`) | 261,831 | `b514f6fc991b9566...66d88d6` | **VERIFIED** |

### 2.2 Documented Authenticity Limitations & Discrepancies in Original Olist Data

1. **Orders Missing Line Items (`WARN-01`):** Exactly `775` out of `99,441` orders in `olist_orders_dataset.csv` have no matching rows in `olist_order_items_dataset.csv` (`603` `unavailable`, `164` `canceled`, `5` `created`, `2` `invoiced`, `1` `shipped`), leaving `98,666` orders with itemized line records.
2. **Order Missing Payment Record (`WARN-02`):** Exactly `1` order (`bfbd0f9bdef84302105ad712db648a6c`) in `olist_orders_dataset.csv` has no record in `olist_order_payments_dataset.csv`, and `768` orders have no review in `olist_order_reviews_dataset.csv`.
3. **Multi-Order `review_id` Reuse (`WARN-03`):** `olist_order_reviews_dataset.csv` contains `99,224` rows but `98,410` unique `review_id` values (`814` rows share a `review_id` when a customer received a single survey email covering split orders). The composite key `(review_id, order_id)` is 100% unique (`99,224` rows).
4. **Untranslated Product Categories & Misspelled Column Names (`WARN-04`):** `olist_products_dataset.csv` has `610` products with null `product_category_name`, `2` products with null physical dimensions, and `2` categories (`pc_gamer` and `portateis_cozinha_e_preparadores_de_alimentos`) missing from `product_category_name_translation.csv`. Original column names `product_name_lenght` and `product_description_lenght` retain Olist's spelling typo.
5. **Geolocation Multiplicity & Coverage Gaps (`WARN-05`):** `olist_geolocation_dataset.csv` has `261,831` exact duplicate rows and multiple lat/lng points per postal prefix; additionally, `157` unique customer zip prefixes (`278` customer rows) and `7` seller zip prefixes are absent from `olist_geolocation_dataset.csv`.
6. **Payment vs. Item Sum Rounding / Voucher Variance (`WARN-06`):** Across the `98,665` orders present in both `order_items` and `order_payments`, `260` orders exhibit an absolute difference `> 0.05 BRL` between `SUM(price + freight_value)` and `SUM(payment_value)` due to installment interest or partial voucher adjustments.

## 3. CommerceIQ v2 Architectural Upgrades & Synthetic Assumptions

### 3.1 Summary of v2 Corrections
1. **Returns vs. Cancellations Separation:** `commerceiq_returns_refunds.csv` (`7,616` rows) now contains **exclusively post-delivery product returns** (`order_status == 'delivered'`), while `commerceiq_cancellations_refunds.csv` (`706` rows) captures all `625` canceled Olist orders (`542` item-level rows + `164` itemless order-level rows) capped by actual Olist `payment_value`.
2. **Plausible Shipment Eligibility & Fulfillment States:** `commerceiq_shipment_tracking_logistics.csv` (`97,658` rows) excludes `1,783` unshipped or pre-shipment canceled orders and partitions plausible shipments into `Delivered` (`96,470`), `In_Transit` (`1,113`), and `Cancelled_After_Shipment` (`75`), setting `actual_delivery_timestamp`, `delivery_variance_days`, and `is_late_delivery` to null on all non-delivered shipments.
3. **Multi-Session Customer Funnel & Conversion Realism:** `commerceiq_customer_sessions_funnel.csv` (`145,458` rows) removes the artificial `1:1` session-per-order lock—featuring `73,461` tracked `Order_Placed` sessions (`< 99,441` orders), `43,701` multi-session customers, `6,631` customers with zero converted sessions, and explicit separation between `order_placed` (`73,461`) and `order_delivered` (`71,237`).
4. **Multi-Period Historical Inventory Modeling (Option A):** `commerceiq_inventory_snapshots.csv` (`137,792` rows) models 4 monthly snapshots (`2018-07-01`, `2018-08-01`, `2018-09-01`, `2018-10-01`) across all `34,448` `(seller_id, product_id)` pairs with exact `opening_stock_units + stock_received_units - units_sold_in_period == closing_stock_units` conservation.
5. **Explicit Documentation of Synthetic Behavioural Assumptions:** Engineered correlations (`late delivery -> lower Olist reviews`, `low reviews -> higher returns`, `SLA breach -> lower CSAT`, `returns/cancellations -> support tickets`) are explicitly documented as **synthetic design assumptions**, not independent empirical findings.

## 4. Automated Validation Results (`validate_commerceiq_dataset.py` v2.0)

| Validation Category | Checks | Passed | Warnings | Failed | Verified Assertions |
| :--- | ---: | ---: | ---: | ---: | :--- |
| **Original Olist Preservation** | 9 | 9 | 0 | 0 | Exact SHA-256 checksums, row counts, and columns preserved across all 9 Olist files. |
| **Olist Baseline Audit** | 3 | 0 | 3 | 0 | Inherent Olist quirks documented (`775` itemless orders, `814` shared `review_id` rows, `2` untranslated categories). |
| **Schema, PK & Composite Uniqueness** | 12 | 12 | 0 | 0 | Exact `snake_case` schemas, zero duplicate PKs/composite keys, and 100% `is_synthetic = True` tagging across all 9 synthetic tables. |
| **Correction 1: Returns vs. Cancellations** | 3 | 3 | 0 | 0 | `0` canceled orders in `commerceiq_returns_refunds.csv` (`7,616` rows); all `625` canceled orders covered in `commerceiq_cancellations_refunds.csv` (`706` rows) within Olist payment caps. |
| **Correction 2: Shipment Eligibility** | 3 | 3 | 0 | 0 | `0` shipments for pre-shipment canceled or unshipped orders; delivery metrics restricted strictly to `96,470` `Delivered` orders (`1,188` non-delivered rows have null delivery metrics). |
| **Correction 3: Customer Sessions** | 2 | 2 | 0 | 0 | `145,458` sessions (`73,461` `Order_Placed` < `99,441` orders; `43,701` multi-session customers; `6,631` non-converting customers; `0` predated orders). |
| **Correction 4: Historical Inventory** | 1 | 1 | 0 | 0 | `4` monthly snapshots (`137,792` rows) with 100% exact stock flow conservation and inter-month continuity. |
| **Foreign-Key Referential Integrity** | 15 | 15 | 0 | 0 | 100% match across all parent Olist and CommerceIQ keys. |
| **Synthetic Behavioural Assumptions** | 1 | 1 | 0 | 0 | Verified calibrated synthetic assumption (`4.29` on-time vs. `2.57` late review score on delivered orders). |
| **Total** | **49** | **46** | **3** | **0** | **100% v2 Validation Pass Rate** |
