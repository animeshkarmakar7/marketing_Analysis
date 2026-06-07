from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import shap

from train_model import CATEGORICAL_FEATURES, DEFAULT_FEATURE_PATH, NUMERIC_FEATURES


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "xgb_conversion_model.pkl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "models" / "shap"
DEFAULT_EXPLANATION_OUTPUT = PROJECT_ROOT / "models" / "shap_top_customer_explanations.csv"


def get_transformed_feature_names(preprocessor) -> list[str]:
    try:
        return list(preprocessor.get_feature_names_out())
    except Exception:
        categorical_encoder = preprocessor.named_transformers_["categorical"]
        categorical_names = list(
            categorical_encoder.get_feature_names_out(CATEGORICAL_FEATURES)
        )
        return NUMERIC_FEATURES + categorical_names


def run_shap_analysis(
    feature_path: Path,
    model_path: Path,
    output_dir: Path,
    explanation_output: Path,
    sample_size: int,
) -> None:
    df = pd.read_csv(feature_path)
    pipeline = joblib.load(model_path)
    preprocessor = pipeline.named_steps["preprocessor"]
    model = pipeline.named_steps["model"]

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    probabilities = pipeline.predict_proba(X)[:, 1]
    X_transformed = preprocessor.transform(X)
    feature_names = get_transformed_feature_names(preprocessor)
    X_transformed_df = pd.DataFrame(X_transformed, columns=feature_names)

    sample = X_transformed_df.sample(
        n=min(sample_size, len(X_transformed_df)),
        random_state=42,
    )
    explainer = shap.TreeExplainer(model)
    shap_values = explainer(sample)

    output_dir.mkdir(parents=True, exist_ok=True)
    explanation_output.parent.mkdir(parents=True, exist_ok=True)

    plt.figure()
    shap.plots.beeswarm(shap_values, max_display=15, show=False)
    plt.tight_layout()
    summary_path = output_dir / "shap_summary_beeswarm.png"
    plt.savefig(summary_path, dpi=160, bbox_inches="tight")
    plt.close()

    plt.figure()
    shap.plots.bar(shap_values, max_display=15, show=False)
    plt.tight_layout()
    bar_path = output_dir / "shap_global_importance.png"
    plt.savefig(bar_path, dpi=160, bbox_inches="tight")
    plt.close()

    top_indices = pd.Series(probabilities).sort_values(ascending=False).head(5).index
    top_rows = []
    all_shap_values = explainer(X_transformed_df.loc[top_indices])

    for plot_number, customer_index in enumerate(top_indices, start=1):
        customer_id = int(df.loc[customer_index, "customer_id"])
        probability = float(probabilities[customer_index])
        explanation = all_shap_values[plot_number - 1]

        plt.figure()
        shap.plots.waterfall(explanation, max_display=12, show=False)
        plt.tight_layout()
        waterfall_path = output_dir / f"customer_{customer_id}_waterfall.png"
        plt.savefig(waterfall_path, dpi=160, bbox_inches="tight")
        plt.close()

        contribution_df = pd.DataFrame(
            {
                "feature": feature_names,
                "shap_value": explanation.values,
                "feature_value": X_transformed_df.loc[customer_index].values,
            }
        )
        top_positive = contribution_df.sort_values("shap_value", ascending=False).head(3)
        top_negative = contribution_df.sort_values("shap_value", ascending=True).head(3)

        top_rows.append(
            {
                "customer_id": customer_id,
                "conversion_probability": probability,
                "top_positive_drivers": "; ".join(
                    f"{row.feature} ({row.shap_value:.4f})"
                    for row in top_positive.itertuples(index=False)
                ),
                "top_negative_drivers": "; ".join(
                    f"{row.feature} ({row.shap_value:.4f})"
                    for row in top_negative.itertuples(index=False)
                ),
                "waterfall_plot": str(waterfall_path),
            }
        )

    pd.DataFrame(top_rows).to_csv(explanation_output, index=False)

    print(f"Saved SHAP summary plot to {summary_path}")
    print(f"Saved SHAP global importance plot to {bar_path}")
    print(f"Saved top customer explanations to {explanation_output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate SHAP explanations.")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURE_PATH)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--explanation-output", type=Path, default=DEFAULT_EXPLANATION_OUTPUT)
    parser.add_argument("--sample-size", type=int, default=500)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_shap_analysis(
        feature_path=args.features,
        model_path=args.model,
        output_dir=args.output_dir,
        explanation_output=args.explanation_output,
        sample_size=args.sample_size,
    )


if __name__ == "__main__":
    main()
