# DustiniaDelixia Delivery Analytics Dashboard

## Project Overview

**DustiniaDelixia Delivery Analytics** is a comprehensive business intelligence dashboard designed to analyze and optimize delivery performance for a Brazilian e-commerce company. This project leverages ClickHouse (OLAP database) and Metabase (BI tool) to transform raw e-commerce data into actionable insights for operational decision-making.

### Key Performance Indicators
| Metric | Value |
|--------|-------|
| **On-Time Delivery Rate** | 91.89% |
| **Delay Rate** | 8.11% |
| **Total Orders Delivered** | 96,984 |
| **Average Delivery Time** | 12.56 days |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Database** | ClickHouse (OLAP Columnar Database) |
| **BI Tool** | Metabase v0.52.5 (Open-Source BI) |
| **Query Language** | SQL (ClickHouse Dialect) |
| **Containerization** | Docker & Docker Compose |
| **Data Processing** | Python (Pandas, Jupyter Notebook) |
| **Dataset** | [DustiniaDelixia_Groceria] |

---

## Project Structure

```
DustiniaDelixia/
│
├── include/data/                    # Raw CSV Data Files
│   ├── category_translation.csv        # Product category translations (PT → EN)
│   ├── closed_deals.csv                # Marketing qualified leads & deals
│   ├── customers.csv                   # Customer information & locations
│   ├── geolocation.csv                 # Brazilian ZIP codes & coordinates
│   ├── mql.csv                         # Marketing qualified leads data
│   ├── order_items.csv                 # Order items & product details
│   ├── order_payments.csv              # Payment information
│   ├── order_reviews.csv               # Customer reviews & ratings
│   ├── orders.csv                      # Order timestamps & status
│   ├── products.csv                    # Product details & categories
│   └── sellers.csv                     # Seller information & locations
│
├── sql/                             # SQL Scripts for Data Modeling
│   ├── create_fact_table.sql           # Creates fact_operational_delivery table
│   └── create_staging_tables.sql       # Creates staging dimension tables
│
├── logs/                            # Application & query logs
│
├── .env                             # Environment variables
├── docker-compose.yml               # Docker orchestration
├── Dockerfile                       # Custom container configuration
├── requirements.txt                 # Python dependencies
│
├── data_profiling.ipynb             # Jupyter notebook for EDA
├── delivery_map.py                  # Python script for geographic visualization
├── delivery_map.html                # Interactive delivery performance map
├── operational_analysis.py          # Operational metrics calculation
│
├── finalproject_mci_2_...           # Main project documentation
└── Metabase - DustiniaDelixia Dashboard.pdf  # Dashboard screenshots
```

---

## Dashboard Structure

### **Page 1: Executive Summary**
High-level KPIs and trends for executive overview:

**Scorecards:**
- On-Time Delivery Rate: **91.89%**
- Delay Rate: **8.11%**
- Total Orders Delivered: **96,984**
- Average Delivery Time: **12.56 days**

**Visualizations:**
- **Delay Rate per Bulan**: Line chart showing monthly delay trends (Jan 2017 - Jul 2018)
- **Top 15 Seller by Delay Rate**: Horizontal bar chart identifying worst-performing sellers
- **Distribusi actual_delivery_days**: Histogram showing delivery time distribution (0-5 hari, 6-10 hari, 11-15 hari, etc.)
- **Breakdown Waktu per Stage**: Bar chart showing average time per stage:
  - Approval Time: **0.43 days**
  - Seller Processing: **2.82 days**
  - Carrier Transit: **9.33 days** (74% of total delivery time)

### **Page 2: Bottleneck & Operational Performance**
Deep-dive analysis into operational inefficiencies:

**Visualizations:**
- **Seller Processing Time vs Delay Rate**: Line chart showing correlation between seller processing time categories (0-3 Hari, 4-6 Hari, 7-9 Hari, 10-12 Hari, >12 Hari) and delay rate
- **Tabel Seller Performance**: Sortable data table with 623 sellers showing:
  - Seller ID, City, State
  - Total Orders, Delay Rate
  - Avg Processing Days, Avg Transit Days
  - Avg Review Score, Risk Category
- **Stage Breakdown per Top State**: Grouped bar chart showing approval, processing, and transit times for top 10 states (PA, MA, CE, PB, BA, PE, MT, ES, MS, GO)

### **Page 3A: Regional & Geographic Analysis**
Geographic performance disparities across Brazil:

**Visualizations:**
- **Persentase Keterlambatan per State**: Horizontal bar chart with national average goal line (8.11%):
  - MA: **19.58%** (highest)
  - CE: **15.38%**
  - BA: **14.08%**
  - RJ: **13.48%**
  - PA: **12.29%**
  - ES: **12.23%**
  - MS: **11.52%**
  - PB: **11.00%**
  - PE: **10.72%**
  - SC: **9.78%**
- **Geographic Performance Map**: Interactive map showing delivery performance across Brazilian states

### **Page 3B: Customer Satisfaction & Daily Patterns**
Customer impact and temporal patterns:

**Visualizations:**
- **Review Score - Tepat Waktu vs Terlambat**: Bar chart showing:
  - On-Time: **4.29**
  - Delayed: **2.57** (1.72-point drop)
- **Rata-rata Review Score**: Scorecard showing **4.16**
- **Review Score per Delay Bucket**: Line chart showing declining trend:
  - 1 - Tepat Waktu: **4.29**
  - 2 - Terlambat 1-3 Hari: **3.77**
  - 3 - Terlambat 4-7 Hari: **2.31**
  - 4 - Terlambat 8-14 Hari: **1.75**
  - 5 - Terlambat >14 Hari: **1.71**
- **Volume Pesanan per Hari**: Bar chart showing daily order volume:
  - Senin: **15.8k** (peak)
  - Selasa: **15.6k**
  - Rabu: **15.2k**
  - Kamis: **14.4k**
  - Jumat: **13.8k**
  - Sabtu: **10.6k** (lowest)
  - Minggu: **11.7k**
- **Delay Rate per Hari**: Bar chart with national average goal line:
  - Senin: **9.03%** (highest)
  - Jumat: **8.43%**
  - Minggu: **7.47%** (lowest)
- **Rata-rata Delivery Time per Hari**: Bar chart showing:
  - Jumat: **13.57 days** (longest)
  - Sabtu: **13.37 days**
  - Minggu: **11.97 days** (shortest)

---

## Key Insights & Business Recommendations

### **1. Carrier Transit is the Primary Bottleneck**
- **Finding**: Carrier Transit takes **9.33 days**, accounting for **74%** of total delivery time (12.56 days)
- **Recommendation**: Renegotiate contracts with carriers, especially for Northeast Brazil routes

### **2. Geographic Disparities are Severe**
- **Finding**: Northeast states (MA 19.58%, CE 15.38%, BA 14.08%) have **2-3x higher delay rates** than Southeast states (SC 9.78%, PR 5.02%)
- **Recommendation**: Establish regional distribution centers in Northeast Brazil to reduce transit times

### **3. Seller Processing Time Directly Impacts Delays**
- **Finding**: Sellers with processing time >12 days have significantly higher delay rates compared to those processing within 0-3 days
- **Recommendation**: Implement SLA incentives for sellers who process orders within 24-48 hours

### **4. Customer Satisfaction Plummets with Delays**
- **Finding**: Review score drops from **4.29** (on-time) to **2.57** (delayed) — a **1.72-point decrease**
- **Finding**: Orders delayed >14 days receive only **1.71** review score
- **Recommendation**: Prioritize on-time delivery for customer retention; consider compensation for severely delayed orders

### **5. Weekend Orders Face Longer Delivery Times**
- **Finding**: Friday (13.57 days) and Saturday (13.37 days) have the longest delivery times
- **Finding**: Monday has the highest delay rate (9.03%) due to weekend backlog
- **Recommendation**: Incentivize weekend seller processing or set +1 day delivery expectation for Friday-Saturday orders

### **6. Top 15 Sellers Drive Disproportionate Delays**
- **Finding**: 15 sellers account for a significant portion of delayed orders
- **Recommendation**: Implement performance improvement plans for bottom-performing sellers; consider offboarding chronic underperformers

---

## Installation & Setup

### **Prerequisites**
- Docker & Docker Compose installed
- 8GB+ RAM recommended (ClickHouse requires sufficient memory)
- 10GB+ free disk space

### **Quick Start**

1. **Clone the repository**
   ```bash
   git clone (https://github.com/Mahendra-TC24/FP-MCI---Logistic-Analytic.git)
   cd DustiniaDelixia
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

3. **Start containers**
   ```bash
   docker-compose up -d
   ```

4. **Access Metabase**
   - Open browser: `http://localhost:3000`
   - Complete initial setup (admin email, password)
   - Connect to ClickHouse database

5. **Import data and run SQL scripts**
   ```bash
   # Create staging tables
   docker-compose exec clickhouse-server clickhouse-client --multiquery < sql/create_staging_tables.sql
   
   # Create fact table
   docker-compose exec clickhouse-server clickhouse-client --multiquery < sql/create_fact_table.sql
   ```

---

## Data Pipeline Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐
│  CSV Files  │ --> │  ClickHouse  │ --> │   Metabase  │ --> │ Dashboard│
│  (Raw Data) │     │ (Data Model) │     │     (BI)    │     │   (UI)   │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────┘
                           │
                    ┌──────┴──────┐
                    │ Star Schema │
                    │  Fact + Dim │
                    └─────────────┘
```

### **Data Model**

**Fact Table:**
- `fact_operational_delivery`: Main fact table with delivery metrics
  - Measures: `is_delayed`, `actual_delivery_days`, `seller_processing_days`, `carrier_transit_days`, `approval_time_days`, `review_score`
  - Foreign Keys: `customer_id`, `seller_id`, `order_id`

**Dimension Tables:**
- `stg_customers`: Customer demographics & location (state, city, lat, lng)
- `stg_sellers`: Seller information & location (state, city)
- `stg_products`: Product details & categories
- `stg_orders`: Order timestamps & status
- `stg_order_items`: Order line items
- `stg_order_reviews`: Review scores & timestamps

---

## Key Metrics & Formulas

| Metric | Formula | Current Value |
|--------|---------|---------------|
| **On-Time Delivery Rate** | `(Total Orders - Delayed Orders) / Total Orders × 100` | 91.89% |
| **Delay Rate** | `Delayed Orders / Total Orders × 100` | 8.11% |
| **Avg Delivery Time** | `AVG(actual_delivery_days)` | 12.56 days |
| **Seller Processing Time** | `AVG(seller_processing_days)` | 2.82 days |
| **Carrier Transit Time** | `AVG(carrier_transit_days)` | 9.33 days |
| **Avg Review Score** | `AVG(review_score)` | 4.16/5 |

---

## Data Profiling & Quality

The `data_profiling.ipynb` notebook performs:
- **Completeness checks**: Missing value analysis across all tables
- **Uniqueness validation**: Primary key & duplicate detection
- **Consistency verification**: Date logic (purchase ≤ approved ≤ delivered)
- **Distribution analysis**: Outlier detection for delivery times
- **Referential integrity**: Foreign key validation between fact & dimension tables

---

## Geographic Analysis

The `delivery_map.py` and `delivery_map.html` provide:
- **Interactive maps**: Showing delivery performance across Brazilian states
- **Regional comparison**: Northeast vs Southeast performance disparities
- **Hotspot identification**: High-delay geographic clusters

---

## Sample SQL Queries

### **Top 10 States by Delay Rate**
```sql
SELECT
    customer_state,
    COUNT(*) AS total_orders,
    ROUND(countIf(is_delayed = 1) * 100.0 / COUNT(*), 2) AS delay_rate_pct,
    ROUND(AVG(actual_delivery_days), 2) AS avg_delivery_days
FROM fact_operational_delivery
GROUP BY customer_state
HAVING total_orders >= 500
ORDER BY delay_rate_pct DESC
LIMIT 10;
```

### **Stage Breakdown Analysis**
```sql
SELECT
    'Approval Time' AS stage,
    ROUND(AVG(approval_time_days), 2) AS avg_days
FROM fact_operational_delivery
UNION ALL
SELECT 'Seller Processing', ROUND(AVG(seller_processing_days), 2)
FROM fact_operational_delivery
UNION ALL
SELECT 'Carrier Transit', ROUND(AVG(carrier_transit_days), 2)
FROM fact_operational_delivery;
```

### **Review Score by Delay Status**
```sql
SELECT
    if(is_delayed = 0, 'Tepat Waktu', 'Terlambat') AS status,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    COUNT(*) AS total_orders
FROM fact_operational_delivery
WHERE review_score IS NOT NULL
GROUP BY is_delayed;
```

---

## Learning Outcomes

This project demonstrates proficiency in:
- **Advanced SQL**: Window functions, CTEs, CASE statements, aggregations
- **OLAP Database Design**: Star schema, columnar storage optimization with ClickHouse
- **Data Modeling**: Fact/dimension table design, ETL processes
- **BI Dashboard Design**: Storytelling with data, KPI visualization in Metabase
- **Geographic Analysis**: Spatial data visualization
- **Business Analytics**: Root cause analysis, actionable recommendations
- **Containerization**: Docker Compose for reproducible environments

---
## License

This project is for **educational purposes** as part of a Final Project submission.  

---
## Author

**[Mahendra Agung Darmawan/5025241032]**    
Final Project - MCI Lab   
[amahendra952@gmail.com]  
[https://github.com/Mahendra-TC24]

---

## Acknowledgments

- **Olist** for providing the public dataset
- **ClickHouse** team for the powerful OLAP database
- **Metabase** team for the excellent open-source BI tool
- **[Instructor/Mentor Name]** for guidance and support

---

