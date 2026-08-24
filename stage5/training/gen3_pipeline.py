"""
Gen 3 Full Pipeline: End-to-end from analyst feedback to evaluation.
Orchestrates: Generate attacks → Retrain → Measure → Report
"""
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage5.adversarial.gen3_generator import Gen3AttackGenerator
from stage5.training.curriculum_retrain import retrain_on_gen3_attacks
from stage5.validation.gen3_evaluation_report import generate_gen3_evaluation_report, print_gen3_report


def run_gen3_pipeline(
    gen2_model,
    analyst_feedback_df,
    original_training_df,
    gen2_preprocessor=None,
    gen2_model_metrics: dict = None,
    output_dir: Path = None
):
    """
    Full Gen 3 pipeline: analyst feedback → Gen 3 attacks → retrain → evaluate.

    Args:
        gen2_model: Trained Gen 2 model
        analyst_feedback_df: 50+ analyst verdicts
        original_training_df: Original synthetic training data
        gen2_model_metrics: Baseline metrics
        output_dir: Where to save outputs

    Returns:
        {
            'gen3_model': trained model,
            'gen3_attacks': generated attacks,
            'curriculum_log': training log,
            'evaluation_report': metrics + analysis,
            'status': 'PASS'
        }
    """

    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "data" / "gen3_pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*80)
    print("GEN 3 FULL PIPELINE: Analyst Feedback → Harder Attacks → Improved Detector")
    print("="*80)

    # ============================================================================
    # STAGE 1: GENERATE GEN 3 ATTACKS
    # ============================================================================
    print("\n[STAGE 1] GENERATING GEN 3 ATTACKS")
    print("-" * 80)

    try:
        generator = Gen3AttackGenerator(gen2_model, original_training_df, gen2_preprocessor)

        # Generate curriculum attacks for all attack families
        families = ['mule_network', 'adversarial_evasion', 'account_takeover']
        gen3_attacks_all = {}

        for family in families:
            print(f"\n  Generating {family}...")
            gen3_attacks_all[family] = generator.generate_curriculum_attacks(
                attack_family=family,
                n_campaigns=100
            )

        print(f"\n  ✓ Generated attacks for {len(families)} families")

    except Exception as e:
        print(f"  ✗ ERROR generating attacks: {e}")
        return {'status': 'FAILED', 'error': str(e)}

    # ============================================================================
    # STAGE 2: CURRICULUM RETRAINING
    # ============================================================================
    print("\n[STAGE 2] CURRICULUM RETRAINING")
    print("-" * 80)

    try:
        # Retrain using adversarial_evasion as primary target
        retrain_result = retrain_on_gen3_attacks(
            analyst_feedback_df=analyst_feedback_df,
            gen3_attacks_by_level=gen3_attacks_all['adversarial_evasion'],
            original_training_df=original_training_df,
            gen2_model=gen2_model,
            gen2_preprocessor=gen2_preprocessor,
            generation_label='gen3',
            target_evasion=0.05,
            output_dir=output_dir
        )

        gen3_model = retrain_result['model']
        gen3_preprocessor = retrain_result['preprocessor']
        curriculum_log = retrain_result['curriculum_log']
        best_evasion = retrain_result['best_evasion']

        print(f"\n  ✓ Retraining complete")
        print(f"    Best evasion achieved: {best_evasion*100:.1f}%")

    except Exception as e:
        print(f"  ✗ ERROR during retraining: {e}")
        return {'status': 'FAILED', 'error': str(e)}

    # ============================================================================
    # STAGE 3: EVALUATION & REPORTING
    # ============================================================================
    print("\n[STAGE 3] EVALUATION & REPORTING")
    print("-" * 80)

    try:
        # Real metrics from the winning curriculum level's train_fraud_model() run.
        gen3_model_metrics = retrain_result['model_metrics']

        evaluation_report = generate_gen3_evaluation_report(
            gen2_model_metrics=gen2_model_metrics or {},
            gen3_model_metrics=gen3_model_metrics,
            curriculum_log=curriculum_log,
            prior_gen_evasion=retrain_result['prior_gen_evasion'],
            best_evasion=best_evasion,
            analyst_feedback_count=len(analyst_feedback_df),
            output_path=output_dir / "gen3_evaluation_report.json"
        )

        print(f"  ✓ Evaluation report generated")
        print_gen3_report(evaluation_report)

    except Exception as e:
        print(f"  ✗ ERROR generating report: {e}")
        return {'status': 'FAILED', 'error': str(e)}

    # ============================================================================
    # RESULT
    # ============================================================================
    print("\n" + "="*80)
    print("GEN 3 PIPELINE COMPLETE")
    print("="*80)

    final_status = 'PASS' if best_evasion < 0.05 else 'FAIL'
    print(f"\nFinal Status: {final_status}")
    print(f"  Evasion Rate: {best_evasion*100:.1f}%")
    print(f"  Target: <5.0%")
    print(f"  Improvement: {'✓ Yes' if best_evasion < 0.10 else '✗ No'}")
    print(f"\nOutputs saved to: {output_dir}")

    return {
        'status': final_status,
        'gen3_model': gen3_model,
        'gen3_preprocessor': gen3_preprocessor,
        'gen3_attacks': gen3_attacks_all,
        'curriculum_log': curriculum_log,
        'evaluation_report': evaluation_report,
        'best_evasion': best_evasion,
        'output_dir': output_dir
    }


if __name__ == "__main__":
    print("Gen 3 Pipeline is ready to run.")
    print("Call run_gen3_pipeline(gen2_model, analyst_feedback_df, training_df)")
