
-- DDL STAGING TABLES - DustiniaDelixia Groceria
-- Engine: ClickHouse

-- Drop tables if exist (untuk idempotency)
DROP TABLE IF EXISTS stg_orders;
DROP TABLE IF EXISTS stg_order_items;
DROP TABLE IF EXISTS stg_customers;
DROP TABLE IF EXISTS stg_sellers;
DROP TABLE IF EXISTS stg_geolocation;
DROP TABLE IF EXISTS stg_products;
DROP TABLE IF EXISTS stg_order_reviews;


-- 1. STG_ORDERS
-- Berisi data pesanan yang sudah difilter (status = delivered)
-- dan dilengkapi dengan metrik SLA operasional
CREATE TABLE IF NOT EXISTS stg_orders
(
    order_id                        String,
    customer_id                     String,
    order_status                    String,
    order_purchase_timestamp        DateTime,
    order_approved_at               DateTime,
    order_delivered_carrier_date    DateTime,
    order_delivered_customer_date   DateTime,
    order_estimated_delivery_date   DateTime,

    -- Feature Engineering SLA
    approval_time_days              Float32,
    seller_processing_days          Float32,
    carrier_transit_days            Float32,
    actual_delivery_days            Float32,
    delay_days                      Float32,
    is_delayed                      UInt8       -- 0 = tepat waktu, 1 = terlambat

) ENGINE = MergeTree()
ORDER BY (order_id, order_purchase_timestamp)
COMMENT 'Staging table untuk data orders yang sudah di-cleaning dan feature engineering SLA';


-- 2. STG_ORDER_ITEMS
-- Berisi detail item per pesanan
CREATE TABLE IF NOT EXISTS stg_order_items
(
    order_id            String,
    order_item_id       UInt8,
    product_id          String,
    seller_id           String,
    shipping_limit_date DateTime,
    price               Float32,
    freight_value       Float32

) ENGINE = MergeTree()
ORDER BY (order_id, order_item_id)
COMMENT 'Staging table untuk data order items';


-- 3. STG_CUSTOMERS
-- Berisi informasi pelanggan dan lokasi
CREATE TABLE IF NOT EXISTS stg_customers
(
    customer_id                 String,
    customer_unique_id          String,
    customer_zip_code_prefix    String,
    customer_city               String,
    customer_state              String

) ENGINE = MergeTree()
ORDER BY customer_id
COMMENT 'Staging table untuk data customers';

-- 4. STG_SELLERS
-- Berisi informasi seller dan lokasi
CREATE TABLE IF NOT EXISTS stg_sellers
(
    seller_id               String,
    seller_zip_code_prefix  String,
    seller_city             String,
    seller_state            String

) ENGINE = MergeTree()
ORDER BY seller_id
COMMENT 'Staging table untuk data sellers';


-- 5. STG_GEOLOCATION
-- Berisi koordinat per zip code prefix (sudah di-deduplikasi)
CREATE TABLE IF NOT EXISTS stg_geolocation
(
    geolocation_zip_code_prefix String,
    lat                         Float32,
    lng                         Float32,
    city                        String,
    state                       String

) ENGINE = MergeTree()
ORDER BY geolocation_zip_code_prefix
COMMENT 'Staging table geolocation sudah di-agregasi per zip code (mean lat/lng)';

-- 6. STG_PRODUCTS
-- Berisi informasi produk dan dimensi fisik
CREATE TABLE IF NOT EXISTS stg_products
(
    product_id                  String,
    product_category_name       String,
    product_name_lenght         Nullable(UInt32),
    product_description_lenght  Nullable(UInt32),
    product_photos_qty          Nullable(UInt8),
    product_weight_g            Float32,
    product_length_cm           Float32,
    product_height_cm           Float32,
    product_width_cm            Float32

) ENGINE = MergeTree()
ORDER BY product_id
COMMENT 'Staging table untuk data products (missing kategori diisi unknown)';


-- 7. STG_ORDER_REVIEWS
-- Berisi review score per pesanan (tanpa kolom teks yang kosong)
CREATE TABLE IF NOT EXISTS stg_order_reviews
(
    review_id               String,
    order_id                String,
    review_score            Nullable(UInt8),
    review_creation_date    DateTime,
    review_answer_timestamp DateTime

) ENGINE = MergeTree()
ORDER BY (order_id, review_id)
COMMENT 'Staging table untuk data order reviews (kolom teks high-missing dihapus)';
