"""
Reduced-scale wrapper around generate_training_data.main() -- same
self-consistent single-simulator pipeline, smaller population and fewer
campaigns per attack family so it fits comfortably in limited free RAM.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import stage5.training.generate_training_data as gtd

# Reduced from the settings.py defaults (100k/4k, 40 campaigns/family) --
# machine has ~4GB free RAM with swap already under pressure.
gtd.STAGE5_N_CONSUMERS = 15_000
gtd.STAGE5_N_MERCHANTS = 600

# Keep the full 40 campaigns/family -- that number is settings.py's own
# calibrated value ("lands fraud+lookalike prevalence under ~1% against a
# 20k consumer baseline" -- see its comment), not an arbitrary choice. An
# earlier version of this script truncated to 12/family to save memory, but
# that starved each of the 13 families down to 46-103 fraud rows (0.19%
# overall prevalence, well under the ~1% design target) -- likely why Gen 4/5
# curriculum retraining plateaued instead of clearing their evasion targets.
# Attack-campaign rows are a rounding error against the 15k-consumer
# baseline's memory footprint (the baseline population + graph + feature
# engineering dominate cost, not campaign count), so restoring the full
# factor costs effectively nothing in RAM -- only wall-clock time.
by_family = {}
for sc in gtd.ATTACK_SCENARIOS:
    by_family.setdefault(sc["attack_id"], []).append(sc)
gtd.ATTACK_SCENARIOS = [sc for fam in by_family.values() for sc in fam]

print(f"Reduced run: {gtd.STAGE5_N_CONSUMERS} consumers, {gtd.STAGE5_N_MERCHANTS} merchants, "
      f"{len(gtd.ATTACK_SCENARIOS)} scenarios ({len(by_family)} families x "
      f"{len(gtd.ATTACK_SCENARIOS) // max(len(by_family), 1)})")

if __name__ == "__main__":
    gtd.main()
