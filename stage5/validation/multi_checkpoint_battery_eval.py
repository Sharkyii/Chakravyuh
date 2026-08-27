"""Compare all 4 curriculum checkpoints (baseline/gen3/gen4/gen5) on exactly
the same wide, disjoint-seed attack battery, each scored against its OWN
fixed-FPR thresholds.

Generates one battery dataset (16 families x 3 intensities x N_SEEDS_PER_CELL
independent seeds), runs BehavioralFeatureTracker over it exactly once, then
scores that single feature matrix with each checkpoint's own
model+preprocessor pair. Fairness requires each checkpoint's own threshold:
the 4 checkpoints have materially different probability calibration (e.g.
gen5's Brier score is ~50x worse than baseline's, with a 0.1%-FPR threshold
near 0.95 vs baseline's ~0.25) -- comparing raw probabilities or applying one
checkpoint's threshold to another's predictions would be meaningless.

Requires the baseline stage2 dataset and the primary combined dataset to
already be generated on disk (not committed to git). Not part of CI.
"""
import sys
import json
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from stage5.config.settings import ALL_FEATURES, HELD_OUT_ATTACK_FAMILY
from stage5.training.train_fraud_model import (
    load_and_prepare,
    pr_auc_score,
    precision_recall_at_fixed_fpr,
)
from stage5.validation.full_family_battery_eval import (
    FAMILIES,
    INTENSITIES,
    load_dataset,
    BASELINE_STAGE2_DIR,
    generate_all_campaigns,
    build_scored_dataframe,
)

N_SEEDS_PER_CELL = 50
# Disjoint from training seeds ([101_000, 116_999]) AND from
# full_family_battery_eval.py's own EVAL_SEED_BASE=900_000_000 run (whose
# range tops out around 900_000_000 + 15*1_000_000 + 2*100_000 + 9 ~=
# 915_200_009) -- this run's range starts at 950_000_000, well clear of both.
EVAL_SEED_BASE = 950_000_000
REPORT_PATH = Path(__file__).resolve().parent / "multi_checkpoint_battery_results.json"

CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "data"
CHECKPOINTS = {
    "baseline": (CHECKPOINT_DIR / "baseline_model.pkl", CHECKPOINT_DIR / "baseline_preprocessor.pkl"),
    "gen3": (CHECKPOINT_DIR / "gen3_model.pkl", CHECKPOINT_DIR / "gen3_preprocessor.pkl"),
    "gen4": (CHECKPOINT_DIR / "gen4_model.pkl", CHECKPOINT_DIR / "gen4_preprocessor.pkl"),
    "gen5": (CHECKPOINT_DIR / "gen5_model.pkl", CHECKPOINT_DIR / "gen5_preprocessor.pkl"),
}


@dataclass
class Checkpoint:
    name: str
    model: object
    preprocessor: object
    thresh_01pct: float
    thresh_1pct: float
    achieved_fpr_01pct: float
    achieved_fpr_1pct: float


def load_checkpoints() -> dict[str, tuple]:
    loaded = {}
    for name, (model_path, preproc_path) in CHECKPOINTS.items():
        assert model_path.exists(), f"missing checkpoint model: {model_path}"
        assert preproc_path.exists(), f"missing checkpoint preprocessor: {preproc_path}"
        loaded[name] = (joblib.load(model_path), joblib.load(preproc_path))
    return loaded


def derive_own_thresholds(loaded: dict[str, tuple]) -> dict[str, Checkpoint]:
    """Each checkpoint's 0.1%/1%-FPR threshold, computed ONLY from that
    checkpoint's own predictions on the primary held-out temporal test split
    -- never borrowed from another checkpoint (gen5's threshold is ~4x
    baseline's on the raw probability scale, so reusing it across checkpoints
    would silently invalidate the comparison).
    """
    print("Loading primary held-out test split to derive per-checkpoint thresholds...", flush=True)
    df = load_and_prepare(held_out_attack_family=HELD_OUT_ATTACK_FAMILY)
    test_df = df[df["split"] == "test"].copy()
    y_test = test_df["is_fraud"].astype(int).to_numpy()
    X_test = test_df.reindex(columns=list(test_df.columns) + [c for c in ALL_FEATURES if c not in test_df.columns])

    checkpoints = {}
    for name, (model, preprocessor) in loaded.items():
        probs = model.predict_proba(preprocessor.transform(X_test[ALL_FEATURES]))[:, 1]
        m01 = precision_recall_at_fixed_fpr(y_test, probs, 0.001)
        m1 = precision_recall_at_fixed_fpr(y_test, probs, 0.01)
        pr_auc = pr_auc_score(y_test, probs)
        roc_auc = roc_auc_score(y_test, probs) if len(set(y_test)) > 1 else float("nan")
        print(f"  {name}: PR-AUC={pr_auc:.4f} ROC-AUC={roc_auc:.4f} "
              f"thresh@0.1%FPR={m01['threshold']:.4f} (achieved {m01['achieved_fpr']*100:.3f}%) "
              f"thresh@1%FPR={m1['threshold']:.4f} (achieved {m1['achieved_fpr']*100:.3f}%)", flush=True)
        checkpoints[name] = Checkpoint(
            name=name, model=model, preprocessor=preprocessor,
            thresh_01pct=m01["threshold"], thresh_1pct=m1["threshold"],
            achieved_fpr_01pct=m01["achieved_fpr"], achieved_fpr_1pct=m1["achieved_fpr"],
        )
    return checkpoints


def score_battery_per_checkpoint(df, checkpoints: dict[str, Checkpoint]) -> dict[str, np.ndarray]:
    X = df[ALL_FEATURES]
    probs_by_checkpoint = {}
    for name, ckpt in checkpoints.items():
        probs_by_checkpoint[name] = ckpt.model.predict_proba(ckpt.preprocessor.transform(X))[:, 1]
    return probs_by_checkpoint


def main(n_seeds: int = N_SEEDS_PER_CELL):
    """Callable directly (e.g. from run_all_generations.py's gen5 stage) with
    an explicit n_seeds, or run as a script -- see __main__ below for the
    CLI wrapper. Kept separate from argparse so importing this function
    doesn't accidentally parse the caller's own command-line arguments.
    """
    print(f"Families: {len(FAMILIES)}, intensities: {len(INTENSITIES)}, seeds/cell: {n_seeds}")
    print(f"Total campaigns to generate: {len(FAMILIES) * len(INTENSITIES) * n_seeds}")
    print(f"Eval seed range: [{EVAL_SEED_BASE}, {EVAL_SEED_BASE + len(FAMILIES) * 1_000_000 - 1}]")
    print("Training seed range: [101000, 116999] -- disjoint by construction.")

    loaded = load_checkpoints()
    checkpoints = derive_own_thresholds(loaded)

    print("\nLoading baseline dataset for attack generation...", flush=True)
    baseline = load_dataset(BASELINE_STAGE2_DIR)

    all_rows, all_meta = generate_all_campaigns(baseline, n_seeds_per_cell=n_seeds, seed_base=EVAL_SEED_BASE)
    print(f"Generated {len(all_rows)} total attack rows across {len(FAMILIES)} families", flush=True)

    # Sanity check: every generated seed must fall in our reserved range and
    # nowhere near the training seed range -- catches a wiring mistake here
    # rather than silently producing a contaminated comparison.
    seeds_used = {m["seed"] for m in all_meta}
    assert all(s >= EVAL_SEED_BASE for s in seeds_used), "a generated seed fell below EVAL_SEED_BASE"
    assert not (seeds_used & set(range(101_000, 117_000))), "a generated seed collided with the training seed range"

    df = build_scored_dataframe(baseline, all_rows, all_meta)
    print(f"Feature matrix built: {len(df)} total rows "
          f"({(df['__family__'] == '__legit__').sum()} legit, {(df['__family__'] != '__legit__').sum()} attack)")

    probs_by_checkpoint = score_battery_per_checkpoint(df, checkpoints)

    families_meta = df["__family__"].values
    intensity_meta = df["__intensity__"].values
    seed_meta = df["__seed__"].values

    # Full per-row granularity, preserved for later per-seed analysis.
    per_row_records = []
    for name, probs in probs_by_checkpoint.items():
        for fam, intensity, seed, prob in zip(families_meta, intensity_meta, seed_meta, probs):
            per_row_records.append({
                "checkpoint": name, "family": fam, "intensity": intensity,
                "seed": int(seed), "prob": float(prob),
            })

    # Aggregated checkpoint x family x intensity table.
    per_row_df = pd.DataFrame(per_row_records)
    thresholds_used = {name: ckpt.thresh_01pct for name, ckpt in checkpoints.items()}
    thresholds_1pct = {name: ckpt.thresh_1pct for name, ckpt in checkpoints.items()}

    per_row_df["hit_01pct"] = per_row_df["prob"] >= per_row_df["checkpoint"].map(thresholds_used)
    per_row_df["hit_1pct"] = per_row_df["prob"] >= per_row_df["checkpoint"].map(thresholds_1pct)

    print("\n" + "=" * 100)
    print("OVERALL BATTERY RECALL PER CHECKPOINT (excludes __legit__)")
    print("=" * 100)
    overall = {}
    for name in checkpoints:
        sub = per_row_df[(per_row_df["checkpoint"] == name) & (per_row_df["family"] != "__legit__")]
        legit_sub = per_row_df[(per_row_df["checkpoint"] == name) & (per_row_df["family"] == "__legit__")]
        recall_01 = sub["hit_01pct"].mean()
        recall_1 = sub["hit_1pct"].mean()
        fpr_01 = legit_sub["hit_01pct"].mean()
        fpr_1 = legit_sub["hit_1pct"].mean()
        overall[name] = {
            "recall_01pct": float(recall_01), "recall_1pct": float(recall_1),
            "legit_fpr_01pct": float(fpr_01), "legit_fpr_1pct": float(fpr_1),
            "n_attack_rows": int(len(sub)), "n_legit_rows": int(len(legit_sub)),
        }
        print(f"  {name:<10} recall@0.1%FPR={recall_01*100:6.2f}%  recall@1%FPR={recall_1*100:6.2f}%  "
              f"(battery legit FPR@0.1%={fpr_01*100:.3f}%  @1%={fpr_1*100:.3f}%)  n={len(sub)}")
    print("=" * 100)

    print("\n" + "=" * 110)
    print("CHECKPOINT x FAMILY x INTENSITY -- recall @ that checkpoint's own 0.1%-FPR threshold")
    header = f"{'Family':<28}" + "".join(f"{name+' L/M/H':>22}" for name in checkpoints)
    print(header)
    print("=" * 110)
    family_intensity_table = []
    for family in FAMILIES:
        row_label = f"{family:<28}"
        row_cells = []
        row_record = {"family": family}
        for name in checkpoints:
            cell_vals = []
            for intensity in ("LOW", "MEDIUM", "HIGH"):
                sub = per_row_df[
                    (per_row_df["checkpoint"] == name)
                    & (per_row_df["family"] == family)
                    & (per_row_df["intensity"] == intensity)
                ]
                if len(sub) == 0:
                    cell_vals.append("n/a")
                    row_record[f"{name}_{intensity}"] = None
                else:
                    r = sub["hit_01pct"].mean()
                    cell_vals.append(f"{r*100:.0f}%")
                    row_record[f"{name}_{intensity}"] = float(r)
            row_cells.append("/".join(cell_vals))
        family_intensity_table.append(row_record)
        print(row_label + "".join(f"{c:>22}" for c in row_cells))
    print("=" * 110)

    REPORT_PATH.write_text(json.dumps({
        "n_seeds_per_cell": N_SEEDS_PER_CELL,
        "eval_seed_base": EVAL_SEED_BASE,
        "checkpoint_thresholds": {
            name: {
                "thresh_01pct": ckpt.thresh_01pct, "thresh_1pct": ckpt.thresh_1pct,
                "achieved_fpr_01pct": ckpt.achieved_fpr_01pct, "achieved_fpr_1pct": ckpt.achieved_fpr_1pct,
            } for name, ckpt in checkpoints.items()
        },
        "overall_battery_recall": overall,
        "family_x_intensity": family_intensity_table,
        "per_row": per_row_records,
    }, indent=2))
    print(f"\nSaved full report (incl. per-row granularity): {REPORT_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-seeds", type=int, default=N_SEEDS_PER_CELL,
                         help="seeds per family x intensity cell (default 50; use a small value for a dry run)")
    args = parser.parse_args()
    main(n_seeds=args.n_seeds)
