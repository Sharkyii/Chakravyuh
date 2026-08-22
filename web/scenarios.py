"""Hand-built example transactions for the web prototype's scenario gallery.

Not generated data -- these are illustrative single rows matching each
family's data signature from docs/attack-catalogue.md's generator merge map,
built for a live demo rather than for training. Every field not set here
gets a neutral default (False for booleans, NaN for everything else) by
`stage5.inference.pipeline.prepare_transaction_df`, so only the fields that
actually distinguish a scenario need to be listed.
"""

from __future__ import annotations

SCENARIOS: dict[str, dict] = {
    "Standard Genuine Payment": {
        "description": (
            "Ordinary UPI payment to an established contact from a known device. "
            "No coercion signals, no graph anomaly -- the baseline every attack "
            "has to hide inside."
        ),
        "expected_attack_id": None,
        "txn": {
            "txn_id": "demo-genuine-1",
            "amount": 480.0,
            "rail": "upi_p2p",
            "channel": "app",
            "auth_method": "upi_pin",
            "device_is_known_for_payer": True,
            "beneficiary_first_time": False,
            "beneficiary_added_ago_s": 60 * 60 * 24 * 200,
            "time_on_confirm_screen_s": 3.1,
            "session_duration_s": 42,
            "pin_attempts": 1,
            "screen_share_active": False,
            "call_active_during_txn": False,
            "accessibility_service_active": False,
            "ip_is_proxy": False,
            "edge_count": 6.0,
            "payer_out_degree": 5.0,
            "payee_in_degree": 40.0,
            "is_two_hop_passthrough": 0.0,
            "mcc": 5411,
        },
    },
    "Phone Call Pressured Transfer": {
        "description": (
            "Own device, correct PIN, brand-new beneficiary -- everything a "
            "rules engine checks looks normal. The only anomaly is intent: "
            "the victim is on a call and being rushed."
        ),
        "expected_attack_id": "scam_induced_push",
        "txn": {
            "txn_id": "demo-scam-1",
            "amount": 45000.0,
            "rail": "upi_p2p",
            "channel": "app",
            "auth_method": "upi_pin",
            "device_is_known_for_payer": True,
            "beneficiary_first_time": True,
            "beneficiary_added_ago_s": 180,
            "time_on_confirm_screen_s": 2.4,
            "session_duration_s": 55,
            "pin_attempts": 1,
            "screen_share_active": True,
            "call_active_during_txn": True,
            "accessibility_service_active": False,
            "ip_is_proxy": False,
            "edge_count": 1.0,
            "payer_out_degree": 3.0,
            "payee_in_degree": 2.0,
            "is_two_hop_passthrough": 0.0,
            "mcc": None,
        },
    },
    "Multi-Account Fund Forwarding": {
        "description": (
            "Individually each hop looks like a real person paying a real "
            "person. Only graph topology -- high fan-in, throughput near 1 -- "
            "betrays it."
        ),
        "expected_attack_id": "mule_network",
        "txn": {
            "txn_id": "demo-mule-1",
            "amount": 9800.0,
            "rail": "upi_p2p",
            "channel": "app",
            "auth_method": "upi_pin",
            "device_is_known_for_payer": True,
            "beneficiary_first_time": False,
            "beneficiary_added_ago_s": 60 * 60 * 24 * 3,
            "time_on_confirm_screen_s": 2.8,
            "session_duration_s": 30,
            "pin_attempts": 1,
            "screen_share_active": False,
            "call_active_during_txn": False,
            "edge_count": 14.0,
            "payer_out_degree": 2.0,
            "payee_in_degree": 47.0,
            "is_two_hop_passthrough": 1.0,
            "mcc": None,
        },
    },
    "Stolen Card Verification": {
        "description": (
            "Micro-amount, high-decline-rate automated probing to find a live "
            "card number -- LLM-optimised BIN attack territory."
        ),
        "expected_attack_id": "card_testing_probe",
        "txn": {
            "txn_id": "demo-cardtest-1",
            "amount": 12.0,
            "rail": "card_cnp",
            "channel": "web",
            "auth_method": "cvv_only",
            "auth_result": "failure",
            "decision": "declined",
            "device_is_known_for_payer": False,
            "beneficiary_first_time": True,
            "beneficiary_added_ago_s": 5,
            "time_on_confirm_screen_s": 0.6,
            "session_duration_s": 4,
            "pin_attempts": 1,
            "ip_is_proxy": True,
            "edge_count": 1.0,
            "payer_out_degree": 1.0,
            "payee_in_degree": 3.0,
            "mcc": 5999,
        },
    },
    "Hidden Detection-Evasive Payment": {
        "description": (
            "The generation-2 attack from docs/closed-loop.md: routes through "
            "the payer's single busiest existing relationship and an "
            "old beneficiary to keep edge_count and beneficiary_added_ago_s -- "
            "the detector's top two features -- inside the normal range on "
            "purpose."
        ),
        "expected_attack_id": "adversarial_evasion",
        "txn": {
            "txn_id": "demo-evasion-1",
            "amount": 340.0,
            "rail": "upi_p2p",
            "channel": "app",
            "auth_method": "upi_pin",
            "device_is_known_for_payer": True,
            "beneficiary_first_time": False,
            "beneficiary_added_ago_s": 60 * 60 * 24 * 400,
            "time_on_confirm_screen_s": 3.4,
            "session_duration_s": 33,
            "pin_attempts": 1,
            "screen_share_active": False,
            "call_active_during_txn": False,
            "edge_count": 9.0,
            "payer_out_degree": 4.0,
            "payee_in_degree": 12.0,
            "is_two_hop_passthrough": 0.0,
            "mcc": None,
        },
    },
}
