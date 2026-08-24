"""
Gen 3 Attack Specifications: Hide top 5 features while maintaining viability.
Each family has a different strategy for hiding signals.
"""

GEN3_SPECS = {
    'mule_network': {
        'description': 'Hide graph structure (fan-in/fan-out) by distributing across established network',
        'target_features_to_hide': ['payer_out_degree', 'edge_count', 'is_two_hop_passthrough'],
        'strategy': 'distribute_across_established_network',
        'parameters': {
            'use_existing_payees_only': True,
            'min_existing_transactions': 3,
            'max_new_payees_per_campaign': 1,
            'beneficiary_age_floor_s': 30 * 86400,  # 30 days minimum
            'spread_transactions': True,
            'randomize_timing': True,
            'max_transactions_per_counterparty': 3,
        },
        'expected_impact': {
            'edge_count': 'reduced',  # No longer obvious fan-in
            'payer_out_degree': 'hidden',  # Uses existing network
            'is_two_hop_passthrough': 'reduced',  # Less obvious routing
        }
    },
    'adversarial_evasion': {
        'description': 'Hide graph age + velocity by blending with legitimate patterns',
        'target_features_to_hide': ['edge_count', 'beneficiary_added_ago_s', 'txn_count_last_1h'],
        'strategy': 'blend_with_legitimate_patterns',
        'parameters': {
            'beneficiary_age_floor_s': 60 * 86400,  # 60 days (established receiver)
            'spread_transactions': True,
            'randomize_timing': True,
            'mimic_historical_behavior': True,
            'max_txn_per_hour': 2,  # Avoid velocity spike
            'use_existing_payee_pool': True,
            'variance_in_amounts': True,
        },
        'expected_impact': {
            'beneficiary_added_ago_s': 'hidden',  # Looks established
            'txn_count_last_1h': 'reduced',  # No velocity spike
            'edge_count': 'reduced',  # Distributed routing
        }
    },
    'account_takeover': {
        'description': 'Hide remote access signals by avoiding detection channels',
        'target_features_to_hide': ['screen_share_active', 'call_active_during_txn', 'new_device_indicator'],
        'strategy': 'avoid_detection_channels',
        'parameters': {
            'use_known_device': True,
            'avoid_remote_access': True,
            'avoid_screen_share': True,
            'avoid_voice_call': True,
            'mimic_legitimate_session': True,
            'use_familiar_ip': True,
        },
        'expected_impact': {
            'screen_share_active': 'false',  # No remote control
            'call_active_during_txn': 'false',  # No voice call
            'device_is_known_for_payer': 'true',  # Familiar device
        }
    },
    'synthetic_identity_bustout': {
        'description': 'Hide credit-building phase by distributing transactions',
        'target_features_to_hide': ['txn_count_last_24h', 'amount_spent_last_24h', 'account_age_days'],
        'strategy': 'distribute_over_time',
        'parameters': {
            'spread_across_days': True,
            'min_days_between_cycles': 7,
            'account_age_floor_days': 90,  # Older accounts less suspicious
            'max_daily_transaction_count': 3,
            'varied_amounts': True,
            'realistic_merchant_distribution': True,
        },
        'expected_impact': {
            'txn_count_last_24h': 'reduced',  # Distributed
            'amount_spent_last_24h': 'reduced',  # Spread out
            'account_age_days': 'hidden',  # Established account
        }
    },
    'card_testing_probe': {
        'description': 'Hide repeated small attempts by spacing them naturally',
        'target_features_to_hide': ['txn_count_last_1h', 'pin_attempts', 'subthreshold_txn_ratio'],
        'strategy': 'natural_spacing',
        'parameters': {
            'min_time_between_attempts': 300,  # 5 minutes
            'max_attempts_per_hour': 2,
            'vary_amounts': True,
            'vary_merchants': True,
            'include_successful_transactions': True,
        },
        'expected_impact': {
            'txn_count_last_1h': 'reduced',  # No clustering
            'pin_attempts': 'hidden',  # Spread out
            'subthreshold_txn_ratio': 'lower',  # Mix of amounts
        }
    },
}

# Curriculum levels: Start easy, gradually increase difficulty
CURRICULUM_LEVELS = {
    'level_1_easy': {
        'description': 'Hide 1-2 features only',
        'features_to_hide': 1,
        'difficulty_multiplier': 1.0,
        'sample_size': 500,
    },
    'level_2_medium': {
        'description': 'Hide 2-3 features',
        'features_to_hide': 2,
        'difficulty_multiplier': 1.5,
        'sample_size': 750,
    },
    'level_3_hard': {
        'description': 'Hide 3-4 features',
        'features_to_hide': 3,
        'difficulty_multiplier': 2.0,
        'sample_size': 1000,
    },
    'level_4_extreme': {
        'description': 'Hide all top 5 features + add noise',
        'features_to_hide': 5,
        'difficulty_multiplier': 3.0,
        'sample_size': 500,  # Fewer extreme variants
    },
}

# Success criteria
GEN3_TARGETS = {
    'evasion_margin_target': 0.05,  # <5% should slip through
    'gen2_recall_maintain': 0.99,  # Should still catch 99%+ of Gen 2 attacks
    'feature_importance_stability': 0.20,  # Top features shouldn't flip >20%
    'campaign_viability': 0.95,  # 95%+ of generated campaigns should be valid
}
