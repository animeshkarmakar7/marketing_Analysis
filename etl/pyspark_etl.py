from __future__ import annotations

import argparse
import csv
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

try:
    from pyspark.sql import DataFrame, SparkSession
    from pyspark.sql import functions as F
except ModuleNotFoundError as exc:
    raise SystemExit(
        "PySpark is not installed in this Python environment. "
        "Install project dependencies first with: pip install -r requirements.txt"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "features.csv"
TEMP_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "_features_spark_output"
REFERENCE_YEAR = 2024

FEATURE_COLUMNS = [
    "customer_id",
    "age",
    "income",
    "total_spend",
    "total_purchases",
    "avg_spend_per_purchase",
    "web_purchase_ratio",
    "deal_sensitivity",
    "recency",
    "num_web_visits_month",
    "campaign_engagement_rate",
    "total_children",
    "has_children",
    "customer_tenure_days",
    "income_per_person",
    "education_rank",
    "marital_clean",
    "complain",
    "response",
]


def load_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def create_spark_session(app_name: str) -> SparkSession:
    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")
    )

    jdbc_jar = os.getenv("MYSQL_JDBC_JAR") or find_cached_mysql_jdbc_jar()
    if jdbc_jar:
        builder = (
            builder.config("spark.driver.extraClassPath", jdbc_jar)
            .config("spark.executor.extraClassPath", jdbc_jar)
        )
    else:
        builder = builder.config("spark.jars.packages", "com.mysql:mysql-connector-j:8.2.0")

    return builder.getOrCreate()


def find_cached_mysql_jdbc_jar() -> str | None:
    ivy_jars = Path.home() / ".ivy2" / "jars"
    matches = sorted(ivy_jars.glob("com.mysql_mysql-connector-j-*.jar"))
    return str(matches[-1]) if matches else None


def read_mysql_table(spark: SparkSession, table_name: str) -> DataFrame:
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    database = os.getenv("MYSQL_DATABASE", "marketing_db")
    user = get_required_env("MYSQL_USER")
    password = get_required_env("MYSQL_PASSWORD")
    jdbc_url = f"jdbc:mysql://{host}:{port}/{database}?useSSL=false&allowPublicKeyRetrieval=true"

    return (
        spark.read.format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", table_name)
        .option("user", user)
        .option("password", password)
        .option("driver", "com.mysql.cj.jdbc.Driver")
        .load()
    )


def safe_divide(numerator: F.Column, denominator: F.Column) -> F.Column:
    return F.when(denominator > 0, numerator / denominator).otherwise(F.lit(0.0))


def build_feature_table(
    customers: DataFrame,
    spending: DataFrame,
    engagement: DataFrame,
    campaigns: DataFrame,
) -> DataFrame:
    joined = (
        customers.alias("c")
        .join(spending.alias("s"), "customer_id", "inner")
        .join(engagement.alias("e"), "customer_id", "inner")
        .join(campaigns.alias("cr"), "customer_id", "inner")
    )

    features = (
        joined.withColumn("age", F.lit(REFERENCE_YEAR) - F.col("year_birth"))
        .withColumn("income", F.col("income").cast("double"))
        .withColumn("total_spend", F.col("total_spend").cast("double"))
        .withColumn("total_purchases", F.col("total_purchases").cast("double"))
        .withColumn(
            "avg_spend_per_purchase",
            safe_divide(F.col("total_spend"), F.col("total_purchases")),
        )
        .withColumn(
            "web_purchase_ratio",
            safe_divide(F.col("num_web_purchases"), F.col("total_purchases")),
        )
        .withColumn(
            "deal_sensitivity",
            safe_divide(F.col("num_deals_purchases"), F.col("total_purchases")),
        )
        .withColumn(
            "campaign_engagement_rate",
            F.col("total_campaigns_accepted") / F.lit(5.0),
        )
        .withColumn(
            "has_children",
            F.when(F.col("total_children") > 0, F.lit(1)).otherwise(F.lit(0)),
        )
        .withColumn(
            "customer_tenure_days",
            F.datediff(F.current_date(), F.col("dt_customer")),
        )
        .withColumn(
            "income_per_person",
            safe_divide(F.col("income"), F.lit(1) + F.col("total_children")),
        )
        .withColumn(
            "education_rank",
            F.when(F.col("education") == "Basic", F.lit(1))
            .when(F.col("education") == "2n Cycle", F.lit(2))
            .when(F.col("education") == "Graduation", F.lit(3))
            .when(F.col("education") == "Master", F.lit(4))
            .when(F.col("education") == "PhD", F.lit(5))
            .otherwise(F.lit(None)),
        )
        .withColumn("complain", F.col("complain").cast("int"))
        .withColumn("response", F.col("response").cast("int"))
    )

    return features.select(*FEATURE_COLUMNS).orderBy("customer_id")


def write_single_csv(features: DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    if TEMP_OUTPUT_DIR.exists():
        shutil.rmtree(TEMP_OUTPUT_DIR)

    # Avoid Hadoop's Windows-only winutils.exe dependency for local CSV writes.
    rows = features.collect()
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(features.columns)
        for row in rows:
            writer.writerow([row[column] for column in features.columns])


def run_etl(output_path: Path) -> None:
    load_environment()
    spark = create_spark_session("MarketingIntelligenceFeatureETL")

    try:
        customers = read_mysql_table(spark, "customers")
        spending = read_mysql_table(spark, "customer_spending")
        engagement = read_mysql_table(spark, "customer_engagement")
        campaigns = read_mysql_table(spark, "campaign_responses")

        features = build_feature_table(customers, spending, engagement, campaigns)
        row_count = features.count()
        write_single_csv(features, output_path)
        print(f"Wrote {row_count} feature rows to {output_path}")
    finally:
        spark.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PySpark feature engineering ETL.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output CSV path. Default: {DEFAULT_OUTPUT_PATH}",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_etl(args.output)


if __name__ == "__main__":
    main()
