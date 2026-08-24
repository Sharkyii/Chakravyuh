"""
Extract top SHAP features and rank by importance and hiding difficulty.
Used to generate targeted adversarial attacks that hide detector's main tells.
"""
import numpy as np
from typing import dict, list, tuple


def get_top_features(model, threshold=0.10) -> list[tuple[str, float]]:
    """
    Extract features above importance threshold.

    Args:
        model: Trained XGBoost model
        threshold: Min importance (default 10%)

    Returns:
        [(feature_name, importance), ...] sorted by importance descending
    """
    if not hasattr(model, 'feature_importances_'):
        return []

    importances = model.feature_importances_
    feature_names = model.get_booster().feature_names

    features_with_importance = [
        (name, imp) for name, imp in zip(feature_names, importances)
        if imp >= threshold
    ]

    # Sort by importance descending
    return sorted(features_with_importance, key=lambda x: x[1], reverse=True)


def calculate_hiding_difficulty(feature_name: str) -> float:
    """
    Rate how hard it is to hide this feature without looking suspicious.

    Returns:
        1.0 = Easy to hide (natural variation)
        0.5 = Medium (requires planning)
        0.1 = Hard (structural requirement)

    Examples:
        - amount: 1.0 (can vary naturally)
        - txn_hour: 1.0 (timing varies)
        - beneficiary_added_ago_s: 0.5 (requires long-term planning)
        - edge_count: 0.5 (requires network setup)
        - screen_share_active: 0.1 (hard to hide if actively compromising)
        - is_fraud: 0.0 (can't hide)
    """

    easy_to_hide = {
        'amount', 'txn_hour', 'tx_dayofweek', 'auth_latency_ms',
        'session_duration_s', 'time_on_confirm_screen_s',
        'pin_attempts', 'amount_deviation', 'inter_txn_time_mean',
        'txn_burstiness', 'amount_std', 'subthreshold_txn_ratio'
    }

    medium_to_hide = {
        'beneficiary_added_ago_s', 'edge_count', 'edge_value_total',
        'txn_count_last_1h', 'txn_count_last_24h', 'amount_spent_last_1h',
        'amount_spent_last_24h', 'new_merchant_indicator', 'new_device_indicator',
        'new_ip_indicator', 'unique_payee_count', 'merchant_diversity',
        'account_age_days', 'time_since_prev_txn'
    }

    hard_to_hide = {
        'screen_share_active', 'call_active_during_txn', 'accessibility_service_active',
        'device_is_known_for_payer', 'beneficiary_first_time', 'is_agent_initiated',
        'ip_is_proxy', 'geo_matches_billing', 'geo_matches_payer_home',
        'is_two_hop_passthrough'
    }

    if feature_name in easy_to_hide:
        return 1.0
    elif feature_name in medium_to_hide:
        return 0.5
    elif feature_name in hard_to_hide:
        return 0.1
    else:
        return 0.3  # Default medium
