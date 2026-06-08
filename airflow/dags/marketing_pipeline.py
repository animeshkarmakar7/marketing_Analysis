"""
Marketing Intelligence System — Airflow DAG
============================================

Nightly pipeline that runs at 02:00 AM every day.

Pipeline tasks (in order):
    1. validate_mysql_connection  — ping MySQL, assert 4 tables × 2240 rows
    2. pyspark_feature_engineering — run pyspark_etl.py → features.csv
    3. score_customers            — load XGB model, score all customers
    4. update_segments            — re-run KMeans, write segment column to MySQL
    5. refresh_dashboard_data     — merge scores + segments → final Power BI CSV

Run interactively (test without scheduler):
    airflow dags test marketing_pipeline 2024-01-01

Trigger manually:
    airflow dags trigger marketing_pipeline

View logs:
    airflow tasks logs marketing_pipeline <task_id> <execution_date>
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # airflow/dags/ → project root
FEATURES_PATH = PROJECT_ROOT / "data" / "processed" / "features.csv"
SEGMENTS_PATH = PROJECT_ROOT / "data" / "processed" / "customer_segments.csv"
SCORES_PATH = PROJECT_ROOT / "data" / "processed" / "conversion_scores.csv"
DASHBOARD_PATH = PROJECT_ROOT / "data" / "processed" / "dashboard_export.csv"
MODELS_DIR = PROJECT_ROOT / "models"
ETL_SCRIPT = PROJECT_ROOT / "etl" / "pyspark_etl.py"
KMEANS_SCRIPT = PROJECT_ROOT / "ml" / "segmentation" / "kmeans_rfm.py"
UPDATE_SEG_SCRIPT = PROJECT_ROOT / "ml" / "segmentation" / "update_segments_mysql.py"
TRAIN_SCRIPT = PROJECT_ROOT / "ml" / "conversion_prediction" / "train_model.py"
ENV_FILE = PROJECT_ROOT / ".env"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log = logging.getLogger("marketing_pipeline")

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _load_env() -> None:
    """Load .env into os.environ so all sub-tasks can read DB credentials."""
    if ENV_FILE.exists():
        from dotenv import load_dotenv  # type: ignore[import]
        load_dotenv(ENV_FILE, override=True)


def _run_script(script_path: Path, extra_args: list[str] | None = None) -> int:
    """
    Run a Python script in a subprocess using the same interpreter that
    is running Airflow.  Streams stdout/stderr to the task log in real time.
    Returns the exit code.
    """
    cmd = [sys.executable, str(script_path)] + (extra_args or [])
    log.info("Running: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    for line in proc.stdout:  # type: ignore[union-attr]
        log.info(line.rstrip())
    proc.wait()
    return proc.returncode


def _assert_file(path: Path, label: str) -> None:
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Expected output missing or empty: {label} → {path}")
    log.info("Verified: %s (%d bytes)", label, path.stat().st_size)


# ---------------------------------------------------------------------------
# Task 1 — Validate MySQL connection + row counts
# ---------------------------------------------------------------------------


def validate_mysql_connection(**context) -> dict:
    """
    Ping the MySQL marketing_db and assert all 4 tables have rows.
    Pushes a summary dict via XCom for downstream tasks.
    """
    _load_env()
    import mysql.connector  # type: ignore[import]

    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "marketing_db"),
    )
    cursor = conn.cursor()

    tables = [
        "customers",
        "customer_spending",
        "customer_engagement",
        "campaign_responses",
    ]
    counts = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
        row_count = cursor.fetchone()[0]
        counts[table] = row_count
        log.info("Table %-30s → %d rows", table, row_count)
        if row_count == 0:
            raise ValueError(f"Table '{table}' is empty — pipeline aborted.")

    cursor.close()
    conn.close()

    summary = {"table_counts": counts, "run_timestamp": datetime.utcnow().isoformat()}
    log.info("MySQL validation passed. Summary: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Task 2 — PySpark feature engineering
# ---------------------------------------------------------------------------


def pyspark_feature_engineering(**context) -> dict:
    """
    Run pyspark_etl.py which reads the 4 MySQL tables via JDBC,
    engineers all features, and writes data/processed/features.csv.
    """
    _load_env()

    exit_code = _run_script(
        ETL_SCRIPT,
        extra_args=["--output", str(FEATURES_PATH)],
    )
    if exit_code != 0:
        raise RuntimeError(f"PySpark ETL failed with exit code {exit_code}")

    _assert_file(FEATURES_PATH, "features.csv")

    import pandas as pd  # type: ignore[import]

    df = pd.read_csv(FEATURES_PATH)
    row_count = len(df)
    col_count = len(df.columns)
    log.info("features.csv: %d rows × %d columns", row_count, col_count)

    return {"feature_rows": row_count, "feature_columns": col_count}


# ---------------------------------------------------------------------------
# Task 3 — Score all customers with XGBoost model
# ---------------------------------------------------------------------------


def score_customers(**context) -> dict:
    """
    Load the trained XGBoost pipeline from models/xgb_conversion_model.pkl,
    run inference on features.csv, and write data/processed/conversion_scores.csv.

    If the model file is missing (first ever run), trains it first.
    """
    _load_env()
    import joblib  # type: ignore[import]
    import pandas as pd  # type: ignore[import]

    model_path = MODELS_DIR / "xgb_conversion_model.pkl"

    # ── Train if model doesn't exist yet ──────────────────────────────────
    if not model_path.exists():
        log.warning("Model not found — running train_model.py first.")
        rc = _run_script(TRAIN_SCRIPT)
        if rc != 0:
            raise RuntimeError("train_model.py failed.")

    _assert_file(model_path, "xgb_conversion_model.pkl")
    _assert_file(FEATURES_PATH, "features.csv")

    # ── Column lists (must match train_model.py) ───────────────────────────
    NUMERIC_FEATURES = [
        "age", "income", "total_spend", "total_purchases",
        "avg_spend_per_purchase", "recency", "num_web_visits_month",
        "campaign_engagement_rate", "education_rank", "total_children",
        "has_children", "web_purchase_ratio", "deal_sensitivity",
        "customer_tenure_days", "income_per_person", "complain",
    ]
    CATEGORICAL_FEATURES = ["marital_clean"]

    df = pd.read_csv(FEATURES_PATH)
    pipeline = joblib.load(model_path)

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    probabilities = pipeline.predict_proba(X)[:, 1]

    scored = df[["customer_id", "response"]].copy()
    scored["conversion_probability"] = probabilities
    scored["recommendation"] = pd.cut(
        scored["conversion_probability"],
        bins=[-0.01, 0.3, 0.6, 1.01],
        labels=["LOW PRIORITY", "MEDIUM PRIORITY", "HIGH PRIORITY"],
    ).astype(str)

    scored.to_csv(SCORES_PATH, index=False)
    _assert_file(SCORES_PATH, "conversion_scores.csv")

    high = int((scored["recommendation"] == "HIGH PRIORITY").sum())
    med  = int((scored["recommendation"] == "MEDIUM PRIORITY").sum())
    low  = int((scored["recommendation"] == "LOW PRIORITY").sum())

    log.info(
        "Scoring complete — HIGH: %d | MEDIUM: %d | LOW: %d | Total: %d",
        high, med, low, len(scored),
    )

    # ── Compute business ROI metrics ───────────────────────────────────────
    z_revenue = 11
    z_cost    = 3
    total_customers = len(scored)
    high_customers  = high
    expected_converts = int(high * 0.638)          # precision @0.6 = 63.8%
    revenue_captured  = expected_converts * z_revenue
    cost_saved        = (total_customers - high_customers) * z_cost
    net_roi_pct       = round(
        ((expected_converts * (z_revenue - z_cost)) / (total_customers * z_cost)) * 100, 2
    )

    log.info(
        "Business ROI estimate — targeting %d customers → "
        "~%d converts | revenue: %d | saved contact cost: %d | ROI: %.1f%%",
        high_customers, expected_converts, revenue_captured, cost_saved, net_roi_pct,
    )

    return {
        "total_scored": total_customers,
        "high_priority": high,
        "medium_priority": med,
        "low_priority": low,
        "estimated_net_roi_pct": net_roi_pct,
    }


# ---------------------------------------------------------------------------
# Task 4 — Re-run KMeans segmentation + write back to MySQL
# ---------------------------------------------------------------------------


def update_segments(**context) -> dict:
    """
    Re-fit KMeans on the latest features.csv, write customer_segments.csv,
    and update the `segment` column in the MySQL customers table.
    """
    _load_env()

    # Step 4a — re-run KMeans segmentation
    rc = _run_script(
        KMEANS_SCRIPT,
        extra_args=[
            "--features",   str(FEATURES_PATH),
            "--segments-output", str(SEGMENTS_PATH),
            "--model-output",    str(MODELS_DIR / "kmeans_model.pkl"),
            "--elbow-output",    str(MODELS_DIR / "kmeans_elbow.png"),
            "--profile-output",  str(MODELS_DIR / "segment_profiles.csv"),
        ],
    )
    if rc != 0:
        raise RuntimeError(f"kmeans_rfm.py failed with exit code {rc}")

    _assert_file(SEGMENTS_PATH, "customer_segments.csv")

    # Step 4b — write segment labels back to MySQL
    rc2 = _run_script(UPDATE_SEG_SCRIPT)
    if rc2 != 0:
        raise RuntimeError(f"update_segments_mysql.py failed with exit code {rc2}")

    import pandas as pd  # type: ignore[import]

    seg_df = pd.read_csv(SEGMENTS_PATH)
    dist = seg_df["segment"].value_counts().to_dict()
    log.info("Segment distribution: %s", dist)

    return {"segment_distribution": dist}


# ---------------------------------------------------------------------------
# Task 5 — Merge all outputs → single CSV for Power BI
# ---------------------------------------------------------------------------


def refresh_dashboard_data(**context) -> dict:
    """
    Join features.csv + conversion_scores.csv + customer_segments.csv
    into a single flat file (dashboard_export.csv) that Power BI can
    import for auto-refresh.

    Columns exported:
        customer_id, age, income, education_rank, marital_clean,
        total_children, total_spend, total_purchases, recency,
        num_web_visits_month, campaign_engagement_rate, customer_tenure_days,
        web_purchase_ratio, deal_sensitivity, income_per_person, complain,
        response, conversion_probability, recommendation, segment,
        pipeline_run_ts
    """
    _load_env()
    import pandas as pd  # type: ignore[import]

    _assert_file(FEATURES_PATH, "features.csv")
    _assert_file(SCORES_PATH, "conversion_scores.csv")
    _assert_file(SEGMENTS_PATH, "customer_segments.csv")

    features = pd.read_csv(FEATURES_PATH)
    scores   = pd.read_csv(SCORES_PATH)[["customer_id", "conversion_probability", "recommendation"]]
    segments = pd.read_csv(SEGMENTS_PATH)[["customer_id", "segment"]]

    # Merge all three on customer_id
    dashboard = (
        features
        .merge(scores, on="customer_id", how="left")
        .merge(segments, on="customer_id", how="left")
    )

    # Add pipeline run timestamp for lineage tracking in Power BI
    dashboard["pipeline_run_ts"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # Keep only the columns Power BI needs (order matches dashboard page layout)
    output_cols = [
        "customer_id", "age", "income", "education_rank", "marital_clean",
        "total_children", "has_children", "total_spend", "total_purchases",
        "avg_spend_per_purchase", "recency", "num_web_visits_month",
        "campaign_engagement_rate", "customer_tenure_days",
        "web_purchase_ratio", "deal_sensitivity", "income_per_person",
        "complain", "response",
        "conversion_probability", "recommendation", "segment",
        "pipeline_run_ts",
    ]
    # Only keep columns that exist in the merged frame
    output_cols = [c for c in output_cols if c in dashboard.columns]
    dashboard[output_cols].to_csv(DASHBOARD_PATH, index=False)

    _assert_file(DASHBOARD_PATH, "dashboard_export.csv")

    # ── Summary KPIs logged into Airflow task log ──────────────────────────
    total       = len(dashboard)
    conv_rate   = dashboard["response"].mean() * 100
    high_pct    = (dashboard["recommendation"] == "HIGH PRIORITY").mean() * 100
    seg_dist    = dashboard["segment"].value_counts().to_dict()
    avg_prob    = dashboard["conversion_probability"].mean()

    log.info("=== PIPELINE SUMMARY ===")
    log.info("Total customers     : %d", total)
    log.info("Actual conv rate    : %.1f%%", conv_rate)
    log.info("HIGH PRIORITY pct   : %.1f%%", high_pct)
    log.info("Avg conv probability: %.4f", avg_prob)
    log.info("Segment distribution: %s", seg_dist)
    log.info("Dashboard CSV path  : %s", DASHBOARD_PATH)
    log.info("========================")

    return {
        "dashboard_rows": total,
        "conversion_rate_pct": round(conv_rate, 2),
        "high_priority_pct": round(high_pct, 2),
        "avg_conversion_probability": round(avg_prob, 4),
        "segment_distribution": seg_dist,
        "output_path": str(DASHBOARD_PATH),
    }


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

default_args = {
    "owner": "animesh.karmakar",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

with DAG(
    dag_id="marketing_pipeline",
    description=(
        "Nightly Marketing Intelligence pipeline: "
        "MySQL → PySpark ETL → XGBoost scoring → KMeans segmentation → Power BI export"
    ),
    default_args=default_args,
    schedule_interval="0 2 * * *",   # every day at 02:00 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["marketing", "ml", "etl", "production"],
    doc_md="""
## Marketing Intelligence Nightly Pipeline

Runs every night at **02:00 AM**.

### Task sequence
| Step | Task ID | What it does |
|------|---------|-------------|
| 1 | `validate_mysql_connection` | Ping MySQL, assert 4 tables have rows |
| 2 | `pyspark_feature_engineering` | Read MySQL → PySpark transformations → features.csv |
| 3 | `score_customers` | XGBoost inference on all customers → conversion_scores.csv |
| 4 | `update_segments` | Re-fit KMeans → customer_segments.csv → MySQL segment column |
| 5 | `refresh_dashboard_data` | Merge all outputs → dashboard_export.csv for Power BI |

### Outputs
- `data/processed/features.csv` — engineered feature table (2,240 rows)
- `data/processed/conversion_scores.csv` — XGBoost probabilities + priority labels
- `data/processed/customer_segments.csv` — KMeans segment assignments
- `data/processed/dashboard_export.csv` — flat file for Power BI auto-refresh
- `models/kmeans_model.pkl` — refreshed KMeans model
    """,
) as dag:

    t1_validate = PythonOperator(
        task_id="validate_mysql_connection",
        python_callable=validate_mysql_connection,
        doc_md="Ping MySQL, check all 4 tables have rows. Pushes row counts via XCom.",
    )

    t2_etl = PythonOperator(
        task_id="pyspark_feature_engineering",
        python_callable=pyspark_feature_engineering,
        doc_md="Run pyspark_etl.py: MySQL JDBC read → feature engineering → features.csv.",
    )

    t3_score = PythonOperator(
        task_id="score_customers",
        python_callable=score_customers,
        doc_md="Load xgb_conversion_model.pkl, score all customers, save conversion_scores.csv.",
    )

    t4_segments = PythonOperator(
        task_id="update_segments",
        python_callable=update_segments,
        doc_md="Re-fit KMeans on latest features → customer_segments.csv → MySQL segment update.",
    )

    t5_dashboard = PythonOperator(
        task_id="refresh_dashboard_data",
        python_callable=refresh_dashboard_data,
        doc_md="Merge features + scores + segments into dashboard_export.csv for Power BI.",
    )

    # Task dependency chain: 1 → 2 → 3 → 4 → 5
    t1_validate >> t2_etl >> t3_score >> t4_segments >> t5_dashboard
