from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
METRICS_PATH = PROJECT_ROOT / "models" / "conversion_model_metrics.json"


def main() -> None:
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    print(f"AUC-ROC: {metrics['auc_roc']:.4f}")
    print(f"Best params: {metrics['best_params']}")
    print("Original class balance:", metrics["class_balance_original"])
    print("Train class balance after SMOTE:", metrics["class_balance_train_after_smote"])
    for threshold, values in metrics["threshold_metrics"].items():
        print(
            f"Threshold {threshold}: precision={values['precision']:.4f}, "
            f"recall={values['recall']:.4f}, f1={values['f1']:.4f}, "
            f"confusion_matrix={values['confusion_matrix']}"
        )


if __name__ == "__main__":
    main()
