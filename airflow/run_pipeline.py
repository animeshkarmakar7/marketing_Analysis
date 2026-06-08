"""
Standalone Task Runner for the Marketing Intelligence Pipeline
==============================================================

Runs each Airflow DAG task as a plain Python function — no Airflow
scheduler or database required.

Usage:
    # Run the full pipeline end-to-end
    python airflow/run_pipeline.py --all

    # Run a single task
    python airflow/run_pipeline.py --task validate_mysql_connection
    python airflow/run_pipeline.py --task pyspark_feature_engineering
    python airflow/run_pipeline.py --task score_customers
    python airflow/run_pipeline.py --task update_segments
    python airflow/run_pipeline.py --task refresh_dashboard_data

    # Dry-run — just print what each task would do
    python airflow/run_pipeline.py --all --dry-run

This script is also the verification tool for Phase 5.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Make the project root importable so DAG task callables can import modules
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "airflow" / "dags"))

# ---------------------------------------------------------------------------
# Mock Airflow to run without apache-airflow package installed
# ---------------------------------------------------------------------------
from types import ModuleType

class DummyDAG:
    def __init__(self, *args, **kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class DummyOperator:
    def __init__(self, *args, **kwargs):
        pass
    def __rshift__(self, other):
        return other

airflow_mock = ModuleType("airflow")
airflow_mock.DAG = DummyDAG  # type: ignore

operators_mock = ModuleType("airflow.operators")
operators_python_mock = ModuleType("airflow.operators.python")
operators_python_mock.PythonOperator = DummyOperator  # type: ignore

sys.modules["airflow"] = airflow_mock
sys.modules["airflow.operators"] = operators_mock
sys.modules["airflow.operators.python"] = operators_python_mock

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  |  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run_pipeline")

# ---------------------------------------------------------------------------
# Import task callables from the DAG (works because Airflow is not required
# at import time — we only need the python_callable functions)
# ---------------------------------------------------------------------------
try:
    from marketing_pipeline import (  # type: ignore[import]
        refresh_dashboard_data,
        pyspark_feature_engineering,
        score_customers,
        update_segments,
        validate_mysql_connection,
    )
except ImportError as e:
    sys.exit(f"Could not import DAG task callables: {e}\n"
             "Make sure you are running from the project root:\n"
             "  python airflow/run_pipeline.py --all")

# ---------------------------------------------------------------------------
# Task registry — maps name → callable
# ---------------------------------------------------------------------------

TASKS: dict[str, tuple[str, object]] = {
    "validate_mysql_connection": (
        "Task 1 - Validate MySQL connection + row counts",
        validate_mysql_connection,
    ),
    "pyspark_feature_engineering": (
        "Task 2 - PySpark ETL -> features.csv",
        pyspark_feature_engineering,
    ),
    "score_customers": (
        "Task 3 - XGBoost scoring -> conversion_scores.csv",
        score_customers,
    ),
    "update_segments": (
        "Task 4 - KMeans segmentation + MySQL update",
        update_segments,
    ),
    "refresh_dashboard_data": (
        "Task 5 - Dashboard export -> dashboard_export.csv",
        refresh_dashboard_data,
    ),
}

TASK_ORDER = list(TASKS.keys())


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _banner(text: str) -> None:
    width = 62
    print()
    print("=" * width)
    print(f"  {text}")
    print("=" * width)


def run_task(task_id: str, dry_run: bool = False) -> dict | None:
    label, callable_ = TASKS[task_id]
    _banner(label)

    if dry_run:
        log.info("[DRY RUN] Would execute: %s", task_id)
        return None

    start = time.perf_counter()
    try:
        result = callable_()
        elapsed = time.perf_counter() - start
        log.info("Task completed in %.1fs - result: %s", elapsed, result)
        return result
    except Exception as exc:
        elapsed = time.perf_counter() - start
        log.error("Task FAILED after %.1fs: %s", elapsed, exc)
        raise


def run_all(dry_run: bool = False) -> None:
    _banner("MARKETING INTELLIGENCE PIPELINE - FULL RUN")
    log.info("Started at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    results: dict[str, dict | None] = {}
    pipeline_start = time.perf_counter()

    for task_id in TASK_ORDER:
        try:
            results[task_id] = run_task(task_id, dry_run=dry_run)
        except Exception:
            log.error("Pipeline aborted at task: %s", task_id)
            print_summary(results, failed_at=task_id)
            sys.exit(1)

    total = time.perf_counter() - pipeline_start
    print_summary(results, failed_at=None, total_seconds=total)


def print_summary(
    results: dict,
    failed_at: str | None,
    total_seconds: float = 0,
) -> None:
    _banner("PIPELINE SUMMARY")

    status_icons = {True: "OK", False: "FAIL"}
    for task_id in TASK_ORDER:
        passed = task_id in results and failed_at != task_id
        label = TASKS[task_id][0]
        icon  = "OK  " if passed else "FAIL"
        print(f"  [{icon}]  {label}")

    if failed_at:
        print(f"\n  Aborted at: {failed_at}")
    else:
        print(f"\n  Total runtime : {total_seconds:.1f}s")
        # Print final dashboard stats if available
        dash = results.get("refresh_dashboard_data")
        if dash:
            print(f"  Customers scored  : {dash.get('dashboard_rows', '?')}")
            print(f"  Conversion rate   : {dash.get('conversion_rate_pct', '?')}%")
            print(f"  HIGH priority     : {dash.get('high_priority_pct', '?')}%")
            print(f"  Avg conv prob     : {dash.get('avg_conversion_probability', '?')}")
            seg = dash.get("segment_distribution", {})
            for seg_name, count in sorted(seg.items()):
                print(f"  Segment {seg_name:<10}: {count}")
        print("\n  Pipeline PASSED")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Marketing Intelligence pipeline tasks without Airflow."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Run all 5 tasks in sequence.",
    )
    group.add_argument(
        "--task",
        choices=list(TASKS.keys()),
        metavar="TASK_ID",
        help=(
            "Run a single task. Choices: "
            + ", ".join(TASKS.keys())
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would run without executing anything.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.all:
        run_all(dry_run=args.dry_run)
    else:
        run_task(args.task, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
