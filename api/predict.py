"""
Prediction logic for the Marketing Intelligence System API.

Loads the trained XGBoost pipeline and KMeans segmentation model once
at startup, then exposes functions called by the FastAPI route handlers.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from schemas import (
    BatchConversionRequest,
    BatchConversionResponse,
    BatchCustomerResult,
    ConversionPredictionRequest,
    ConversionPredictionResponse,
    RecommendationLabel,
    SegmentLabel,
)

# ---------------------------------------------------------------------------
# Paths — resolve relative to project root
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
PROJECT_ROOT = _HERE.parent

CONVERSION_MODEL_PATH = PROJECT_ROOT / "models" / "xgb_conversion_model.pkl"
KMEANS_MODEL_PATH = PROJECT_ROOT / "models" / "kmeans_model.pkl"
METRICS_PATH = PROJECT_ROOT / "models" / "conversion_model_metrics.json"
CONVERSION_SCORES_PATH = PROJECT_ROOT / "data" / "processed" / "conversion_scores.csv"
CUSTOMER_SEGMENTS_PATH = PROJECT_ROOT / "data" / "processed" / "customer_segments.csv"



NUMERIC_FEATURES = [
    "age",
    "income",
    "total_spend",
    "total_purchases",
    "avg_spend_per_purchase",
    "recency",
    "num_web_visits_month",
    "campaign_engagement_rate",
    "education_rank",
    "total_children",
    "has_children",
    "web_purchase_ratio",
    "deal_sensitivity",
    "customer_tenure_days",
    "income_per_person",
    "complain",
]
CATEGORICAL_FEATURES = ["marital_clean"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# RFM columns for segment lookup (matches kmeans_rfm.py)
RFM_FEATURES = ["recency", "total_purchases", "total_spend"]

# Probability thresholds → recommendation labels
_THRESHOLDS = [
    (0.6, RecommendationLabel.HIGH),
    (0.3, RecommendationLabel.MEDIUM),
    (0.0, RecommendationLabel.LOW),
]


# ---------------------------------------------------------------------------
# Model loader (cached — loaded once per process lifetime)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_conversion_pipeline() -> Any:
    """Load and cache the XGBoost sklearn Pipeline."""
    if not CONVERSION_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Conversion model not found at {CONVERSION_MODEL_PATH}. "
            "Run ml/conversion_prediction/train_model.py first."
        )
    return joblib.load(CONVERSION_MODEL_PATH)


@lru_cache(maxsize=1)
def _load_kmeans_artifact() -> dict[str, Any]:
    """Load and cache the KMeans pipeline + label map."""
    if not KMEANS_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"KMeans model not found at {KMEANS_MODEL_PATH}. "
            "Run ml/segmentation/kmeans_rfm.py first."
        )
    return joblib.load(KMEANS_MODEL_PATH)


@lru_cache(maxsize=1)
def _load_metrics() -> dict[str, Any]:
    """Load and cache the conversion model metrics JSON."""
    if not METRICS_PATH.exists():
        return {"auc_roc": 0.0}
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_segment_lookup() -> dict[int, str]:
    """
    Build a customer_id → segment name lookup from the pre-scored CSV.
    Falls back to an empty dict if the file doesn't exist.
    """
    if not CUSTOMER_SEGMENTS_PATH.exists():
        return {}
    df = pd.read_csv(CUSTOMER_SEGMENTS_PATH, usecols=["customer_id", "segment"])
    return dict(zip(df["customer_id"].astype(int), df["segment"].astype(str)))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _probability_to_recommendation(probability: float) -> RecommendationLabel:
    """Map a float probability to a human-readable recommendation label."""
    for threshold, label in _THRESHOLDS:
        if probability >= threshold:
            return label
    return RecommendationLabel.LOW


def _rfm_to_segment(
    recency: float,
    total_purchases: float,
    total_spend: float,
) -> SegmentLabel:
    """
    Predict the RFM segment for arbitrary feature values using the
    trained KMeans pipeline.  Falls back to 'Unknown' on any error.
    """
    try:
        artifact = _load_kmeans_artifact()
        pipeline = artifact["pipeline"]
        label_map: dict[int, str] = artifact["label_map"]

        X = pd.DataFrame(
            [[recency, total_purchases, total_spend]],
            columns=RFM_FEATURES,
        )
        cluster_id = int(pipeline.predict(X)[0])
        segment_name = label_map.get(cluster_id, "Unknown")
        return SegmentLabel(segment_name) if segment_name in SegmentLabel._value2member_map_ else SegmentLabel.UNKNOWN
    except Exception:
        return SegmentLabel.UNKNOWN


def _request_to_dataframe(request: ConversionPredictionRequest) -> pd.DataFrame:
    """Convert a single Pydantic request to a one-row DataFrame."""
    row = request.model_dump()
    row["marital_clean"] = row["marital_clean"].value  # Enum → string
    return pd.DataFrame([row])[ALL_FEATURES]





def get_model_info() -> dict[str, Any]:
    """
    Return model metadata for the /health endpoint.
    Loads models eagerly so errors surface at startup.
    """
    pipeline = _load_conversion_pipeline()
    metrics = _load_metrics()
    feature_count = len(ALL_FEATURES)
    return {
        "model_loaded": True,
        "model_version": "xgb_conversion_v1",
        "auc_roc": metrics.get("auc_roc", 0.0),
        "feature_count": feature_count,
    }


def predict_single(
    request: ConversionPredictionRequest,
) -> ConversionPredictionResponse:
    pipeline = _load_conversion_pipeline()
    metrics = _load_metrics()

    df = _request_to_dataframe(request)
    probability = float(pipeline.predict_proba(df)[0, 1])
    recommendation = _probability_to_recommendation(probability)
    segment = _rfm_to_segment(
        recency=request.recency,
        total_purchases=request.total_purchases,
        total_spend=request.total_spend,
    )

    return ConversionPredictionResponse(
        conversion_probability=round(probability, 4),
        recommendation=recommendation,
        segment=segment,
        model_auc_roc=metrics.get("auc_roc", 0.0),
    )


def predict_batch(request: BatchConversionRequest) -> BatchConversionResponse:
    pipeline = _load_conversion_pipeline()
    metrics = _load_metrics()

    rows = []
    rfm_rows = []
    for item in request.customers:
        row = item.model_dump()
        row["marital_clean"] = row["marital_clean"].value
        rows.append(row)
        rfm_rows.append(
            [item.recency, item.total_purchases, item.total_spend]
        )

    df = pd.DataFrame(rows)[ALL_FEATURES]
    probabilities: np.ndarray = pipeline.predict_proba(df)[:, 1]

    # Batch segment prediction
    try:
        artifact = _load_kmeans_artifact()
        km_pipeline = artifact["pipeline"]
        label_map: dict[int, str] = artifact["label_map"]
        rfm_df = pd.DataFrame(rfm_rows, columns=RFM_FEATURES)
        cluster_ids = km_pipeline.predict(rfm_df).tolist()
        segments = [
            label_map.get(c, "Unknown") for c in cluster_ids
        ]
    except Exception:
        segments = ["Unknown"] * len(rows)

    results: list[BatchCustomerResult] = []
    high_count = medium_count = low_count = 0

    for idx, (prob, seg_name) in enumerate(zip(probabilities, segments)):
        rec = _probability_to_recommendation(float(prob))
        seg_label = (
            SegmentLabel(seg_name)
            if seg_name in SegmentLabel._value2member_map_
            else SegmentLabel.UNKNOWN
        )

        if rec == RecommendationLabel.HIGH:
            high_count += 1
        elif rec == RecommendationLabel.MEDIUM:
            medium_count += 1
        else:
            low_count += 1

        results.append(
            BatchCustomerResult(
                index=idx,
                conversion_probability=round(float(prob), 4),
                recommendation=rec,
                segment=seg_label,
            )
        )

    return BatchConversionResponse(
        results=results,
        model_auc_roc=metrics.get("auc_roc", 0.0),
        total_customers=len(results),
        high_priority_count=high_count,
        medium_priority_count=medium_count,
        low_priority_count=low_count,
    )
