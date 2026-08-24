"""
Cost limiter for hackathon: Manual click-based budget enforcement.
- $1/day maximum budget (hackathon safe)
- Max 20 runs/day (prevents runaway)
- Manual click triggers (no auto-execution)
- Shows detailed impact report before each run
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class CostLimiter:
    """Track API usage with strict hackathon limits."""

    def __init__(self, budget_file: Optional[Path] = None):
        """
        Args:
            budget_file: Path to store daily usage log
        """
        if budget_file is None:
            budget_file = Path(__file__).resolve().parent.parent / "data" / "api_usage.log"

        self.budget_file = Path(budget_file)
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)

        # Hackathon limits
        self.daily_limit_usd = 1.0  # $1/day for hackathon
        self.max_runs_per_day = 20  # Max 20 runs/day

        # Usage tracking
        self._load_usage_log()

    def _load_usage_log(self):
        """Load today's usage from file."""
        self.today = datetime.now().date()
        self.usage_today_usd = 0.0
        self.request_count_today = 0

        if not self.budget_file.exists():
            return

        with open(self.budget_file, "r") as f:
            for line in f:
                try:
                    parts = line.strip().split("|")
                    if len(parts) >= 2:
                        date_str = parts[0]
                        usage_str = parts[1]

                        log_date = datetime.fromisoformat(date_str).date()
                        if log_date == self.today:
                            self.usage_today_usd += float(usage_str)
                            self.request_count_today += 1
                except ValueError:
                    pass

    def _log_usage(self, cost_usd: float):
        """Log a single API call."""
        with open(self.budget_file, "a") as f:
            f.write(f"{datetime.now().isoformat()}|{cost_usd}\n")

        self.usage_today_usd += cost_usd
        self.request_count_today += 1

    def check_can_analyze(self) -> tuple[bool, str]:
        """
        Check if we can afford another analysis call.
        Hackathon mode: strict limits to prevent overspending.

        Returns:
            (can_proceed, reason)
        """
        # Claude Sonnet 5: ~$0.003 per 1K input tokens, ~$0.015 per 1K output
        # Estimate: ~$0.005 per call
        estimated_cost = 0.005

        # Check run count first
        if self.request_count_today >= self.max_runs_per_day:
            return False, f"❌ Max {self.max_runs_per_day} runs/day reached. ({self.request_count_today}/{self.max_runs_per_day})"

        # Check budget
        if self.usage_today_usd + estimated_cost > self.daily_limit_usd:
            remaining_budget = self.daily_limit_usd - self.usage_today_usd
            return False, f"❌ Daily budget exhausted. ${self.usage_today_usd:.3f}/${self.daily_limit_usd:.2f} spent. Need ${estimated_cost:.3f}, have ${remaining_budget:.3f}"

        return True, "✓ Budget OK"

    def log_analysis(self, cost_usd: float = 0.005):
        """Log an analyst analysis call."""
        self._log_usage(cost_usd)

    def get_usage_summary(self) -> dict:
        """Get today's usage summary for display."""
        can_proceed, status = self.check_can_analyze()

        return {
            "today": self.today.isoformat(),
            "spent_usd": round(self.usage_today_usd, 4),
            "daily_limit_usd": self.daily_limit_usd,
            "remaining_usd": round(self.daily_limit_usd - self.usage_today_usd, 4),
            "request_count": self.request_count_today,
            "max_runs": self.max_runs_per_day,
            "can_proceed": can_proceed,
            "status": status,
            "percent_budget_used": round((self.usage_today_usd / self.daily_limit_usd) * 100, 1),
            "percent_runs_used": round((self.request_count_today / self.max_runs_per_day) * 100, 1)
        }


# Global instance
_limiter = None


def get_limiter() -> CostLimiter:
    """Get or create global cost limiter."""
    global _limiter
    if _limiter is None:
        _limiter = CostLimiter()
    return _limiter


def check_budget() -> dict:
    """Check current budget status."""
    return get_limiter().get_usage_summary()


def should_proceed_with_analysis() -> tuple[bool, dict]:
    """
    Determine if we should run an analysis.

    Returns:
        (should_proceed, budget_info)
    """
    limiter = get_limiter()
    can_proceed, reason = limiter.check_can_analyze()
    summary = limiter.get_usage_summary()

    return can_proceed, summary


if __name__ == "__main__":
    limiter = get_limiter()

    print("=" * 70)
    print("COST LIMITER STATUS")
    print("=" * 70)

    summary = limiter.get_usage_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")

    print(f"\nDaily budget: ${summary['daily_limit_usd']:.2f}")
    print(f"Spent today: ${summary['spent_usd']:.2f}")
    print(f"Remaining: ${summary['remaining_usd']:.2f}")
    print(f"Can proceed: {summary['can_proceed']}")
