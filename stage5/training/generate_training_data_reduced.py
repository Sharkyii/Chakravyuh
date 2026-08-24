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

# Truncate each family's expanded campaign list (originally 40/family) down
# to 12/family -- still enough for a per-split fraud count that isn't noise,
# far lighter than the full 520-scenario run.
by_family = {}
for sc in gtd.ATTACK_SCENARIOS:
    by_family.setdefault(sc["attack_id"], []).append(sc)
gtd.ATTACK_SCENARIOS = [sc for fam in by_family.values() for sc in fam[:12]]

print(f"Reduced run: {gtd.STAGE5_N_CONSUMERS} consumers, {gtd.STAGE5_N_MERCHANTS} merchants, "
      f"{len(gtd.ATTACK_SCENARIOS)} scenarios ({len(by_family)} families x 12)")

if __name__ == "__main__":
    gtd.main()
