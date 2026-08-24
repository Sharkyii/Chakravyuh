"""
Gen 4 Attack Specifications: Ensemble evasion - hide from combinations of features.
Instead of hiding single features, Gen 4 trades off multiple signals.
Example: Low edge_count BUT high txn_count_last_1h (conflicting signals).
"""

GEN4_SPECS = {
    'ensemble_low_edge_high_velocity': {
        'description': 'Keep edge_count low (hidden) but increase transaction velocity',
        'strategy': 'trade_off_graph_for_velocity',
        'hiding_features': ['edge_count', 'is_two_hop_passthrough'],
        'exposing_features': ['txn_count_last_1h', 'amount_spent_last_1h'],
        'parameters': {
            'use_single_top_counterparty': True,  # Hide: low edge_count
            'increase_velocity': True,  # Expose: high velocity (confuses detector)
            'max_txn_per_hour': 5,  # High velocity
            'beneficiary_age_floor_s': 30 * 86400,
        },
        'rationale': 'Model sees either low-graph OR high-velocity, not both clearly anomalous',
        'detection_challenge': 'Is low-graph with high-velocity fraud or just enthusiastic user?'
    },
    'ensemble_established_payee_new_behavior': {
        'description': 'Use old payee (high beneficiary_age) but new behavior pattern',
        'strategy': 'trade_off_age_for_behavior',
        'hiding_features': ['beneficiary_added_ago_s'],
        'exposing_features': ['amount_deviation', 'time_since_prev_txn'],
        'parameters': {
            'use_existing_payee_pool': True,  # Hide: old beneficiary age
            'vary_amounts_significantly': True,  # Expose: unusual amounts
            'change_timing_pattern': True,  # Expose: unusual timing
            'amount_multiplier_range': [0.5, 2.0],  # Deviation from normal
        },
        'rationale': 'Old payee looks legitimate but behavior is anomalous',
        'detection_challenge': 'Is it a loyal customer making unusual purchase or fraud?'
    },
    'ensemble_known_device_new_ip': {
        'description': 'Use known device BUT new/proxy IP (conflicting device/IP signals)',
        'strategy': 'trade_off_device_for_ip',
        'hiding_features': ['device_is_known_for_payer'],
        'exposing_features': ['ip_is_proxy', 'new_ip_indicator'],
        'parameters': {
            'use_known_device': True,  # Hide: familiar device
            'use_proxy_ip': True,  # Expose: proxy/VPN
            'mismatched_ip_device': True,  # Conflict: device ≠ IP location
        },
        'rationale': 'Known device from unknown IP (legitimate traveler or compromised)',
        'detection_challenge': 'Could be roaming user with VPN or remote fraud'
    },
    'ensemble_mixed_transaction_sizes': {
        'description': 'Mix of small threshold-beating + large amounts (velocity + amount signals)',
        'strategy': 'trade_off_amount_for_count',
        'hiding_features': ['subthreshold_txn_ratio'],
        'exposing_features': ['txn_count_last_24h', 'amount_spent_last_24h'],
        'parameters': {
            'mix_small_and_large': True,  # Some under/over threshold
            'total_daily_volume_high': True,  # But volume is high
            'strategic_ordering': True,  # Arrange to avoid patterns
        },
        'rationale': 'Transactions individually look normal, aggregate is suspicious',
        'detection_challenge': 'Is it many small purchases + one big one, or structured fraud?'
    },
    'ensemble_distributed_graph_concentrated_value': {
        'description': 'Spread across many edges BUT concentrate value (graph spreading + value spike)',
        'strategy': 'trade_off_graph_for_value',
        'hiding_features': ['payer_out_degree', 'edge_value_total'],
        'exposing_features': ['amount', 'amount_spent_last_24h'],
        'parameters': {
            'distribute_across_payees': True,  # Hide: spread out graph
            'concentrate_in_largest_transaction': True,  # Expose: large final txn
            'num_small_payees': 8,  # Build to large transfer
            'final_amount_multiplier': 3.0,  # Last one is 3x normal
        },
        'rationale': 'Many small transactions to build legitimacy, then one big theft',
        'detection_challenge': 'Looks like normal spending pattern until final spike'
    },
    'ensemble_low_velocity_high_anomaly': {
        'description': 'Slow transactions BUT high feature anomalies (timing vs content mismatch)',
        'strategy': 'trade_off_velocity_for_anomaly',
        'hiding_features': ['txn_count_last_1h', 'txn_count_last_24h'],
        'exposing_features': ['time_on_confirm_screen_s', 'pin_attempts'],
        'parameters': {
            'slow_transaction_rate': True,  # Hide: low velocity
            'high_friction_indicators': True,  # Expose: hesitation, retries
            'confirm_screen_time_high': True,  # Long time on confirmation
            'pin_attempts_multiple': True,  # Multiple failed PIN attempts
        },
        'rationale': 'Slow, careful transactions but showing signs of struggle (victim being coerced?)',
        'detection_challenge': 'Is it someone cautious or someone under duress?'
    }
}

# Curriculum levels: Easier to harder ensemble attacks
CURRICULUM_LEVELS = {
    'level_1_simple_ensemble': {
        'description': 'Trade off 2 features (1 hidden, 1 exposed)',
        'complexity': 1,
        'hiding_count': 1,
        'exposing_count': 1,
        'sample_size': 400,
    },
    'level_2_complex_ensemble': {
        'description': 'Trade off 3 features (2 hidden, 1-2 exposed)',
        'complexity': 2,
        'hiding_count': 2,
        'exposing_count': 2,
        'sample_size': 600,
    },
    'level_3_multi_ensemble': {
        'description': 'Trade off 4-5 features (multiple simultaneous trades)',
        'complexity': 3,
        'hiding_count': 3,
        'exposing_count': 3,
        'sample_size': 800,
    },
    'level_4_extreme_ensemble': {
        'description': 'Trade off all top features + add cross-family combinations',
        'complexity': 4,
        'hiding_count': 5,
        'exposing_count': 5,
        'sample_size': 500,
    },
}

# Success criteria for Gen 4
GEN4_TARGETS = {
    'evasion_margin_target': 0.15,  # <15% should slip through (harder than Gen 3)
    'gen3_recall_maintain': 0.98,  # Should still catch 98%+ of Gen 3 attacks
    'gen2_recall_maintain': 0.99,  # Should still catch 99%+ of Gen 2 attacks
    'feature_importance_stability': 0.25,  # Some ranking shift OK (model adapting)
}

# Interpretation guide
INTERPRETATION = {
    'why_harder': 'Gen 4 attacks trade off features — model can\'t rely on any single signal, must learn combinations',
    'why_15_percent': 'Ensemble attacks are structurally harder. Catching 85% is realistic for this complexity',
    'when_to_gen5': 'If Gen 4 evasion > 15%, generate Gen 5 (multi-family attacks)',
    'when_to_deploy': 'If Gen 4 evasion < 15%, model is solid against known ensemble attacks',
}
