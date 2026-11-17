-- ============================================================================
-- CommerceIQ v2 — PostgreSQL 15+ Production Warehouse Schema (18 Tables)
-- ============================================================================
-- Preserves all 9 original Olist tables untouched and integrates the 9
-- CommerceIQ v2 synthetic tables with strict PK, FK, and CHECK constraints.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS commerceiq;
SET search_path TO commerceiq, public;

-- ----------------------------------------------------------------------------
-- PART A: ORIGINAL OLIST TABLES (9 TABLES — PRESERVED UNCHANGED)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS olist_customers_dataset (
    customer_id VARCHAR(32) PRIMARY KEY,
    customer_unique_id VARCHAR(32) NOT NULL,
    customer_zip_code_prefix INTEGER NOT NULL,
    customer_city VARCHAR(100) NOT NULL,
    customer_state CHAR(2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_olist_cust_unique ON olist_customers_dataset(customer_unique_id);

CREATE TABLE IF NOT EXISTS olist_geolocation_dataset (
    geolocation_zip_code_prefix INTEGER NOT NULL,
    geolocation_lat DOUBLE PRECISION NOT NULL,
    geolocation_lng DOUBLE PRECISION NOT NULL,
    geolocation_city VARCHAR(100) NOT NULL,
    geolocation_state CHAR(2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_olist_geo_zip ON olist_geolocation_dataset(geolocation_zip_code_prefix);

CREATE TABLE IF NOT EXISTS olist_sellers_dataset (
    seller_id VARCHAR(32) PRIMARY KEY,
    seller_zip_code_prefix INTEGER NOT NULL,
    seller_city VARCHAR(100) NOT NULL,
    seller_state CHAR(2) NOT NULL
);

CREATE TABLE IF NOT EXISTS product_category_name_translation (
    product_category_name VARCHAR(100) PRIMARY KEY,
    product_category_name_english VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS olist_products_dataset (
    product_id VARCHAR(32) PRIMARY KEY,
    product_category_name VARCHAR(100),
    product_name_lenght DOUBLE PRECISION,
    product_description_lenght DOUBLE PRECISION,
    product_photos_qty DOUBLE PRECISION,
    product_weight_g DOUBLE PRECISION,
    product_length_cm DOUBLE PRECISION,
    product_height_cm DOUBLE PRECISION,
    product_width_cm DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS olist_orders_dataset (
    order_id VARCHAR(32) PRIMARY KEY,
    customer_id VARCHAR(32) NOT NULL REFERENCES olist_customers_dataset(customer_id),
    order_status VARCHAR(30) NOT NULL,
    order_purchase_timestamp TIMESTAMP NOT NULL,
    order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_olist_orders_cust ON olist_orders_dataset(customer_id);
CREATE INDEX IF NOT EXISTS idx_olist_orders_purchase ON olist_orders_dataset(order_purchase_timestamp);

CREATE TABLE IF NOT EXISTS olist_order_items_dataset (
    order_id VARCHAR(32) NOT NULL REFERENCES olist_orders_dataset(order_id),
    order_item_id INTEGER NOT NULL,
    product_id VARCHAR(32) NOT NULL REFERENCES olist_products_dataset(product_id),
    seller_id VARCHAR(32) NOT NULL REFERENCES olist_sellers_dataset(seller_id),
    shipping_limit_date TIMESTAMP NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    freight_value NUMERIC(12,2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS olist_order_payments_dataset (
    order_id VARCHAR(32) NOT NULL REFERENCES olist_orders_dataset(order_id),
    payment_sequential INTEGER NOT NULL,
    payment_type VARCHAR(30) NOT NULL,
    payment_installments INTEGER NOT NULL,
    payment_value NUMERIC(12,2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE IF NOT EXISTS olist_order_reviews_dataset (
    review_id VARCHAR(32) NOT NULL,
    order_id VARCHAR(32) NOT NULL REFERENCES olist_orders_dataset(order_id),
    review_score INTEGER NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TIMESTAMP NOT NULL,
    review_answer_timestamp TIMESTAMP,
    PRIMARY KEY (review_id, order_id)
);

-- ----------------------------------------------------------------------------
-- PART B: SYNTHETIC COMMERCEIQ v2 TABLES (9 TABLES — EXPLICITLY TAGGED)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS commerceiq_marketing_campaigns (
    campaign_id VARCHAR(32) PRIMARY KEY,
    campaign_name VARCHAR(150) NOT NULL,
    marketing_channel VARCHAR(50) NOT NULL,
    ad_platform VARCHAR(50) NOT NULL,
    cost_model VARCHAR(20) NOT NULL,
    target_audience_segment VARCHAR(80) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL CHECK (end_date >= start_date),
    planned_budget_brl NUMERIC(12,2) NOT NULL CHECK (planned_budget_brl >= 0),
    actual_spend_brl NUMERIC(12,2) NOT NULL CHECK (actual_spend_brl >= 0 AND actual_spend_brl <= planned_budget_brl + 0.01),
    impressions BIGINT NOT NULL CHECK (impressions > 0),
    clicks BIGINT NOT NULL CHECK (clicks <= impressions),
    is_synthetic BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_synthetic = TRUE),
    data_source VARCHAR(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS commerceiq_customer_acquisition_attribution (
    customer_unique_id VARCHAR(32) PRIMARY KEY,
    first_order_id VARCHAR(32) NOT NULL REFERENCES olist_orders_dataset(order_id),
    acquisition_timestamp TIMESTAMP NOT NULL,
    first_order_timestamp TIMESTAMP NOT NULL CHECK (first_order_timestamp >= acquisition_timestamp),
    first_touch_campaign_id VARCHAR(32) NOT NULL REFERENCES commerceiq_marketing_campaigns(campaign_id),
    last_touch_campaign_id VARCHAR(32) NOT NULL REFERENCES commerceiq_marketing_campaigns(campaign_id),
    acquisition_channel VARCHAR(50) NOT NULL,
    primary_device_type VARCHAR(30) NOT NULL,
    customer_acquisition_cost_brl NUMERIC(10,2) NOT NULL CHECK (customer_acquisition_cost_brl >= 0),
    lifetime_orders_count INTEGER NOT NULL CHECK (lifetime_orders_count >= 1),
    loyalty_tier VARCHAR(20) NOT NULL,
    marketing_email_opt_in BOOLEAN NOT NULL,
    predicted_churn_probability NUMERIC(6,4) NOT NULL CHECK (predicted_churn_probability BETWEEN 0 AND 1),
    is_synthetic BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_synthetic = TRUE),
    data_source VARCHAR(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS commerceiq_product_costs_pricing (
    product_id VARCHAR(32) PRIMARY KEY REFERENCES olist_products_dataset(product_id),
    product_category_english VARCHAR(100) NOT NULL,
    msrp_list_price_brl NUMERIC(12,2) NOT NULL,
    min_historical_selling_price_brl NUMERIC(12,2) NOT NULL,
    median_historical_selling_price_brl NUMERIC(12,2) NOT NULL,
    max_historical_selling_price_brl NUMERIC(12,2) NOT NULL,
    unit_cogs_brl NUMERIC(12,2) NOT NULL CHECK (unit_cogs_brl > 0 AND unit_cogs_brl <= min_historical_selling_price_brl),
    packaging_handling_cost_brl NUMERIC(10,2) NOT NULL,
    olist_marketplace_commission_pct NUMERIC(6,4) NOT NULL,
    max_allowed_discount_pct NUMERIC(6,4) NOT NULL,
    tax_icms_rate_pct NUMERIC(6,4) NOT NULL,
    is_synthetic BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_synthetic = TRUE),
    data_source VARCHAR(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS commerceiq_returns_refunds (
    return_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL,
    order_item_id INTEGER NOT NULL,
    product_id VARCHAR(32) NOT NULL REFERENCES olist_products_dataset(product_id),
    seller_id VARCHAR(32) NOT NULL REFERENCES olist_sellers_dataset(seller_id),
    customer_id VARCHAR(32) NOT NULL REFERENCES olist_customers_dataset(customer_id),
    return_request_timestamp TIMESTAMP NOT NULL,
    refund_processed_timestamp TIMESTAMP NOT NULL CHECK (refund_processed_timestamp >= return_request_timestamp),
    return_reason VARCHAR(60) NOT NULL,
    resolution_outcome VARCHAR(40) NOT NULL,
    item_inspection_disposition VARCHAR(40) NOT NULL,
    original_item_price_brl NUMERIC(12,2) NOT NULL,
    original_freight_value_brl NUMERIC(12,2) NOT NULL,
    refunded_amount_brl NUMERIC(12,2) NOT NULL CHECK (refunded_amount_brl >= 0),
    reverse_logistics_cost_brl NUMERIC(10,2) NOT NULL CHECK (reverse_logistics_cost_brl >= 0),
    is_synthetic BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_synthetic = TRUE),
    data_source VARCHAR(40) NOT NULL,
    UNIQUE (order_id, order_item_id),
    FOREIGN KEY (order_id, order_item_id) REFERENCES olist_order_items_dataset(order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS commerceiq_cancellations_refunds (
    cancellation_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL REFERENCES olist_orders_dataset(order_id),
    order_item_id INTEGER,
    product_id VARCHAR(32) REFERENCES olist_products_dataset(product_id),
    seller_id VARCHAR(32) REFERENCES olist_sellers_dataset(seller_id),
    customer_id VARCHAR(32) NOT NULL REFERENCES olist_customers_dataset(customer_id),
    cancellation_stage VARCHAR(40) NOT NULL,
    cancellation_reason VARCHAR(60) NOT NULL,
    cancellation_timestamp TIMESTAMP NOT NULL,
    refund_processed_timestamp TIMESTAMP NOT NULL CHECK (refund_processed_timestamp >= cancellation_timestamp),
    original_item_price_brl NUMERIC(12,2),
    original_freight_value_brl NUMERIC(12,2),
    eligible_payment_brl NUMERIC(12,2) NOT NULL CHECK (eligible_payment_brl >= 0),
    refunded_amount_brl NUMERIC(12,2) NOT NULL CHECK (refunded_amount_brl >= 0 AND refunded_amount_brl <= eligible_payment_brl + 0.01),
    intercept_or_restocking_cost_brl NUMERIC(10,2) NOT NULL CHECK (intercept_or_restocking_cost_brl >= 0),
    refund_status VARCHAR(40) NOT NULL,
    is_synthetic BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_synthetic = TRUE),
    data_source VARCHAR(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS commerceiq_shipment_tracking_logistics (
    shipment_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL UNIQUE REFERENCES olist_orders_dataset(order_id),
    primary_seller_id VARCHAR(32) NOT NULL REFERENCES olist_sellers_dataset(seller_id),
    fulfillment_state VARCHAR(40) NOT NULL,
    origin_state CHAR(2) NOT NULL,
    destination_state CHAR(2) NOT NULL,
    is_interstate_shipment BOOLEAN NOT NULL,
    carrier_name VARCHAR(50) NOT NULL,
    service_tier VARCHAR(20) NOT NULL,
    customer_freight_charged_brl NUMERIC(12,2) NOT NULL,
    actual_carrier_cost_brl NUMERIC(12,2) NOT NULL,
    freight_margin_brl NUMERIC(12,2) NOT NULL,
    carrier_handoff_timestamp TIMESTAMP,
    actual_delivery_timestamp TIMESTAMP,
    estimated_delivery_date DATE NOT NULL,
    delivery_variance_days NUMERIC(8,2),
    is_late_delivery BOOLEAN,
    delivery_attempts_count INTEGER NOT NULL,
    delivery_exception_code VARCHAR(60) NOT NULL,
    is_synthetic BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_synthetic = TRUE),
    data_source VARCHAR(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS commerceiq_customer_sessions_funnel (
    session_id VARCHAR(32) PRIMARY KEY,
    customer_unique_id VARCHAR(32) NOT NULL,
    order_id VARCHAR(32) REFERENCES olist_orders_dataset(order_id),
    campaign_id VARCHAR(32) NOT NULL REFERENCES commerceiq_marketing_campaigns(campaign_id),
    session_start_timestamp TIMESTAMP NOT NULL,
    session_end_timestamp TIMESTAMP NOT NULL CHECK (session_end_timestamp >= session_start_timestamp),
    session_duration_seconds INTEGER NOT NULL CHECK (session_duration_seconds > 0),
    device_type VARCHAR(30) NOT NULL,
    product_viewed BOOLEAN NOT NULL,
    page_views INTEGER NOT NULL CHECK (page_views >= 1),
    products_viewed INTEGER NOT NULL CHECK (products_viewed >= 0),
    added_to_cart BOOLEAN NOT NULL,
    checkout_initiated BOOLEAN NOT NULL,
    order_placed BOOLEAN NOT NULL,
    order_delivered BOOLEAN NOT NULL,
    funnel_exit_stage VARCHAR(40) NOT NULL,
    is_synthetic BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_synthetic = TRUE),
    data_source VARCHAR(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS commerceiq_inventory_snapshots (
    inventory_record_id VARCHAR(32) PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    seller_id VARCHAR(32) NOT NULL REFERENCES olist_sellers_dataset(seller_id),
    product_id VARCHAR(32) NOT NULL REFERENCES olist_products_dataset(product_id),
    warehouse_region_state CHAR(2) NOT NULL,
    opening_stock_units INTEGER NOT NULL CHECK (opening_stock_units >= 0),
    stock_received_units INTEGER NOT NULL CHECK (stock_received_units >= 0),
    units_sold_in_period INTEGER NOT NULL CHECK (units_sold_in_period >= 0),
    closing_stock_units INTEGER NOT NULL CHECK (closing_stock_units = opening_stock_units + stock_received_units - units_sold_in_period),
    reserved_quantity INTEGER NOT NULL CHECK (reserved_quantity >= 0 AND reserved_quantity <= closing_stock_units),
    available_quantity INTEGER NOT NULL CHECK (available_quantity = closing_stock_units - reserved_quantity),
    safety_stock_units INTEGER NOT NULL,
    reorder_point_units INTEGER NOT NULL,
    supplier_lead_time_days INTEGER NOT NULL,
    stockout_occurred BOOLEAN NOT NULL,
    inventory_valuation_cogs_brl NUMERIC(12,2) NOT NULL,
    stock_health_status VARCHAR(30) NOT NULL,
    is_synthetic BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_synthetic = TRUE),
    data_source VARCHAR(40) NOT NULL,
    UNIQUE (snapshot_date, seller_id, product_id)
);

CREATE TABLE IF NOT EXISTS commerceiq_customer_support_tickets (
    ticket_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL REFERENCES olist_orders_dataset(order_id),
    customer_unique_id VARCHAR(32) NOT NULL,
    ticket_channel VARCHAR(40) NOT NULL,
    issue_category VARCHAR(60) NOT NULL,
    priority_level VARCHAR(20) NOT NULL,
    ticket_created_timestamp TIMESTAMP NOT NULL,
    ticket_resolved_timestamp TIMESTAMP NOT NULL CHECK (ticket_resolved_timestamp >= ticket_created_timestamp),
    first_response_time_minutes INTEGER NOT NULL,
    resolution_time_hours NUMERIC(8,2) NOT NULL,
    sla_breached BOOLEAN NOT NULL,
    agent_interactions_count INTEGER NOT NULL,
    post_ticket_csat_score INTEGER NOT NULL CHECK (post_ticket_csat_score BETWEEN 1 AND 5),
    is_synthetic BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_synthetic = TRUE),
    data_source VARCHAR(40) NOT NULL
);
