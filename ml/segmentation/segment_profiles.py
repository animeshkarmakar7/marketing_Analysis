from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEGMENTS_PATH = PROJECT_ROOT / "data" / "processed" / "customer_segments.csv"
FEATURES_PATH = PROJECT_ROOT / "data" / "processed" / "features.csv"
OUTPUT_PATH = PROJECT_ROOT / "models" / "segment_business_summary.csv"


def main() -> None:
    segments = pd.read_csv(SEGMENTS_PATH)
    features = pd.read_csv(FEATURES_PATH)
    df = features.merge(
        segments[["customer_id", "cluster", "segment"]],
        on="customer_id",
        how="inner",
    )

    summary = (
        df.groupby("segment")
        .agg(
            customers=("customer_id", "count"),
            avg_recency=("recency", "mean"),
            avg_total_purchases=("total_purchases", "mean"),
            avg_total_spend=("total_spend", "mean"),
            historical_spend=("total_spend", "sum"),
            avg_conversion_rate=("response", "mean"),
            avg_income=("income", "mean"),
            avg_web_purchase_ratio=("web_purchase_ratio", "mean"),
            avg_deal_sensitivity=("deal_sensitivity", "mean"),
        )
        .reset_index()
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved business segment summary to {OUTPUT_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
