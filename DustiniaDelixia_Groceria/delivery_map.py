"""
delivery_map.py — Peta Interaktif Delivery Performance
Output: delivery_map.html (buka di browser)

Cara menjalankan:
  pip install folium pandas numpy
  Jika menggunakan ClickHouse, tambahkan clickhouse-driver:
  pip install clickhouse-driver
  python delivery_map.py

Mode data:
  - 'csv'        : baca langsung dari file CSV (default)
  - 'clickhouse' : baca dari ClickHouse 
"""

import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap, MarkerCluster
import os
import webbrowser

# KONFIGURASI
DATA_MODE = 'csv'  # ganti ke 'clickhouse' jika ClickHouse sudah running
DATA_DIR  = './include/data/'   # path ke folder CSV
OUTPUT    = 'delivery_map.html' # nama file output

# Koordinat pusat Indonesia
MAP_CENTER = [-2.5, 118.0]
MAP_ZOOM   = 5

# LOAD DATA
print("Loading data...")

clickhouse_available = False
if DATA_MODE == 'clickhouse':
    try:
        from clickhouse_driver import Client
        clickhouse_available = True
    except ImportError:
        print("⚠️ clickhouse_driver tidak ditemukan. Beralih ke mode CSV.")
        DATA_MODE = 'csv'

if DATA_MODE == 'clickhouse' and clickhouse_available:
    try:
        client = Client(host='clickhouse', port=9000, user='airflow', password='', database='airflow', connect_timeout=5)

        # Query agregasi per state dari fact table
        rows, cols = client.execute("""
            SELECT
                customer_state,
                count()                                             AS total_orders,
                round(countIf(is_delayed=1)/count()*100, 2)        AS delay_rate_pct,
                round(avg(actual_delivery_days), 2)                AS avg_delivery_days,
                round(avg(carrier_transit_days), 2)                AS avg_carrier_days,
                round(avg(review_score), 2)                        AS avg_review_score,
                round(avg(customer_lat), 4)                        AS lat,
                round(avg(customer_lng), 4)                        AS lng
            FROM fact_operational_delivery
            WHERE customer_lat IS NOT NULL AND customer_lng IS NOT NULL
            GROUP BY customer_state
            ORDER BY delay_rate_pct DESC
        """, with_column_types=True)
        state_df = pd.DataFrame(rows, columns=[c[0] for c in cols])
        print(f"✅ Loaded dari ClickHouse: {len(state_df)} states")
    except Exception as e:
        print(f"❌ ClickHouse connection failed: {str(e)}")
        print("⚠️  Beralih ke mode CSV...\n")
        DATA_MODE = 'csv'

else:
    # Mode CSV: bangun dari raw files
    orders      = pd.read_csv(DATA_DIR + 'orders.csv')
    customers   = pd.read_csv(DATA_DIR + 'customers.csv')
    geolocation = pd.read_csv(DATA_DIR + 'geolocation.csv')
    reviews     = pd.read_csv(DATA_DIR + 'order_reviews.csv')

    # Cleaning orders
    time_cols = ['order_purchase_timestamp','order_approved_at',
                 'order_delivered_carrier_date','order_delivered_customer_date',
                 'order_estimated_delivery_date']
    for col in time_cols:
        orders[col] = pd.to_datetime(orders[col], errors='coerce')
    orders = orders[orders['order_status'] == 'delivered'].copy()
    orders.dropna(subset=['order_approved_at','order_delivered_customer_date',
                          'order_delivered_carrier_date'], inplace=True)

    orders['actual_delivery_days'] = (
        orders['order_delivered_customer_date'] - orders['order_purchase_timestamp']
    ).dt.total_seconds() / 86400
    orders['carrier_transit_days'] = (
        orders['order_delivered_customer_date'] - orders['order_delivered_carrier_date']
    ).dt.total_seconds() / 86400
    orders['delay_days'] = (
        orders['order_delivered_customer_date'] - orders['order_estimated_delivery_date']
    ).dt.total_seconds() / 86400
    orders['is_delayed'] = (orders['delay_days'] > 0).astype(int)

    # Cleaning geolocation
    geo_clean = geolocation.groupby('geolocation_zip_code_prefix').agg(
        lat=('geolocation_lat','mean'),
        lng=('geolocation_lng','mean')
    ).reset_index()
    geo_clean['geolocation_zip_code_prefix'] = geo_clean['geolocation_zip_code_prefix'].astype(str)
    customers['customer_zip_code_prefix'] = customers['customer_zip_code_prefix'].astype(str)

    # Reviews
    reviews['review_score'] = pd.to_numeric(reviews['review_score'], errors='coerce')

    # Join semua
    df = (orders
          .merge(customers[['customer_id','customer_state','customer_zip_code_prefix']], on='customer_id', how='left')
          .merge(geo_clean, left_on='customer_zip_code_prefix', right_on='geolocation_zip_code_prefix', how='left')
          .merge(reviews[['order_id','review_score']], on='order_id', how='left')
    )

    # Agregasi per state
    state_df = (
        df.groupby('customer_state')
        .agg(
            total_orders      =('order_id','count'),
            delay_rate_pct    =('is_delayed', lambda x: round(x.mean()*100, 2)),
            avg_delivery_days =('actual_delivery_days', lambda x: round(x.mean(), 2)),
            avg_carrier_days  =('carrier_transit_days', lambda x: round(x.mean(), 2)),
            avg_review_score  =('review_score', lambda x: round(x.mean(), 2)),
            lat               =('lat','mean'),
            lng               =('lng','mean'),
        )
        .reset_index()
        .dropna(subset=['lat','lng'])
    )
    print(f"✅ Loaded dari CSV: {len(state_df)} states")

# Agregasi per kota untuk heatmap detail
if DATA_MODE == 'csv':
    city_df = (
        df.groupby(['customer_state', 'lat', 'lng'])
        .agg(
            total_orders   =('order_id','count'),
            delay_rate_pct =('is_delayed', lambda x: round(x.mean()*100, 2)),
        )
        .reset_index()
        .dropna(subset=['lat','lng'])
        .query('total_orders >= 5')
    )
else:
    try:
        rows2, cols2 = client.execute("""
            SELECT customer_state, customer_lat AS lat, customer_lng AS lng,
                   count() AS total_orders,
                   round(countIf(is_delayed=1)/count()*100,2) AS delay_rate_pct
            FROM fact_operational_delivery
            WHERE customer_lat IS NOT NULL
            GROUP BY customer_state, customer_lat, customer_lng
            HAVING total_orders >= 5
        """, with_column_types=True)
        city_df = pd.DataFrame(rows2, columns=[c[0] for c in cols2])
    except Exception as e:
        print(f"❌ City-level query failed: {str(e)}")
        print("⚠️  Menggunakan data tier-state saja...\n")
        city_df = pd.DataFrame()  # Empty dataframe

print(f"✅ City-level data: {len(city_df):,} titik koordinat")

# HELPER: Warna berdasarkan delay rate
def delay_color(rate):
    if rate < 5:    return '#1a9641'   # hijau tua  — sangat baik
    elif rate < 15: return '#a6d96a'   # hijau muda — baik
    elif rate < 25: return '#ffffbf'   # kuning     — perlu perhatian
    elif rate < 40: return '#fdae61'   # oranye     — bermasalah
    else:           return '#d7191c'   # merah      — kritis

def delay_label(rate):
    if rate < 5:    return 'Sangat Baik'
    elif rate < 15: return 'Baik'
    elif rate < 25: return 'Perlu Perhatian'
    elif rate < 40: return 'Bermasalah'
    else:           return 'Kritis'

# BUILD MAP
print("Building map...")

m = folium.Map(
    location=MAP_CENTER,
    zoom_start=MAP_ZOOM,
    tiles='CartoDB positron',
    prefer_canvas=True,
)

# --- LAYER 1: HeatMap — intensitas delay per koordinat ---
heat_data = [
    [row['lat'], row['lng'], row['delay_rate_pct'] / 100]
    for _, row in city_df.iterrows()
    if not (np.isnan(row['lat']) or np.isnan(row['lng']))
]

heatmap_layer = folium.FeatureGroup(name='🌡️ Heatmap Delay Rate', show=True)
HeatMap(
    heat_data,
    min_opacity=0.3,
    max_zoom=10,
    radius=25,
    blur=20,
    gradient={
        '0.0': '#1a9641',
        '0.2': '#a6d96a',
        '0.4': '#ffffbf',
        '0.6': '#fdae61',
        '0.8': '#d7191c',
        '1.0': '#7b0000',
    }
).add_to(heatmap_layer)
heatmap_layer.add_to(m)

# --- LAYER 2: Circle Marker per State ---
state_layer = folium.FeatureGroup(name='📍 Marker per State', show=True)

if DATA_MODE == 'csv':
    national_avg_delay = df['is_delayed'].mean() * 100
    national_avg_delivery = df['actual_delivery_days'].mean()
else:
    try:
        res = client.execute("SELECT round(countIf(is_delayed=1)/count()*100, 2), round(avg(actual_delivery_days), 2) FROM fact_operational_delivery")
        national_avg_delay = res[0][0]
        national_avg_delivery = res[0][1]
    except Exception:
        national_avg_delay = (state_df['delay_rate_pct'] * state_df['total_orders']).sum() / state_df['total_orders'].sum()
        national_avg_delivery = (state_df['avg_delivery_days'] * state_df['total_orders']).sum() / state_df['total_orders'].sum()

for _, row in state_df.iterrows():
    color  = delay_color(row['delay_rate_pct'])
    label  = delay_label(row['delay_rate_pct'])
    radius = max(8, min(30, row['total_orders'] / 500))

    popup_html = f"""
    <div style="font-family:Arial,sans-serif; min-width:220px;">
        <h4 style="margin:0 0 8px 0; color:#2c3e50; border-bottom:2px solid {color}; padding-bottom:4px;">
            📍 State: <b>{row['customer_state']}</b>
        </h4>
        <table style="width:100%; font-size:13px; border-collapse:collapse;">
            <tr><td style="padding:3px 0;">Status</td>
                <td style="text-align:right;"><b>{label}</b></td></tr>
            <tr style="background:#f8f9fa;"><td style="padding:3px 0;">Delay Rate</td>
                <td style="text-align:right; color:{'#e74c3c' if row['delay_rate_pct'] > national_avg_delay else '#27ae60'};"><b>{row['delay_rate_pct']}%</b></td></tr>
            <tr><td style="padding:3px 0;">Avg Delivery Time</td>
                <td style="text-align:right;"><b>{row['avg_delivery_days']} hari</b></td></tr>
            <tr style="background:#f8f9fa;"><td style="padding:3px 0;">Avg Carrier Transit</td>
                <td style="text-align:right;"><b>{row['avg_carrier_days']} hari</b></td></tr>
            <tr><td style="padding:3px 0;">Avg Review Score</td>
                <td style="text-align:right;"><b>⭐ {row['avg_review_score']}</b></td></tr>
            <tr style="background:#f8f9fa;"><td style="padding:3px 0;">Total Pesanan</td>
                <td style="text-align:right;"><b>{int(row['total_orders']):,}</b></td></tr>
        </table>
        <div style="margin-top:8px; font-size:11px; color:#7f8c8d;">
            Nasional avg delay: {national_avg_delay:.1f}% |
            Nasional avg delivery: {national_avg_delivery:.1f} hari
        </div>
    </div>
    """

    folium.CircleMarker(
        location=[row['lat'], row['lng']],
        radius=radius,
        color='white',
        weight=1.5,
        fill=True,
        fill_color=color,
        fill_opacity=0.85,
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=f"{row['customer_state']} | Delay: {row['delay_rate_pct']}% | {int(row['total_orders']):,} orders",
    ).add_to(state_layer)

state_layer.add_to(m)

# --- LAYER KONTROL ---
folium.LayerControl(position='topright', collapsed=False).add_to(m)


# LEGEND
legend_html = """
<div style="
    position: fixed;
    bottom: 40px; left: 20px;
    z-index: 1000;
    background: white;
    border-radius: 10px;
    padding: 14px 18px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.2);
    font-family: Arial, sans-serif;
    font-size: 13px;
    min-width: 200px;
">
    <b style="font-size:14px;">📊 Delay Rate</b>
    <hr style="margin:8px 0; border-color:#eee;">
    <div style="display:flex; align-items:center; margin:5px 0;">
        <span style="background:#1a9641; width:14px; height:14px; border-radius:50%; display:inline-block; margin-right:8px;"></span>
        Sangat Baik (&lt; 5%)
    </div>
    <div style="display:flex; align-items:center; margin:5px 0;">
        <span style="background:#a6d96a; width:14px; height:14px; border-radius:50%; display:inline-block; margin-right:8px;"></span>
        Baik (5% – 15%)
    </div>
    <div style="display:flex; align-items:center; margin:5px 0;">
        <span style="background:#ffffbf; width:14px; height:14px; border-radius:50%; display:inline-block; margin-right:8px; border:1px solid #ccc;"></span>
        Perlu Perhatian (15% – 25%)
    </div>
    <div style="display:flex; align-items:center; margin:5px 0;">
        <span style="background:#fdae61; width:14px; height:14px; border-radius:50%; display:inline-block; margin-right:8px;"></span>
        Bermasalah (25% – 40%)
    </div>
    <div style="display:flex; align-items:center; margin:5px 0;">
        <span style="background:#d7191c; width:14px; height:14px; border-radius:50%; display:inline-block; margin-right:8px;"></span>
        Kritis (&gt; 40%)
    </div>
    <hr style="margin:8px 0; border-color:#eee;">
    <div style="font-size:11px; color:#7f8c8d;">
        Ukuran marker = volume pesanan<br>
        Klik marker untuk detail lengkap
    </div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# TITLE & INFO BOX
# Hitung statistik untuk title box
worst_state     = state_df.loc[state_df['delay_rate_pct'].idxmax(), 'customer_state']
worst_delay     = state_df['delay_rate_pct'].max()
best_state      = state_df.loc[state_df['delay_rate_pct'].idxmin(), 'customer_state']
best_delay      = state_df['delay_rate_pct'].min()
critical_states = (state_df['delay_rate_pct'] > 40).sum()
on_time_rate    = 100 - national_avg_delay

title_html = f"""
<div style="
    position: fixed;
    top: 15px; left: 50%;
    transform: translateX(-50%);
    z-index: 1000;
    background: rgba(255,255,255,0.97);
    border-radius: 10px;
    padding: 12px 24px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.2);
    font-family: Arial, sans-serif;
    text-align: center;
    min-width: 560px;
">
    <div style="font-size:17px; font-weight:bold; color:#2c3e50;">
        🗺️ Peta Delivery Performance — DustiniaDelixia Groceria
    </div>
    <div style="font-size:12px; color:#7f8c8d; margin-top:4px;">
        Persona: Operational Analyst &nbsp;|&nbsp; Final Project MCI 2026
    </div>
    <div style="display:flex; justify-content:center; gap:24px; margin-top:10px; font-size:13px;">
        <div style="text-align:center;">
            <div style="font-size:20px; font-weight:bold; color:#27ae60;">{on_time_rate:.1f}%</div>
            <div style="color:#7f8c8d;">On-Time Rate</div>
        </div>
        <div style="text-align:center;">
            <div style="font-size:20px; font-weight:bold; color:#e74c3c;">{national_avg_delay:.1f}%</div>
            <div style="color:#7f8c8d;">Avg Delay Rate</div>
        </div>
        <div style="text-align:center;">
            <div style="font-size:20px; font-weight:bold; color:#e74c3c;">{critical_states}</div>
            <div style="color:#7f8c8d;">State Kritis (&gt;40%)</div>
        </div>
        <div style="text-align:center;">
            <div style="font-size:20px; font-weight:bold; color:#e74c3c;">{worst_state}</div>
            <div style="color:#7f8c8d;">State Terburuk ({worst_delay:.0f}%)</div>
        </div>
        <div style="text-align:center;">
            <div style="font-size:20px; font-weight:bold; color:#27ae60;">{best_state}</div>
            <div style="color:#7f8c8d;">State Terbaik ({best_delay:.0f}%)</div>
        </div>
    </div>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

# SAVE
m.save(OUTPUT)
print(f"\n✅ Peta berhasil dibuat: {OUTPUT}")
print(f"   Total states    : {len(state_df)}")
print(f"   Total titik peta: {len(city_df):,}")
print(f"   On-Time Rate    : {on_time_rate:.2f}%")
print(f"   Avg Delay Rate  : {national_avg_delay:.2f}%")
print(f"   State Terburuk  : {worst_state} ({worst_delay:.1f}%)")
print(f"   State Terbaik   : {best_state} ({best_delay:.1f}%)")
print(f"\n📂 Buka file ini di browser:")
print(f"   {os.path.abspath(OUTPUT)}")

