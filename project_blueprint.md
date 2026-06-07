# Marketing Intelligence System — Complete Project Blueprint

## Dataset: IBM Marketing Campaign (2240 rows, 29 columns)

---

## What Your Dataset Actually Contains

| Column Group | Columns | What It Represents |
|---|---|---|
| Customer Identity | ID, Year_Birth, Education, Marital_Status | Who the customer is |
| Financial | Income | Earning capacity |
| Household | Kidhome, Teenhome | Life stage |
| Engagement | Dt_Customer, Recency, NumWebVisitsMonth | How they interact |
| Spending | MntWines, MntFruits, MntMeatProducts, MntFishProducts, MntSweetProducts, MntGoldProds | What they spend on |
| Purchase Channels | NumDealsPurchases, NumWebPurchases, NumCatalogPurchases, NumStorePurchases | How they buy |
| Campaign Response | AcceptedCmp1–5, Response | Which campaigns they responded to |
| Complaints | Complain | Satisfaction signal |
| Cost Metadata | Z_CostContact, Z_Revenue | Campaign economics |

**Key business insight from the data:**
- `Response` = Did customer accept the LAST campaign? → This is your **conversion label**
- `AcceptedCmp1–5` = Did they accept earlier campaigns? → This is your **campaign history**
- `Z_CostContact = 3`, `Z_Revenue = 11` → Fixed per customer → ROI = Revenue - Cost = 8 per conversion

---

## MySQL Database Design

### Why These 4 Tables?

Your raw CSV is one flat file. In a real company, this data lives in **separate systems**:
- CRM system → customer profiles
- Finance system → income and spend
- Campaign system → which campaigns ran, which were accepted
- Engagement system → website visits, recency

You'll split it to demonstrate SQL skills (joins, CTEs, window functions).

---

### Table 1: customers

```sql
CREATE DATABASE marketing_db;
USE marketing_db;

CREATE TABLE customers (
    customer_id       INT PRIMARY KEY,
    year_birth        INT NOT NULL,
    age               INT GENERATED ALWAYS AS (2024 - year_birth) STORED,
    education         ENUM('Basic', '2n Cycle', 'Graduation', 'Master', 'PhD') NOT NULL,
    marital_status    ENUM('Single', 'Together', 'Married', 'Divorced', 'Widow', 'Alone', 'Absurd', 'YOLO') NOT NULL,
    marital_clean     VARCHAR(20) GENERATED ALWAYS AS (
                        CASE 
                          WHEN marital_status IN ('Alone','Absurd','YOLO') THEN 'Single'
                          WHEN marital_status = 'Together' THEN 'Married'
                          ELSE marital_status
                        END
                      ) STORED,
    income            DECIMAL(12,2),
    kidhome           INT DEFAULT 0,
    teenhome          INT DEFAULT 0,
    total_children    INT GENERATED ALWAYS AS (kidhome + teenhome) STORED,
    dt_customer       DATE NOT NULL,
    complain          TINYINT(1) DEFAULT 0,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Why `marital_clean`?** Your dataset has 'YOLO', 'Absurd', 'Alone' — junk values. You engineer a clean column directly in the schema. This shows data quality thinking.

---

### Table 2: customer_spending

```sql
CREATE TABLE customer_spending (
    spending_id           INT AUTO_INCREMENT PRIMARY KEY,
    customer_id           INT NOT NULL,
    mnt_wines             INT DEFAULT 0,
    mnt_fruits            INT DEFAULT 0,
    mnt_meat_products     INT DEFAULT 0,
    mnt_fish_products     INT DEFAULT 0,
    mnt_sweet_products    INT DEFAULT 0,
    mnt_gold_prods        INT DEFAULT 0,
    total_spend           INT GENERATED ALWAYS AS (
                            mnt_wines + mnt_fruits + mnt_meat_products +
                            mnt_fish_products + mnt_sweet_products + mnt_gold_prods
                          ) STORED,
    num_deals_purchases   INT DEFAULT 0,
    num_web_purchases     INT DEFAULT 0,
    num_catalog_purchases INT DEFAULT 0,
    num_store_purchases   INT DEFAULT 0,
    total_purchases       INT GENERATED ALWAYS AS (
                            num_deals_purchases + num_web_purchases +
                            num_catalog_purchases + num_store_purchases
                          ) STORED,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);
```

---

### Table 3: customer_engagement

```sql
CREATE TABLE customer_engagement (
    engagement_id         INT AUTO_INCREMENT PRIMARY KEY,
    customer_id           INT NOT NULL,
    recency               INT NOT NULL COMMENT 'Days since last purchase',
    num_web_visits_month  INT DEFAULT 0,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);
```

---

### Table 4: campaign_responses

```sql
CREATE TABLE campaign_responses (
    response_id       INT AUTO_INCREMENT PRIMARY KEY,
    customer_id       INT NOT NULL,
    campaign_1        TINYINT(1) DEFAULT 0,
    campaign_2        TINYINT(1) DEFAULT 0,
    campaign_3        TINYINT(1) DEFAULT 0,
    campaign_4        TINYINT(1) DEFAULT 0,
    campaign_5        TINYINT(1) DEFAULT 0,
    response          TINYINT(1) DEFAULT 0 COMMENT 'Accepted last campaign',
    total_campaigns_accepted INT GENERATED ALWAYS AS (
                               campaign_1 + campaign_2 + campaign_3 +
                               campaign_4 + campaign_5
                             ) STORED,
    z_cost_contact    INT DEFAULT 3,
    z_revenue         INT DEFAULT 11,
    revenue_generated INT GENERATED ALWAYS AS (response * 11) STORED,
    cost_incurred     INT GENERATED ALWAYS AS (3) STORED,
    net_value         INT GENERATED ALWAYS AS ((response * 11) - 3) STORED,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);
```

---

### Load Data from CSV (Python script — run once)

```python
# scripts/load_data.py
import pandas as pd
import mysql.connector

df = pd.read_csv('data/raw/marketing_campaign.csv', sep='\t')  # check separator
df['Income'] = df['Income'].fillna(df['Income'].median())
df['Dt_Customer'] = pd.to_datetime(df['Dt_Customer'], dayfirst=True)

conn = mysql.connector.connect(
    host='localhost', user='root', password='yourpassword', database='marketing_db'
)
cursor = conn.cursor()

for _, row in df.iterrows():
    # customers
    cursor.execute("""
        INSERT IGNORE INTO customers 
        (customer_id, year_birth, education, marital_status, income, kidhome, teenhome, dt_customer, complain)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (row.ID, row.Year_Birth, row.Education, row.Marital_Status,
          row.Income, row.Kidhome, row.Teenhome, row.Dt_Customer.date(), row.Complain))

    # spending
    cursor.execute("""
        INSERT INTO customer_spending
        (customer_id, mnt_wines, mnt_fruits, mnt_meat_products, mnt_fish_products,
         mnt_sweet_products, mnt_gold_prods, num_deals_purchases, num_web_purchases,
         num_catalog_purchases, num_store_purchases)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (row.ID, row.MntWines, row.MntFruits, row.MntMeatProducts, row.MntFishProducts,
          row.MntSweetProducts, row.MntGoldProds, row.NumDealsPurchases, row.NumWebPurchases,
          row.NumCatalogPurchases, row.NumStorePurchases))

    # engagement
    cursor.execute("""
        INSERT INTO customer_engagement (customer_id, recency, num_web_visits_month)
        VALUES (%s,%s,%s)
    """, (row.ID, row.Recency, row.NumWebVisitsMonth))

    # campaign_responses
    cursor.execute("""
        INSERT INTO campaign_responses
        (customer_id, campaign_1, campaign_2, campaign_3, campaign_4, campaign_5, response,
         z_cost_contact, z_revenue)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (row.ID, row.AcceptedCmp1, row.AcceptedCmp2, row.AcceptedCmp3,
          row.AcceptedCmp4, row.AcceptedCmp5, row.Response, row.Z_CostContact, row.Z_Revenue))

conn.commit()
cursor.close()
conn.close()
print("Data loaded successfully.")
```

---

## 10 Interview-Ready SQL Queries

### Q1: What is the campaign conversion rate?
```sql
SELECT 
    COUNT(*) AS total_customers,
    SUM(response) AS total_conversions,
    ROUND(SUM(response) * 100.0 / COUNT(*), 2) AS conversion_rate_pct
FROM campaign_responses;
```

### Q2: Which education level has the highest average spend?
```sql
SELECT 
    c.education,
    ROUND(AVG(s.total_spend), 2) AS avg_total_spend,
    COUNT(*) AS customer_count
FROM customers c
JOIN customer_spending s ON c.customer_id = s.customer_id
GROUP BY c.education
ORDER BY avg_total_spend DESC;
```

### Q3: Top 10% spenders — who are they?
```sql
WITH spend_ranked AS (
    SELECT 
        c.customer_id,
        c.age,
        c.education,
        c.income,
        s.total_spend,
        NTILE(10) OVER (ORDER BY s.total_spend DESC) AS spend_decile
    FROM customers c
    JOIN customer_spending s ON c.customer_id = s.customer_id
)
SELECT * FROM spend_ranked WHERE spend_decile = 1;
```

### Q4: Campaign ROI analysis — which campaign number performed best?
```sql
SELECT 
    'Campaign 1' AS campaign, SUM(campaign_1) AS accepted, 
    SUM(campaign_1) * 11 AS revenue, SUM(campaign_1) * 3 AS cost,
    ROUND((SUM(campaign_1) * 11 - SUM(campaign_1) * 3) * 100.0 / NULLIF(SUM(campaign_1) * 3, 0), 2) AS roi_pct
FROM campaign_responses
UNION ALL
SELECT 'Campaign 2', SUM(campaign_2), SUM(campaign_2)*11, SUM(campaign_2)*3,
    ROUND((SUM(campaign_2)*11 - SUM(campaign_2)*3)*100.0/NULLIF(SUM(campaign_2)*3,0),2) FROM campaign_responses
UNION ALL
SELECT 'Campaign 3', SUM(campaign_3), SUM(campaign_3)*11, SUM(campaign_3)*3,
    ROUND((SUM(campaign_3)*11 - SUM(campaign_3)*3)*100.0/NULLIF(SUM(campaign_3)*3,0),2) FROM campaign_responses
UNION ALL
SELECT 'Campaign 4', SUM(campaign_4), SUM(campaign_4)*11, SUM(campaign_4)*3,
    ROUND((SUM(campaign_4)*11 - SUM(campaign_4)*3)*100.0/NULLIF(SUM(campaign_4)*3,0),2) FROM campaign_responses
UNION ALL
SELECT 'Campaign 5', SUM(campaign_5), SUM(campaign_5)*11, SUM(campaign_5)*3,
    ROUND((SUM(campaign_5)*11 - SUM(campaign_5)*3)*100.0/NULLIF(SUM(campaign_5)*3,0),2) FROM campaign_responses;
```

### Q5: RFM scoring per customer
```sql
WITH rfm_base AS (
    SELECT 
        c.customer_id,
        e.recency,
        s.total_purchases AS frequency,
        s.total_spend AS monetary
    FROM customers c
    JOIN customer_engagement e ON c.customer_id = e.customer_id
    JOIN customer_spending s ON c.customer_id = s.customer_id
),
rfm_scored AS (
    SELECT *,
        NTILE(5) OVER (ORDER BY recency ASC) AS r_score,      -- lower recency = better
        NTILE(5) OVER (ORDER BY frequency DESC) AS f_score,
        NTILE(5) OVER (ORDER BY monetary DESC) AS m_score
    FROM rfm_base
)
SELECT *, (r_score + f_score + m_score) AS rfm_total FROM rfm_scored
ORDER BY rfm_total DESC;
```

### Q6: Customers at risk — high historical spend, not buying recently
```sql
SELECT 
    c.customer_id,
    c.age,
    c.income,
    s.total_spend,
    e.recency,
    cr.total_campaigns_accepted
FROM customers c
JOIN customer_spending s ON c.customer_id = s.customer_id
JOIN customer_engagement e ON c.customer_id = e.customer_id
JOIN campaign_responses cr ON c.customer_id = cr.customer_id
WHERE s.total_spend > 1000
  AND e.recency > 60
  AND cr.response = 0
ORDER BY s.total_spend DESC;
```

### Q7: Channel preference by customer segment
```sql
SELECT 
    CASE 
        WHEN s.total_spend > 1500 THEN 'VIP'
        WHEN s.total_spend > 500 THEN 'Loyal'
        WHEN e.recency > 60 THEN 'At Risk'
        ELSE 'New'
    END AS segment,
    ROUND(AVG(s.num_web_purchases), 2) AS avg_web,
    ROUND(AVG(s.num_catalog_purchases), 2) AS avg_catalog,
    ROUND(AVG(s.num_store_purchases), 2) AS avg_store,
    COUNT(*) AS count
FROM customers c
JOIN customer_spending s ON c.customer_id = s.customer_id
JOIN customer_engagement e ON c.customer_id = e.customer_id
GROUP BY segment;
```

### Q8: Revenue at risk from complainers
```sql
SELECT 
    cr.complain,
    COUNT(*) AS customers,
    ROUND(AVG(s.total_spend), 2) AS avg_spend,
    SUM(s.total_spend) AS total_revenue_at_risk
FROM customers cr
JOIN customer_spending s ON cr.customer_id = s.customer_id
GROUP BY cr.complain;
```

### Q9: Cumulative spend over customer tenure (window function)
```sql
SELECT 
    c.customer_id,
    c.dt_customer,
    s.total_spend,
    SUM(s.total_spend) OVER (ORDER BY c.dt_customer ROWS UNBOUNDED PRECEDING) AS cumulative_revenue
FROM customers c
JOIN customer_spending s ON c.customer_id = s.customer_id
ORDER BY c.dt_customer;
```

### Q10: Income vs spend correlation buckets
```sql
SELECT 
    CASE 
        WHEN c.income < 30000 THEN 'Low (<30K)'
        WHEN c.income < 60000 THEN 'Mid (30-60K)'
        WHEN c.income < 90000 THEN 'High (60-90K)'
        ELSE 'Very High (>90K)'
    END AS income_band,
    COUNT(*) AS customers,
    ROUND(AVG(s.total_spend), 2) AS avg_spend,
    ROUND(AVG(cr.response), 3) AS conversion_rate
FROM customers c
JOIN customer_spending s ON c.customer_id = s.customer_id
JOIN campaign_responses cr ON c.customer_id = cr.customer_id
GROUP BY income_band
ORDER BY avg_spend DESC;
```

---

## Complete Folder Structure

```
marketing-intelligence-system/
│
├── data/
│   ├── raw/
│   │   └── marketing_campaign.csv          ← original dataset
│   └── processed/
│       └── features.csv                    ← output from PySpark ETL
│
├── database/
│   ├── schema.sql                          ← all 4 CREATE TABLE queries
│   ├── load_data.py                        ← Python script to insert CSV into MySQL
│   └── queries/
│       ├── rfm_scoring.sql
│       ├── campaign_roi.sql
│       ├── customer_segments.sql
│       └── channel_analysis.sql
│
├── etl/
│   └── pyspark_etl.py                      ← PySpark feature engineering pipeline
│
├── ml/
│   ├── segmentation/
│   │   ├── kmeans_rfm.py                   ← Model 1: K-Means segmentation
│   │   └── segment_profiles.py             ← Describe each cluster
│   ├── ctr_prediction/
│   │   ├── train_ctr_model.py              ← Model 2: XGBoost CTR predictor
│   │   └── evaluate_ctr.py
│   └── conversion_prediction/
│       ├── train_conversion_model.py       ← Model 3: XGBoost/LightGBM
│       └── shap_analysis.py               ← SHAP explainability
│
├── models/
│   ├── kmeans_model.pkl
│   ├── xgb_ctr_model.pkl
│   └── xgb_conversion_model.pkl
│
├── api/
│   ├── main.py                             ← FastAPI app
│   ├── schemas.py                          ← Pydantic input/output models
│   └── predict.py                          ← Prediction logic
│
├── airflow/
│   └── dags/
│       └── marketing_pipeline.py           ← Nightly DAG
│
├── dashboard/
│   └── marketing_dashboard.pbix            ← Power BI file
│
├── notebooks/
│   ├── 01_eda.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_segmentation.ipynb
│   ├── 04_ctr_model.ipynb
│   └── 05_conversion_shap.ipynb
│
├── requirements.txt
├── .env                                    ← DB credentials (never commit)
├── .gitignore
└── README.md
```

---

## Tech Stack (Final Decision)

| Layer | Tool | Why |
|---|---|---|
| Database | MySQL | Industry standard, you know it, matches JDs |
| Data Engineering | PySpark | Scalability story in interviews |
| ML | scikit-learn, XGBoost, LightGBM | Industry standard |
| Explainability | SHAP | Business trust requirement |
| Pipeline | Apache Airflow | Production-grade automation |
| API | FastAPI | Fast, modern, async Python |
| Dashboard | Power BI | You already have experience |
| IDE | VS Code | With Python + Jupyter extensions |
| Version Control | Git + GitHub | Mandatory for portfolio |

---

## requirements.txt

```
pandas==2.1.4
numpy==1.26.2
scikit-learn==1.3.2
xgboost==2.0.2
lightgbm==4.1.0
shap==0.44.0
pyspark==3.5.0
fastapi==0.108.0
uvicorn==0.25.0
pydantic==2.5.3
mysql-connector-python==8.2.0
sqlalchemy==2.0.23
python-dotenv==1.0.0
matplotlib==3.8.2
seaborn==0.13.0
joblib==1.3.2
apache-airflow==2.8.0
```

---

## What Each Model Uses From This Dataset

### Model 1 — K-Means Segmentation
**Features:** Recency, total_purchases (frequency), total_spend (monetary) → RFM
**Output:** 4 clusters labeled as VIP / Loyal / At Risk / New

### Model 2 — Conversion Prediction (your main model)
**Label:** `Response` (0 or 1)
**Features:** age, income, total_spend, total_purchases, recency, num_web_visits_month, total_campaigns_accepted, education, total_children
**Note:** `Response = 1` is only ~15% of data → handle class imbalance with SMOTE (you know this from churn project)

### SHAP Output
For each prediction → which features pushed conversion probability up or down.
Example: "High income (+0.18), low recency (+0.14), complained before (-0.22)"

---

## Expected Project Outcomes

| Deliverable | What It Proves |
|---|---|
| 4 MySQL tables with FK constraints | Relational DB design + data modeling |
| 10 SQL queries (CTEs, window functions) | Analyst-level SQL |
| PySpark ETL pipeline | Big data / distributed computing |
| K-Means with RFM | Unsupervised ML + business segmentation |
| XGBoost conversion model (AUC > 0.80 expected) | Supervised ML + classification |
| SHAP waterfall plots | Model explainability |
| FastAPI with 2 endpoints | ML deployment |
| Airflow DAG | Pipeline automation |
| Power BI 3-page dashboard | Business communication |

---

## What You Say In Interviews

> "I built a Marketing Intelligence System using the IBM Marketing Campaign dataset.
> The pipeline starts with a normalized MySQL schema across 4 tables — customers, spending, engagement, and campaign responses.
> PySpark handles feature engineering at scale, producing RFM metrics and behavioral features.
> I built three models: K-Means for customer segmentation, and XGBoost for both campaign response prediction and conversion scoring.
> SHAP values explain every individual prediction for business stakeholders.
> The full pipeline is automated with Airflow and predictions are served via FastAPI.
> A Power BI dashboard gives the marketing team segment-level targeting recommendations and campaign ROI visibility."

**Total build time:** 5 weeks
**GitHub repo:** One clean repo, well-documented README, deployed FastAPI
