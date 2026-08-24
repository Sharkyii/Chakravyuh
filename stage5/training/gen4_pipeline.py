"""
Gen 4 Full Pipeline: Ensemble evasion attacks → Curriculum retrain → Evaluation.
Same orchestration pattern as Gen 3, but harder attacks.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage5.adversarial.gen4_generator import Gen4AttackGenerator
from stage5.training.curriculum_retrain import retrain_on_gen3_attacks  # Reuse curriculum logic
from stage5.validation.gen4_evaluation_report import generate_gen4_evaluation_report, print_gen4_report


def run_gen4_pipeline(
    gen3_model,
    gen3_training_data_df,
    analyst_feedback_df,
    gen3_preprocessor=None,
    gen3_model_metrics: dict = None,
    output_dir: Path = None
):
    """
    Full Gen 4 pipeline: generate ensemble attacks → retrain → evaluate.

    Args:
        gen3_model: Trained Gen 3 model
        gen3_training_data_df: Training data used for Gen 3
        gen3_model_metrics: Baseline metrics from Gen 3
        output_dir: Where to save outputs

    Returns:
        {
            'gen4_model': trained model,
            'gen4_attacks': generated attacks,
            'curriculum_log': training log,
            'evaluation_report': metrics + analysis,
            'status': 'PASS' or 'FAIL'
        }
    """

    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "data" / "gen4_pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*80)
    print("GEN 4 FULL PIPELINE: Ensemble Evasion → Curriculum Retrain → Evaluation")
    print("="*80)

    # ============================================================================
    # STAGE 1: GENERATE GEN 4 ENSEMBLE ATTACKS
    # ============================================================================
    print("\n[STAGE 1] GENERATING GEN 4 ENSEMBLE ATTACKS")
    print("-" * 80)

    try:
        generator = Gen4AttackGenerator(gen3_model, gen3_training_data_df, gen3_preprocessor)

        print(f"\n  Generating ensemble attacks (6 trading strategies)...")
        gen4_attacks = generator.generate_curriculum_attacks(n_campaigns=100)

        total_gen4 = sum(len(v) for v in gen4_attacks.values())
        print(f"  ✓ Generated {total_gen4} ensemble attack variants")

        # Estimate evasion on Gen 3 model
        all_attacks = [a for level_attacks in gen4_attacks.values() for a in level_attacks]
        estimated_evasion = generator.estimate_evasion_rate(all_attacks)
        print(f"    Estimated evasion on Gen 3 model: {estimated_evasion*100:.1f}%")

    except Exception as e:
        print(f"  ✗ ERROR generating attacks: {e}")
        return {'status': 'FAILED', 'error': str(e)}

    # ============================================================================
    # STAGE 2: CURRICULUM RETRAINING
    # ============================================================================
    print("\n[STAGE 2] CURRICULUM RETRAINING ON ENSEMBLE ATTACKS")
    print("-" * 80)

    try:
        print(f"\n  Retraining on Gen 4 ensemble attacks...")

        retrain_result = retrain_on_gen3_attacks(
            analyst_feedback_df=analyst_feedback_df,
            gen3_attacks_by_level=gen4_attacks,
            original_training_df=gen3_training_data_df,
            gen2_model=gen3_model,
            gen2_preprocessor=gen3_preprocessor,
            generation_label='gen4',
            target_evasion=0.15,
            output_dir=output_dir,
        )

        gen4_model = retrain_result['model']
        gen4_preprocessor = retrain_result['preprocessor']
        curriculum_log = retrain_result['curriculum_log']
        gen4_evasion = retrain_result['best_evasion']

        print(f"\n  ✓ Retraining complete")
        print(f"    Best evasion achieved: {gen4_evasion*100:.1f}%")

    except Exception as e:
        print(f"  ✗ ERROR during retraining: {e}")
        return {'status': 'FAILED', 'error': str(e)}

    # ============================================================================
    # STAGE 3: EVALUATION & REPORTING
    # ============================================================================
    print("\n[STAGE 3] EVALUATION & REPORTING")
    print("-" * 80)

    try:
        gen4_model_metrics = retrain_result['model_metrics']

        evaluation_report = generate_gen4_evaluation_report(
            gen3_model_metrics=gen3_model_metrics or {},
            gen4_model_metrics=gen4_model_metrics,
            curriculum_log=curriculum_log,
            prior_gen_evasion=retrain_result['prior_gen_evasion'],
            gen4_evasion_rate=gen4_evasion,
            output_path=output_dir / "gen4_evaluation_report.json"
        )

        print(f"  ✓ Evaluation report generated")
        print_gen4_report(evaluation_report)

    except Exception as e:
        print(f"  ✗ ERROR generating report: {e}")
        return {'status': 'FAILED', 'error': str(e)}

    # ============================================================================
    # RESULT
    # ============================================================================
    print("\n" + "="*80)
    print("GEN 4 PIPELINE COMPLETE")
    print("="*80)

    prior_evasion = retrain_result['prior_gen_evasion']
    final_status = 'PASS' if gen4_evasion < 0.15 else 'FAIL'
    print(f"\nFinal Status: {final_status}")
    print(f"  Evasion Rate: {gen4_evasion*100:.1f}%")
    print(f"  Target: <15.0%")
    if prior_evasion is not None:
        print(f"  Improvement over Gen 3 model on these attacks: "
              f"{'Yes' if gen4_evasion < prior_evasion else 'No (regression)'} "
              f"({prior_evasion*100:.1f}% -> {gen4_evasion*100:.1f}%)")
    print(f"\nOutputs saved to: {output_dir}")

    recommendation = "Deploy Gen 4 model" if final_status == 'PASS' else "Generate Gen 5 attacks"
    print(f"Recommendation: {recommendation}")

    return {
        'status': final_status,
        'gen4_model': gen4_model,
        'gen4_preprocessor': gen4_preprocessor,
        'gen4_attacks': gen4_attacks,
        'curriculum_log': curriculum_log,
        'evaluation_report': evaluation_report,
        'evasion_rate': gen4_evasion,
        'output_dir': output_dir
    }


if __name__ == "__main__":
    print("Gen 4 Pipeline is ready to run.")
    print("Call run_gen4_pipeline(gen3_model, gen3_training_df, analyst_feedback_df)")
