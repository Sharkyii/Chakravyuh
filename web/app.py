"""Web prototype -- the closed loop, live. Run with:

    uv run streamlit run web/app.py

Three tabs: score a transaction through the real Stage 6 pipeline and see
why it was flagged, inspect what the detector currently relies on and what
the next-generation adaptive attack targets, and browse the frozen attack
catalogue. Everything here reads real project artifacts (the trained model
if one exists, docs/model-choice.md's recorded numbers, docs/attack-catalogue.md's
generator merge map) rather than staging fake data for the demo.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from stage5.config.settings import MODELS_DIR  # noqa: E402
from stage5.training.build_adaptive_attack_config import build_adaptive_config  # noqa: E402
from web.scenarios import SCENARIOS  # noqa: E402

st.set_page_config(page_title="Chakravyuh -- closed loop", layout="wide")

st.title("Chakravyuh")
st.caption(
    "Mastercard Innovation Challenge 2026 -- identify GenAI payment fraud, generate it "
    "synthetically, defend against it, close the loop. This page demonstrates the "
    "third and fourth of those live against real project code."
)

tab_score, tab_loop, tab_catalogue = st.tabs(["Live scoring", "Closed loop", "Attack catalogue"])


def _models_available() -> bool:
    return (
        (MODELS_DIR / "fraud_model.pkl").exists()
        and (MODELS_DIR / "preprocessor.pkl").exists()
        and (MODELS_DIR / "attack_classifier.pkl").exists()
        and (MODELS_DIR / "attack_class_mapping.json").exists()
    )


# --- Tab 1: Live scoring ------------------------------------------------

with tab_score:
    st.subheader("Score a transaction")
    st.write(
        "Pick a scenario, optionally override the fields that matter, and run it through "
        "the real detector (`stage5.inference.pipeline.analyze_transaction`) -- the same "
        "fraud model, attack classifier, risk fusion, and analyst-narrative layer described "
        "in `docs/model-choice.md` and `docs/closed-loop.md`."
    )

    if not _models_available():
        st.warning(
            "No trained model found in `stage5/models/`. This page needs one to score "
            "anything live -- train the pipeline first:\n\n"
            "```\nuv run python -m stage5.training.generate_training_data\n"
            "uv run python -m stage5.training.train_fraud_model\n"
            "uv run python -m stage5.training.train_attack_classifier\n```\n\n"
            "Scenario descriptions and the closed-loop/catalogue tabs still work without it."
        )

    scenario_name = st.selectbox("Scenario", list(SCENARIOS.keys()))
    scenario = SCENARIOS[scenario_name]
    st.info(scenario["description"])

    txn = dict(scenario["txn"])

    with st.expander("Override fields (see the score move live)", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            txn["amount"] = st.number_input("amount (INR)", value=float(txn.get("amount", 0.0)), step=10.0)
            txn["screen_share_active"] = st.checkbox(
                "screen_share_active", value=bool(txn.get("screen_share_active", False))
            )
            txn["call_active_during_txn"] = st.checkbox(
                "call_active_during_txn", value=bool(txn.get("call_active_during_txn", False))
            )
        with col2:
            txn["beneficiary_first_time"] = st.checkbox(
                "beneficiary_first_time", value=bool(txn.get("beneficiary_first_time", False))
            )
            ben_age_days = st.slider(
                "beneficiary_added_ago (days)",
                min_value=0,
                max_value=730,
                value=int(txn.get("beneficiary_added_ago_s", 0) / 86400),
            )
            txn["beneficiary_added_ago_s"] = ben_age_days * 86400
            txn["accessibility_service_active"] = st.checkbox(
                "accessibility_service_active", value=bool(txn.get("accessibility_service_active", False))
            )
        with col3:
            txn["edge_count"] = st.slider(
                "edge_count (payer<->payee, this window)",
                min_value=0.0,
                max_value=40.0,
                value=float(txn.get("edge_count", 1.0)),
            )
            txn["time_on_confirm_screen_s"] = st.slider(
                "time_on_confirm_screen_s", min_value=0.1, max_value=15.0,
                value=float(txn.get("time_on_confirm_screen_s", 3.0)),
            )
            txn["device_is_known_for_payer"] = st.checkbox(
                "device_is_known_for_payer", value=bool(txn.get("device_is_known_for_payer", True))
            )

    if st.button("Run risk assessment", type="primary"):
        if not _models_available():
            st.error("Can't score -- train the pipeline first (see the warning above).")
        else:
            from stage5.inference.pipeline import analyze_transaction

            with st.spinner("Scoring..."):
                result = analyze_transaction(txn)

            c1, c2, c3 = st.columns(3)
            c1.metric("Risk score", f"{result['risk_score']:.1f} / 100")
            c2.metric("Risk level", result["risk_level"])
            c3.metric("Action", result["recommended_action"])

            st.write("**Predicted attack family probabilities**")
            probs = pd.Series(result["attack_probabilities"]).sort_values(ascending=False)
            st.bar_chart(probs)

            st.write("**Contributing signals**")
            if result["contributing_signals"]:
                for signal in result["contributing_signals"]:
                    st.write(f"- {signal}")
            else:
                st.write("_None triggered._")

            st.write("**Analyst narrative**")
            analysis = result["llm_analysis"]
            st.write(analysis["fraud_explanation"])
            st.write(f"*{analysis['attack_family_interpretation']}*")
            with st.expander("Investigation steps + caveats"):
                for step in analysis["investigation_steps"]:
                    st.write(f"- {step}")
                st.caption(analysis["uncertainty_caveats"])


# --- Tab 2: Closed loop --------------------------------------------------

with tab_loop:
    st.subheader("What the detector relies on, and what closes the loop")
    st.write(
        "Full writeup in `docs/closed-loop.md`. Summary: after fixing three compounding "
        "leaks (`issues.md` I6/I7/I17 -- shallow-copy lookalikes, campaign structure as a "
        "near-perfect tell, a hardcoded `ip_asn` default), the detector's numbers became "
        "genuinely imperfect for the first time, and feature importance spread across "
        "plausible signals instead of one dominant proxy."
    )

    st.write("**Recorded numbers (temporal split, held-out `synthetic_identity_bustout`)**")
    metrics_df = pd.DataFrame(
        [
            {"Metric": "PR-AUC", "Value": "0.9866"},
            {"Metric": "Recall @ 0.1% FPR", "Value": "0.9775"},
            {"Metric": "Recall @ 1% FPR", "Value": "0.9902"},
            {"Metric": "Held-out family recall @ 0.1%/1% FPR", "Value": "1.0000 (see caveat in docs/closed-loop.md)"},
        ]
    )
    st.table(metrics_df)

    if (MODELS_DIR / "fraud_model.pkl").exists() and (MODELS_DIR / "preprocessor.pkl").exists():
        import joblib
        import numpy as np

        model = joblib.load(MODELS_DIR / "fraud_model.pkl")
        preprocessor = joblib.load(MODELS_DIR / "preprocessor.pkl")
        if hasattr(model, "feature_importances_"):
            names = preprocessor.get_feature_names_out()
            imp = model.feature_importances_
            order = np.argsort(imp)[::-1][:10]
            st.write("**Live feature importances (currently saved model)**")
            st.bar_chart(pd.Series({names[i]: float(imp[i]) for i in order}))
    else:
        st.caption(
            "No model currently saved -- the table above reflects the last recorded "
            "training run (see docs/model-choice.md), not a live read."
        )

    st.write("**What the next generation of `adversarial_evasion` will target**")
    adaptive_config = build_adaptive_config()
    if adaptive_config:
        st.json(adaptive_config)
        st.caption(
            "Derived live from the currently-saved model's feature importances "
            "(`stage5/training/build_adaptive_attack_config.py`). The next "
            "`generate_training_data` run applies this automatically."
        )
    else:
        st.caption(
            "Empty -- either no model is saved yet, or nothing cleared the 10% "
            "importance threshold. Static defaults apply."
        )


# --- Tab 3: Attack catalogue ---------------------------------------------

with tab_catalogue:
    st.subheader("13 generators, from a 58-entry catalogue")
    st.write("Full catalogue: `docs/attack-catalogue.md`. Merge map summary:")

    catalogue_rows = [
        ("G01", "scam_induced_push", "UPI P2P", "Genuine device/PIN, new beneficiary, coercion session fields"),
        ("G02", "mule_network", "UPI P2P / IMPS", "Fan-in, pass-through, throughput ratio -> 1"),
        ("G03", "card_testing_probe", "Card CNP", "Micro-amounts, high decline rate, card rotation"),
        ("G04", "adversarial_evasion", "Any", "Probe then optimise; features tuned inside legit distribution"),
        ("G05", "first_party_dispute", "Card CNP / UPI P2M / BNPL", "Transaction genuine; signal is claimant dispute history"),
        ("G06", "stealth_mandate", "UPI mandate", "Uniform small recurring amounts, max_amount >> actual_amount"),
        ("G07", "synthetic_merchant", "UPI P2M / BNPL", "New merchant, step volume curve, registry-unverified KYB"),
        ("G08", "transaction_laundering", "Card CNP / UPI P2M", "mcc_declared != mcc_inferred_from_basket"),
        ("G09", "credential_takeover", "Card / UPI", "Auth succeeds, device/session anomalous, high-risk account change"),
        ("G10", "synthetic_identity_bustout", "BNPL / Card / Wallet", "Credit-building phase then simultaneous utilisation spike"),
        ("G11", "subthreshold_fragmentation", "UPI Lite / Wallet", "Uniform amounts just under a limit"),
        ("G12", "agentic_injection", "UPI mandate / Agentic", "is_agent_initiated, beneficiary != seller of record"),
        ("G13", "insider_abuse", "Merchant KYB / Bank", "No external anomaly; approval-velocity signals only"),
    ]
    st.table(pd.DataFrame(catalogue_rows, columns=["ID", "Generator", "Primary rail(s)", "Data signature"]))

    st.caption(
        "6 catalogue entries are deck-only (no distinct in-log signature or depend on "
        "physical-world events the payment log never sees) -- see docs/attack-catalogue.md "
        "for the full list and reasoning."
    )
