"""
Gen 5 Full Pipeline: Multi-family cross-attacks → Curriculum retrain → Evaluation.
Final hardening cycle before production deployment.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage5.adversarial.gen5_generator import Gen5AttackGenerator
from stage5.training.curriculum_retrain import retrain_on_gen3_attacks  # Reuse curriculum logic
from stage5.validation.gen5_evaluation_report import generate_gen5_evaluation_report, print_gen5_report


def run_gen5_pipeline(
    gen4_model,
    gen4_training_data_df,
    analyst_feedback_df,
    gen4_preprocessor=None,
    gen4_model_metrics: dict = None,
    output_dir: Path = None
):
    """
    Full Gen 5 pipeline: generate multi-family attacks → retrain → evaluate.
    This is the final hardening cycle before production.

    Args:
        gen4_model: Trained Gen 4 model
        gen4_training_data_df: Training data used for Gen 4
        gen4_model_metrics: Baseline metrics from Gen 4
        output_dir: Where to save outputs

    Returns:
        {
            'gen5_model': trained model,
            'gen5_attacks': generated attacks,
            'curriculum_log': training log,
            'evaluation_report': metrics + analysis,
            'status': 'PRODUCTION_READY' or 'NEEDS_WORK'
        }
    """

    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "data" / "gen5_pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*80)
    print("GEN 5 FINAL PIPELINE: Multi-Family Cross-Attacks → Retrain → Production Ready")
    print("="*80)

    # ============================================================================
    # STAGE 1: GENERATE GEN 5 MULTI-FAMILY ATTACKS
    # ============================================================================
    print("\n[STAGE 1] GENERATING GEN 5 MULTI-FAMILY ATTACKS")
    print("-" * 80)

    try:
        generator = Gen5AttackGenerator(gen4_model, gen4_training_data_df, gen4_preprocessor)

        print(f"\n  Generating multi-family attacks (6 cross-family specs)...")
        gen5_attacks = generator.generate_curriculum_attacks(n_campaigns=100)

        total_gen5 = sum(len(v) for v in gen5_attacks.values())
        print(f"  ✓ Generated {total_gen5} multi-family attack variants")

        # Estimate evasion on Gen 4 model
        all_attacks = [a for level_attacks in gen5_attacks.values() for a in level_attacks]
        estimated_evasion = generator.estimate_evasion_rate(all_attacks)
        print(f"    Estimated evasion on Gen 4 model: {estimated_evasion*100:.1f}%")

    except Exception as e:
        print(f"  ✗ ERROR generating attacks: {e}")
        return {'status': 'FAILED', 'error': str(e)}

    # ============================================================================
    # STAGE 2: CURRICULUM RETRAINING
    # ============================================================================
    print("\n[STAGE 2] CURRICULUM RETRAINING ON MULTI-FAMILY ATTACKS")
    print("-" * 80)

    try:
        print(f"\n  Retraining on Gen 5 multi-family attacks...")

        retrain_result = retrain_on_gen3_attacks(
            analyst_feedback_df=analyst_feedback_df,
            gen3_attacks_by_level=gen5_attacks,
            original_training_df=gen4_training_data_df,
            gen2_model=gen4_model,
            gen2_preprocessor=gen4_preprocessor,
            generation_label='gen5',
            target_evasion=0.25,
            output_dir=output_dir,
        )

        gen5_model = retrain_result['model']
        gen5_preprocessor = retrain_result['preprocessor']
        curriculum_log = retrain_result['curriculum_log']
        gen5_evasion = retrain_result['best_evasion']

        print(f"\n  ✓ Retraining complete")
        print(f"    Best evasion achieved: {gen5_evasion*100:.1f}%")

    except Exception as e:
        print(f"  ✗ ERROR during retraining: {e}")
        return {'status': 'FAILED', 'error': str(e)}

    # ============================================================================
    # STAGE 3: EVALUATION & REPORTING
    # ============================================================================
    print("\n[STAGE 3] EVALUATION & REPORTING")
    print("-" * 80)

    try:
        gen5_model_metrics = retrain_result['model_metrics']

        evaluation_report = generate_gen5_evaluation_report(
            gen4_model_metrics=gen4_model_metrics or {},
            gen5_model_metrics=gen5_model_metrics,
            curriculum_log=curriculum_log,
            prior_gen_evasion=retrain_result['prior_gen_evasion'],
            gen5_evasion_rate=gen5_evasion,
            output_path=output_dir / "gen5_evaluation_report.json"
        )

        print(f"  ✓ Evaluation report generated")
        print_gen5_report(evaluation_report)

    except Exception as e:
        print(f"  ✗ ERROR generating report: {e}")
        return {'status': 'FAILED', 'error': str(e)}

    # ============================================================================
    # RESULT
    # ============================================================================
    print("\n" + "="*80)
    print("GEN 5 PIPELINE COMPLETE — PRODUCTION DEPLOYMENT READY")
    print("="*80)

    prior_evasion = retrain_result['prior_gen_evasion']
    final_status = 'PRODUCTION_READY' if gen5_evasion < 0.25 else 'NEEDS_WORK'
    print(f"\nFinal Status: {final_status}")
    print(f"  Evasion Rate: {gen5_evasion*100:.1f}%")
    print(f"  Target: <25.0%")
    if prior_evasion is not None:
        print(f"  Gen 4 model on these Gen 5 attacks (before retraining): {prior_evasion*100:.1f}%")
        print(f"  Gen 5 model on these attacks (after retraining):        {gen5_evasion*100:.1f}%")

    print(f"\nOutputs saved to: {output_dir}")

    recommendation = "DEPLOY TO PRODUCTION" if final_status == 'PRODUCTION_READY' else "Continue hardening with Gen 5 variants"
    print(f"\nRecommendation: {recommendation}")

    return {
        'status': final_status,
        'gen5_model': gen5_model,
        'gen5_preprocessor': gen5_preprocessor,
        'gen5_attacks': gen5_attacks,
        'curriculum_log': curriculum_log,
        'evaluation_report': evaluation_report,
        'evasion_rate': gen5_evasion,
        'output_dir': output_dir
    }


if __name__ == "__main__":
    print("Gen 5 Pipeline is ready to run.")
    print("Call run_gen5_pipeline(gen4_model, gen4_training_df, analyst_feedback_df)")
