from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEATURE_PATH = PROJECT_ROOT / "data" / "processed" / "features.csv"
DEFAULT_SEGMENT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "customer_segments.csv"
DEFAULT_MODEL_OUTPUT = PROJECT_ROOT / "models" / "kmeans_model.pkl"
DEFAULT_ELBOW_OUTPUT = PROJECT_ROOT / "models" / "kmeans_elbow.png"
DEFAULT_PROFILE_OUTPUT = PROJECT_ROOT / "models" / "segment_profiles.csv"

RFM_FEATURES = ["recency", "total_purchases", "total_spend"]


def load_features(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = sorted(set(["customer_id", *RFM_FEATURES]) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns in features file: {missing}")
    return df


def assign_segment_names(profile: pd.DataFrame) -> dict[int, str]:
    profile = profile.copy()
    profile["recency_rank"] = profile["recency"].rank(ascending=True)
    profile["purchase_rank"] = profile["total_purchases"].rank(ascending=False)
    profile["spend_rank"] = profile["total_spend"].rank(ascending=False)
    profile["vip_score"] = (
        profile["recency_rank"] + profile["purchase_rank"] + profile["spend_rank"]
    )
    profile["at_risk_score"] = (
        profile["recency"].rank(ascending=False)
        + profile["total_spend"].rank(ascending=False)
        + profile["total_purchases"].rank(ascending=False)
    )

    labels: dict[int, str] = {}
    vip_cluster = int(profile.sort_values("vip_score").iloc[0]["cluster"])
    labels[vip_cluster] = "VIP"

    remaining = profile[~profile["cluster"].isin(labels)]
    at_risk_cluster = int(remaining.sort_values("at_risk_score").iloc[0]["cluster"])
    labels[at_risk_cluster] = "At Risk"

    remaining = profile[~profile["cluster"].isin(labels)]
    loyal_cluster = int(
        remaining.sort_values(
            ["total_spend", "total_purchases", "recency"],
            ascending=[False, False, True],
        ).iloc[0]["cluster"]
    )
    labels[loyal_cluster] = "Loyal"

    remaining = profile[~profile["cluster"].isin(labels)]
    new_cluster = int(remaining.iloc[0]["cluster"])
    labels[new_cluster] = "New"
    return labels


def save_elbow_plot(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inertias = []
    cluster_range = range(2, 9)

    scaled = StandardScaler().fit_transform(df[RFM_FEATURES])
    for k in cluster_range:
        model = KMeans(n_clusters=k, random_state=42, n_init=20)
        model.fit(scaled)
        inertias.append(model.inertia_)

    plt.figure(figsize=(8, 5))
    plt.plot(list(cluster_range), inertias, marker="o")
    plt.title("K-Means Elbow Method for RFM Segmentation")
    plt.xlabel("Number of clusters")
    plt.ylabel("Inertia")
    plt.xticks(list(cluster_range))
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()


def run_segmentation(
    feature_path: Path,
    segment_output: Path,
    model_output: Path,
    elbow_output: Path,
    profile_output: Path,
) -> None:
    df = load_features(feature_path)

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("kmeans", KMeans(n_clusters=4, random_state=42, n_init=50)),
        ]
    )
    clusters = pipeline.fit_predict(df[RFM_FEATURES])
    df["cluster"] = clusters

    profile = (
        df.groupby("cluster")
        .agg(
            customers=("customer_id", "count"),
            recency=("recency", "mean"),
            total_purchases=("total_purchases", "mean"),
            total_spend=("total_spend", "mean"),
            conversion_rate=("response", "mean"),
        )
        .reset_index()
    )
    label_map = assign_segment_names(profile)
    df["segment"] = df["cluster"].map(label_map)
    profile["segment"] = profile["cluster"].map(label_map)

    silhouette = silhouette_score(
        pipeline.named_steps["scaler"].transform(df[RFM_FEATURES]),
        clusters,
    )

    model_output.parent.mkdir(parents=True, exist_ok=True)
    segment_output.parent.mkdir(parents=True, exist_ok=True)
    profile_output.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {
            "pipeline": pipeline,
            "rfm_features": RFM_FEATURES,
            "label_map": label_map,
            "silhouette_score": silhouette,
        },
        model_output,
    )
    save_elbow_plot(df, elbow_output)

    segment_columns = [
        "customer_id",
        "recency",
        "total_purchases",
        "total_spend",
        "cluster",
        "segment",
        "response",
    ]
    df[segment_columns].to_csv(segment_output, index=False)
    profile.sort_values("segment").to_csv(profile_output, index=False)

    print(f"Saved model to {model_output}")
    print(f"Saved segment assignments to {segment_output}")
    print(f"Saved segment profiles to {profile_output}")
    print(f"Saved elbow plot to {elbow_output}")
    print(f"Silhouette score: {silhouette:.4f}")
    print(profile.sort_values("segment").to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train K-Means RFM customer segmentation.")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURE_PATH)
    parser.add_argument("--segments-output", type=Path, default=DEFAULT_SEGMENT_OUTPUT)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL_OUTPUT)
    parser.add_argument("--elbow-output", type=Path, default=DEFAULT_ELBOW_OUTPUT)
    parser.add_argument("--profile-output", type=Path, default=DEFAULT_PROFILE_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_segmentation(
        feature_path=args.features,
        segment_output=args.segments_output,
        model_output=args.model_output,
        elbow_output=args.elbow_output,
        profile_output=args.profile_output,
    )


if __name__ == "__main__":
    main()
