"""
Quantify attack family diversity via clustering and feature-space separation.
Measures: cluster count, intra/inter-family distances, PCA visualization.
"""
import sys
from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from scipy.spatial.distance import pdist, squareform, cdist
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage5.config.settings import STAGE5_DATA_DIR, ALL_FEATURES
from stage5.training.train_fraud_model import load_and_prepare


def analyze_diversity():
    """
    Cluster all generated fraud rows by family, measure separation.
    """
    print("="*80)
    print("ATTACK FAMILY DIVERSITY ANALYSIS")
    print("="*80)

    # Load the full dataset with engineered features
    print("\n[1/4] Loading dataset with engineered features...")
    combined_dir = STAGE5_DATA_DIR / "combined"
    df = load_and_prepare(combined_dir=combined_dir)

    # Keep only fraud rows (attacks)
    fraud_df = df[df['is_fraud'] == 1].copy()
    print(f"  Total fraud rows: {len(fraud_df)}")

    if 'attack_family' not in fraud_df.columns:
        print("  WARNING: 'attack_family' column not found; cannot cluster by family")
        return

    families = fraud_df['attack_family'].value_counts()
    print(f"  Families found: {len(families)}")
    for fam, count in families.items():
        print(f"    {fam}: {count} rows")

    # Prepare feature matrix (standardized)
    print("\n[2/4] Standardizing feature space...")
    X = fraud_df[ALL_FEATURES].fillna(0).values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    print(f"  Shape: {X_scaled.shape}")

    # Compute pairwise distances to find natural cluster count
    print("\n[3/4] Computing within/between-family distances...")
    family_labels = fraud_df['attack_family'].values
    family_names = sorted(fraud_df['attack_family'].unique())

    metrics = {
        'n_families': len(family_names),
        'total_fraud_rows': len(fraud_df),
        'families': {}
    }

    # Within-family and between-family distances
    intra_dists = []
    inter_dists = []

    for fam in family_names:
        mask = family_labels == fam
        n_fam = mask.sum()
        if n_fam < 2:
            continue

        X_fam = X_scaled[mask]

        # Intra-family: avg pairwise distance within this family
        if n_fam > 1:
            intra_dist = np.mean(pdist(X_fam))
            intra_dists.append(intra_dist)

        metrics['families'][fam] = {'count': n_fam}

    # Inter-family: avg distance between any two families
    for i, fam1 in enumerate(family_names):
        for fam2 in family_names[i+1:]:
            mask1 = family_labels == fam1
            mask2 = family_labels == fam2
            X1 = X_scaled[mask1]
            X2 = X_scaled[mask2]
            inter_dist = np.mean(cdist(X1, X2))
            inter_dists.append(inter_dist)

    avg_intra = np.mean(intra_dists) if intra_dists else 0
    avg_inter = np.mean(inter_dists) if inter_dists else 0

    metrics['avg_intra_family_distance'] = float(avg_intra)
    metrics['avg_inter_family_distance'] = float(avg_inter)
    metrics['separation_ratio'] = float(avg_inter / avg_intra) if avg_intra > 0 else 0

    print(f"  Avg within-family distance: {avg_intra:.4f}")
    print(f"  Avg between-family distance: {avg_inter:.4f}")
    print(f"  Separation ratio: {metrics['separation_ratio']:.2f}x")

    # K-means to find natural clustering
    print("\n[4/4] Finding natural cluster structure (k-means elbow)...")
    inertias = []
    silhouette_scores = []
    K_range = range(2, min(20, len(family_names) + 3))

    from sklearn.metrics import silhouette_score

    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X_scaled)
        inertias.append(kmeans.inertia_)
        sil = silhouette_score(X_scaled, kmeans.labels_)
        silhouette_scores.append(sil)

    # Find elbow
    best_k = K_range[np.argmax(silhouette_scores)]
    metrics['estimated_natural_clusters'] = int(best_k)
    metrics['silhouette_scores'] = {int(k): float(s) for k, s in zip(K_range, silhouette_scores)}

    print(f"  Estimated natural clusters (by silhouette): {best_k}")
    print(f"  Best silhouette score: {max(silhouette_scores):.4f}")

    # PCA visualization
    print("\n[5/5] Computing PCA projection for visualization...")
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_scaled)

    metrics['pca_variance_explained'] = [float(v) for v in pca.explained_variance_ratio_]
    print(f"  PCA variance explained: {pca.explained_variance_ratio_} (cumsum: {pca.explained_variance_ratio_.sum():.2%})")

    # Save metrics
    out_dir = Path(__file__).resolve().parent.parent / "reports"
    out_dir.mkdir(exist_ok=True)

    metrics_path = out_dir / "attack_diversity_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"\n  Metrics saved: {metrics_path}")

    # Plot PCA colored by family
    fig, ax = plt.subplots(figsize=(12, 8))
    colors = plt.cm.tab20(np.linspace(0, 1, len(family_names)))

    for i, fam in enumerate(family_names):
        mask = family_labels == fam
        ax.scatter(X_pca[mask, 0], X_pca[mask, 1], label=fam, alpha=0.6, s=30, color=colors[i])

    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%})")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%})")
    ax.set_title("Attack Families: Feature-Space Clustering (PCA)")
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    ax.grid(True, alpha=0.3)

    plot_path = out_dir / "attack_diversity_pca.png"
    fig.tight_layout()
    fig.savefig(plot_path, dpi=100)
    print(f"  PCA plot saved: {plot_path}")

    print("\n" + "="*80)
    print("DIVERSITY ANALYSIS COMPLETE")
    print("="*80)
    print(f"\nSUMMARY:")
    print(f"  Current attack families: {metrics['n_families']}")
    print(f"  Separation ratio: {metrics['separation_ratio']:.2f}x")
    print(f"  Natural cluster estimate: {metrics['estimated_natural_clusters']}")

    return metrics


if __name__ == "__main__":
    analyze_diversity()
