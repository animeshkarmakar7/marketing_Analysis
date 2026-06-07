from __future__ import annotations

import argparse
import os
from pathlib import Path

import mysql.connector
import pandas as pd
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "raw" / "marketing_campaign.csv"

REQUIRED_COLUMNS = {
    "ID",
    "Year_Birth",
    "Education",
    "Marital_Status",
    "Income",
    "Kidhome",
    "Teenhome",
    "Dt_Customer",
    "Recency",
    "MntWines",
    "MntFruits",
    "MntMeatProducts",
    "MntFishProducts",
    "MntSweetProducts",
    "MntGoldProds",
    "NumDealsPurchases",
    "NumWebPurchases",
    "NumCatalogPurchases",
    "NumStorePurchases",
    "NumWebVisitsMonth",
    "AcceptedCmp1",
    "AcceptedCmp2",
    "AcceptedCmp3",
    "AcceptedCmp4",
    "AcceptedCmp5",
    "Complain",
    "Z_CostContact",
    "Z_Revenue",
    "Response",
}


def get_connection():
    load_dotenv(PROJECT_ROOT / ".env")
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "marketing_db"),
    )


def read_marketing_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, sep="\t")
    missing_columns = REQUIRED_COLUMNS.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"CSV is missing required columns: {missing}")

    df["Income"] = df["Income"].fillna(df["Income"].median())
    df["Dt_Customer"] = pd.to_datetime(df["Dt_Customer"], dayfirst=True).dt.date
    return df


def reset_tables(cursor) -> None:
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in (
        "campaign_responses",
        "customer_engagement",
        "customer_spending",
        "customers",
    ):
        cursor.execute(f"TRUNCATE TABLE {table}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def load_dataframe(df: pd.DataFrame, reset: bool) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    if reset:
        reset_tables(cursor)

    customer_sql = """
        INSERT INTO customers (
            customer_id, year_birth, education, marital_status, income,
            kidhome, teenhome, dt_customer, complain
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            year_birth = VALUES(year_birth),
            education = VALUES(education),
            marital_status = VALUES(marital_status),
            income = VALUES(income),
            kidhome = VALUES(kidhome),
            teenhome = VALUES(teenhome),
            dt_customer = VALUES(dt_customer),
            complain = VALUES(complain)
    """

    spending_sql = """
        INSERT INTO customer_spending (
            customer_id, mnt_wines, mnt_fruits, mnt_meat_products,
            mnt_fish_products, mnt_sweet_products, mnt_gold_prods,
            num_deals_purchases, num_web_purchases, num_catalog_purchases,
            num_store_purchases
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            mnt_wines = VALUES(mnt_wines),
            mnt_fruits = VALUES(mnt_fruits),
            mnt_meat_products = VALUES(mnt_meat_products),
            mnt_fish_products = VALUES(mnt_fish_products),
            mnt_sweet_products = VALUES(mnt_sweet_products),
            mnt_gold_prods = VALUES(mnt_gold_prods),
            num_deals_purchases = VALUES(num_deals_purchases),
            num_web_purchases = VALUES(num_web_purchases),
            num_catalog_purchases = VALUES(num_catalog_purchases),
            num_store_purchases = VALUES(num_store_purchases)
    """

    engagement_sql = """
        INSERT INTO customer_engagement (
            customer_id, recency, num_web_visits_month
        )
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            recency = VALUES(recency),
            num_web_visits_month = VALUES(num_web_visits_month)
    """

    campaign_sql = """
        INSERT INTO campaign_responses (
            customer_id, campaign_1, campaign_2, campaign_3, campaign_4,
            campaign_5, response, z_cost_contact, z_revenue
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            campaign_1 = VALUES(campaign_1),
            campaign_2 = VALUES(campaign_2),
            campaign_3 = VALUES(campaign_3),
            campaign_4 = VALUES(campaign_4),
            campaign_5 = VALUES(campaign_5),
            response = VALUES(response),
            z_cost_contact = VALUES(z_cost_contact),
            z_revenue = VALUES(z_revenue)
    """

    try:
        for row in df.itertuples(index=False):
            cursor.execute(
                customer_sql,
                (
                    int(row.ID),
                    int(row.Year_Birth),
                    row.Education,
                    row.Marital_Status,
                    float(row.Income),
                    int(row.Kidhome),
                    int(row.Teenhome),
                    row.Dt_Customer,
                    int(row.Complain),
                ),
            )
            cursor.execute(
                spending_sql,
                (
                    int(row.ID),
                    int(row.MntWines),
                    int(row.MntFruits),
                    int(row.MntMeatProducts),
                    int(row.MntFishProducts),
                    int(row.MntSweetProducts),
                    int(row.MntGoldProds),
                    int(row.NumDealsPurchases),
                    int(row.NumWebPurchases),
                    int(row.NumCatalogPurchases),
                    int(row.NumStorePurchases),
                ),
            )
            cursor.execute(
                engagement_sql,
                (
                    int(row.ID),
                    int(row.Recency),
                    int(row.NumWebVisitsMonth),
                ),
            )
            cursor.execute(
                campaign_sql,
                (
                    int(row.ID),
                    int(row.AcceptedCmp1),
                    int(row.AcceptedCmp2),
                    int(row.AcceptedCmp3),
                    int(row.AcceptedCmp4),
                    int(row.AcceptedCmp5),
                    int(row.Response),
                    int(row.Z_CostContact),
                    int(row.Z_Revenue),
                ),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load marketing campaign CSV into MySQL.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"Path to marketing_campaign.csv. Default: {DEFAULT_CSV_PATH}",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate Phase 1 tables before loading.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = read_marketing_csv(args.csv)
    load_dataframe(df, reset=args.reset)
    print(f"Loaded {len(df)} customers into marketing_db.")


if __name__ == "__main__":
    main()
