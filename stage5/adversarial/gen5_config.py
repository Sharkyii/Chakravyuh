"""
Gen 5 Attack Specifications: Multi-family cross-attack combinations.
Instead of single family → trade off features within that family.
Gen 5 combines features across attack families to create novel evasion.
Example: mule_network + card_testing + account_takeover features in one attack.
"""

GEN5_SPECS = {
    'cross_family_mule_and_testing': {
        'description': 'Combine mule network (low edge_count) + card testing (rapid, low amounts)',
        'families': ['mule_network', 'card_testing_probe'],
        'mixing_strategy': 'fast_low_value',
        'hidden_features': ['edge_count', 'payer_out_degree'],
        'exposed_features': ['txn_count_last_1h', 'amount'],
        'real_world_example': 'Quick pulse of micro-transactions to collect valid cards',
        'parameters': {
            'use_single_top_counterparty': True,  # mule: low graph
            'rapid_txn_sequence': True,  # card testing: fast
            'small_amounts': True,  # card testing: probe amounts
            'amount_range': [0.99, 9.99],  # Just under detection
        }
    },
    'cross_family_bustout_and_evasion': {
        'description': 'Combine synthetic identity bustout + adversarial evasion',
        'families': ['synthetic_identity_bustout', 'adversarial_evasion'],
        'mixing_strategy': 'slow_high_value',
        'hidden_features': ['new_account_age_s', 'address_change_recent'],
        'exposed_features': ['amount_spent_last_24h', 'txn_count_last_24h'],
        'real_world_example': 'Fake account slowly building history, then liquidating',
        'parameters': {
            'use_old_created_account': True,  # Make account look established
            'feature_spoofing_enabled': True,  # Evasion: hide feature changes
            'gradual_velocity_increase': True,  # Slow build-up
            'final_large_txn': True,  # Then large withdrawal
        }
    },
    'cross_family_takeover_and_network': {
        'description': 'Combine account takeover + mule network operations',
        'families': ['account_takeover', 'mule_network'],
        'mixing_strategy': 'compromised_then_forward',
        'hidden_features': ['new_ip_indicator', 'edge_count'],
        'exposed_features': ['time_since_prev_txn', 'payer_out_degree'],
        'real_world_example': 'Compromised account suddenly forwarding money through mule chain',
        'parameters': {
            'ip_change_subtle': True,  # Not obviously new IP
            'establish_mule_chain': True,  # Forward to multiple accounts
            'timing_mimics_user': True,  # But unusual pattern
            'use_multiple_mules': True,  # Network spread
        }
    },
    'cross_family_bustout_testing_combined': {
        'description': 'Combine bustout (high final value) + testing (rapid low value first)',
        'families': ['synthetic_identity_bustout', 'card_testing_probe'],
        'mixing_strategy': 'probe_then_exploit',
        'hidden_features': ['txn_count_last_1h', 'amount_deviation'],
        'exposed_features': ['amount_spent_last_24h', 'time_on_confirm_screen_s'],
        'real_world_example': 'Test small txns to verify active, then large withdrawal',
        'parameters': {
            'initial_probe_phase': True,  # Small testing txns
            'probe_count': 5,
            'probe_amounts': [1.0, 2.0, 5.0, 10.0, 20.0],
            'transition_to_large': True,  # Jump to large amount
            'final_amount_multiplier': 50.0,  # 50x first probe
        }
    },
    'cross_family_takeover_testing_evasion': {
        'description': 'Combine takeover (IP/device change) + testing + evasion (feature spoofing)',
        'families': ['account_takeover', 'card_testing_probe', 'adversarial_evasion'],
        'mixing_strategy': 'three_way_confusion',
        'hidden_features': ['device_is_known_for_payer', 'new_ip_indicator', 'beneficiary_added_ago_s'],
        'exposed_features': ['txn_count_last_1h', 'amount', 'pin_attempts'],
        'real_world_example': 'New IP, testing cards, spoofing additional features to look confused user',
        'parameters': {
            'change_ip_and_device': True,  # Takeover signal
            'card_test_sequence': True,  # Testing signal
            'spoof_multiple_features': True,  # Evasion signal
            'add_friction_indicators': True,  # PIN retries (looks genuine)
        }
    },
    'cross_family_mule_bustout_network': {
        'description': 'Combine all network-based: mule + bustout network spread + takeover chain',
        'families': ['mule_network', 'synthetic_identity_bustout', 'account_takeover'],
        'mixing_strategy': 'complex_network_flow',
        'hidden_features': ['payer_out_degree', 'new_account_age_s', 'edge_count'],
        'exposed_features': ['amount_spent_last_24h', 'time_since_prev_txn', 'txn_count_last_24h'],
        'real_world_example': 'Coordinated attack: takeover original account → forward through mule network → funnel to bustout fake account',
        'parameters': {
            'compromise_real_account': True,  # Takeover
            'establish_mule_chain': True,  # Mule network (5-10 hops)
            'funnel_to_fake_account': True,  # Bustout destination
            'obscure_final_destination': True,  # Hide true attacker
            'num_mule_hops': 7,
        }
    }
}

# Curriculum levels: Progressive difficulty for multi-family attacks
CURRICULUM_LEVELS = {
    'level_1_simple_cross_family': {
        'description': '2-family cross-attack (mule + testing)',
        'complexity': 1,
        'num_families': 2,
        'feature_combinations': 3,
        'sample_size': 300,
    },
    'level_2_moderate_cross_family': {
        'description': '2-family combinations with more sophisticated mixing',
        'complexity': 2,
        'num_families': 2,
        'feature_combinations': 5,
        'sample_size': 400,
    },
    'level_3_complex_cross_family': {
        'description': '3-family combinations (takeover + testing + evasion)',
        'complexity': 3,
        'num_families': 3,
        'feature_combinations': 7,
        'sample_size': 500,
    },
    'level_4_extreme_cross_family': {
        'description': '3+ family combinations with adversarial timing',
        'complexity': 4,
        'num_families': 3,
        'feature_combinations': 10,
        'sample_size': 400,
    },
}

# Success criteria for Gen 5
GEN5_TARGETS = {
    'evasion_margin_target': 0.25,  # <25% should slip through (much harder than Gen 4)
    'gen4_recall_maintain': 0.95,  # Should still catch 95%+ of Gen 4 attacks
    'gen3_recall_maintain': 0.98,  # Should still catch 98%+ of Gen 3 attacks
    'cross_family_detection_rate': 0.80,  # Can detect cross-family combos 80%+ of time
}

# Interpretation guide
INTERPRETATION = {
    'why_harder': 'Gen 5 combines attack families — single-family detectors fail, need holistic understanding',
    'why_25_percent': 'Multi-family attacks are extremely hard. Catching 75% is realistic for this complexity',
    'when_to_stop': 'If Gen 5 evasion > 25%, or if ensemble still strong after Gen 5, model is robust enough for production',
    'when_to_deploy': 'After passing Gen 5, detector is hardened against all known attack strategies',
    'next_frontier': 'Post-Gen 5: analyst-in-the-loop feedback on Gen 5 evasions, continuous retraining',
}
