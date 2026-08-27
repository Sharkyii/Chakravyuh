"""Cheap, always-runnable checks on the committed model_metadata.json.

These pin the ordering _calibrated_base_score() (stage5/inference/pipeline.py)
assumes between its two calibration anchors. A curriculum retrain that
promotes a new model into stage5/models/ without recomputing
model_metadata.json (see stage5/validation/evaluate_deployed_model.py) can
leave selected_threshold stale relative to the model's actual fixed-FPR
thresholds -- silently inverting the ordering and breaking the risk-score
fusion for every live prediction without any loud failure. Caught once by
hand this way; pinned here so it can't happen silently again.
"""

import json

from stage5.config.settings import MODELS_DIR


def _load_metadata() -> dict:
    return json.loads((MODELS_DIR / "model_metadata.json").read_text())


def test_fixed_fpr_thresholds_are_monotonic():
    metadata = _load_metadata()
    points = sorted(
        metadata["test_metrics"]["fixed_fpr_operating_points"], key=lambda p: p["target_fpr"]
    )
    assert len(points) >= 2, "expected at least the 0.1%/1% FPR operating points"
    for lower_fpr, higher_fpr in zip(points, points[1:]):
        # A stricter (lower) target FPR must require a higher score threshold.
        assert lower_fpr["threshold"] > higher_fpr["threshold"], (
            f"threshold at {lower_fpr['target_fpr']*100:.2f}% FPR "
            f"({lower_fpr['threshold']}) should exceed the threshold at "
            f"{higher_fpr['target_fpr']*100:.2f}% FPR ({higher_fpr['threshold']})"
        )


def test_selected_threshold_sits_between_recall_and_saturation():
    metadata = _load_metadata()
    points = {
        p["target_fpr"]: p["threshold"]
        for p in metadata["test_metrics"]["fixed_fpr_operating_points"]
    }
    recall_threshold = points[
        0.01
    ]  # the 1%-FPR point _calibrated_base_score() calls recall_threshold
    selected_threshold = metadata["selected_threshold"]

    assert recall_threshold < selected_threshold < 1.0, (
        f"_calibrated_base_score() requires recall_threshold ({recall_threshold}) < "
        f"selected_threshold ({selected_threshold}) < 1.0 -- if this fails after a "
        f"retrain, model_metadata.json's selected_threshold is stale relative to the "
        f"promoted model; rerun stage5/validation/evaluate_deployed_model.py"
    )
