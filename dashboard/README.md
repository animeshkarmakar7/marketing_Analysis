# 📊 Marketing Intelligence Dashboard — Power BI Build Guide

> **This is the complete implementation blueprint for Phase 6.** It details the visual theme, data modeling, copy-pasteable DAX formulas, page layouts, and exact verification numbers to build the final `marketing_dashboard.pbix`.

---

## 🎨 Premium Visual Theme & Styling

To make this dashboard feel extremely premium and modern (inspired by glassmorphism and modern SaaS designs), apply the following styles:

* **Theme**: Sleek Dark Mode
* **Color Palette**:
  * **Page Background**: `#0F172A` (Deep Slate Blue)
  * **Card/Visual Background**: `#1E293B` (Slate Gray, 60% opacity with subtle borders `#334155`)
  * **Text Primary**: `#F8FAFC` (Ice White)
  * **Text Secondary**: `#94A3B8` (Cool Gray)
  * **Primary Metric (Conversions/VIP)**: `#6366F1` (Electric Indigo)
  * **Secondary Metric (ROI/Revenue)**: `#10B981` (Emerald Green)
  * **Complaints / Low Priority**: `#EF4444` (Vibrant Red)
  * **Warning / At Risk**: `#F59E0B` (Amber Gold)
* **Typography**:
  * **Headers**: `Segoe UI Semibold` or `Outfit`
  * **Values**: `Segoe UI Bold` or `DIN` (monospaced numbers look cleaner in cards)

---

## 🔌 Step 1: Connect Data Sources

In Power BI Desktop, you will load data from two sources to build a robust relational star schema:

### Source A: MySQL Database (Direct Connection)
1. Install the [MySQL ODBC Connector](https://dev.mysql.com/downloads/connector/odbc/) if you haven't already.
2. In Power BI, click **Get Data** -> **MySQL database**.
3. Server: `localhost:3306` | Database: `marketing_db`
4. Select all 4 tables: `customers`, `customer_spending`, `customer_engagement`, and `campaign_responses`.

### Source B: Processed ML Scores (CSV)
1. Click **Get Data** -> **Text/CSV**.
2. Select [dashboard_export.csv](file:///d:/DataScience/data/processed/dashboard_export.csv).
3. Change column data types if necessary (ensure `customer_id` is an Integer, and `conversion_probability` is a Decimal).

### Model View (Relationships)
In the Power BI **Model View**, set up the following relationships. Power BI should auto-detect most of them:
* `customers[customer_id]` (1) ─── (1) `customer_spending[customer_id]` (Active, 1-to-1)
* `customers[customer_id]` (1) ─── (1) `customer_engagement[customer_id]` (Active, 1-to-1)
* `customers[customer_id]` (1) ─── (1) `campaign_responses[customer_id]` (Active, 1-to-1)
* `customers[customer_id]` (1) ─── (1) `dashboard_export[customer_id]` (Active, 1-to-1)

---

## 🧮 Step 2: Create DAX Measures

Create a new table named `_Measures` to store all calculated metrics. Copy-paste these DAX formulas:

### Demographics & Engagement
```dax
Total Customers = COUNTROWS(customers)

Avg Age = AVERAGE(customers[age])

Avg Income = AVERAGE(customers[income])

Avg Recency = AVERAGE(customer_engagement[recency])
```

### Campaign Economics (Untargeted Baseline)
```dax
Baseline Revenue = SUM(campaign_responses[revenue_generated])

Baseline Cost = COUNTROWS(campaign_responses) * 3

Baseline Net Value = [Baseline Revenue] - [Baseline Cost]

Baseline ROI = DIVIDE([Baseline Net Value], [Baseline Cost], 0)
```

### ML-Optimized Economics (High Priority Only)
```dax
Targeted Customers = CALCULATE(
    COUNTROWS(dashboard_export), 
    dashboard_export[recommendation] = "HIGH PRIORITY"
)

Targeted Cost = [Targeted Customers] * 3

-- ML Model outputs a 63.8% precision at the 0.6 threshold
Targeted Expected Converts = SUMX(
    FILTER(dashboard_export, dashboard_export[recommendation] = "HIGH PRIORITY"),
    dashboard_export[conversion_probability]
)

Targeted Revenue = [Targeted Expected Converts] * 11

Targeted Net Value = [Targeted Revenue] - [Targeted Cost]

Targeted ROI = DIVIDE([Targeted Net Value], [Targeted Cost], 0)

-- Targeting Efficiency Outcomes
Cost Saved = [Baseline Cost] - [Targeted Cost]

Incremental ROI Lift = [Targeted ROI] - [Baseline ROI]
```

### Customer Segments & Risk
```dax
At Risk Count = CALCULATE(
    COUNTROWS(dashboard_export), 
    dashboard_export[segment] = "At Risk"
)

Revenue At Risk = CALCULATE(
    SUM(customer_spending[total_spend]), 
    dashboard_export[segment] = "At Risk"
)

Avg Conversion Probability = AVERAGE(dashboard_export[conversion_probability])
```

---

## 📋 Step 3: Page-by-Page Layout Guide

### 📱 PAGE 1: Executive Summary
*Focus: Compare historical untargeted campaigns against the ML-optimized targeting strategy.*

* **Header**: "Marketing Intelligence — Executive Summary"
* **Filters (Left Sidebar)**:
  * Dropdown: `Education`
  * Dropdown: `Marital Clean`
  * Slider: `Age`
* **KPI Cards (Top Row)**:
  * Total Customers: **2,240**
  * Overall Conversion Rate: **14.91%**
  * Baseline ROI: **-45.33%** (Format: Red/Amber)
  * ML-Targeted ROI: **132.74%** (Format: Emerald Green)
* **Dual Comparison Table / Card Set**:
  * **Baseline (Target Everyone)**: Cost: `$6,720` | Revenue: `$3,674` | Net Value: `-$3,046`
  * **ML-Targeted (High Priority Only)**: Cost: `$846` | Revenue: `$1,969` | Net Value: `$1,123`
* **Outcome Highlight Visual**:
  * Large Card: Cost Saved: **$5,874**
  * Large Card: ROI Increase: **+178%**
* **Chart**:
  * *Monthly Trend of Customer Acquisition*: Line Chart. X-axis: `Dt_Customer` (grouped by Year-Month), Y-axis: `Total Customers`.

---

### 📱 PAGE 2: Customer Intelligence
*Focus: Deep dive into customer behaviors, profiles, and K-Means segmentation results.*

* **KPI Cards (Top Row)**:
  * VIP Customers: **511** (Avg Conv Prob: **33.38%**)
  * At-Risk Customers: **541** (Revenue At Risk: **$622,343**)
* **Visuals**:
  * **Segment Distribution (Pie/Donut Chart)**:
    * Legend: `segment` (VIP, Loyal, At Risk, New)
    * Values: `Total Customers`
  * **Avg Conversion Probability by Segment (Clustered Column Chart)**:
    * X-axis: `segment`
    * Y-axis: `Avg Conversion Probability`
  * **Income vs Total Spend (Scatter Plot)**:
    * X-axis: `Income` (Filter out outliers > $150K)
    * Y-axis: `Total Spend`
    * Legend: `segment`
  * **Risk Profile Matrix (Table Visual)**:
    * Columns: `segment`, `Total Customers`, `Avg Spend`, `Avg Recency`, `Revenue At Risk`

---

### 📱 PAGE 3: Campaign Analytics
*Focus: Drill down into individual campaigns, response rates, and purchase channels.*

* **KPI Cards (Top Row)**:
  * Most Successful Campaign: **Campaign 4** (7.46% response)
  * Multi-Campaign Responders: **463** customers (Accepted >= 1 campaign)
* **Visuals**:
  * **Acceptance Rate by Campaign (Clustered Bar Chart)**:
    * Y-axis: Campaigns (Campaign 1, 2, 3, 4, 5, Latest Response)
    * X-axis: Response Rate % (e.g. 6.43%, 1.34%, 7.28%, 7.46%, 7.28%, 14.91%)
  * **Multi-Campaign Acceptance Count (Stacked Column Chart)**:
    * X-axis: Number of Campaigns Accepted (0 to 5)
    * Y-axis: Customer Count
    * Legend: `Education` (Graduation, PhD, etc.)
  * **Channel Usage by Segment (Matrix Visual)**:
    * Rows: `segment`
    * Columns: Value averages for `Web Purchases`, `Catalog Purchases`, `Store Purchases`, `Deals Purchases`
  * **Revenue vs Cost Waterfall Chart**:
    * Show how baseline cost accumulates vs baseline revenue resulting in a net loss, compared to how ML targeting targets only High Priority, resulting in a net profit.

---

## 🔍 Validation Checklist

Use these SQL/Python pre-calculated numbers to double-check that your Power BI relationships, DAX formulas, and filters are working correctly:

| Metric | Ground Truth Value | What it validates |
|---|---|---|
| **Total Customers** | `2,240` | Data load & relationships integrity |
| **Conversion Rate** | `14.91%` | Baseline conversion DAX measure |
| **Baseline Cost** | `$6,720.00` | Baseline cost calculation |
| **Baseline Revenue** | `$3,674.00` | Baseline revenue calculation |
| **VIP Count** | `511` | Segment assignments matching K-Means |
| **At Risk Spend** | `$622,343.00` | Revenue at risk calculations |
| **Campaign 3 Accepts**| `163` | Historical campaign joins |
| **Web purchases VIP** | `6.12` (avg) | Channel preference aggregation |
