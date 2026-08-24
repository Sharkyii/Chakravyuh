"""
Accumulate analyst feedback and trigger retraining when thresholds are met.
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


class FeedbackStore:
    """Store and manage analyst verdicts."""

    def __init__(self, feedback_dir: Path = None):
        """
        Args:
            feedback_dir: Where to store feedback.parquet
        """
        if feedback_dir is None:
            feedback_dir = Path(__file__).resolve().parent.parent / "data"

        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_path = self.feedback_dir / "analyst_feedback.parquet"

    def add_verdict(self, transaction_id: str, verdict: dict) -> None:
        """
        Add one analyst verdict.

        Args:
            transaction_id: Unique ID for the transaction
            verdict: Dict with analyst_verdict, confidence, reasoning, etc.
        """
        # Load existing feedback
        if self.feedback_path.exists():
            df = pd.read_parquet(self.feedback_path)
        else:
            df = pd.DataFrame()

        # Append new feedback
        new_row = {
            "transaction_id": transaction_id,
            "timestamp": datetime.now().isoformat(),
            **verdict
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        # Save
        df.to_parquet(self.feedback_path, index=False)

    def get_feedback_count(self) -> int:
        """How many analyst verdicts have we collected?"""
        if not self.feedback_path.exists():
            return 0
        df = pd.read_parquet(self.feedback_path)
        return len(df)

    def get_confirmed_fraud(self) -> pd.DataFrame:
        """Get all transactions analyst marked as FRAUD."""
        if not self.feedback_path.exists():
            return pd.DataFrame()

        df = pd.read_parquet(self.feedback_path)
        return df[df["analyst_verdict"] == "FRAUD"].copy()

    def get_confirmed_legitimate(self) -> pd.DataFrame:
        """Get all transactions analyst marked as LEGITIMATE."""
        if not self.feedback_path.exists():
            return pd.DataFrame()

        df = pd.read_parquet(self.feedback_path)
        return df[df["analyst_verdict"] == "LEGITIMATE"].copy()

    def should_trigger_retrain(self) -> tuple[bool, str]:
        """
        Decide if we have enough feedback to retrain.

        Returns:
            (should_retrain, reason)
        """
        count = self.get_feedback_count()
        fraud_count = len(self.get_confirmed_fraud())

        if fraud_count >= 20:
            return True, f"Enough fraud feedback ({fraud_count} confirmed)"

        if count >= 50:
            return True, f"Enough total feedback ({count} verdicts)"

        return False, f"Not enough feedback yet ({count}/50, {fraud_count}/20 fraud)"

    def get_summary(self) -> dict:
        """Get summary statistics about feedback collected."""
        if not self.feedback_path.exists():
            return {
                "total_feedback": 0,
                "fraud_confirmed": 0,
                "legitimate_confirmed": 0,
                "unsure": 0,
                "should_retrain": False,
                "reason": "No feedback collected yet"
            }

        df = pd.read_parquet(self.feedback_path)

        fraud = len(df[df["analyst_verdict"] == "FRAUD"])
        legit = len(df[df["analyst_verdict"] == "LEGITIMATE"])
        unsure = len(df[df["analyst_verdict"] == "UNSURE"])
        total = len(df)

        should_retrain, reason = self.should_trigger_retrain()

        return {
            "total_feedback": total,
            "fraud_confirmed": fraud,
            "legitimate_confirmed": legit,
            "unsure": unsure,
            "fraud_confidence": df[df["analyst_verdict"] == "FRAUD"]["analyst_confidence"].mean() if fraud > 0 else 0,
            "should_retrain": should_retrain,
            "reason": reason,
            "last_updated": df["timestamp"].max() if len(df) > 0 else None
        }


def check_retraining_eligibility() -> dict:
    """
    Check if feedback conditions are met for retraining.

    Returns:
        {
            "should_retrain": bool,
            "summary": feedback summary,
            "next_steps": str
        }
    """
    store = FeedbackStore()
    summary = store.get_summary()
    should_retrain, reason = store.should_trigger_retrain()

    return {
        "should_retrain": should_retrain,
        "summary": summary,
        "next_steps": (
            "Run: python -m stage5.training.feedback_retrain_orchestrator"
            if should_retrain else
            f"Collect more feedback. {reason}"
        )
    }


if __name__ == "__main__":
    # Demo usage
    store = FeedbackStore()

    print("=" * 70)
    print("FEEDBACK AGGREGATOR DEMO")
    print("=" * 70)

    # Simulate adding some feedback
    demo_verdicts = [
        {
            "analyst_verdict": "FRAUD",
            "analyst_confidence": 0.95,
            "analyst_reasoning": "New payee + odd timing + amount spike",
            "key_signals": ["edge_count", "beneficiary_added_ago_s"],
            "patterns": ["mule_network_pattern"]
        },
        {
            "analyst_verdict": "LEGITIMATE",
            "analyst_confidence": 0.92,
            "analyst_reasoning": "Remittance to known family member",
            "key_signals": ["beneficiary_added_ago_s"],
            "patterns": ["legitimate_remittance_pattern"]
        }
    ]

    print("\nAdding demo verdicts...")
    for i, verdict in enumerate(demo_verdicts):
        store.add_verdict(f"txn_{i:04d}", verdict)
        print(f"  Added verdict {i+1}")

    print("\nFeedback Summary:")
    summary = store.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print("\nRetrain Eligibility:")
    eligibility = check_retraining_eligibility()
    print(f"  Should retrain: {eligibility['should_retrain']}")
    print(f"  Next steps: {eligibility['next_steps']}")
