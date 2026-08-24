"""
Gen 3 Attack Generator: Create adversarial variants that hide top SHAP features.
Implements curriculum learning: Easy (hide 1 feature) → Hard (hide 5 features).
"""
import numpy as np
import pandas as pd
from pathlib import Path
from stage5.adversarial.gen3_config import GEN3_SPECS, CURRICULUM_LEVELS, GEN3_TARGETS
from stage5.adversarial.feature_targeting import get_top_features


class Gen3AttackGenerator:
    """Generate Gen 3 attacks that target top detector features."""

    def __init__(self, gen2_model, gen2_training_data_df: pd.DataFrame, gen2_preprocessor=None):
        """
        Args:
            gen2_model: Trained Gen 2 fraud detector
            gen2_training_data_df: Original training data (to learn legitimate patterns)
            gen2_preprocessor: fitted ColumnTransformer gen2_model expects its
                input through -- an XGBClassifier can't score raw categorical/
                unscaled features directly.
        """
        self.gen2_model = gen2_model
        self.training_df = gen2_training_data_df
        self.gen2_preprocessor = gen2_preprocessor

        # Extract top features
        self.top_features = get_top_features(gen2_model, threshold=0.10)
        print(f"Gen 3 targeting top features: {[f[0] for f in self.top_features[:5]]}")

    def generate_curriculum_attacks(self, attack_family='adversarial_evasion', n_campaigns=100):
        """
        Generate attacks at multiple difficulty levels.

        Args:
            attack_family: Which family to target
            n_campaigns: Campaigns per difficulty level

        Returns:
            {
                'level_1_easy': [...],
                'level_2_medium': [...],
                'level_3_hard': [...],
                'level_4_extreme': [...]
            }
        """

        if attack_family not in GEN3_SPECS:
            raise ValueError(f"Unknown family: {attack_family}")

        spec = GEN3_SPECS[attack_family]
        attacks_by_level = {}

        for level_name, level_config in CURRICULUM_LEVELS.items():
            print(f"\n  Generating {level_name}: {level_config['description']}")

            # Generate attacks at this difficulty
            level_attacks = self._generate_level_attacks(
                attack_family,
                n_samples=level_config['sample_size'],
                n_features_to_hide=level_config['features_to_hide'],
                difficulty_multiplier=level_config['difficulty_multiplier']
            )

            attacks_by_level[level_name] = level_attacks
            print(f"    Generated {len(level_attacks)} variants")

        return attacks_by_level

    def _generate_level_attacks(
        self,
        attack_family: str,
        n_samples: int,
        n_features_to_hide: int,
        difficulty_multiplier: float
    ) -> list[dict]:
        """
        Generate attacks for one difficulty level.

        Strategy:
        1. Start with base attack configuration
        2. Select N top features to hide (based on difficulty)
        3. Apply hiding strategies
        4. Generate feature vectors

        Returns:
            List of attack dictionaries with features + metadata
        """

        spec = GEN3_SPECS[attack_family]
        attacks = []

        # Get legitimate distribution to match
        legit_samples = self.training_df[self.training_df['is_fraud'] == False]

        for i in range(n_samples):
            # Pick random legitimate transaction as template
            template = legit_samples.sample(1).iloc[0]

            # Select features to hide (top N_features_to_hide)
            features_to_hide = [f[0] for f in self.top_features[:n_features_to_hide]]

            # Apply spec parameters
            attack_features = self._apply_hiding_strategy(
                template,
                spec['parameters'],
                features_to_hide,
                difficulty_multiplier
            )

            attacks.append({
                'features': attack_features,
                'family': attack_family,
                'features_hidden': features_to_hide,
                'difficulty': difficulty_multiplier,
                'label': 1  # Fraud
            })

        return attacks

    def _apply_hiding_strategy(
        self,
        template: pd.Series,
        params: dict,
        features_to_hide: list,
        difficulty_multiplier: float
    ) -> dict:
        """
        Apply hiding strategy parameters to create an attack variant.

        Examples:
          - If hiding 'beneficiary_added_ago_s': set to 60 days
          - If hiding 'edge_count': distribute across multiple payees
          - If hiding 'txn_count_last_1h': spread transactions over time
        """

        attack = template.copy()

        # Apply general parameters
        for param_key, param_value in params.items():
            if param_key == 'beneficiary_age_floor_s' and 'beneficiary_added_ago_s' in features_to_hide:
                # Ensure beneficiary looks old
                attack['beneficiary_added_ago_s'] = max(param_value, float(attack.get('beneficiary_added_ago_s', param_value)))

            elif param_key == 'use_existing_payees_only' and param_value and 'edge_count' in features_to_hide:
                # Don't add new counterparties
                attack['new_ip_indicator'] = False
                attack['new_device_indicator'] = False

            elif param_key == 'max_txn_per_hour' and 'txn_count_last_1h' in features_to_hide:
                # Reduce transaction velocity
                attack['txn_count_last_1h'] = min(param_value, int(attack.get('txn_count_last_1h', param_value)))

            elif param_key == 'use_known_device' and 'device_is_known_for_payer' in features_to_hide:
                # Use familiar device
                attack['device_is_known_for_payer'] = True

            elif param_key == 'avoid_screen_share' and 'screen_share_active' in features_to_hide:
                attack['screen_share_active'] = False

            elif param_key == 'avoid_voice_call' and 'call_active_during_txn' in features_to_hide:
                attack['call_active_during_txn'] = False

        # Add difficulty-based noise
        # Higher difficulty = more variations from template
        if difficulty_multiplier > 1.0:
            for feature in attack.index:
                if feature not in features_to_hide and np.random.random() < 0.1:
                    # Small random variation to avoid signature patterns
                    if attack[feature].dtype in [float, np.float64]:
                        attack[feature] *= np.random.uniform(0.95, 1.05)

        return attack

    def estimate_evasion_rate(self, attacks: list[dict]) -> float:
        """
        Quick estimate: What % of these attacks evade the Gen 2 model?

        This is prediction-only, not ground truth.
        Real evasion is measured after retraining.
        """

        if not attacks:
            return 0.0

        # Extract features
        feature_df = pd.DataFrame([a['features'] for a in attacks])
        X = self.gen2_preprocessor.transform(feature_df) if self.gen2_preprocessor is not None else feature_df.values

        # Score with Gen 2 model
        scores = self.gen2_model.predict_proba(X)[:, 1]

        # Evasion: How many score < threshold (0.45)?
        threshold = 0.45
        evaded = np.sum(scores < threshold)
        evasion_rate = evaded / len(attacks) if attacks else 0

        return evasion_rate
