"""
Cross-generation evaluation: does the final deployed model (Gen 5's
checkpoint, promoted to stage5/models/) still hold up against Gen 3's and
Gen 4's attacks, or did chasing harder attacks regress it on easier ones?

Regenerates the same three attack sets each generation's pipeline built
(same generator classes, same seeds via the same prior-model inputs, same
n_campaigns), then scores the ONE deployed model against all three. This is
inference only -- no retraining -- so it's cheap to rerun after any change.

Answers: "what does the model we actually ship catch, across the full
attack lineage" -- the one table worth reporting, instead of five
generation-specific stories.
"""
import sys
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage5.training.train_fraud_model import load_and_prepare
from stage5.adversarial.gen3_generator import Gen3AttackGenerator
from stage5.adversarial.gen4_generator import Gen4AttackGenerator
from stage5.adversarial.gen5_generator import Gen5AttackGenerator
from stage5.adversarial.evasion_margin_calculator import measure_evasion_margin
from stage5.config.settings import ALL_FEATURES, MODELS_DIR

OUT_DIR = Path("stage5/data")
DATA_DIR = Path("data/generated/stage5/combined")


def as_feature_frame(attacks: list) -> pd.DataFrame:
    df = pd.DataFrame([a['features'] for a in attacks])
    return df.reindex(columns=ALL_FEATURES)


def flatten(attacks_by_level: dict) -> list:
    return [a for level in attacks_by_level.values() for a in level]


def main():
    print("=" * 80)
    print("CROSS-GENERATION EVALUATION: final deployed model vs. Gen 3/4/5 attacks")
    print("=" * 80)

    print("\nLoading dataset + prior-generation checkpoints...")
    df = load_and_prepare(combined_dir=DATA_DIR)

    gen2_model = joblib.load(OUT_DIR / "baseline_model.pkl")
    gen2_preprocessor = joblib.load(OUT_DIR / "baseline_preprocessor.pkl")
    gen3_model = joblib.load(OUT_DIR / "gen3_model.pkl")
    gen3_preprocessor = joblib.load(OUT_DIR / "gen3_preprocessor.pkl")
    gen4_model = joblib.load(OUT_DIR / "gen4_model.pkl")
    gen4_preprocessor = joblib.load(OUT_DIR / "gen4_preprocessor.pkl")

    deployed_model = joblib.load(MODELS_DIR / "fraud_model.pkl")
    deployed_preprocessor = joblib.load(MODELS_DIR / "preprocessor.pkl")
    print("  Deployed model loaded from stage5/models/fraud_model.pkl (the Gen 5 checkpoint)")

    print("\nRegenerating Gen 3 attacks (adversarial_evasion family, the one used for retraining)...")
    gen3_generator = Gen3AttackGenerator(gen2_model, df, gen2_preprocessor)
    gen3_attacks = gen3_generator.generate_curriculum_attacks(attack_family='adversarial_evasion', n_campaigns=100)
    gen3_flat = flatten(gen3_attacks)
    print(f"  {len(gen3_flat)} Gen 3 attack variants")

    print("\nRegenerating Gen 4 ensemble attacks...")
    gen4_generator = Gen4AttackGenerator(gen3_model, df, gen3_preprocessor)
    gen4_attacks = gen4_generator.generate_curriculum_attacks(n_campaigns=100)
    gen4_flat = flatten(gen4_attacks)
    print(f"  {len(gen4_flat)} Gen 4 attack variants")

    print("\nRegenerating Gen 5 multi-family attacks...")
    gen5_generator = Gen5AttackGenerator(gen4_model, df, gen4_preprocessor)
    gen5_attacks = gen5_generator.generate_curriculum_attacks(n_campaigns=100)
    gen5_flat = flatten(gen5_attacks)
    print(f"  {len(gen5_flat)} Gen 5 attack variants")

    print("\n" + "=" * 80)
    print("SCORING DEPLOYED MODEL AGAINST EACH ATTACK GENERATION")
    print("=" * 80)

    results = {}
    for label, flat_attacks in [("gen3_attacks", gen3_flat), ("gen4_attacks", gen4_flat), ("gen5_attacks", gen5_flat)]:
        X = as_feature_frame(flat_attacks)
        y = np.ones(len(X))
        margin = measure_evasion_margin(
            deployed_model, X, y, generation=label, preprocessor=deployed_preprocessor,
        )
        results[label] = margin
        print(f"\n  {label:15s} n={len(X):5d}  evasion={margin['evasion_percent']:>8s}  "
              f"caught={margin['caught']}/{margin['total']}  status={margin['status']}")

    report = {
        "model": "deployed (stage5/models/fraud_model.pkl, promoted from Gen 5 checkpoint)",
        "results_by_attack_generation": results,
        "interpretation": (
            "Each row is the SAME deployed model scored against a different generation's "
            "attack set. A materially higher evasion rate on gen3/gen4 attacks than the "
            "gen5 curriculum log reported would mean the model regressed on easier attacks "
            "while being hardened against harder ones -- the thing this check exists to catch."
        ),
    }

    out_path = Path("stage5/validation/cross_generation_evaluation.json")
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nReport saved: {out_path}")


if __name__ == "__main__":
    main()
