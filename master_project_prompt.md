# MASTER PROJECT PROMPT
# Marketing Intelligence System — End to End Build

---

## USE THIS PROMPT AT THE START OF EVERY NEW CONVERSATION

Paste this entire prompt whenever you start a new chat session for this project.
It will give the AI full context so you never have to re-explain anything.

---

## WHO I AM

I am Animesh Karmakar, a final-year B.E. student in Artificial Intelligence & Data Science
at Terna Engineering College, Mumbai University. I am building this project as a portfolio
piece for fresher Data Analyst / AI-ML Engineer roles at companies like Deloitte, IBM,
Fractal, Sigmoid, and EXL.

I work in VS Code on Windows. My database is MySQL (local). I write Python.
I am comfortable with scikit-learn, XGBoost, SHAP, and Power BI from previous projects.

---

## WHAT THIS PROJECT IS

**Project Name:** Marketing Intelligence System

**One-line description:**
An end-to-end data science and engineering system that helps a marketing team decide
which customers to target, which campaigns to run, and where to allocate budget —
using real customer behavior data, machine learning predictions, and automated pipelines.

**Business problem being solved:**
A company runs 5 marketing campaigns across its customer base.
The problems are:
- They contact every customer with every campaign, wasting budget
- They don't know which customers are most likely to respond
- They can't explain WHY a customer was targeted
- Campaign ROI is unknown and unoptimized
- No automation — everything is manual

**What the system delivers:**
1. Customer segments (VIP / Loyal / At Risk / New) using RFM analysis
2. A conversion prediction model — probability each customer will accept the next campaign
3. SHAP-based explanation for every prediction (why did the model say this?)
4. Campaign ROI analysis across all 5 historical campaigns
5. A Power BI dashboard for the marketing team
6. A FastAPI endpoint so other systems can call the model
7. An Airflow DAG that runs the full pipeline automatically every night

---

## DATASET

**File:** marketing_campaign.csv
**Source:** IBM Marketing Campaign dataset (public)
**Rows:** 2,240 customers
**Columns:** 29

**All 29 columns and what they mean:**

| Column | Type | Meaning |
|---|---|---|
| ID | int | Unique customer identifier |
| Year_Birth | int | Birth year → used to derive Age |
| Education | str | Graduation / PhD / Master / Basic / 2n Cycle |
| Marital_Status | str | Single / Together / Married / Divorced / Widow / Alone / Absurd / YOLO |
| Income | float | Annual income (24 nulls → fill with median) |
| Kidhome | int | Number of kids at home |
| Teenhome | int | Number of teenagers at home |
| Dt_Customer | str | Date customer joined (format: DD-MM-YYYY) |
| Recency | int | Days since last purchase (lower = more recent = better) |
| MntWines | int | Amount spent on wine in last 2 years |
| MntFruits | int | Amount spent on fruits |
| MntMeatProducts | int | Amount spent on meat |
| MntFishProducts | int | Amount spent on fish |
| MntSweetProducts | int | Amount spent on sweets |
| MntGoldProds | int | Amount spent on gold products |
| NumDealsPurchases | int | Purchases made with a discount |
| NumWebPurchases | int | Purchases via website |
| NumCatalogPurchases | int | Purchases via catalog |
| NumStorePurchases | int | Purchases in-store |
| NumWebVisitsMonth | int | Website visits per month |
| AcceptedCmp1 | int | 1 if accepted campaign 1, else 0 |
| AcceptedCmp2 | int | 1 if accepted campaign 2, else 0 |
| AcceptedCmp3 | int | 1 if accepted campaign 3, else 0 |
| AcceptedCmp4 | int | 1 if accepted campaign 4, else 0 |
| AcceptedCmp5 | int | 1 if accepted campaign 5, else 0 |
| Complain | int | 1 if customer complained in last 2 years |
| Z_CostContact | int | Fixed cost to contact a customer = 3 (constant) |
| Z_Revenue | int | Fixed revenue if customer converts = 11 (constant) |
| Response | int | TARGET LABEL — 1 if accepted last campaign, 0 if not |

**Critical data facts:**
- `Response` is the main prediction target (binary: 0 or 1)
- Only ~15% of customers have Response = 1 → severe class imbalance → must use SMOTE
- Marital_Status has junk values (YOLO, Absurd, Alone) → clean to: Single / Married / Divorced / Widow
- Income has 24 nulls → fill with median before anything else
- Z_CostContact = 3 and Z_Revenue = 11 are constants for all rows
- Net value per conversion = 11 - 3 = 8 (this is the business ROI basis)

---

## TECH STACK (FULL)

| Layer | Technology | Purpose |
|---|---|---|
| IDE | VS Code | All Python development |
| Database | MySQL (local) | Store raw data in normalized tables |
| Data Engineering | PySpark | Feature engineering at scale |
| Machine Learning | scikit-learn, XGBoost, LightGBM | Segmentation + prediction models |
| Imbalance Handling | imbalanced-learn (SMOTE) | Fix the 85/15 class split |
| Explainability | SHAP | Explain individual predictions |
| Pipeline Automation | Apache Airflow | Nightly automated pipeline DAG |
| API | FastAPI + Uvicorn | Serve model predictions via REST |
| Dashboard | Power BI Desktop | Business-facing visual dashboard |
| Version Control | Git + GitHub | Portfolio and collaboration |
| Environment | Python 3.10+, venv | Clean dependency management |

**Python packages to install:**
```
pandas==2.1.4
numpy==1.26.2
scikit-learn==1.3.2
xgboost==2.0.2
lightgbm==4.1.0
imbalanced-learn==0.11.0
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

## MYSQL DATABASE DESIGN

**Database name:** `marketing_db`

**4 tables — normalized from the flat CSV:**

### Table 1: customers
Stores core customer identity and demographics.
Columns: customer_id, year_birth, age (generated), education, marital_status,
marital_clean (generated — maps junk values), income, kidhome, teenhome,
total_children (generated), dt_customer, complain

### Table 2: customer_spending
Stores all spend and purchase channel data per customer.
Columns: spending_id, customer_id (FK), mnt_wines, mnt_fruits, mnt_meat_products,
mnt_fish_products, mnt_sweet_products, mnt_gold_prods,
total_spend (generated), num_deals_purchases, num_web_purchases,
num_catalog_purchases, num_store_purchases, total_purchases (generated)

### Table 3: customer_engagement
Stores behavioral engagement metrics.
Columns: engagement_id, customer_id (FK), recency, num_web_visits_month

### Table 4: campaign_responses
Stores all campaign acceptance history and the target label.
Columns: response_id, customer_id (FK), campaign_1 through campaign_5,
response (TARGET), total_campaigns_accepted (generated),
z_cost_contact, z_revenue, revenue_generated (generated),
net_value (generated = response * 11 - 3)

---

## COMPLETE FOLDER STRUCTURE

```
marketing-intelligence-system/
│
├── data/
│   ├── raw/
│   │   └── marketing_campaign.csv
│   └── processed/
│       └── features.csv
│
├── database/
│   ├── schema.sql
│   ├── load_data.py
│   └── queries/
│       ├── rfm_scoring.sql
│       ├── campaign_roi.sql
│       ├── customer_segments.sql
│       └── channel_analysis.sql
│
├── etl/
│   └── pyspark_etl.py
│
├── ml/
│   ├── segmentation/
│   │   ├── kmeans_rfm.py
│   │   └── segment_profiles.py
│   ├── conversion_prediction/
│   │   ├── train_model.py
│   │   ├── evaluate_model.py
│   │   └── shap_analysis.py
│
├── models/
│   ├── kmeans_model.pkl
│   └── xgb_conversion_model.pkl
│
├── api/
│   ├── main.py
│   ├── schemas.py
│   └── predict.py
│
├── airflow/
│   └── dags/
│       └── marketing_pipeline.py
│
├── dashboard/
│   └── marketing_dashboard.pbix
│
├── notebooks/
│   ├── 01_eda.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_segmentation.ipynb
│   ├── 04_conversion_model.ipynb
│   └── 05_shap_explainability.ipynb
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

---

## WHAT EACH PHASE BUILDS

### Phase 1 — Database (Week 1)
**Goal:** Get data out of the flat CSV and into a proper relational MySQL database.

Steps:
1. Write schema.sql with all 4 tables and foreign keys
2. Write load_data.py to read the CSV and INSERT into MySQL
3. Write 10 SQL queries covering: CTEs, window functions, UNION, aggregations
4. Queries must answer real business questions:
   - Campaign ROI by campaign number
   - Top 10% spenders by income band
   - At-risk customers (high spend, high recency, no recent conversion)
   - RFM scoring with NTILE window function
   - Channel preference by customer type

**Deliverable:** Working MySQL database with data loaded + 10 saved SQL queries

---

### Phase 2 — PySpark ETL (Week 2)
**Goal:** Build a scalable feature engineering pipeline.

**Input:** Read 4 MySQL tables via JDBC connector
**Output:** Write a clean feature table (features.csv or back into MySQL)

**Features to engineer:**

| Feature | Formula |
|---|---|
| age | 2024 - Year_Birth |
| total_spend | sum of all Mnt columns |
| total_purchases | sum of all Num purchases |
| avg_spend_per_purchase | total_spend / total_purchases |
| web_purchase_ratio | num_web_purchases / total_purchases |
| deal_sensitivity | num_deals_purchases / total_purchases |
| campaign_engagement_rate | total_campaigns_accepted / 5 |
| customer_tenure_days | today - dt_customer |
| has_children | 1 if kidhome + teenhome > 0 |
| income_per_person | income / (1 + kidhome + teenhome) |
| marital_clean | Single / Married / Divorced / Widow (cleaned) |
| education_rank | ordinal: Basic=1, 2nCycle=2, Graduation=3, Master=4, PhD=5 |

**Deliverable:** pyspark_etl.py that reads MySQL → transforms → writes features.csv

---

### Phase 3 — Machine Learning (Week 3)

#### Model 1: Customer Segmentation (K-Means)
**Algorithm:** KMeans (k=4)
**Input features:** recency, total_purchases, total_spend (RFM)
**Preprocessing:** StandardScaler before fitting
**Output:** Segment label per customer

Segment definitions based on cluster centroids:
- VIP → low recency, high frequency, high monetary
- Loyal → moderate recency, moderate frequency, moderate monetary
- At Risk → high recency, low recent activity, was previously good
- New → very recent join date, low history

Use Elbow Method to justify k=4.
Save segment assignments back to MySQL (add `segment` column to customers table).

#### Model 2: Conversion Prediction (XGBoost)
**Target:** Response (0 or 1)
**Input features:** age, income, total_spend, total_purchases, recency,
num_web_visits_month, campaign_engagement_rate, education_rank,
total_children, web_purchase_ratio, deal_sensitivity, customer_tenure_days
**Class imbalance fix:** SMOTE on training set only (never on test set)
**Evaluation metrics:** AUC-ROC, Precision, Recall, F1, Confusion Matrix
**Expected AUC:** > 0.78

Hyperparameter tuning: GridSearchCV or Optuna
Save trained model as: models/xgb_conversion_model.pkl

#### SHAP Explainability
Run SHAP on the conversion model.
Generate:
- Summary plot (global feature importance)
- Waterfall plot for individual customer predictions
- Force plot for top 5 high-probability customers

**Business output example:**
```
Customer #5524 — Conversion Probability: 81%

Pushing probability UP:
+ High total_spend (+0.22)
+ Low recency — bought recently (+0.18)
+ High campaign_engagement_rate (+0.14)

Pushing probability DOWN:
- Has children (-0.08)
- Low web visits (-0.05)
```

**Deliverable:** Trained pkl models + SHAP plots saved as PNG in models/ folder

---

### Phase 4 — FastAPI (Week 4, Part 1)

**File:** api/main.py

Two endpoints:

**POST /predict-conversion**
Input:
```json
{
  "age": 45,
  "income": 58000,
  "total_spend": 1200,
  "total_purchases": 18,
  "recency": 30,
  "num_web_visits_month": 6,
  "campaign_engagement_rate": 0.4,
  "education_rank": 3,
  "total_children": 0,
  "web_purchase_ratio": 0.5,
  "deal_sensitivity": 0.1,
  "customer_tenure_days": 900
}
```
Output:
```json
{
  "conversion_probability": 0.81,
  "recommendation": "HIGH PRIORITY — target this customer",
  "segment": "VIP"
}
```

**GET /health**
Returns API status.

Run with: `uvicorn api.main:app --reload`

**Deliverable:** Working FastAPI app, testable via browser at localhost:8000/docs

---

### Phase 5 — Airflow DAG (Week 4, Part 2)

**File:** airflow/dags/marketing_pipeline.py

DAG runs every night at 2:00 AM.

```
Task 1: extract_mysql_data
   ↓ Pull latest data from MySQL
Task 2: pyspark_feature_engineering
   ↓ Run pyspark_etl.py
Task 3: score_customers
   ↓ Load xgb_conversion_model.pkl → predict on all customers → save scores
Task 4: update_segments
   ↓ Re-run KMeans → update segment labels in MySQL
Task 5: refresh_dashboard_data
   ↓ Export scored CSV for Power BI auto-refresh
```

**Deliverable:** Working DAG visible in Airflow UI at localhost:8080

---

### Phase 6 — Power BI Dashboard (Week 5)

**Connect to:** MySQL database directly (use MySQL ODBC connector)
**Also import:** features.csv with model scores and segment labels

**3 pages:**

Page 1 — Executive Summary
- Total customers: 2,240
- Overall conversion rate: ~15%
- Total revenue from conversions (Response=1 × 11)
- Total campaign cost (2240 × 3)
- Net ROI
- Monthly trend of customer acquisition (Dt_Customer)

Page 2 — Customer Intelligence
- Segment distribution: pie chart (VIP / Loyal / At Risk / New)
- Avg conversion probability by segment: bar chart
- Income vs Total Spend: scatter plot colored by segment
- At-risk customers count with revenue at risk (total_spend of at-risk customers)

Page 3 — Campaign Analytics
- Acceptance rate by campaign (Cmp1–Cmp5): bar chart
- Who responded to multiple campaigns: stacked bar by education
- Channel preference by segment: web vs catalog vs store
- Revenue vs Cost: waterfall chart showing net ROI

**Deliverable:** marketing_dashboard.pbix with 3 pages, all KPIs validated against SQL

---

## ENGINEERED FEATURES REFERENCE TABLE

This is the exact list of features that go into the ML models.
Always use this as the source of truth.

| Feature Name | Source Columns | Formula | Use in Model |
|---|---|---|---|
| age | Year_Birth | 2024 - Year_Birth | Conversion |
| income | Income | fill nulls with median | Conversion |
| total_spend | Mnt* (6 cols) | sum of all 6 | Both |
| total_purchases | Num*Purchases (4 cols) | sum of all 4 | Both |
| avg_spend_per_purchase | total_spend, total_purchases | total_spend / total_purchases | Conversion |
| web_purchase_ratio | NumWebPurchases, total_purchases | web / total | Conversion |
| deal_sensitivity | NumDealsPurchases, total_purchases | deals / total | Conversion |
| recency | Recency | direct | Both |
| num_web_visits_month | NumWebVisitsMonth | direct | Conversion |
| campaign_engagement_rate | AcceptedCmp1-5 | sum / 5 | Conversion |
| total_children | Kidhome + Teenhome | direct sum | Both |
| has_children | total_children | 1 if > 0 else 0 | Segmentation |
| customer_tenure_days | Dt_Customer | (today - Dt_Customer).days | Conversion |
| income_per_person | Income, total_children | income / (1 + children) | Conversion |
| education_rank | Education | Basic=1, 2nCycle=2, Grad=3, Master=4, PhD=5 | Conversion |
| marital_clean | Marital_Status | Single/Married/Divorced/Widow | Conversion |
| complain | Complain | direct | Conversion |

---

## BUSINESS OUTCOMES TO QUANTIFY

These are the numbers you state in interviews. Calculate them from actual model results.

1. **Targeting efficiency improvement:**
   "By targeting only customers with conversion probability > 0.6,
   we contact X% of customers but capture Y% of all conversions.
   This saves ₹Z in contact costs."

2. **Campaign ROI:**
   "Campaign 3 had the highest acceptance rate of X%.
   At Z_CostContact=3 and Z_Revenue=11, ROI = ((accepts × 8) / (total_customers × 3)) × 100%"

3. **At-risk revenue:**
   "Customers in the At Risk segment represent ₹X in historical spend.
   Win-back campaigns targeting this segment have a Y% conversion probability."

4. **Model precision:**
   "At a 0.6 probability threshold, the model achieves X% precision —
   meaning X out of every 10 customers we target actually convert."

---

## WHAT I HAVE ALREADY BUILT (PREVIOUS PROJECTS — FOR CONTEXT)

Do not rebuild these. They are only context for my skill level.

1. **Customer Churn Prediction** (GitHub: animeshkarmakar7/CustomerChurnReport)
   - IBM Telco dataset
   - Used SMOTE, GridSearchCV, SHAP, XGBoost
   - Built Power BI dashboard with DAX — AUC-ROC 0.8398
   - Calculated 274% retention ROI business case

2. **SANGRAHAK** (GitHub: ShewaleParth/AI-Based-Inevtnory-Control-and-Depot-Management)
   - MERN + Flask + Docker + AWS EC2
   - ARIMA demand forecasting, XGBoost classifier, Random Forest
   - Deployed live on EC2

I am familiar with: SMOTE, SHAP, XGBoost, Power BI DAX, FastAPI basics, Docker basics.
I am learning: PySpark, Airflow, production ML pipelines.

---

## HOW TO USE THIS PROMPT

When starting a new session, paste this full prompt and then add your specific request.

Examples:

> [paste this prompt]
> Now write the complete schema.sql file with all 4 MySQL tables.

> [paste this prompt]
> Now write pyspark_etl.py — the full PySpark feature engineering script
> that reads from MySQL and outputs features.csv

> [paste this prompt]
> Now write train_model.py — the XGBoost conversion prediction model
> with SMOTE, GridSearchCV, and model evaluation.

> [paste this prompt]
> Now write the FastAPI main.py with /predict-conversion and /health endpoints.

> [paste this prompt]
> I got this error while running pyspark_etl.py: [paste error]
> Fix it without changing the overall structure.

> [paste this prompt]
> Now write the Airflow DAG file with all 5 tasks.

---

## CURRENT BUILD STATUS

Update this section as you complete each phase.

- [ ] Phase 1: MySQL database + schema + load_data.py + 10 SQL queries
- [ ] Phase 2: PySpark ETL pipeline
- [ ] Phase 3: K-Means segmentation model
- [ ] Phase 3: XGBoost conversion model + SHAP
- [x] Phase 4: FastAPI endpoints  ← DONE (3 endpoints: /health, /predict-conversion, /predict-conversion/batch)
- [ ] Phase 4: Airflow DAG
- [ ] Phase 5: Power BI dashboard
- [ ] Final: README.md + GitHub push + documentation

---

*Project: Marketing Intelligence System | Developer: Animesh Karmakar | Stack: MySQL + PySpark + XGBoost + SHAP + FastAPI + Airflow + Power BI*
