"""
Pydantic schemas for the Marketing Intelligence System API.

Defines request/response models for all endpoints with field-level
validation and documentation.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RecommendationLabel(str, Enum):
    HIGH = "HIGH PRIORITY — target this customer"
    MEDIUM = "MEDIUM PRIORITY — monitor this customer"
    LOW = "LOW PRIORITY — deprioritize this customer"


class SegmentLabel(str, Enum):
    VIP = "VIP"
    LOYAL = "Loyal"
    AT_RISK = "At Risk"
    NEW = "New"
    UNKNOWN = "Unknown"


class MaritalStatus(str, Enum):
    SINGLE = "Single"
    MARRIED = "Married"
    DIVORCED = "Divorced"
    WIDOW = "Widow"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ConversionPredictionRequest(BaseModel):
    """
    Input features required to predict a customer's conversion probability.
    All features match the engineered columns produced by the PySpark ETL
    pipeline (features.csv) and used to train the XGBoost model.
    """

    age: int = Field(
        ...,
        ge=18,
        le=100,
        description="Customer age derived from Year_Birth (2024 - Year_Birth).",
        examples=[45],
    )
    income: float = Field(
        ...,
        ge=0,
        description="Annual household income in local currency. Nulls filled with median.",
        examples=[58000.0],
    )
    total_spend: float = Field(
        ...,
        ge=0,
        description="Total spend across all product categories in last 2 years.",
        examples=[1200.0],
    )
    total_purchases: int = Field(
        ...,
        ge=0,
        description="Total number of purchases across all channels.",
        examples=[18],
    )
    avg_spend_per_purchase: float = Field(
        ...,
        ge=0,
        description="total_spend / total_purchases. Pass 0 when total_purchases is 0.",
        examples=[66.67],
    )
    recency: int = Field(
        ...,
        ge=0,
        description="Days since last purchase. Lower = more recently active.",
        examples=[30],
    )
    num_web_visits_month: int = Field(
        ...,
        ge=0,
        description="Number of website visits in the last month.",
        examples=[6],
    )
    campaign_engagement_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fraction of the 5 past campaigns the customer accepted (0–1).",
        examples=[0.4],
    )
    education_rank: int = Field(
        ...,
        ge=1,
        le=5,
        description="Ordinal education level: Basic=1, 2nCycle=2, Graduation=3, Master=4, PhD=5.",
        examples=[3],
    )
    total_children: int = Field(
        ...,
        ge=0,
        description="Total number of children at home (Kidhome + Teenhome).",
        examples=[0],
    )
    has_children: int = Field(
        ...,
        ge=0,
        le=1,
        description="Binary flag: 1 if total_children > 0 else 0.",
        examples=[0],
    )
    web_purchase_ratio: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="num_web_purchases / total_purchases. Pass 0 when total_purchases is 0.",
        examples=[0.5],
    )
    deal_sensitivity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="num_deals_purchases / total_purchases. Pass 0 when total_purchases is 0.",
        examples=[0.1],
    )
    customer_tenure_days: int = Field(
        ...,
        ge=0,
        description="Number of days since the customer joined (today - Dt_Customer).",
        examples=[900],
    )
    income_per_person: float = Field(
        ...,
        ge=0,
        description="income / (1 + total_children). Spending power adjusted for household size.",
        examples=[58000.0],
    )
    complain: int = Field(
        ...,
        ge=0,
        le=1,
        description="1 if customer complained in the last 2 years, else 0.",
        examples=[0],
    )
    marital_clean: MaritalStatus = Field(
        ...,
        description="Cleaned marital status. Junk values (YOLO/Absurd/Alone) mapped to Single.",
        examples=["Single"],
    )

    @field_validator("campaign_engagement_rate", "web_purchase_ratio", "deal_sensitivity")
    @classmethod
    def clamp_ratio(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "age": 45,
                    "income": 58000,
                    "total_spend": 1200,
                    "total_purchases": 18,
                    "avg_spend_per_purchase": 66.67,
                    "recency": 30,
                    "num_web_visits_month": 6,
                    "campaign_engagement_rate": 0.4,
                    "education_rank": 3,
                    "total_children": 0,
                    "has_children": 0,
                    "web_purchase_ratio": 0.5,
                    "deal_sensitivity": 0.1,
                    "customer_tenure_days": 900,
                    "income_per_person": 58000.0,
                    "complain": 0,
                    "marital_clean": "Single",
                }
            ]
        }
    }


class BatchConversionRequest(BaseModel):
    """Batch prediction request — accepts a list of customer feature records."""

    customers: list[ConversionPredictionRequest] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of customer feature records for batch scoring.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ConversionPredictionResponse(BaseModel):
    """Single-customer prediction response."""

    conversion_probability: float = Field(
        ...,
        description="Predicted probability (0–1) that the customer accepts the next campaign.",
        examples=[0.81],
    )
    recommendation: RecommendationLabel = Field(
        ...,
        description=(
            "Action label derived from conversion_probability thresholds: "
            "HIGH ≥ 0.6 | MEDIUM 0.3–0.6 | LOW < 0.3."
        ),
    )
    segment: SegmentLabel = Field(
        ...,
        description=(
            "RFM-based segment assigned to the nearest cluster centroid. "
            "Requires customer_id lookup; returned as 'Unknown' for ad-hoc inputs."
        ),
    )
    model_auc_roc: float = Field(
        ...,
        description="Held-out AUC-ROC of the production model (informational).",
        examples=[0.8779],
    )


class BatchCustomerResult(BaseModel):
    """Single result row within a batch response."""

    index: int = Field(..., description="Zero-based position in the request list.")
    conversion_probability: float
    recommendation: RecommendationLabel
    segment: SegmentLabel


class BatchConversionResponse(BaseModel):
    """Batch prediction response."""

    results: list[BatchCustomerResult]
    model_auc_roc: float
    total_customers: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int


class HealthResponse(BaseModel):
    """API health check response."""

    status: str = Field(..., examples=["ok"])
    model_loaded: bool
    model_version: str
    auc_roc: float
    feature_count: int
    message: str


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    detail: str
    error_code: Optional[str] = None
