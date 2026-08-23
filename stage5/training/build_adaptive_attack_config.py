"""Closes the loop: reads a trained detector's feature importances and
derives the `config` dict the next generation of `adversarial_evasion`
campaigns should use to specifically target whatever the detector currently
leans on most (issues.md I11).

This is the missing half of "detector misses -> new attack variant ->
detector improves." The `adaptive_top_counterparty`/`beneficiary_age_floor_s`
config keys this produces are consumed by
`src.attacks.generators.AdversarialEvasionAttack.generate` -- see that
class's docstring-adjacent comment for what each one changes.

Usage (second and later pipeline iterations only -- the first run has no
prior model to adapt to, and falls back to static defaults):

    from stage5.training.build_adaptive_attack_config import build_adaptive_config
    config = build_adaptive_config()
    generator.generate(baseline, seed=seed, intensity=intensity, config=config)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import joblib

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from stage5.config.settings import MODELS_DIR

# If a feature holds at least this share of total importance, the adaptive
# attack should specifically target it. Reasoned threshold, not tuned against
# a labelled outcome: high enough to ignore noise in a long importance tail,
# low enough to catch a feature that dominates without being the single top
# one (docs/model-choice.md's post-I6/I7/I17 run had edge_count at 34%).
TARGET_IMPORTANCE_THRESHOLD = 0.10

# How close to the population maximum to push beneficiary_added_ago_s when
# that feature clears the threshold -- 80% of the way from floor to ceiling,
# not the ceiling itself, so the distribution doesn't collapse to a single
# suspiciously-exact value.
BENEFICIARY_AGE_ADAPTIVE_FRACTION = 0.8


def build_adaptive_config() -> dict[str, Any]:
    """Inspect the currently-saved fraud model and return an `adversarial_evasion`
    config dict targeting whichever features it currently relies on most.
    Returns {} (falls back to static defaults) if no model has been trained yet.
    """
    model_path = MODELS_DIR / "fraud_model.pkl"
    preprocessor_path = MODELS_DIR / "preprocessor.pkl"
    if not (model_path.exists() and preprocessor_path.exists()):
        return {}

    model = joblib.load(model_path)
    preprocessor = joblib.load(preprocessor_path)
    if not hasattr(model, "feature_importances_"):
        return {}

    names = preprocessor.get_feature_names_out()
    importances = model.feature_importances_
    by_name = dict(zip(names, importances))

    config: dict[str, Any] = {}

    edge_count_importance = by_name.get("num__edge_count", 0.0)
    if edge_count_importance >= TARGET_IMPORTANCE_THRESHOLD:
        # For Gen 3, instead of concentrating on a single top counterparty,
        # spread volume across a wide pool to evade density detection.
        config["adaptive_volume_splitting"] = True

    ben_age_importance = by_name.get("num__beneficiary_added_ago_s", 0.0)
    if ben_age_importance >= TARGET_IMPORTANCE_THRESHOLD:
        from src.generators import calibration as cal

        floor = cal.LEGIT_EXISTING_BENEFICIARY_MIN_AGE_S
        ceiling = cal.LEGIT_EXISTING_BENEFICIARY_MAX_AGE_S
        config["beneficiary_age_floor_s"] = int(
            floor + BENEFICIARY_AGE_ADAPTIVE_FRACTION * (ceiling - floor)
        )
        # Enable Gen 3 full sleeper emulation
        config["adaptive_sleeper"] = True

    return config


if __name__ == "__main__":
    result = build_adaptive_config()
    if result:
        print(f"Adaptive config derived from current model: {result}")
    else:
        print("No trained model found (or no feature cleared the target threshold) -- static defaults apply.")
