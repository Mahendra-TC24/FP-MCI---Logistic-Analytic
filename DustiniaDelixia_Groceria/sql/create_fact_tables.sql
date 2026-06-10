-- DDL FACT TABLE - DustiniaDelixia Groceria
-- Engine: ClickHouse



-- Tabel utama analitik yang menggabungkan semua staging tables
-- Berisi metrik SLA, finansial, produk, seller, customer, review
DROP TABLE IF EXISTS fact_operational_delivery;

CREATE TABLE IF NOT EXISTS fact_operational_delivery
(
    -- === IDENTITAS ORDER ===
    order_id                        String,
    customer_id                     String,
    order_status                    String,

    -- === TIMESTAMPS ===
    order_purchase_timestamp        DateTime,
    order_approved_at               DateTime,
    order_delivered_carrier_date    DateTime,
    order_delivered_customer_date   DateTime,
    order_estimated_delivery_date   DateTime,

    -- === METRIK SLA OPERASIONAL ===
    approval_time_days              Float32     COMMENT 'Waktu purchase → approved (hari)',
    seller_processing_days          Float32     COMMENT 'Waktu approved → diserahkan ke carrier (hari)',
    carrier_transit_days            Float32     COMMENT 'Waktu carrier pickup → diterima customer (hari)',
    actual_delivery_days            Float32     COMMENT 'Total waktu pengiriman purchase → delivered (hari)',
    delay_days                      Float32     COMMENT 'Selisih actual vs estimasi (negatif = lebih cepat)',
    is_delayed                      UInt8       COMMENT '1 = terlambat, 0 = tepat waktu',

    -- === METRIK FINANSIAL ===
    price                           Float32     COMMENT 'Harga item (dari order_items, diambil pertama)',
    freight_value                   Float32     COMMENT 'Biaya pengiriman item',

    -- === INFO PRODUK ===
    product_id                      String,
    product_category_name           String      COMMENT 'Kategori produk (unknown jika kosong)',
    product_weight_g                Float32,

    -- === INFO SELLER ===
    seller_id                       String,
    seller_city                     String,
    seller_state                    String,
    seller_zip_code_prefix          String,

    -- === INFO CUSTOMER ===
    customer_city                   String,
    customer_state                  String,
    customer_zip_code_prefix        String,

    -- === KOORDINAT CUSTOMER (dari geolocation) ===
    customer_lat                    Nullable(Float32),
    customer_lng                    Nullable(Float32),

    -- === REVIEW ===
    review_score                    Nullable(UInt8) COMMENT 'Skor review 1-5, NULL jika tidak ada review'

) ENGINE = MergeTree()
ORDER BY (order_id, order_purchase_timestamp)
PARTITION BY toYYYYMM(order_purchase_timestamp)
COMMENT 'Fact table utama operasional pengiriman DustiniaDelixia Groceria';


-- INSERT INTO FACT TABLE
-- Jalankan setelah semua staging tables terisi
INSERT INTO fact_operational_delivery
SELECT
    o.order_id,
    o.customer_id,
    o.order_status,

    -- Timestamps
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,

    -- SLA metrics
    o.approval_time_days,
    o.seller_processing_days,
    o.carrier_transit_days,
    o.actual_delivery_days,
    o.delay_days,
    o.is_delayed,

    -- Finansial (ambil item pertama per order)
    oi.price,
    oi.freight_value,

    -- Produk
    p.product_id,
    p.product_category_name,
    p.product_weight_g,

    -- Seller
    s.seller_id,
    s.seller_city,
    s.seller_state,
    s.seller_zip_code_prefix,

    -- Customer
    c.customer_city,
    c.customer_state,
    c.customer_zip_code_prefix,

    -- Koordinat customer
    g.lat  AS customer_lat,
    g.lng  AS customer_lng,

    -- Review
    r.review_score

FROM stg_orders o

-- Join order items (ambil 1 item per order, yang pertama)
LEFT JOIN (
    SELECT order_id, product_id, seller_id, price, freight_value
    FROM stg_order_items
    WHERE (order_id, order_item_id) IN (
        SELECT order_id, min(order_item_id)
        FROM stg_order_items
        GROUP BY order_id
    )
) oi ON o.order_id = oi.order_id

-- Join products
LEFT JOIN stg_products p ON oi.product_id = p.product_id

-- Join sellers
LEFT JOIN stg_sellers s ON oi.seller_id = s.seller_id

-- Join customers
LEFT JOIN stg_customers c ON o.customer_id = c.customer_id

-- Join geolocation (koordinat customer)
LEFT JOIN stg_geolocation g ON c.customer_zip_code_prefix = g.geolocation_zip_code_prefix

-- Join reviews (left join karena tidak semua order punya review)
LEFT JOIN stg_order_reviews r ON o.order_id = r.order_id;



-- Delivery performance summary keseluruhan
SELECT
    count()                                             AS total_orders,
    round(avg(actual_delivery_days), 2)                 AS avg_delivery_days,
    round(avg(approval_time_days), 2)                   AS avg_approval_days,
    round(avg(seller_processing_days), 2)               AS avg_seller_processing_days,
    round(avg(carrier_transit_days), 2)                 AS avg_carrier_transit_days,
    round(avg(delay_days), 2)                           AS avg_delay_days,
    round(countIf(is_delayed = 0) / count() * 100, 2)  AS on_time_rate_pct,
    round(countIf(is_delayed = 1) / count() * 100, 2)  AS delay_rate_pct
FROM fact_operational_delivery;

-- Delay rate & average delivery per customer state
SELECT
    customer_state,
    count()                                             AS total_orders,
    countIf(is_delayed = 1)                             AS delayed_orders,
    round(countIf(is_delayed = 1) / count() * 100, 2)  AS delay_rate_pct,
    round(avg(actual_delivery_days), 2)                 AS avg_delivery_days,
    round(avg(carrier_transit_days), 2)                 AS avg_carrier_transit_days,
    round(avg(review_score), 2)                         AS avg_review_score
FROM fact_operational_delivery
GROUP BY customer_state
ORDER BY delay_rate_pct DESC;

-- Seller performance ranking
SELECT
    seller_id,
    seller_city,
    seller_state,
    count()                                             AS total_orders,
    countIf(is_delayed = 1)                             AS delayed_orders,
    round(countIf(is_delayed = 1) / count() * 100, 2)  AS delay_rate_pct,
    round(avg(seller_processing_days), 2)               AS avg_processing_days,
    round(avg(review_score), 2)                         AS avg_review_score
FROM fact_operational_delivery
GROUP BY seller_id, seller_city, seller_state
HAVING total_orders >= 10
ORDER BY delay_rate_pct DESC;

-- SLA bottleneck breakdown (stage comparison)
SELECT
    round(avg(approval_time_days), 2)       AS avg_approval_days,
    round(avg(seller_processing_days), 2)   AS avg_seller_processing_days,
    round(avg(carrier_transit_days), 2)     AS avg_carrier_transit_days,
    round(median(approval_time_days), 2)    AS median_approval_days,
    round(median(seller_processing_days), 2) AS median_seller_processing_days,
    round(median(carrier_transit_days), 2)  AS median_carrier_transit_days
FROM fact_operational_delivery;

-- Korelasi delay vs review score
SELECT
    is_delayed,
    round(avg(review_score), 3)     AS avg_review_score,
    count()                         AS total_orders,
    round(avg(delay_days), 2)       AS avg_delay_days
FROM fact_operational_delivery
WHERE review_score IS NOT NULL
GROUP BY is_delayed
ORDER BY is_delayed;

--  Monthly trend delivery performance
SELECT
    toYYYYMM(order_purchase_timestamp)                  AS year_month,
    count()                                             AS total_orders,
    round(avg(actual_delivery_days), 2)                 AS avg_delivery_days,
    round(countIf(is_delayed = 1) / count() * 100, 2)  AS delay_rate_pct,
    round(avg(review_score), 2)                         AS avg_review_score
FROM fact_operational_delivery
GROUP BY year_month
ORDER BY year_month;

-- On-time delivery rate overall
SELECT
    round(countIf(is_delayed = 0) / count() * 100, 2) AS on_time_rate_pct
FROM fact_operational_delivery

-- Delay rate overall
SELECT
    round(countIf(is_delayed = 1) / count() * 100, 2) AS delay_rate_pct
FROM fact_operational_delivery

-- Total orders overall
SELECT
    count() AS total_orders
FROM fact_operational_delivery

-- Average delivery days overall
SELECT
    round(avg(actual_delivery_days), 2) AS avg_delivery_days
FROM fact_operational_delivery

--  Average review score overall
SELECT
    round(avg(review_score), 2) AS avg_review_score
FROM fact_operational_delivery
WHERE review_score IS NOT NULL;

-- Chart Delay Rate per Bulan
SELECT 
    toStartOfMonth(order_purchase_timestamp) AS bulan,
    round(countIf(is_delayed = 1) / count() * 100, 2) AS delay_rate_pct,
    count() AS total_orders
FROM fact_operational_delivery
GROUP BY bulan
ORDER BY bulan ASC


-- Distribusi_actual_delivery_days 
SELECT
    CASE
        WHEN actual_delivery_days <= 5 THEN '0-5 hari'
        WHEN actual_delivery_days <= 10 THEN '6-10 hari'
        WHEN actual_delivery_days <= 15 THEN '11-15 hari'
        WHEN actual_delivery_days <= 20 THEN '16-20 hari'
        WHEN actual_delivery_days <= 30 THEN '21-30 hari'
        ELSE '>30 hari'
    END AS delivery_bucket,
    COUNT(*) AS total_orders,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM fact_operational_delivery), 2) AS percentage
FROM fact_operational_delivery
GROUP BY delivery_bucket
ORDER BY
    CASE delivery_bucket
        WHEN '0-5 hari' THEN 1
        WHEN '6-10 hari' THEN 2
        WHEN '11-15 hari' THEN 3
        WHEN '16-20 hari' THEN 4
        WHEN '21-30 hari' THEN 5
        ELSE 6
    END;


-- Breakdown rata-rata waktu per stage (approval, seller processing, carrier transit)
SELECT
    'Approval Time' AS stage_name,
    ROUND(AVG(approval_time_days), 2) AS avg_days,
    ROUND(MIN(approval_time_days), 2) AS min_days,
    ROUND(MAX(approval_time_days), 2) AS max_days,
    COUNT(*) AS total_orders
FROM fact_operational_delivery

UNION ALL

SELECT
    'Seller Processing' AS stage_name,
    ROUND(AVG(seller_processing_days), 2) AS avg_days,
    ROUND(MIN(seller_processing_days), 2) AS min_days,
    ROUND(MAX(seller_processing_days), 2) AS max_days,
    COUNT(*) AS total_orders
FROM fact_operational_delivery

UNION ALL

SELECT
    'Carrier Transit' AS stage_name,
    ROUND(AVG(carrier_transit_days), 2) AS avg_days,
    ROUND(MIN(carrier_transit_days), 2) AS min_days,
    ROUND(MAX(carrier_transit_days), 2) AS max_days,
    COUNT(*) AS total_orders
FROM fact_operational_delivery

ORDER BY avg_days DESC;


-- Top 15 seller dengan delay rate tertinggi (minimal 20 pesanan)
SELECT
    CONCAT('Seller ', LEFT(seller_id, 6)) AS seller_label,
    
    -- Data untuk Tooltip
    seller_city,
    seller_state,
    
    -- Metrik Utama
    ROUND(countIf(is_delayed = 1) * 100.0 / COUNT(*), 2) AS delay_rate_pct,
    COUNT(*) AS total_orders

FROM fact_operational_delivery
GROUP BY seller_id, seller_city, seller_state

-- Hanya tampilkan seller dengan minimal 20 pesanan
HAVING total_orders >= 20 

ORDER BY delay_rate_pct DESC
LIMIT 15;

-- Stage Breakdown per State (hanya yang punya minimal 500 pesanan)
SELECT
    customer_state,
    ROUND(AVG(approval_time_days), 2) AS approval_days,
    ROUND(AVG(seller_processing_days), 2) AS seller_processing_days,
    ROUND(AVG(carrier_transit_days), 2) AS carrier_transit_days,
    ROUND(AVG(actual_delivery_days), 2) AS total_delivery_days,
    COUNT(*) AS total_orders
FROM fact_operational_delivery
GROUP BY customer_state
HAVING COUNT(*) >= 500
ORDER BY total_delivery_days DESC
LIMIT 10;

-- Chart Seller Processing Time vs Delay Rate
SELECT
    CASE
        WHEN avg_processing_days <= 3  THEN '1. 0-3 Hari'
        WHEN avg_processing_days <= 6  THEN '2. 4-6 Hari'
        WHEN avg_processing_days <= 9  THEN '3. 7-9 Hari'
        WHEN avg_processing_days <= 12 THEN '4. 10-12 Hari'
        ELSE                                '5. > 12 Hari'
    END AS processing_bucket,
    round(avg(delay_rate_pct), 2) AS avg_delay_rate_pct,
    count() AS total_sellers
FROM (
    SELECT
        seller_id,
        avg(seller_processing_days) AS avg_processing_days,
        countIf(is_delayed=1)/count()*100 AS delay_rate_pct
    FROM fact_operational_delivery
    GROUP BY seller_id
    HAVING count() >= 10
)
GROUP BY processing_bucket
ORDER BY processing_bucket ASC

-- Delay Rate per Kategori Produk (hanya kategori dengan minimal 100 pesanan)
SELECT
    -- Translasi Manual menggunakan CASE WHEN
    CASE p.product_category_name
        WHEN 'beleza_saude' THEN 'Health & Beauty'
        WHEN 'informatica_acessorios' THEN 'Computers & Accessories'
        WHEN 'automotivo' THEN 'Automotive'
        WHEN 'cama_mesa_banho' THEN 'Bed, Bath & Table'
        WHEN 'moveis_decoracao' THEN 'Furniture & Decor'
        WHEN 'esporte_lazer' THEN 'Sports & Leisure'
        WHEN 'perfumaria' THEN 'Perfumery'
        WHEN 'utilidades_domesticas' THEN 'Home Utilities'
        WHEN 'telefonia' THEN 'Telephony'
        WHEN 'relogios_presentes' THEN 'Watches & Gifts'
        WHEN 'alimentos_bebidas' THEN 'Food & Drink'
        WHEN 'bebes' THEN 'Baby'
        WHEN 'papelaria' THEN 'Stationery'
        WHEN 'tablets_impressao_imagem' THEN 'Tablets, Printing & Image'
        WHEN 'brinquedos' THEN 'Toys'
        WHEN 'telefonia_fixa' THEN 'Fixed Telephony'
        WHEN 'ferramentas_jardim' THEN 'Garden Tools'
        WHEN 'fashion_bolsas_e_acessorios' THEN 'Fashion Bags & Accessories'
        WHEN 'eletroportateis' THEN 'Small Appliances'
        WHEN 'consoles_games' THEN 'Consoles & Games'
        WHEN 'audio' THEN 'Audio'
        WHEN 'fashion_calcados' THEN 'Fashion Shoes'
        WHEN 'cool_stuff' THEN 'Cool Stuff'
        WHEN 'malas_acessorios' THEN 'Luggage & Accessories'
        WHEN 'climatizacao' THEN 'Air Conditioning'
        WHEN 'construcao_ferramentas_construcao' THEN 'Construction Tools'
        WHEN 'moveis_cozinha_area_de_servico_jantar_e_jardim' THEN 'Kitchen & Garden Furniture'
        WHEN 'construcao_ferramentas_jardim' THEN 'Garden Tools'
        WHEN 'fashion_roupa_masculina' THEN 'Men''s Fashion'
        WHEN 'pet_shop' THEN 'Pet Shop'
        WHEN 'moveis_escritorio' THEN 'Office Furniture'
        WHEN 'market_place' THEN 'Marketplace'
        WHEN 'eletronicos' THEN 'Electronics'
        WHEN 'eletrodomesticos' THEN 'Home Appliances'
        WHEN 'artigos_de_festas' THEN 'Party Supplies'
        WHEN 'casa_conforto' THEN 'Home Comfort'
        WHEN 'construcao_ferramentas_ferramentas' THEN 'General Tools'
        WHEN 'agro_industria_e_comercio' THEN 'Agro Industry'
        WHEN 'moveis_colchao_e_estofado' THEN 'Mattress & Upholstery'
        WHEN 'livros_tecnicos' THEN 'Technical Books'
        WHEN 'casa_construcao' THEN 'Home Construction'
        WHEN 'instrumentos_musicais' THEN 'Musical Instruments'
        WHEN 'moveis_sala' THEN 'Living Room Furniture'
        WHEN 'construcao_ferramentas_iluminacao' THEN 'Lighting Tools'
        WHEN 'industria_comercio_e_negocios' THEN 'Industry & Commerce'
        WHEN 'alimentos' THEN 'Food'
        WHEN 'artes' THEN 'Art'
        WHEN 'moveis_quarto' THEN 'Bedroom Furniture'
        WHEN 'livros_interesse_geral' THEN 'General Books'
        WHEN 'construcao_ferramentas_seguranca' THEN 'Safety Tools'
        WHEN 'fashion_underwear_e_moda_praia' THEN 'Underwear & Beachwear'
        WHEN 'fashion_esporte' THEN 'Sportswear'
        WHEN 'sinalizacao_e_seguranca' THEN 'Signaling & Security'
        WHEN 'pcs' THEN 'PCs'
        WHEN 'artigos_de_natal' THEN 'Christmas Supplies'
        WHEN 'fashion_roupa_feminina' THEN 'Women''s Fashion'
        WHEN 'eletrodomesticos_2' THEN 'Home Appliances 2'
        WHEN 'livros_importados' THEN 'Imported Books'
        WHEN 'bebidas' THEN 'Drinks'
        WHEN 'cine_foto' THEN 'Cine & Photo'
        WHEN 'la_cuisine' THEN 'La Cuisine'
        WHEN 'musica' THEN 'Music'
        WHEN 'casa_conforto_2' THEN 'Home Comfort 2'
        WHEN 'portateis_casa_forno_e_cafe' THEN 'Home, Oven & Coffee'
        WHEN 'cds_dvds_musicais' THEN 'CDs, DVDs & Music'
        WHEN 'dvds_blu_ray' THEN 'DVDs & Blu-ray'
        WHEN 'flores' THEN 'Flowers'
        WHEN 'artes_e_artesanato' THEN 'Arts & Crafts'
        WHEN 'fraldas_higiene' THEN 'Diapers & Hygiene'
        WHEN 'fashion_roupa_infanto_juvenil' THEN 'Kids Fashion'
        WHEN 'seguros_e_servicos' THEN 'Security & Services'
        ELSE replace(p.product_category_name, '_', ' ') -- Fallback jika ada kategori baru
    END AS product_category_en,
    
    COUNT(*) AS total_orders,
    ROUND(countIf(fod.is_delayed = 1) * 100.0 / COUNT(*), 2) AS delay_rate_pct,
    ROUND(AVG(fod.actual_delivery_days), 2) AS avg_delivery_days,
    ROUND(AVG(fod.review_score), 2) AS avg_review_score

FROM fact_operational_delivery fod
JOIN stg_order_items oi ON fod.order_id = oi.order_id
JOIN stg_products p ON oi.product_id = p.product_id

WHERE p.product_category_name IS NOT NULL
GROUP BY product_category_en
HAVING total_orders >= 100
ORDER BY delay_rate_pct DESC
LIMIT 10;

-- Tabel Seller Performance dengan Risk Level
SELECT
    seller_id,
    seller_city,
    seller_state,
    count()                                             AS total_orders,
    round(countIf(is_delayed=1)/count()*100, 2)         AS delay_rate_pct,
    round(avg(seller_processing_days), 2)               AS avg_processing_days,
    round(avg(carrier_transit_days), 2)                 AS avg_transit_days,
    round(avg(review_score), 2)                         AS avg_review_score,
    CASE
        WHEN countIf(is_delayed=1)/count()*100 >= 30 THEN '🚨 Kritis'
        WHEN countIf(is_delayed=1)/count()*100 >= 20 THEN '🔴 Tinggi'
        WHEN countIf(is_delayed=1)/count()*100 >= 10 THEN '🟠 Sedang'
        ELSE                                              '🟢 Baik'
    END AS risk_level
FROM fact_operational_delivery
GROUP BY seller_id, seller_city, seller_state
HAVING total_orders >= 10
ORDER BY delay_rate_pct DESC


-- Geographic Performmance Map
SELECT
    customer_city,
    customer_state,
    COUNT(*) AS total_orders,
    ROUND(AVG(actual_delivery_days), 2) AS avg_delivery_days,
    ROUND(countIf(is_delayed = 1) * 100.0 / COUNT(*), 2) AS delay_rate_pct,
    AVG(customer_lat) AS lat,
    AVG(customer_lng) AS lng
FROM fact_operational_delivery
GROUP BY customer_city, customer_state
HAVING total_orders >= 100-- Filter kota dengan minimal 100 pesanan
ORDER BY total_orders DESC
LIMIT 100;

-- State-to-State Delivery Performance (hanya rute dengan minimal 50 pesanan)
SELECT
    s.seller_state AS origin_state,
    c.customer_state AS destination_state,
    CONCAT(s.seller_state, ' → ', c.customer_state) AS delivery_route,
    COUNT(*) AS total_orders,
    ROUND(AVG(actual_delivery_days), 2) AS avg_delivery_days,
    ROUND(countIf(is_delayed = 1) * 100.0 / COUNT(*), 2) AS delay_rate_pct,
    ROUND(AVG(carrier_transit_days), 2) AS avg_transit_days
FROM fact_operational_delivery fod
JOIN stg_sellers s ON fod.seller_id = s.seller_id
JOIN stg_customers c ON fod.customer_id = c.customer_id
GROUP BY origin_state, destination_state, delivery_route
HAVING total_orders >= 50
ORDER BY delay_rate_pct DESC
LIMIT 10;


-- Customer Lifetime Value & Delay Impact 
SELECT
    CASE
        WHEN customer_id IN (
            SELECT customer_id 
            FROM fact_operational_delivery 
            GROUP BY customer_id 
            HAVING COUNT(*) >= 5
        ) THEN '1. High Frequency (≥5 orders)'
        WHEN customer_id IN (
            SELECT customer_id 
            FROM fact_operational_delivery 
            GROUP BY customer_id 
            HAVING COUNT(*) BETWEEN 2 AND 4
        ) THEN '2. Medium Frequency (2-4 orders)'
        ELSE '3. Low Frequency (1 order)'
    END AS customer_segment,
    COUNT(DISTINCT customer_id) AS total_customers,
    COUNT(*) AS total_orders,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(countIf(is_delayed = 1) * 100.0 / COUNT(*), 2) AS delay_rate_pct,
    ROUND(AVG(actual_delivery_days), 2) AS avg_delivery_days
FROM fact_operational_delivery
GROUP BY customer_segment
ORDER BY customer_segment ASC;

-- Bar Char: Review Score - Tepat Waktu vs Terlambat
SELECT
    if(is_delayed = 0, 'Tepat Waktu', 'Terlambat') AS status_pengiriman,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    COUNT(*) AS total_orders,
    ROUND(MIN(review_score), 0) AS min_score,
    ROUND(MAX(review_score), 0) AS max_score
FROM fact_operational_delivery
WHERE review_score IS NOT NULL
GROUP BY is_delayed
ORDER BY is_delayed ASC;				


-- Review Score per Delay Bucket
SELECT
    CASE
        WHEN delay_days <= 0 THEN '1 - Tepat Waktu'
        WHEN delay_days > 0 AND delay_days <= 3 THEN '2 - Terlambat 1-3 Hari'
        WHEN delay_days > 3 AND delay_days <= 7 THEN '3 - Terlambat 4-7 Hari'
        WHEN delay_days > 7 AND delay_days <= 14 THEN '4 - Terlambat 8-14 Hari'
        ELSE '5 - Terlambat >14 Hari'
    END AS delay_bucket,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    COUNT(*) AS total_orders,
    ROUND(MIN(review_score), 0) AS min_score,
    ROUND(MAX(review_score), 0) AS max_score
FROM fact_operational_delivery
WHERE review_score IS NOT NULL
GROUP BY delay_bucket
ORDER BY delay_bucket ASC;

-- Volume pesanan per hari dalam seminggu
SELECT
    toDayOfWeek(order_purchase_timestamp) AS day_of_week,
    CASE toDayOfWeek(order_purchase_timestamp)
        WHEN 1 THEN 'Senin'
        WHEN 2 THEN 'Selasa'
        WHEN 3 THEN 'Rabu'
        WHEN 4 THEN 'Kamis'
        WHEN 5 THEN 'Jumat'
        WHEN 6 THEN 'Sabtu'
        WHEN 7 THEN 'Minggu'
    END AS nama_hari,
    COUNT(*) AS total_orders,
    ROUND(AVG(review_score), 2) AS avg_review_score
FROM fact_operational_delivery
GROUP BY day_of_week, nama_hari
ORDER BY day_of_week ASC;

-- Delay Rate per hari dalam seminggu
SELECT
    toDayOfWeek(order_purchase_timestamp) AS day_of_week,
    CASE toDayOfWeek(order_purchase_timestamp)
        WHEN 1 THEN 'Senin'
        WHEN 2 THEN 'Selasa'
        WHEN 3 THEN 'Rabu'
        WHEN 4 THEN 'Kamis'
        WHEN 5 THEN 'Jumat'
        WHEN 6 THEN 'Sabtu'
        WHEN 7 THEN 'Minggu'
    END AS nama_hari,
    ROUND(countIf(is_delayed = 1) * 100.0 / COUNT(*), 2) AS delay_rate_pct,
    COUNT(*) AS total_orders,
    ROUND(AVG(actual_delivery_days), 2) AS avg_delivery_days
FROM fact_operational_delivery
GROUP BY day_of_week, nama_hari
ORDER BY day_of_week ASC;


-- Rata rata Delivery Time per Hari 
SELECT
    toDayOfWeek(order_purchase_timestamp) AS day_of_week,
    CASE toDayOfWeek(order_purchase_timestamp)
        WHEN 1 THEN 'Senin'
        WHEN 2 THEN 'Selasa'
        WHEN 3 THEN 'Rabu'
        WHEN 4 THEN 'Kamis'
        WHEN 5 THEN 'Jumat'
        WHEN 6 THEN 'Sabtu'
        WHEN 7 THEN 'Minggu'
    END AS nama_hari,
    ROUND(AVG(actual_delivery_days), 2) AS avg_delivery_days,
    ROUND(MIN(actual_delivery_days), 0) AS min_days,
    ROUND(MAX(actual_delivery_days), 0) AS max_days,
    COUNT(*) AS total_orders
FROM fact_operational_delivery
GROUP BY day_of_week, nama_hari
ORDER BY day_of_week ASC;

-- Peak Hour Analysis (jam sibuk order)
SELECT
    CASE
        WHEN toHour(order_purchase_timestamp) BETWEEN 0 AND 5 THEN '1. 00:00 - 05:59 (Dini Hari)'
        WHEN toHour(order_purchase_timestamp) BETWEEN 6 AND 11 THEN '2. 06:00 - 11:59 (Pagi)'
        WHEN toHour(order_purchase_timestamp) BETWEEN 12 AND 17 THEN '3. 12:00 - 17:59 (Siang)'
        ELSE '4. 18:00 - 23:59 (Malam)'
    END AS time_period,

    COUNT(*) AS total_orders,

    countIf(is_delayed = 1) AS delayed_orders,

    ROUND(
        countIf(is_delayed = 1) * 100.0 / COUNT(*),
        2
    ) AS delay_rate_pct

FROM fact_operational_delivery
GROUP BY time_period
ORDER BY time_period;

-- Presentase Keterlambatan per Negara Bagian Customer
SELECT
    customer_state,
    COUNT(*) AS total_orders,
    ROUND(countIf(is_delayed = 1) * 100.0 / COUNT(*), 2) AS delay_rate_pct,
    ROUND(AVG(actual_delivery_days), 2) AS avg_delivery_days,
    ROUND(AVG(review_score), 2) AS avg_review_score
FROM fact_operational_delivery
GROUP BY customer_state
ORDER BY delay_rate_pct DESC
