"""
Marketing Intelligence System — Power BI KPI Verification Script
================================================================

Connects to MySQL and reads the processed dashboard data to pre-calculate
all KPIs, segment distributions, and campaign metrics. Use these numbers
to validate your Power BI DAX measures and visuals.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

DASHBOARD_CSV = PROJECT_ROOT / "data" / "processed" / "dashboard_export.csv"


def get_mysql_connection():
    import mysql.connector
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "marketing_db"),
    )


def calculate_kpis():
    print("=" * 60)
    print("           POWER BI KPI VERIFICATION REPORT")
    print("=" * 60)

    # 1. Load data
    if not DASHBOARD_CSV.exists():
        print(f"Error: {DASHBOARD_CSV} not found. Run the pipeline first: python airflow/run_pipeline.py --all")
        sys.exit(1)

    df = pd.read_csv(DASHBOARD_CSV)
    
    # Connect to MySQL to pull historical campaigns
    conn = get_mysql_connection()
    campaign_df = pd.read_sql("SELECT customer_id, campaign_1, campaign_2, campaign_3, campaign_4, campaign_5 FROM campaign_responses", conn)
    conn.close()

    # Merge for complete campaign reporting
    df_merged = df.merge(campaign_df, on="customer_id", how="left")

    total_customers = len(df_merged)
    actual_conversions = int(df_merged["response"].sum())
    conversion_rate = (actual_conversions / total_customers) * 100

    # Economics
    z_cost = 3
    z_rev = 11
    total_cost = total_customers * z_cost
    total_revenue = actual_conversions * z_rev
    net_roi = total_revenue - total_cost
    roi_pct = (net_roi / total_cost) * 100

    # -------------------------------------------------------------
    # Page 1 — Executive Summary KPIs
    # -------------------------------------------------------------
    print("\n--- PAGE 1: EXECUTIVE SUMMARY KPIs ---")
    print(f"Total Customers           : {total_customers:,}")
    print(f"Overall Conversion Rate   : {conversion_rate:.2f}%")
    print(f"Total Campaign Cost (C)   : ${total_cost:,.2f}  (Formula: Count * $3)")
    print(f"Total Revenue (R)         : ${total_revenue:,.2f}  (Formula: Converts * $11)")
    print(f"Net ROI (R - C)           : ${net_roi:,.2f}")
    print(f"ROI Percentage            : {roi_pct:.2f}%")

    # -------------------------------------------------------------
    # Page 2 — Customer Intelligence KPIs
    # -------------------------------------------------------------
    print("\n--- PAGE 2: CUSTOMER INTELLIGENCE ---")
    
    print("\nSegment Distribution:")
    seg_counts = df_merged["segment"].value_counts()
    seg_pct = df_merged["segment"].value_counts(normalize=True) * 100
    for seg in sorted(seg_counts.index):
        count = seg_counts[seg]
        pct = seg_pct[seg]
        avg_prob = df_merged[df_merged["segment"] == seg]["conversion_probability"].mean() * 100
        print(f"  Segment {seg:<12}: {count:,} ({pct:.2f}%) | Avg Conv Prob: {avg_prob:.2f}%")

    # At-risk Revenue and Count
    at_risk_df = df_merged[df_merged["segment"] == "At Risk"]
    at_risk_count = len(at_risk_df)
    at_risk_spend = at_risk_df["total_spend"].sum()
    print(f"\nAt-Risk Customers Count   : {at_risk_count:,}")
    print(f"Revenue At-Risk (Spend)   : ${at_risk_spend:,.2f}")

    # -------------------------------------------------------------
    # Page 3 — Campaign Analytics KPIs
    # -------------------------------------------------------------
    print("\n--- PAGE 3: CAMPAIGN ANALYTICS ---")
    
    # Campaign acceptance rates
    print("\nCampaign Acceptance Rates:")
    campaigns = ["campaign_1", "campaign_2", "campaign_3", "campaign_4", "campaign_5", "response"]
    campaign_labels = {
        "campaign_1": "Campaign 1",
        "campaign_2": "Campaign 2",
        "campaign_3": "Campaign 3",
        "campaign_4": "Campaign 4",
        "campaign_5": "Campaign 5",
        "response": "Campaign 6 (Latest)"
    }
    for cmp in campaigns:
        accepts = int(df_merged[cmp].sum())
        rate = (accepts / total_customers) * 100
        # Cost-revenue metrics per campaign
        cost = total_customers * 3
        rev = accepts * 11
        net = rev - cost
        roi = (net / cost) * 100
        label = campaign_labels[cmp]
        print(f"  {label:<20}: {accepts:,} accepts | Rate: {rate:.2f}% | ROI: {roi:.2f}%")

    # Responded to multiple campaigns
    print("\nResponded to Multiple Campaigns (out of Campaign 1-5):")
    df_merged["cmp_count"] = (
        df_merged["campaign_1"] + 
        df_merged["campaign_2"] + 
        df_merged["campaign_3"] + 
        df_merged["campaign_4"] + 
        df_merged["campaign_5"]
    )
    multi_counts = df_merged["cmp_count"].value_counts().sort_index()
    for count, customers in multi_counts.items():
        pct = (customers / total_customers) * 100
        print(f"  Accepted {count} campaigns: {customers:,} customers ({pct:.2f}%)")

    # Channel preferences by segment
    print("\nChannel Preference (Average Purchases by Segment):")
    channels = ["num_web_purchases", "num_catalog_purchases", "num_store_purchases", "num_deals_purchases"]
    
    # Load spending fields from DB to verify raw counts
    conn = get_mysql_connection()
    spend_db_df = pd.read_sql("SELECT customer_id, num_web_purchases, num_catalog_purchases, num_store_purchases, num_deals_purchases FROM customer_spending", conn)
    conn.close()
    
    df_channels = df_merged[["customer_id", "segment"]].merge(spend_db_df, on="customer_id", how="left")
    channel_summary = df_channels.groupby("segment")[channels].mean()
    print(channel_summary.round(2).to_string())

    print("=" * 60)


if __name__ == "__main__":
    calculate_kpis()
