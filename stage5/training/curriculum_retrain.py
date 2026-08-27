"""
Curriculum Retraining: train on a generation's attacks with progressive
difficulty levels, measuring evasion at each stage. Used by Gen 3, 4, and 5
pipelines alike -- the mechanics don't depend on which generation's attacks
are being fed in, only the level names and target evasion threshold differ.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json

from stage5.training.train_fraud_model import (
    precision_recall_at_fixed_fpr,
    train_fraud_model,
)
from stage5.adversarial.evasion_margin_calculator import measure_evasion_margin
from stage5.config.settings import ALL_FEATURES


def _as_feature_frame(attacks: list) -> pd.DataFrame:
    """Attack dicts -> a DataFrame aligned to the model's full feature schema.

    Any ALL_FEATURES column the attack generator didn't populate is left NaN;
    the preprocessor's imputers handle that the same as a genuinely missing
    real-world field.
    """
    df = pd.DataFrame([a['features'] for a in attacks])
    return df.reindex(columns=ALL_FEATURES)


RETAINED_SAMPLE_CAP = 1500
LEVEL_ATTACK_CAP = 600
TRAIN_FRACTION = 0.8
# Curriculum pass/fail checks use the detector's 1%-FPR decision point, the
# same operational definition of "caught" used by the production inference
# path.  This must be derived separately for every checkpoint, since their
# probability calibrations change during retraining.
CURRICULUM_FIXED_FPR_TARGET = 0.01


def _fixed_fpr_threshold(model, preprocessor, reference_df: pd.DataFrame) -> float:
    """Derive a checkpoint's 1%-FPR threshold on its held-out temporal test set."""
    calibration_df = reference_df[reference_df['split'] == 'test']
    if calibration_df.empty or calibration_df['is_fraud'].nunique() < 2:
        raise ValueError(
            "Cannot calibrate curriculum evasion threshold: the reference test "
            "split must contain both legitimate and fraud rows."
        )

    X = calibration_df.reindex(columns=ALL_FEATURES)
    probabilities = model.predict_proba(preprocessor.transform(X))[:, 1]
    return precision_recall_at_fixed_fpr(
        calibration_df['is_fraud'].to_numpy(), probabilities,
        CURRICULUM_FIXED_FPR_TARGET,
    )['threshold']


def retrain_on_gen3_attacks(
    analyst_feedback_df: pd.DataFrame,
    gen3_attacks_by_level: dict,
    original_training_df: pd.DataFrame,
    gen2_model,
    gen2_preprocessor=None,
    generation_label: str = 'gen3',
    target_evasion: float = 0.05,
    output_dir: Path = None,
    accumulated_attacks_df: pd.DataFrame = None,
) -> dict:
    """
    Retrain on a generation's attacks using curriculum learning.

    Flow:
    1. Start with the easiest level
    2. Train model
    3. Evaluate: prior-generation recall (no regression) + this generation's evasion
    4. Move to the next level
    5. Repeat through the hardest level, stopping early once target_evasion is met

    Args:
        analyst_feedback_df: analyst verdicts (training data)
        gen3_attacks_by_level: {level_name: [attack, ...], ...} -- level names
            and count are whatever the generation's attack generator produced;
            this function makes no assumption about their spelling.
        original_training_df: Original synthetic training data (needs 'split',
            'is_fraud', and the model's feature columns)
        gen2_model: Previous generation's model (used only for before/after
            evasion comparison, not required to be non-None)
        gen2_preprocessor: the fitted ColumnTransformer gen2_model was trained
            with. Required to score gen2_model correctly -- an XGBClassifier
            can't take raw categorical/unscaled features directly.
        generation_label: passed through to measure_evasion_margin for
            logging/context, and used to name output files
        target_evasion: stop the curriculum early once evasion drops at or
            below this value (Gen 3: 0.05, Gen 4: 0.15, Gen 5: 0.25 per the
            brief's escalating targets)
        output_dir: Where to save training logs
        accumulated_attacks_df: prior generations' retained attack rows (see
            `retained_attacks` in this function's return value), mixed into
            every level's training set alongside this generation's own
            attacks. Without this, each generation trains from scratch on
            (base data + only its own new attacks) and has zero exposure to
            earlier generations' attack patterns -- confirmed via
            cross_generation_eval.py to cause exactly the regression this
            parameter exists to prevent: a Gen 5-trained model evading 85%
            of Gen 3's attacks despite Gen 3 itself having gotten that down
            to 34%. Pass None only for the first generation in the chain.

    Returns:
        {
            'model': trained model (best-evasion checkpoint),
            'preprocessor': that checkpoint's fitted ColumnTransformer,
            'model_metrics': that checkpoint's real train_fraud_model() metrics,
            'curriculum_log': {level_name: {...}, ...},
            'best_evasion': float,
            'improvement_from_gen2': bool,
            'prior_gen_evasion': float | None,  # this generation's attacks against gen2_model, before retraining
            'retained_attacks': pd.DataFrame,  # this generation's attack sample, to pass as
                                                # the NEXT generation's accumulated_attacks_df
        }
    """

    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "data" / f"{generation_label}_training"
    output_dir.mkdir(parents=True, exist_ok=True)

    curriculum_log = {}
    best_model = None
    best_preprocessor = None
    best_model_metrics = None
    best_threshold = None
    best_evasion = 1.0
    all_models = {}

    levels = list(gen3_attacks_by_level.keys())
    this_gen_levels_seen: list[pd.DataFrame] = []
    this_gen_test_seen: list[pd.DataFrame] = []

    n_accumulated = len(accumulated_attacks_df) if accumulated_attacks_df is not None else 0
    if n_accumulated:
        print(f"\n  Carrying forward {n_accumulated} retained attack rows from prior generations")

    print("\n" + "="*70)
    print(f"{generation_label.upper()} CURRICULUM RETRAINING")
    print("="*70)

    # Baseline: how badly does the PRIOR model do against these new attacks,
    # before any retraining? This is "why we retrain" -- the evasion measurement
    # that motivates this whole cycle, not something to leave hardcoded.
    prior_gen_evasion = None
    if gen2_model is not None and gen2_preprocessor is not None:
        all_attacks_flat = [a for lvl in gen3_attacks_by_level.values() for a in lvl]
        if all_attacks_flat:
            baseline_X = _as_feature_frame(all_attacks_flat)
            baseline_y = np.ones(len(baseline_X))
            baseline_threshold = _fixed_fpr_threshold(
                gen2_model, gen2_preprocessor, original_training_df,
            )
            baseline_margin = measure_evasion_margin(
                gen2_model, baseline_X, baseline_y,
                generation=generation_label, preprocessor=gen2_preprocessor,
                threshold=baseline_threshold,
            )
            prior_gen_evasion = baseline_margin['evasion_margin']
            print(f"\n  Baseline: {generation_label} attacks vs prior-generation model: "
                  f"{prior_gen_evasion*100:.1f}% evasion (why we retrain)")

    for level_idx, level_name in enumerate(levels):
        print(f"\n[{level_idx+1}/{len(levels)}] {level_name.upper()}")
        print("-" * 70)

        gen3_attacks = gen3_attacks_by_level[level_name]
        if not gen3_attacks:
            print("  Skipping (no attacks generated)")
            continue

        gen3_df = _as_feature_frame(gen3_attacks)
        gen3_df['is_fraud'] = 1
        # Shuffle before capping, not .head(): gen3_attacks is now several
        # families concatenated in list order (see gen3_pipeline.py), each
        # contributing hundreds of rows per level -- .head(LEVEL_ATTACK_CAP)
        # on the raw concatenation would keep every row from the first
        # family or two and silently drop every family listed after them
        # once their combined size exceeds the cap, exactly reproducing the
        # "family never actually trained on" bug the merge was meant to fix.
        gen3_df = gen3_df.sample(frac=1.0, random_state=42).reset_index(drop=True)
        gen3_df = gen3_df.head(LEVEL_ATTACK_CAP)

        # Split into a genuine train portion (so the model actually learns
        # this pattern) and a held-out test portion (for honest evasion
        # measurement on rows it never trained on). Tagging every attack row
        # 'test' -- the previous behavior -- meant train_fraud_model() routed
        # 100% of them to test_df and 0% to train_df: no generation ever
        # trained on a single adversarial example. Confirmed via
        # cross_generation_eval.py + a direct feature_importances_ comparison
        # showing gen3_model.pkl was bit-for-bit identical to the
        # pre-curriculum baseline.
        rng = np.random.default_rng(42)
        shuffled = rng.permutation(len(gen3_df))
        n_train = int(len(gen3_df) * TRAIN_FRACTION)
        gen3_train_rows = gen3_df.iloc[shuffled[:n_train]].copy()
        gen3_train_rows['split'] = 'train'
        gen3_test_rows = gen3_df.iloc[shuffled[n_train:]].copy()
        gen3_test_rows['split'] = 'test'

        # Accumulate across levels WITHIN this generation -- not just across
        # generations via accumulated_attacks_df. Without this, level 2's
        # training set discards level 1's attacks entirely (fresh batch each
        # level), so a model that reaches level 4 has forgotten level 1's
        # easy patterns by the time it's learned level 4's extreme ones.
        this_gen_levels_seen.append(gen3_train_rows)
        this_gen_test_seen.append(gen3_test_rows)
        cumulative_train_this_gen = pd.concat(this_gen_levels_seen, ignore_index=True, sort=False)
        cumulative_test_this_gen = pd.concat(this_gen_test_seen, ignore_index=True, sort=False)

        concat_parts = [
            original_training_df[original_training_df['split'].isin(['train', 'validation'])],
            analyst_feedback_df.assign(split='train') if len(analyst_feedback_df) else analyst_feedback_df,
            cumulative_train_this_gen,
        ]
        if accumulated_attacks_df is not None and len(accumulated_attacks_df):
            concat_parts.append(accumulated_attacks_df)
        training_df = pd.concat(concat_parts, ignore_index=True, sort=False)

        print(f"  Training data size: {len(training_df)}")
        print(f"    Original: {len(original_training_df)}")
        print(f"    Analyst feedback: {len(analyst_feedback_df)}")
        print(f"    {generation_label} (train, cumulative through this level): {len(cumulative_train_this_gen)}   {generation_label} (held-out test, cumulative): {len(cumulative_test_this_gen)}")
        print(f"    Retained from prior generations: {n_accumulated}")

        try:
            train_result = train_fraud_model(training_df)
            level_model = train_result['model']
            level_preprocessor = train_result['preprocessor']
            all_models[level_name] = level_model
        except Exception as e:
            print(f"  ERROR training: {e}")
            continue

        print("\n  Evaluation:")
        level_threshold = _fixed_fpr_threshold(
            level_model, level_preprocessor, original_training_df,
        )
        print(
            f"    Threshold: {level_threshold:.4f} "
            f"(own {CURRICULUM_FIXED_FPR_TARGET:.0%}-FPR operating point)"
        )

        # "No regression" check: this freshly retrained model should still
        # catch fraud the original data already had labelled.
        gen2_margin = None
        prior_fraud = original_training_df[original_training_df['is_fraud'] == 1]
        gen2_attacks_test = prior_fraud.sample(min(100, len(prior_fraud)), random_state=42) if len(prior_fraud) else prior_fraud
        if len(gen2_attacks_test) > 0:
            gen2_margin = measure_evasion_margin(
                level_model, gen2_attacks_test.reindex(columns=ALL_FEATURES),
                gen2_attacks_test['is_fraud'].values, generation='prior',
                preprocessor=level_preprocessor,
                threshold=level_threshold,
            )
            print(f"    Prior-gen evasion: {gen2_margin['evasion_percent']} (should be near 0%)")

        # Measured on the CUMULATIVE held-out test rows across every level
        # trained so far this generation -- not just the level just trained.
        # A model that only ever saw "easy" attacks can hit a low evasion
        # number on an "easy" held-out set while still failing badly on
        # medium/hard/extreme variants it was never exposed to; scoring
        # against the full spectrum trained so far is what makes this number
        # honest. (Confirmed via cross_generation_eval.py: a checkpoint that
        # looked like 2% evasion here was actually 43%+ against the full
        # 4-level attack set, because it had stopped after level 1.)
        this_gen_evasion = measure_evasion_margin(
            level_model, cumulative_test_this_gen[ALL_FEATURES], cumulative_test_this_gen['is_fraud'].values,
            generation=generation_label, preprocessor=level_preprocessor,
            threshold=level_threshold,
        )
        print(f"    {generation_label} evasion: {this_gen_evasion['evasion_percent']} (target <{target_evasion*100:.0f}%)")

        # <=, not <: if every level ties (e.g. all at the 1.0 sentinel because
        # this attack family is hard enough that no level improves at all),
        # the pipeline must still come out of this with *some* checkpoint
        # saved -- a strict "<" would leave best_model as None forever and
        # crash Stage 3's report generation instead of just reporting a
        # genuinely bad (but real) result.
        if this_gen_evasion['evasion_margin'] <= best_evasion:
            best_evasion = this_gen_evasion['evasion_margin']
            best_model = level_model
            best_preprocessor = level_preprocessor
            best_model_metrics = train_result['metrics']
            best_threshold = train_result['threshold']

        curriculum_log[level_name] = {
            'prior_gen_evasion': gen2_margin,
            f'{generation_label}_evasion': this_gen_evasion,
            'training_size': len(training_df),
            'status': 'PASS' if this_gen_evasion['status'] == 'PASS' else 'FAIL',
        }

        # Always continue through every level -- no early exit. Stopping as
        # soon as any single level's evasion dips below target used to mean
        # a model that passed on level 1's "easy" held-out set alone got
        # deployed having never trained on levels 2-4 (medium/hard/extreme).
        # Since evaluation is now against the CUMULATIVE held-out set (all
        # levels trained so far), "target achieved" only means something once
        # every level has been folded in -- so just report status and move on.
        if level_idx < len(levels) - 1:
            status_note = "target already met on cumulative set" if this_gen_evasion['evasion_margin'] <= target_evasion else "above target"
            print(f"\n  Action: {status_note}; continuing to {levels[level_idx+1]} for full curriculum coverage")
        else:
            print("\n  Action: Final level reached")

    log_path = output_dir / "curriculum_log.json"
    with open(log_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'generation': generation_label,
            'curriculum_log': curriculum_log,
            'best_evasion': best_evasion,
            'prior_gen_evasion': prior_gen_evasion,
            'all_models_trained': list(all_models.keys()),
        }, f, indent=2, default=str)

    # Retained sample to carry into the NEXT generation's accumulated_attacks_df:
    # a slice across every level actually trained this generation (not just the
    # hardest), so the next generation sees this generation's easy-to-extreme
    # spectrum rather than only its endpoint. Capped so accumulated size grows
    # linearly (one cap's worth per generation), not with each level's own count.
    if this_gen_levels_seen:
        retained_attacks = pd.concat(this_gen_levels_seen, ignore_index=True, sort=False)
        if len(retained_attacks) > RETAINED_SAMPLE_CAP:
            retained_attacks = retained_attacks.sample(RETAINED_SAMPLE_CAP, random_state=42)
    else:
        retained_attacks = pd.DataFrame(columns=ALL_FEATURES + ['is_fraud', 'split'])

    print("\n" + "="*70)
    print("CURRICULUM TRAINING COMPLETE")
    print("="*70)
    print(f"Best {generation_label} evasion achieved: {best_evasion*100:.1f}%")
    print(f"Target: <{target_evasion*100:.0f}%")
    print(f"Status: {'PASS' if best_evasion < target_evasion else 'FAIL'}")
    print(f"Retained {len(retained_attacks)} {generation_label} attack rows for next generation's training")
    print(f"Log saved: {log_path}")

    return {
        'model': best_model,
        'preprocessor': best_preprocessor,
        'model_metrics': best_model_metrics,
        'threshold': best_threshold,
        'curriculum_log': curriculum_log,
        'best_evasion': best_evasion,
        'prior_gen_evasion': prior_gen_evasion,
        'improvement_from_gen2': (prior_gen_evasion is not None and best_evasion < prior_gen_evasion),
        'all_models': all_models,
        'log_path': log_path,
        'retained_attacks': retained_attacks,
    }
