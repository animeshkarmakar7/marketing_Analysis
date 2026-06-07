from __future__ import annotations

import os
from pathlib import Path

import mysql.connector
import pandas as pd
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEGMENTS_PATH = PROJECT_ROOT / "data" / "processed" / "customer_segments.csv"


def get_connection():
    load_dotenv(PROJECT_ROOT / ".env")
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "marketing_db"),
    )


def ensure_segment_column(cursor) -> None:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'customers'
          AND column_name = 'segment'
        """
    )
    exists = cursor.fetchone()[0] > 0
    if not exists:
        cursor.execute(
            """
            ALTER TABLE customers
            ADD COLUMN segment ENUM('VIP', 'Loyal', 'At Risk', 'New') NULL
            """
        )


def update_segments() -> None:
    segments = pd.read_csv(SEGMENTS_PATH)
    required = {"customer_id", "segment"}
    missing = sorted(required - set(segments.columns))
    if missing:
        raise ValueError(f"Missing required columns in segment file: {missing}")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        ensure_segment_column(cursor)
        rows = [
            (row.segment, int(row.customer_id))
            for row in segments[["customer_id", "segment"]].itertuples(index=False)
        ]
        cursor.executemany(
            "UPDATE customers SET segment = %s WHERE customer_id = %s",
            rows,
        )
        conn.commit()
        print(f"Updated {cursor.rowcount} customer segment values in MySQL.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    update_segments()
