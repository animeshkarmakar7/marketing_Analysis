

from __future__ import annotations

import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

_API_DIR = Path(__file__).resolve().parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from predict import (  # noqa: E402  (import after sys.path patch)
    get_model_info,
    predict_batch,
    predict_single,
)
from schemas import (  # noqa: E402
    BatchConversionRequest,
    BatchConversionResponse,
    ConversionPredictionRequest,
    ConversionPredictionResponse,
    ErrorResponse,
    HealthResponse,
)



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("marketing_api")



_model_info: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Load models once when the server starts; release on shutdown."""
    logger.info("Loading ML models …")
    try:
        _model_info.update(get_model_info())
        logger.info(
            "Models loaded ✓  |  AUC-ROC: %.4f  |  features: %d",
            _model_info["auc_roc"],
            _model_info["feature_count"],
        )
    except FileNotFoundError as exc:
        logger.error("Model file missing: %s", exc)
        logger.error(
            "Run the training scripts before starting the API:\n"
            "  python ml/segmentation/kmeans_rfm.py\n"
            "  python ml/conversion_prediction/train_model.py"
        )
        raise
    yield
    logger.info("API shutting down.")




app = FastAPI(
    title="Marketing Intelligence System API",
    description=(
        "Predicts customer conversion probability for the next marketing campaign "
        "and classifies customers into RFM segments (VIP / Loyal / At Risk / New). "
        "Built with XGBoost (AUC-ROC 0.88) + KMeans on the IBM Marketing Campaign dataset."
    ),
    version="1.0.0",
    contact={
        "name": "Animesh Karmakar",
        "url": "https://github.com/animeshkarmakar7",
    },
    license_info={"name": "MIT"},
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)




@app.middleware("http")
async def add_process_time_header(request: Request, call_next):  # type: ignore
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
    return response


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error.", "error_code": "INTERNAL_ERROR"},
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="API health check",
    tags=["Monitoring"],
)
async def health() -> HealthResponse:
    """
    Returns the current health status of the API and whether the ML models
    are loaded successfully.

    Use this endpoint to verify the service is ready before sending
    prediction requests.
    """
    if not _model_info.get("model_loaded"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML models are not loaded. Check server logs.",
        )
    return HealthResponse(
        status="ok",
        model_loaded=_model_info["model_loaded"],
        model_version=_model_info["model_version"],
        auc_roc=_model_info["auc_roc"],
        feature_count=_model_info["feature_count"],
        message=(
            f"Marketing Intelligence API is running. "
            f"Model AUC-ROC: {_model_info['auc_roc']:.4f}."
        ),
    )


@app.post(
    "/predict-conversion",
    response_model=ConversionPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict campaign conversion probability for a single customer",
    tags=["Prediction"],
    responses={
        422: {"model": ErrorResponse, "description": "Validation error — check input fields."},
        500: {"model": ErrorResponse, "description": "Model inference failed."},
    },
)
async def predict_conversion(
    request: ConversionPredictionRequest,
) -> ConversionPredictionResponse:
    """
    ### Predict campaign conversion probability for a single customer.

    Provide the 17 engineered features for a customer and receive:

    - **conversion_probability** — probability (0–1) the customer accepts the next campaign
    - **recommendation** — action label based on probability thresholds:
        - `HIGH PRIORITY` → prob ≥ 0.60
        - `MEDIUM PRIORITY` → prob 0.30–0.60
        - `LOW PRIORITY` → prob < 0.30
    - **segment** — customer's RFM segment (VIP / Loyal / At Risk / New)
    - **model_auc_roc** — held-out AUC-ROC of the production model

    #### Business interpretation
    At the 0.60 threshold the model achieves **64% precision**, meaning
    ~6 out of every 10 customers targeted actually convert.  
    This reduces wasted contact spend by targeting the most likely converters.

    #### Feature engineering reference
    | Feature | Formula |
    |---|---|
    | age | 2024 − Year_Birth |
    | total_spend | sum of all 6 Mnt* columns |
    | campaign_engagement_rate | campaigns accepted / 5 |
    | income_per_person | income / (1 + total_children) |
    | avg_spend_per_purchase | total_spend / total_purchases |
    """
    try:
        logger.info(
            "Single prediction request | age=%d income=%.0f recency=%d",
            request.age,
            request.income,
            request.recency,
        )
        result = predict_single(request)
        logger.info(
            "Prediction complete | prob=%.4f recommendation=%s segment=%s",
            result.conversion_probability,
            result.recommendation.value,
            result.segment.value,
        )
        return result
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Inference error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model inference failed. See server logs for details.",
        ) from exc


@app.post(
    "/predict-conversion/batch",
    response_model=BatchConversionResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch score multiple customers in one request",
    tags=["Prediction"],
    responses={
        422: {"model": ErrorResponse, "description": "Validation error — check input fields."},
        500: {"model": ErrorResponse, "description": "Batch inference failed."},
    },
)
async def predict_conversion_batch(
    request: BatchConversionRequest,
) -> BatchConversionResponse:
    """
    ### Score multiple customers in a single request (max 500).

    Accepts a JSON body with a `customers` array.  Returns:

    - **results** — individual scores for each customer (index-aligned)
    - **high_priority_count** / **medium_priority_count** / **low_priority_count**
      — summary counts for budget allocation decisions
    - **model_auc_roc** — held-out AUC-ROC of the production model

    #### Use case
    Use this endpoint to score an entire marketing list before a campaign
    and extract only `HIGH PRIORITY` customers to target.
    """
    try:
        logger.info(
            "Batch prediction request | customers=%d", len(request.customers)
        )
        result = predict_batch(request)
        logger.info(
            "Batch complete | high=%d medium=%d low=%d",
            result.high_priority_count,
            result.medium_priority_count,
            result.low_priority_count,
        )
        return result
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Batch inference error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch inference failed. See server logs for details.",
        ) from exc




@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to interactive Swagger docs."""
    from fastapi.responses import RedirectResponse  # noqa: PLC0415

    return RedirectResponse(url="/docs")




if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
