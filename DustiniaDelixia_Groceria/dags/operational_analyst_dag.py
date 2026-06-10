"""
DAG: operational_analyst_dag.py

Pipeline end-to-end:
  1. Create staging tables di ClickHouse
  2. Extract + Clean + Load tiap CSV ke staging table
  3. Buat fact table dari JOIN semua staging tables
  4. Data quality check

Cara menjalankan:
  - Connection ID Airflow: clickhouse_default
  - Letakkan file CSV di folder: include/data/
  - Trigger DAG dari Airflow UI
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

import pandas as pd
import numpy as np
from clickhouse_driver import Client
import os
import logging


# Konfigurasi koneksi ClickHouse dari environment variables (default untuk local dev)
CLICKHOUSE_HOST     = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT     = int(os.getenv("CLICKHOUSE_PORT", 9000))
CLICKHOUSE_USER     = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DB       = os.getenv("CLICKHOUSE_DB", "default")

# Path ke folder data CSV
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "include", "data")

DEFAULT_ARGS = {
    "owner"           : "operational_analyst",
    "depends_on_past" : False,
    "email_on_failure": False,
    "email_on_retry"  : False,
    "retries"         : 1,
    "retry_delay"     : timedelta(minutes=5),
}



# Helper function untuk koneksi ClickHouse
def get_client() -> Client:
    return Client(
        host    =CLICKHOUSE_HOST,
        port    =CLICKHOUSE_PORT,
        user    =CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DB,
    )



# Task 1: Create staging tables 
def create_staging_tables():
    """Membuat semua staging tables di ClickHouse (idempotent)."""
    client = get_client()
    ddl_path = os.path.join(os.path.dirname(__file__), "..", "sql", "create_staging_tables.sql")

    with open(ddl_path, "r") as f:
        sql_content = f.read()

    # Pisahkan per statement dan eksekusi satu per satu
    statements = [s.strip() for s in sql_content.split(";") if s.strip()]
    for stmt in statements:
        # Hapus baris komentar murni agar tidak salah deteksi
        clean_lines = [line for line in stmt.split('\n') if not line.strip().startswith("--") and not line.strip().startswith("/*")]
        clean_stmt = "\n".join(clean_lines).strip()
        
        if not clean_stmt:
            continue
            
        try:
            client.execute(clean_stmt)
            logging.info(f"Executed: {clean_stmt[:60]}...")
        except Exception as e:
            logging.warning(f"Skip/Warning: {e}")

    logging.info("Staging tables created successfully.")



# TASK 2–8: Extract, Clean, Load per table
def load_orders():
    """Extract orders.csv → Clean → Load ke stg_orders."""
    client = get_client()
    df = pd.read_csv(os.path.join(DATA_DIR, "orders.csv"))
    logging.info(f"  Loaded orders.csv: {len(df):,} baris")

    # -- Cleaning ---
    # Konversi semua timestamp
    time_cols = [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date"
    ]
    for col in time_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Filter hanya status delivered
    df = df[df["order_status"] == "delivered"].copy()

    # Drop baris dengan timestamp kritis kosong
    df.dropna(subset=["order_approved_at", "order_delivered_customer_date",
                      "order_delivered_carrier_date"], inplace=True)

    # --- Feature Engineering SLA ---
    df["approval_time_days"] = (
        df["order_approved_at"] - df["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400

    df["seller_processing_days"] = (
        df["order_delivered_carrier_date"] - df["order_approved_at"]
    ).dt.total_seconds() / 86400

    df["carrier_transit_days"] = (
        df["order_delivered_customer_date"] - df["order_delivered_carrier_date"]
    ).dt.total_seconds() / 86400

    df["actual_delivery_days"] = (
        df["order_delivered_customer_date"] - df["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400

    df["delay_days"] = (
        df["order_delivered_customer_date"] - df["order_estimated_delivery_date"]
    ).dt.total_seconds() / 86400

    # Clip nilai negatif pada SLA (bukan delay_days)
    for col in ["approval_time_days", "seller_processing_days", "carrier_transit_days"]:
        df[col] = df[col].clip(lower=0)

    df["is_delayed"] = (df["delay_days"] > 0).astype(int)

    # --- Load ---
    client.execute("TRUNCATE TABLE IF EXISTS stg_orders")
    records = df[[
        "order_id", "customer_id", "order_status",
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date",
        "approval_time_days", "seller_processing_days", "carrier_transit_days",
        "actual_delivery_days", "delay_days", "is_delayed"
    ]].values.tolist()

    client.execute("INSERT INTO stg_orders VALUES", records)
    logging.info(f" stg_orders loaded: {len(records):,} baris")


def load_order_items():
    """Extract order_items.csv → Clean → Load ke stg_order_items."""
    client = get_client()
    df = pd.read_csv(os.path.join(DATA_DIR, "order_items.csv"))
    logging.info(f"  Loaded order_items.csv: {len(df):,} baris")

    df["price"]         = pd.to_numeric(df["price"], errors="coerce")
    df["freight_value"] = pd.to_numeric(df["freight_value"], errors="coerce")
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"], errors="coerce")

    client.execute("TRUNCATE TABLE IF EXISTS stg_order_items")
    records = df[["order_id", "order_item_id", "product_id", "seller_id",
                  "shipping_limit_date", "price", "freight_value"]].values.tolist()
    client.execute("INSERT INTO stg_order_items VALUES", records)
    logging.info(f"stg_order_items loaded: {len(records):,} baris")


def load_customers():
    """Extract customers.csv → Clean → Load ke stg_customers."""
    client = get_client()
    df = pd.read_csv(os.path.join(DATA_DIR, "customers.csv"))
    logging.info(f"  Loaded customers.csv: {len(df):,} baris")

    df["customer_zip_code_prefix"] = df["customer_zip_code_prefix"].astype(str)

    client.execute("TRUNCATE TABLE IF EXISTS stg_customers")
    records = df[["customer_id", "customer_unique_id", "customer_zip_code_prefix",
                  "customer_city", "customer_state"]].values.tolist()
    client.execute("INSERT INTO stg_customers VALUES", records)
    logging.info(f"stg_customers loaded: {len(records):,} baris")


def load_sellers():
    """Extract sellers.csv → Clean → Load ke stg_sellers."""
    client = get_client()
    df = pd.read_csv(os.path.join(DATA_DIR, "sellers.csv"))
    logging.info(f"  Loaded sellers.csv: {len(df):,} baris")

    df["seller_zip_code_prefix"] = df["seller_zip_code_prefix"].astype(str)

    client.execute("TRUNCATE TABLE IF EXISTS stg_sellers")
    records = df[["seller_id", "seller_zip_code_prefix",
                  "seller_city", "seller_state"]].values.tolist()
    client.execute("INSERT INTO stg_sellers VALUES", records)
    logging.info(f"stg_sellers loaded: {len(records):,} baris")


def load_geolocation():
    """Extract geolocation.csv → Deduplikasi → Load ke stg_geolocation."""
    client = get_client()
    df = pd.read_csv(os.path.join(DATA_DIR, "geolocation.csv"))
    logging.info(f"  Loaded geolocation.csv: {len(df):,} baris (raw)")

    # Konversi zip code ke string karena di database bertipe String
    df["geolocation_zip_code_prefix"] = df["geolocation_zip_code_prefix"].astype(str)

    # Sort untuk konsistensi (biar "first" selalu sama)
    df = df.sort_values("geolocation_zip_code_prefix").reset_index(drop=True)
    
    # Agregasi per zip code prefix (mean koordinat, first city/state)
    # Note: Round mean ke 6 decimal untuk konsistensi floating-point
    geo_clean = df.groupby("geolocation_zip_code_prefix", sort=False).agg(
        lat  =("geolocation_lat",  lambda x: round(x.mean(), 6)),
        lng  =("geolocation_lng",  lambda x: round(x.mean(), 6)),
        city =("geolocation_city", "first"),
        state=("geolocation_state","first"),
    ).reset_index()
    logging.info(f"  Geolocation setelah agregasi: {len(geo_clean):,} baris")

    client.execute("TRUNCATE TABLE IF EXISTS stg_geolocation")
    records = geo_clean[["geolocation_zip_code_prefix", "lat", "lng",
                          "city", "state"]].values.tolist()
    client.execute("INSERT INTO stg_geolocation VALUES", records)
    logging.info(f"stg_geolocation loaded: {len(records):,} baris")


def load_products():
    """Extract products.csv → Clean → Load ke stg_products."""
    client = get_client()
    df = pd.read_csv(os.path.join(DATA_DIR, "products.csv"))
    logging.info(f"  Loaded products.csv: {len(df):,} baris")

    # Isi kategori kosong
    df["product_category_name"] = df["product_category_name"].fillna("unknown")

    # Drop baris dengan dimensi fisik kosong
    df.dropna(subset=["product_weight_g", "product_length_cm",
                      "product_height_cm", "product_width_cm"], inplace=True)

    # Handle nullable int columns: biarkan dulu dalam bentuk numerik di Pandas
    for col in ["product_name_lenght", "product_description_lenght", "product_photos_qty"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    client.execute("TRUNCATE TABLE IF EXISTS stg_products")
    raw_records = df[[
        "product_id", "product_category_name",
        "product_name_lenght", "product_description_lenght", "product_photos_qty",
        "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"
    ]].values.tolist()
    
    # Lakukan konversi di level List Python agar Pandas tidak diam-diam auto-cast kembali ke Float
    records = []
    for r in raw_records:
        records.append([
            r[0], r[1],
            int(r[2]) if pd.notna(r[2]) else None,
            int(r[3]) if pd.notna(r[3]) else None,
            int(r[4]) if pd.notna(r[4]) else None,
            r[5], r[6], r[7], r[8]
        ])
        
    client.execute("INSERT INTO stg_products VALUES", records)
    logging.info(f"stg_products loaded: {len(records):,} baris")


def load_order_reviews():
    """Extract order_reviews.csv → Clean → Load ke stg_order_reviews."""
    client = get_client()
    df = pd.read_csv(os.path.join(DATA_DIR, "order_reviews.csv"))
    logging.info(f"  Loaded order_reviews.csv: {len(df):,} baris")

    # Drop kolom teks yang >80% kosong
    df.drop(columns=["review_comment_title", "review_comment_message"],
            inplace=True, errors="ignore")

    df["review_creation_date"]    = pd.to_datetime(df["review_creation_date"], errors="coerce")
    df["review_answer_timestamp"] = pd.to_datetime(df["review_answer_timestamp"], errors="coerce")
    
    # Biarkan dulu review_score ditangani pandas
    df["review_score"] = pd.to_numeric(df["review_score"], errors="coerce")
    
    # [DATA CLEANSING] Pastikan skor review hanya 1 sampai 5. Jika tidak, set menjadi None (NULL)
    df.loc[~df["review_score"].isin([1, 2, 3, 4, 5]), "review_score"] = None

    # Drop baris tanpa review_id atau order_id
    df.dropna(subset=["review_id", "order_id"], inplace=True)

    client.execute("TRUNCATE TABLE IF EXISTS stg_order_reviews")
    raw_records = df[["review_id", "order_id", "review_score",
                      "review_creation_date", "review_answer_timestamp"]].values.tolist()
                      
    # Lakukan casting integer di luar Pandas
    records = []
    for r in raw_records:
        records.append([
            r[0], r[1],
            int(r[2]) if pd.notna(r[2]) else None,
            r[3], r[4]
        ])
        
    client.execute("INSERT INTO stg_order_reviews VALUES", records)
    logging.info(f"stg_order_reviews loaded: {len(records):,} baris")



# Task 9: Create Fact Table
def create_fact_table():
    """Membuat fact_operational_delivery dari JOIN semua staging tables."""
    client = get_client()
    sql_path = os.path.join(os.path.dirname(__file__), "..", "sql", "create_fact_tables.sql")

    with open(sql_path, "r") as f:
        sql_content = f.read()

    statements = [s.strip() for s in sql_content.split(";") if s.strip()]
    for stmt in statements:
        # Hapus baris komentar murni agar tidak salah deteksi
        clean_lines = [line for line in stmt.split('\n') if not line.strip().startswith("--") and not line.strip().startswith("/*")]
        clean_stmt = "\n".join(clean_lines).strip()
        
        if not clean_stmt:
            continue
            
        try:
            client.execute(clean_stmt)
            logging.info(f"Executed: {clean_stmt[:70]}...")
        except Exception as e:
            logging.warning(f"Skip/Warning: {e}")

    # Verifikasi jumlah baris
    result = client.execute("SELECT count() FROM fact_operational_delivery")
    count = result[0][0]
    logging.info(f"fact_operational_delivery loaded: {count:,} baris")



# Task 10: Data Quality Check
def data_quality_check():
    """Validasi data di fact table setelah pipeline selesai."""
    client = get_client()
    errors = []

    checks = {
        "fact_operational_delivery row count > 0": (
            "SELECT count() FROM fact_operational_delivery", lambda x: x > 0
        ),
        "No NULL order_id": (
            "SELECT countIf(order_id = '') FROM fact_operational_delivery", lambda x: x == 0
        ),
        "No negative actual_delivery_days": (
            "SELECT countIf(actual_delivery_days < 0) FROM fact_operational_delivery", lambda x: x == 0
        ),
        "review_score in range 1-5 or NULL": (
            "SELECT countIf(review_score NOT IN (1,2,3,4,5) AND review_score IS NOT NULL) FROM fact_operational_delivery",
            lambda x: x == 0
        ),
        "is_delayed only 0 or 1": (
            "SELECT countIf(is_delayed NOT IN (0,1)) FROM fact_operational_delivery", lambda x: x == 0
        ),
    }

    print("\n" + "="*60)
    print("  DATA QUALITY CHECK REPORT")
    print("="*60)

    for check_name, (query, validator) in checks.items():
        result = client.execute(query)[0][0]
        status = "PASS" if validator(result) else "❌ FAIL"
        if not validator(result):
            errors.append(check_name)
        print(f"  {status} | {check_name} (value: {result})")

    print("="*60)

    if errors:
        raise ValueError(f"Data quality check FAILED untuk: {errors}")

    logging.info("Semua data quality checks passed!")



# Dag Definition
with DAG(
    dag_id="operational_analyst_dag",
    default_args=DEFAULT_ARGS,
    description="Pipeline Operational Analyst - DustiniaDelixia Groceria FP MCI 2026",
    schedule_interval="@once",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1, 
    tags=["operational", "mci", "final_project"],
) as dag:

    # ── Start ──────────────────────────────────────────────
    start = EmptyOperator(task_id="start")

    # ── Task 1: Create staging tables ──────────────────────
    t_create_staging = PythonOperator(
        task_id="create_staging_tables",
        python_callable=create_staging_tables,
    )

    # ── Task 2–8: Load staging tables (paralel) ────────────
    t_load_orders = PythonOperator(
        task_id="load_orders",
        python_callable=load_orders,
    )
    t_load_order_items = PythonOperator(
        task_id="load_order_items",
        python_callable=load_order_items,
    )
    t_load_customers = PythonOperator(
        task_id="load_customers",
        python_callable=load_customers,
    )
    t_load_sellers = PythonOperator(
        task_id="load_sellers",
        python_callable=load_sellers,
    )
    t_load_geolocation = PythonOperator(
        task_id="load_geolocation",
        python_callable=load_geolocation,
    )
    t_load_products = PythonOperator(
        task_id="load_products",
        python_callable=load_products,
    )
    t_load_reviews = PythonOperator(
        task_id="load_order_reviews",
        python_callable=load_order_reviews,
    )

    # ── Task 9: Create fact table ───────────────────────────
    t_create_fact = PythonOperator(
        task_id="create_fact_table",
        python_callable=create_fact_table,
    )

    # ── Task 10: Data quality check ─────────────────────────
    t_dq_check = PythonOperator(
        task_id="data_quality_check",
        python_callable=data_quality_check,
    )

    # ── End ─────────────────────────────────────────────────
    end = EmptyOperator(task_id="end")

    # ── DEPENDENCY GRAPH ────────────────────────────────────
    #
    #  start
    #    │
    #    ▼
    #  create_staging_tables
    #    │
    #    ├──► load_orders
    #    ├──► load_order_items
    #    ├──► load_customers       (semua paralel)
    #    ├──► load_sellers
    #    ├──► load_geolocation
    #    ├──► load_products
    #    └──► load_order_reviews
    #              │
    #              ▼
    #         create_fact_table
    #              │
    #              ▼
    #         data_quality_check
    #              │
    #              ▼
    #             end

    start >> t_create_staging

    t_create_staging >> [
        t_load_orders,
        t_load_order_items,
        t_load_customers,
        t_load_sellers,
        t_load_geolocation,
        t_load_products,
        t_load_reviews,
    ]

    [
        t_load_orders,
        t_load_order_items,
        t_load_customers,
        t_load_sellers,
        t_load_geolocation,
        t_load_products,
        t_load_reviews,
    ] >> t_create_fact

    t_create_fact >> t_dq_check >> end
