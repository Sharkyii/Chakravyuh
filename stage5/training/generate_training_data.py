import os
import sys
import json
import shutil
from pathlib import Path
from dataclasses import asdict

# Add project root to python path to resolve imports
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.generators.dataset import generate_stage1_dataset
from src.dataset.stage2 import build_stage2_dataset
from src.dataset.loader import load_dataset, EXPECTED_TABLES
from src.attacks.registry import build_attack_generator
from src.attacks.generators import make_legit_lookalike_rows
from stage5.training.build_adaptive_attack_config import build_adaptive_config
from src.graph.builder import GraphBuildConfig, build_graph_edges
from src.schema import TABLE_ARROW_SCHEMAS
import pyarrow as pa
import pyarrow.parquet as pq

# Load config settings
from stage5.config.settings import (
    STAGE5_DATA_DIR,
    STAGE2_OUTPUT_DIR,
    STAGE5_N_CONSUMERS,
    STAGE5_N_MERCHANTS,
    ATTACK_EXPANSION_FACTOR,
)

ATTACK_SCENARIOS = [
    {"attack_id": "scam_induced_push", "seed": 101, "intensity": "MEDIUM"},
    {"attack_id": "mule_network", "seed": 102, "intensity": "MEDIUM"},
    {"attack_id": "card_testing_probe", "seed": 103, "intensity": "MEDIUM"},
    {"attack_id": "adversarial_evasion", "seed": 104, "intensity": "MEDIUM"},
    {"attack_id": "first_party_dispute", "seed": 105, "intensity": "MEDIUM"},
    {"attack_id": "stealth_mandate", "seed": 106, "intensity": "MEDIUM"},
    {"attack_id": "synthetic_merchant", "seed": 107, "intensity": "MEDIUM"},
    {"attack_id": "transaction_laundering", "seed": 108, "intensity": "MEDIUM"},
    {"attack_id": "credential_takeover", "seed": 109, "intensity": "MEDIUM"},
    {"attack_id": "synthetic_identity_bustout", "seed": 110, "intensity": "MEDIUM"},
    {"attack_id": "subthreshold_fragmentation", "seed": 111, "intensity": "MEDIUM"},
    {"attack_id": "agentic_injection", "seed": 112, "intensity": "MEDIUM"},
    {"attack_id": "insider_abuse", "seed": 113, "intensity": "MEDIUM"},
    {"attack_id": "device_fan_out", "seed": 114, "intensity": "MEDIUM"},
    {"attack_id": "balance_drain_exit", "seed": 115, "intensity": "MEDIUM"},
]
# Expand each attack family to multiple distinct campaigns for richer fraud data,
# varying the seed. Factor and baseline population size are both centralised in
# stage5/config/settings.py -- see the comment there on why this isn't 100.
EXPANSION_FACTOR = ATTACK_EXPANSION_FACTOR
expanded_scenarios = []
for base in ATTACK_SCENARIOS:
    for i in range(EXPANSION_FACTOR):
        expanded_scenarios.append({
            "attack_id": base["attack_id"],
            # `* 1000` keeps each family's expanded seed range (base*1000 ..
            # base*1000+EXPANSION_FACTOR-1) from overlapping any other
            # family's, as long as EXPANSION_FACTOR stays under 1000. The
            # previous `base["seed"] + i` scheme used adjacent base seeds
            # (101, 102, 103, ...) with a wide expansion, so e.g. seed 105
            # was reused by five different families -- AttackGenerator.generate()
            # seeds its RNG with this integer alone, so same-seed campaigns
            # from unrelated families produced colliding txn_id uuids
            # (confirmed: ~3.2k duplicate transaction rows in a full run),
            # which corrupted every downstream `merge(on="txn_id")`.
            "seed": base["seed"] * 1000 + i,
            "intensity": base["intensity"]
        })
ATTACK_SCENARIOS = expanded_scenarios

def _row_dict(row) -> dict:
    if isinstance(row, dict):
        return row
    out = {}
    from dataclasses import fields
    for field in fields(row):
        value = getattr(row, field.name)
        out[field.name] = value.value if hasattr(value, "value") else value
    return out

def _write_table(path: Path, table_name: str, rows: list) -> None:
    pylist = [_row_dict(r) for r in rows]
    table = pa.Table.from_pylist(pylist, schema=TABLE_ARROW_SCHEMAS[table_name])
    pq.write_table(table, path)

def check_baseline_cache(baseline_dir: Path, n_consumers: int, n_merchants: int, seed: int = 42) -> bool:
    """Returns True if the baseline cache exists and matches the requested settings."""
    manifest_path = baseline_dir / "cache_manifest.json"
    if not baseline_dir.exists() or not manifest_path.exists():
        return False
    try:
        cached = json.loads(manifest_path.read_text(encoding="utf-8"))
        return (cached.get("n_consumers") == n_consumers and
                cached.get("n_merchants") == n_merchants and
                cached.get("seed") == seed)
    except Exception:
        return False

def main():
    print("=== Generating Stage 5 training dataset ===")
    
    # 1. Generate optimized Stage 1 and Stage 2 baseline
    baseline_s1 = STAGE5_DATA_DIR / "baseline" / "stage1"
    baseline_s2 = STAGE5_DATA_DIR / "baseline" / "stage2"
    combined_dir = STAGE5_DATA_DIR / "combined"
    
    print(f"Checking if baseline Stage 2 exists and matches settings at {baseline_s2}...")
    if not check_baseline_cache(baseline_s2, STAGE5_N_CONSUMERS, STAGE5_N_MERCHANTS, 42):
        print(f"Generating Stage 1 baseline with n_consumers={STAGE5_N_CONSUMERS}...")
        generate_stage1_dataset(
            seed=42,
            output_dir=baseline_s1,
            n_consumers=STAGE5_N_CONSUMERS,
            n_merchants=STAGE5_N_MERCHANTS,
            clean=True,
        )
        print("Building Stage 2 baseline (generating graph edges)...")
        build_stage2_dataset(input_dir=baseline_s1, output_dir=baseline_s2, clean=True)
        
        # Write cache manifest
        baseline_s2.mkdir(parents=True, exist_ok=True)
        (baseline_s2 / "cache_manifest.json").write_text(json.dumps({
            "n_consumers": STAGE5_N_CONSUMERS,
            "n_merchants": STAGE5_N_MERCHANTS,
            "seed": 42
        }, indent=2), encoding="utf-8")
        
        print("Baseline generation complete!")
    else:
        print("Using existing Stage 2 baseline.")
        
    baseline = load_dataset(baseline_s2)
    
    # Keep lists of all transactions and labels
    # baseline.transactions and baseline.labels are already lists of dictionaries
    all_transactions = list(baseline.transactions)
    all_labels = list(baseline.labels)
    
    scenarios_summary = []

    # Closed loop (issues.md I11): if a prior detector generation left a
    # trained model behind, derive a config targeting whatever feature it
    # currently relies on most and apply it to this run's adversarial_evasion
    # campaigns. Empty on a first-ever run -- falls back to static defaults.
    adaptive_config = build_adaptive_config()
    if adaptive_config:
        print(f"Adaptive attack config derived from prior model: {adaptive_config}")

    # 2. Layer attack scenarios
    for sc in ATTACK_SCENARIOS:
        attack_id = sc["attack_id"]
        seed = sc["seed"]
        intensity = sc["intensity"]

        print(f"Layering attack: {attack_id} (seed={seed}, intensity={intensity})...")
        generator = build_attack_generator(attack_id)

        # Generate the attack
        campaign, attack_txs, attack_labels = generator.generate(
            baseline,
            seed=seed,
            intensity=intensity,
            config=adaptive_config if attack_id in ("adversarial_evasion", "synthetic_identity_bustout") else None,
        )
        
        # Standardize dataclasses/objects to dicts if needed
        txs_dicts = [_row_dict(t) for t in attack_txs]
        labels_dicts = [_row_dict(l) for l in attack_labels]

        # legit_lookalike companion population -- without this the classifier
        # never has to separate fraud from its legitimate near-neighbour, and
        # trivially inflates every metric (brief section 6: "the classifier
        # separates two trivially different distributions... meaningless
        # within thirty seconds").
        lookalike_txs, lookalike_labels = make_legit_lookalike_rows(
            attack_rows=txs_dicts, attack_labels=labels_dicts, seed=seed, baseline=baseline
        )
        txs_dicts = txs_dicts + lookalike_txs
        labels_dicts = labels_dicts + lookalike_labels

        # Inject scenario_id if present/customized, otherwise we have campaign_id
        scenario_id = f"{attack_id}_seed{seed}"
        for t in txs_dicts:
            t["scenario_id"] = scenario_id
        for l in labels_dicts:
            l["scenario_id"] = scenario_id
            
        all_transactions.extend(txs_dicts)
        all_labels.extend(labels_dicts)
        
        scenarios_summary.append({
            "attack_id": attack_id,
            "seed": seed,
            "intensity": intensity,
            "campaign_id": campaign.campaign_id,
            "scenario_id": scenario_id,
            "n_transactions": len(txs_dicts),
            "n_labels": len(labels_dicts),
            "n_fraud": sum(1 for l in labels_dicts if l["is_fraud"]),
            "n_lookalike": sum(1 for l in labels_dicts if l.get("is_legit_lookalike", False))
        })
        
    n_fraud = sum(1 for l in all_labels if l.get("is_fraud"))
    n_lookalike = sum(1 for l in all_labels if l.get("is_legit_lookalike"))
    n_total = len(all_transactions)
    print(f"Total transactions after layering: {n_total}")
    print(f"Total labels after layering: {len(all_labels)}")
    print(
        f"Fraud prevalence: {n_fraud}/{n_total} ({100 * n_fraud / n_total:.2f}%) -- "
        f"lookalike: {n_lookalike}/{n_total} ({100 * n_lookalike / n_total:.2f}%). "
        "Check this against stage5/config/settings.py's reasoning comment; adjust "
        "ATTACK_EXPANSION_FACTOR or STAGE5_N_CONSUMERS if it drifts far from ~1-5%."
    )

    # 3. Create combined directory and write parquet tables
    if combined_dir.exists():
        shutil.rmtree(combined_dir)
    combined_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy static tables
    for table_name in EXPECTED_TABLES:
        if table_name in ("transactions", "labels", "graph_edges"):
            continue
        shutil.copy2(baseline_s2 / f"{table_name}.parquet", combined_dir / f"{table_name}.parquet")
        
    # Build final graph edges on combined transactions
    print("Building final graph edges on the combined dataset...")
    final_graph = build_graph_edges(all_transactions, GraphBuildConfig())
    final_graph_dicts = [asdict(edge) for edge in final_graph]
    
    # Write transactions, labels, graph_edges
    print("Writing combined tables...")
    _write_table(combined_dir / "transactions.parquet", "transactions", all_transactions)
    _write_table(combined_dir / "labels.parquet", "labels", all_labels)
    _write_table(combined_dir / "graph_edges.parquet", "graph_edges", final_graph_dicts)
    
    # Write manifest
    manifest = {
        "dataset_version": "stage5-combined-v1",
        "n_transactions": n_total,
        "n_labels": len(all_labels),
        "n_graph_edges": len(final_graph_dicts),
        "n_fraud": n_fraud,
        "n_lookalike": n_lookalike,
        "fraud_prevalence": n_fraud / n_total if n_total else 0.0,
        "lookalike_prevalence": n_lookalike / n_total if n_total else 0.0,
        "scenarios": scenarios_summary,
        "baseline_dir": str(baseline_s2.as_posix()),
    }
    
    (combined_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )
    
    # Create empty validation report for combined loader compatibility
    (combined_dir / "validation_report.json").write_text(
        json.dumps({"ok": True, "errors": [], "summary": {}}, indent=2) + "\n",
        encoding="utf-8"
    )
    
    print("=== Stage 5 training dataset generation complete! ===")

if __name__ == "__main__":
    main()
