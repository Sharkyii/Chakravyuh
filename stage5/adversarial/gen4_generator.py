"""
Gen 4 Attack Generator: Ensemble evasion with feature trading.
Hide some features while exposing others to confuse multi-feature detection.
"""
import numpy as np
import pandas as pd
from stage5.adversarial.gen4_config import GEN4_SPECS, CURRICULUM_LEVELS


class Gen4AttackGenerator:
    """Generate Gen 4 attacks that trade off multiple features."""

    def __init__(self, gen3_model, gen3_training_data_df: pd.DataFrame):
        """
        Args:
            gen3_model: Trained Gen 3 model
            gen3_training_data_df: Training data used for Gen 3
        """
        self.gen3_model = gen3_model
        self.training_df = gen3_training_data_df

    def generate_curriculum_attacks(self, n_campaigns=100):
        """
        Generate Gen 4 ensemble attacks at multiple difficulty levels.

        Args:
            n_campaigns: Attack campaigns per difficulty level

        Returns:
            {
                'level_1_simple_ensemble': [...],
                'level_2_complex_ensemble': [...],
                'level_3_multi_ensemble': [...],
                'level_4_extreme_ensemble': [...]
            }
        """

        attacks_by_level = {}
        ensemble_specs = list(GEN4_SPECS.values())

        print(f"\nGenerating Gen 4 ensemble attacks ({len(ensemble_specs)} trading strategies)")

        for level_name, level_config in CURRICULUM_LEVELS.items():
            print(f"\n  {level_name}: {level_config['description']}")

            level_attacks = []

            # Cycle through ensemble specs, generating attacks at this level
            for i in range(level_config['sample_size']):
                spec_idx = i % len(ensemble_specs)
                spec = ensemble_specs[spec_idx]

                attack = self._generate_ensemble_attack(
                    spec,
                    hiding_count=level_config['hiding_count'],
                    exposing_count=level_config['exposing_count'],
                    complexity=level_config['complexity']
                )

                level_attacks.append(attack)

            attacks_by_level[level_name] = level_attacks
            print(f"    Generated {len(level_attacks)} ensemble variants")

        return attacks_by_level

    def _generate_ensemble_attack(self, spec: dict, hiding_count: int, exposing_count: int, complexity: int) -> dict:
        """
        Generate one ensemble attack using the spec.

        Strategy:
        1. Pick a legitimate template
        2. Apply spec parameters to hide some features
        3. Deliberately expose other features (trading off signals)
        4. Result: Mixed signal that confuses single-feature detection
        """

        # Get legitimate template
        legit_samples = self.training_df[self.training_df['is_fraud'] == False]
        template = legit_samples.sample(1).iloc[0].copy()

        # Apply spec parameters
        attack = template.copy()

        # Hide features (make them look normal)
        for param_key, param_value in spec['parameters'].items():
            if param_key == 'use_single_top_counterparty' and param_value:
                attack['edge_count'] = 2  # Low edge count
                attack['payer_out_degree'] = 2
                attack['is_two_hop_passthrough'] = False

            elif param_key == 'increase_velocity' and param_value:
                attack['txn_count_last_1h'] = 5  # High velocity (conflicting signal)
                attack['txn_count_last_24h'] = 12

            elif param_key == 'use_existing_payee_pool' and param_value:
                attack['beneficiary_added_ago_s'] = 90 * 86400  # Old payee

            elif param_key == 'vary_amounts_significantly' and param_value:
                attack['amount'] = attack.get('amount', 1000) * np.random.uniform(0.5, 2.0)
                attack['amount_deviation'] = np.random.uniform(1.5, 3.0)

            elif param_key == 'change_timing_pattern' and param_value:
                attack['time_since_prev_txn'] = np.random.randint(60, 3600)  # Unusual timing
                attack['tx_hour'] = np.random.randint(0, 24)

            elif param_key == 'use_known_device' and param_value:
                attack['device_is_known_for_payer'] = True

            elif param_key == 'use_proxy_ip' and param_value:
                attack['ip_is_proxy'] = True
                attack['new_ip_indicator'] = True

            elif param_key == 'mix_small_and_large' and param_value:
                attack['subthreshold_txn_ratio'] = np.random.uniform(0.2, 0.4)
                attack['txn_count_last_24h'] = np.random.randint(8, 15)

            elif param_key == 'distribute_across_payees' and param_value:
                attack['payer_out_degree'] = np.random.randint(5, 10)
                attack['edge_count'] = np.random.randint(4, 8)

            elif param_key == 'concentrate_in_largest_transaction' and param_value:
                attack['amount'] = attack.get('amount', 1000) * 3.0

            elif param_key == 'slow_transaction_rate' and param_value:
                attack['txn_count_last_1h'] = 1
                attack['txn_count_last_24h'] = 2

            elif param_key == 'high_friction_indicators' and param_value:
                attack['time_on_confirm_screen_s'] = np.random.randint(30, 120)
                attack['pin_attempts'] = np.random.randint(2, 4)

        # Add complexity-based noise
        if complexity > 1:
            # Higher complexity = more variation
            for feature in attack.index:
                if attack[feature].dtype in [float, np.float64] and np.random.random() < 0.05:
                    attack[feature] *= np.random.uniform(0.90, 1.10)

        return {
            'features': attack,
            'family': spec['description'],
            'hiding_features': spec.get('hiding_features', []),
            'exposing_features': spec.get('exposing_features', []),
            'strategy': spec['strategy'],
            'label': 1,  # Fraud
            'complexity': complexity
        }

    def estimate_evasion_rate(self, attacks: list[dict]) -> float:
        """
        Estimate evasion rate: % of Gen 4 attacks that evade Gen 3 model.
        """

        if not attacks:
            return 0.0

        feature_vectors = np.array([a['features'].values for a in attacks])
        scores = self.gen3_model.predict_proba(feature_vectors)[:, 1]

        threshold = 0.45
        evaded = np.sum(scores < threshold)
        evasion_rate = evaded / len(attacks) if attacks else 0

        return evasion_rate
