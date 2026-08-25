"""
Sequential driver: baseline -> Gen 3 -> Gen 4 -> Gen 5.

Run one stage per process invocation (`--stage baseline|gen3|gen4|gen5`) so
each generation's memory is fully released by the OS when its process exits,
not just gc'd within one long-running process -- deliberate, since this
machine has limited free RAM. Each stage loads only what it needs from the
previous stage's saved artifacts on disk.
"""
import argparse
import gc
import sys
import json
import joblib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd

from stage5.training.train_fraud_model import train_fraud_model, load_and_prepare
from stage5.training.gen3_pipeline import run_gen3_pipeline
from stage5.training.gen4_pipeline import run_gen4_pipeline
from stage5.training.gen5_pipeline import run_gen5_pipeline
from stage5.config.settings import MODELS_DIR

DATA_DIR = Path("data/generated/stage5/combined")
OUT_DIR = Path("stage5/data")


def load_df():
    # Same feature engineering + temporal split as train_fraud_model.main()
    # -- the raw parquet alone has neither engineered features nor a split
    # column.
    df = load_and_prepare(combined_dir=DATA_DIR)
    print(f"  {len(df)} rows loaded")
    return df


def empty_feedback(df):
    return pd.DataFrame(columns=df.columns)


def load_retained_attacks(*paths: Path) -> pd.DataFrame | None:
    """Concatenate whichever of the given retained-attack parquet files exist.

    Each generation's retained sample is saved separately (gen3_retained_attacks.parquet,
    etc.) so a generation only needs to know about the ones before it, not maintain
    one ever-growing file itself.
    """
    frames = [pd.read_parquet(p) for p in paths if p.exists()]
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True, sort=False)


def save_retained_attacks(df: pd.DataFrame, path: Path) -> None:
    df.to_parquet(path, index=False)
    print(f"  Saved {len(df)} retained attack rows to {path}")


def run_baseline():
    print("=" * 80)
    print("BASELINE TRAINING (pre-curriculum)")
    print("=" * 80)

    # train_fraud_model.main() (run earlier in the pipeline) already trained
    # and saved this exact baseline to stage5/models/ -- reuse it rather than
    # pay for training the same thing twice.
    if (MODELS_DIR / "fraud_model.pkl").exists() and (MODELS_DIR / "model_metadata.json").exists():
        print(f"  Reusing baseline already trained by train_fraud_model.main() at {MODELS_DIR}")
        model = joblib.load(MODELS_DIR / "fraud_model.pkl")
        preprocessor = joblib.load(MODELS_DIR / "preprocessor.pkl")
        metadata = json.loads((MODELS_DIR / "model_metadata.json").read_text())
        metrics = {"validation_metrics": metadata["validation_metrics"], "test_metrics": metadata["test_metrics"]}
    else:
        df = load_df()
        result = train_fraud_model(df)
        model, preprocessor, metrics = result["model"], result["preprocessor"], result["metrics"]

    joblib.dump(model, OUT_DIR / "baseline_model.pkl")
    joblib.dump(preprocessor, OUT_DIR / "baseline_preprocessor.pkl")
    (OUT_DIR / "baseline_evaluation_report.json").write_text(
        json.dumps(metrics, indent=2, default=str)
    )
    print(f"  Baseline PR-AUC: {metrics['test_metrics']['pr_auc']:.4f}")
    print("BASELINE COMPLETE")


def run_gen3():
    print("=" * 80)
    print("GEN 3 PIPELINE")
    print("=" * 80)
    df = load_df()
    gen2_model = joblib.load(OUT_DIR / "baseline_model.pkl")
    gen2_preprocessor = joblib.load(OUT_DIR / "baseline_preprocessor.pkl")
    gen2_model_metrics = json.loads((OUT_DIR / "baseline_evaluation_report.json").read_text())

    result = run_gen3_pipeline(
        gen2_model=gen2_model,
        analyst_feedback_df=empty_feedback(df),
        original_training_df=df,
        gen2_preprocessor=gen2_preprocessor,
        gen2_model_metrics=gen2_model_metrics,
        output_dir=OUT_DIR / "gen3_pipeline",
        accumulated_attacks_df=None,  # Gen 3 is first in the chain, nothing to carry forward yet
    )
    if result.get("status") == "FAILED":
        print(f"Gen 3 FAILED: {result.get('error')}")
        sys.exit(1)

    joblib.dump(result["gen3_model"], OUT_DIR / "gen3_model.pkl")
    joblib.dump(result["gen3_preprocessor"], OUT_DIR / "gen3_preprocessor.pkl")
    (OUT_DIR / "gen3_evaluation_report.json").write_text(
        json.dumps(result["evaluation_report"], indent=2, default=str)
    )
    save_retained_attacks(result["retained_attacks"], OUT_DIR / "gen3_retained_attacks.parquet")
    print(f"\n  Gen 3 best evasion: {result['best_evasion']*100:.1f}%")
    print("GEN3 COMPLETE")


def run_gen4():
    print("=" * 80)
    print("GEN 4 PIPELINE")
    print("=" * 80)
    df = load_df()
    gen3_model = joblib.load(OUT_DIR / "gen3_model.pkl")
    gen3_preprocessor = joblib.load(OUT_DIR / "gen3_preprocessor.pkl")

    accumulated = load_retained_attacks(OUT_DIR / "gen3_retained_attacks.parquet")

    result = run_gen4_pipeline(
        gen3_model=gen3_model,
        gen3_training_data_df=df,
        analyst_feedback_df=empty_feedback(df),
        gen3_preprocessor=gen3_preprocessor,
        gen3_model_metrics=None,
        output_dir=OUT_DIR / "gen4_pipeline",
        accumulated_attacks_df=accumulated,
    )
    if result.get("status") == "FAILED":
        print(f"Gen 4 FAILED: {result.get('error')}")
        sys.exit(1)

    joblib.dump(result["gen4_model"], OUT_DIR / "gen4_model.pkl")
    joblib.dump(result["gen4_preprocessor"], OUT_DIR / "gen4_preprocessor.pkl")
    (OUT_DIR / "gen4_evaluation_report.json").write_text(
        json.dumps(result["evaluation_report"], indent=2, default=str)
    )
    save_retained_attacks(result["retained_attacks"], OUT_DIR / "gen4_retained_attacks.parquet")
    print(f"\n  Gen 4 evasion rate: {result['evasion_rate']*100:.1f}%")
    print("GEN4 COMPLETE")


def run_gen5():
    print("=" * 80)
    print("GEN 5 PIPELINE")
    print("=" * 80)
    df = load_df()
    gen4_model = joblib.load(OUT_DIR / "gen4_model.pkl")
    gen4_preprocessor = joblib.load(OUT_DIR / "gen4_preprocessor.pkl")

    accumulated = load_retained_attacks(
        OUT_DIR / "gen3_retained_attacks.parquet", OUT_DIR / "gen4_retained_attacks.parquet",
    )

    result = run_gen5_pipeline(
        gen4_model=gen4_model,
        gen4_training_data_df=df,
        analyst_feedback_df=empty_feedback(df),
        gen4_preprocessor=gen4_preprocessor,
        gen4_model_metrics=None,
        output_dir=OUT_DIR / "gen5_pipeline",
        accumulated_attacks_df=accumulated,
    )
    if result.get("status") == "FAILED":
        print(f"Gen 5 FAILED: {result.get('error')}")
        sys.exit(1)

    joblib.dump(result["gen5_model"], OUT_DIR / "gen5_model.pkl")
    joblib.dump(result["gen5_preprocessor"], OUT_DIR / "gen5_preprocessor.pkl")
    (OUT_DIR / "gen5_evaluation_report.json").write_text(
        json.dumps(result["evaluation_report"], indent=2, default=str)
    )
    save_retained_attacks(result["retained_attacks"], OUT_DIR / "gen5_retained_attacks.parquet")
    print(f"\n  Gen 5 evasion rate: {result['evasion_rate']*100:.1f}%")

    # Promote the fully-hardened Gen 5 model to the path the live inference
    # pipeline (stage5/inference/pipeline.py) actually loads from, so the
    # deployed app serves the curriculum-hardened model, not the pre-curriculum
    # baseline.
    joblib.dump(result["gen5_model"], MODELS_DIR / "fraud_model.pkl")
    joblib.dump(result["gen5_preprocessor"], MODELS_DIR / "preprocessor.pkl")
    print(f"  Promoted Gen 5 model to {MODELS_DIR} for live inference")
    print("GEN5 COMPLETE")


STAGES = {"baseline": run_baseline, "gen3": run_gen3, "gen4": run_gen4, "gen5": run_gen5}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=list(STAGES.keys()))
    args = parser.parse_args()
    STAGES[args.stage]()
    gc.collect()
