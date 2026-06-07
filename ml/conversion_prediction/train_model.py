from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEATURE_PATH = PROJECT_ROOT / "data" / "processed" / "features.csv"
DEFAULT_MODEL_OUTPUT = PROJECT_ROOT / "models" / "xgb_conversion_model.pkl"
DEFAULT_METRICS_OUTPUT = PROJECT_ROOT / "models" / "conversion_model_metrics.json"
DEFAULT_SCORED_OUTPUT = PROJECT_ROOT / "data" / "processed" / "conversion_scores.csv"

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
TARGET = "response"


def load_features(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"customer_id", TARGET, *NUMERIC_FEATURES, *CATEGORICAL_FEATURES}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns in features file: {missing}")
    return df


def make_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def evaluate_thresholds(y_true, probabilities: pd.Series | list[float]) -> dict[str, dict]:
    results = {}
    for threshold in (0.5, 0.6):
        predictions = (probabilities >= threshold).astype(int)
        results[str(threshold)] = {
            "precision": precision_score(y_true, predictions, zero_division=0),
            "recall": recall_score(y_true, predictions, zero_division=0),
            "f1": f1_score(y_true, predictions, zero_division=0),
            "confusion_matrix": confusion_matrix(y_true, predictions).tolist(),
        }
    return results


def run_training(
    feature_path: Path,
    model_output: Path,
    metrics_output: Path,
    scored_output: Path,
) -> None:
    df = load_features(feature_path)
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    preprocessor = make_preprocessor()
    X_train_processed = preprocessor.fit_transform(X_train)
    X_test_processed = preprocessor.transform(X_test)

    smote = SMOTE(random_state=42)
    X_train_resampled, y_train_resampled = smote.fit_resample(X_train_processed, y_train)

    base_model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        random_state=42,
        n_jobs=-1,
    )
    param_grid = {
        "n_estimators": [100, 200],
        "max_depth": [3, 4],
        "learning_rate": [0.03, 0.08],
        "subsample": [0.8, 1.0],
        "colsample_bytree": [0.8, 1.0],
    }
    cv = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)
    search = GridSearchCV(
        estimator=base_model,
        param_grid=param_grid,
        scoring="roc_auc",
        cv=cv,
        n_jobs=-1,
        verbose=0,
    )
    search.fit(X_train_resampled, y_train_resampled)

    best_model = search.best_estimator_
    test_probabilities = best_model.predict_proba(X_test_processed)[:, 1]
    test_predictions = (test_probabilities >= 0.5).astype(int)
    auc = roc_auc_score(y_test, test_probabilities)

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", best_model),
        ]
    )

    all_probabilities = pipeline.predict_proba(X)[:, 1]
    scored = df[["customer_id", TARGET]].copy()
    scored["conversion_probability"] = all_probabilities
    scored["recommendation"] = pd.cut(
        scored["conversion_probability"],
        bins=[-0.01, 0.3, 0.6, 1.0],
        labels=["LOW PRIORITY", "MEDIUM PRIORITY", "HIGH PRIORITY"],
    ).astype(str)

    metrics = {
        "auc_roc": auc,
        "best_params": search.best_params_,
        "class_balance_original": y.value_counts().sort_index().to_dict(),
        "class_balance_train_after_smote": pd.Series(y_train_resampled)
        .value_counts()
        .sort_index()
        .to_dict(),
        "threshold_metrics": evaluate_thresholds(y_test, test_probabilities),
        "classification_report_threshold_0_5": classification_report(
            y_test,
            test_predictions,
            output_dict=True,
            zero_division=0,
        ),
        "feature_columns": {
            "numeric": NUMERIC_FEATURES,
            "categorical": CATEGORICAL_FEATURES,
        },
    }

    model_output.parent.mkdir(parents=True, exist_ok=True)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    scored_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_output)
    scored.to_csv(scored_output, index=False)
    metrics_output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"Saved model to {model_output}")
    print(f"Saved metrics to {metrics_output}")
    print(f"Saved scored customers to {scored_output}")
    print(f"AUC-ROC: {auc:.4f}")
    print(f"Best params: {search.best_params_}")
    for threshold, values in metrics["threshold_metrics"].items():
        print(
            f"Threshold {threshold}: precision={values['precision']:.4f}, "
            f"recall={values['recall']:.4f}, f1={values['f1']:.4f}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train XGBoost conversion model.")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURE_PATH)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL_OUTPUT)
    parser.add_argument("--metrics-output", type=Path, default=DEFAULT_METRICS_OUTPUT)
    parser.add_argument("--scored-output", type=Path, default=DEFAULT_SCORED_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_training(
        feature_path=args.features,
        model_output=args.model_output,
        metrics_output=args.metrics_output,
        scored_output=args.scored_output,
    )


if __name__ == "__main__":
    main()
