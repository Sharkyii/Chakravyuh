"""
Gen 5 Attack Generator: Multi-family cross-attack combinations.
Combine features from 2-3 attack families to create novel evasion vectors.
"""
import numpy as np
import pandas as pd
from stage5.adversarial.gen5_config import GEN5_SPECS, CURRICULUM_LEVELS


class Gen5AttackGenerator:
    """Generate Gen 5 attacks combining multiple families."""

    def __init__(self, gen4_model, gen4_training_data_df: pd.DataFrame, gen4_preprocessor=None):
        """
        Args:
            gen4_model: Trained Gen 4 model
            gen4_training_data_df: Training data used for Gen 4
            gen4_preprocessor: fitted ColumnTransformer gen4_model expects
                its input through.
        """
        self.gen4_model = gen4_model
        self.training_df = gen4_training_data_df
        self.gen4_preprocessor = gen4_preprocessor

    def generate_curriculum_attacks(self, n_campaigns=100):
        """
        Generate Gen 5 multi-family attacks at multiple difficulty levels.

        Args:
            n_campaigns: Attack campaigns per difficulty level

        Returns:
            {
                'level_1_simple_cross_family': [...],
                'level_2_moderate_cross_family': [...],
                'level_3_complex_cross_family': [...],
                'level_4_extreme_cross_family': [...]
            }
        """

        attacks_by_level = {}
        specs = list(GEN5_SPECS.values())

        print(f"\nGenerating Gen 5 multi-family attacks ({len(specs)} cross-family specs)")

        for level_name, level_config in CURRICULUM_LEVELS.items():
            print(f"\n  {level_name}: {level_config['description']}")

            level_attacks = []

            # Cycle through specs, generating attacks at this level
            for i in range(level_config['sample_size']):
                spec_idx = i % len(specs)
                spec = specs[spec_idx]

                attack = self._generate_cross_family_attack(
                    spec,
                    num_families=level_config['num_families'],
                    feature_combinations=level_config['feature_combinations'],
                    complexity=level_config['complexity']
                )

                level_attacks.append(attack)

            attacks_by_level[level_name] = level_attacks
            print(f"    Generated {len(level_attacks)} multi-family variants")

        return attacks_by_level

    def _generate_cross_family_attack(self, spec: dict, num_families: int, feature_combinations: int, complexity: int) -> dict:
        """
        Generate one cross-family attack using the spec.

        Strategy:
        1. Pick a legitimate template
        2. Apply features from first family
        3. Mix in features from second (and optional third) family
        4. Result: Attack signature spans multiple family profiles
        """

        # Template must be a genuine fraud row: a cross-family attack is a
        # real fraudulent transaction whose signature spans multiple attack
        # profiles. Starting from a legit row (the previous behaviour) left
        # the vector reading as legitimate everywhere the spec's parameters
        # didn't explicitly override it.
        fraud_samples = self.training_df[self.training_df['is_fraud'] == True]
        if fraud_samples.empty:
            fraud_samples = self.training_df[self.training_df['is_fraud'] == False]
        template = fraud_samples.sample(1).iloc[0].copy()

        attack = template.copy()

        # Apply spec parameters (from multiple families)
        for param_key, param_value in spec['parameters'].items():
            if not param_value:
                continue

            # Mule network parameters
            if param_key == 'use_single_top_counterparty' and param_value:
                attack['edge_count'] = 2
                attack['payer_out_degree'] = 2
                attack['is_two_hop_passthrough'] = False

            # Card testing parameters
            elif param_key == 'rapid_txn_sequence' and param_value:
                attack['txn_count_last_1h'] = 4
                attack['txn_count_last_24h'] = 8

            elif param_key == 'small_amounts' and param_value:
                attack['amount'] = np.random.uniform(0.99, 9.99)
                attack['amount_spent_last_1h'] = attack['amount'] * 3

            elif param_key == 'amount_range' and isinstance(param_value, list):
                attack['amount'] = np.random.uniform(param_value[0], param_value[1])

            # Bustout parameters
            elif param_key == 'use_old_created_account' and param_value:
                attack['new_account_age_s'] = 60 * 86400  # Fake old

            elif param_key == 'feature_spoofing_enabled' and param_value:
                attack['address_change_recent'] = False

            elif param_key == 'gradual_velocity_increase' and param_value:
                attack['txn_count_last_7d'] = np.random.randint(15, 25)
                attack['txn_count_last_24h'] = np.random.randint(5, 10)

            elif param_key == 'final_large_txn' and param_value:
                attack['amount'] = attack.get('amount', 1000) * 5.0

            # Account takeover parameters
            elif param_key == 'ip_change_subtle' and param_value:
                attack['new_ip_indicator'] = True
                attack['ip_is_proxy'] = False  # Not obviously suspicious

            elif param_key == 'establish_mule_chain' and param_value:
                attack['payer_out_degree'] = np.random.randint(4, 8)
                attack['edge_count'] = np.random.randint(3, 7)

            elif param_key == 'timing_mimics_user' and param_value:
                attack['time_since_prev_txn'] = np.random.randint(120, 1200)
                attack['tx_hour'] = np.random.choice([9, 10, 14, 15, 20, 21])

            elif param_key == 'use_multiple_mules' and param_value:
                attack['unique_beneficiaries_last_7d'] = np.random.randint(6, 12)

            # Probe-then-exploit (testing → bustout)
            elif param_key == 'initial_probe_phase' and param_value:
                attack['txn_count_last_1h'] = 5

            elif param_key == 'probe_count' and isinstance(param_value, int):
                attack['txn_count_last_24h'] = param_value

            elif param_key == 'transition_to_large' and param_value:
                attack['amount'] = np.random.uniform(100, 500)

            elif param_key == 'final_amount_multiplier' and isinstance(param_value, float):
                attack['amount'] *= param_value

            # Evasion parameters
            elif param_key == 'spoof_multiple_features' and param_value:
                attack['beneficiary_added_ago_s'] = np.random.randint(30, 365) * 86400

            elif param_key == 'add_friction_indicators' and param_value:
                attack['pin_attempts'] = np.random.randint(2, 4)
                attack['time_on_confirm_screen_s'] = np.random.randint(30, 120)

            elif param_key == 'obscure_final_destination' and param_value:
                # Add extra hops
                attack['unique_beneficiaries_last_7d'] = np.random.randint(8, 15)

            elif param_key == 'num_mule_hops' and isinstance(param_value, int):
                attack['edge_count'] = min(param_value, 10)  # Max hops

        # Add complexity-based variation. attack[feature] is a scalar (one
        # row's value), not a Series -- only numpy float scalars carry
        # .dtype, plain Python strings/bools/None don't.
        if complexity > 1:
            for feature in attack.index:
                value = attack[feature]
                if isinstance(value, (float, np.floating)) and not pd.isna(value) and np.random.random() < 0.08:
                    attack[feature] = value * np.random.uniform(0.85, 1.15)

        return {
            'features': attack,
            'families': spec['families'],
            'mixing_strategy': spec['mixing_strategy'],
            'hidden_features': spec['hidden_features'],
            'exposed_features': spec['exposed_features'],
            'label': 1,  # Fraud
            'complexity': complexity,
            'description': spec['description']
        }

    def estimate_evasion_rate(self, attacks: list[dict]) -> float:
        """
        Estimate evasion rate: % of Gen 5 attacks that evade Gen 4 model.
        """

        if not attacks:
            return 0.0

        feature_df = pd.DataFrame([a['features'] for a in attacks])
        X = self.gen4_preprocessor.transform(feature_df) if self.gen4_preprocessor is not None else feature_df.values
        scores = self.gen4_model.predict_proba(X)[:, 1]

        threshold = 0.45
        evaded = np.sum(scores < threshold)
        evasion_rate = evaded / len(attacks) if attacks else 0

        return evasion_rate
