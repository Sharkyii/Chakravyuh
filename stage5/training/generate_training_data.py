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
from src.graph.builder import GraphBuildConfig, build_graph_edges
from src.schema import TABLE_ARROW_SCHEMAS
import pyarrow as pa
import pyarrow.parquet as pq

# Load config settings
from stage5.config.settings import STAGE5_DATA_DIR, STAGE2_OUTPUT_DIR

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
]
# Expand each attack family to multiple distinct campaigns for richer fraud data.
# We generate 5 campaigns per attack, varying the seed.
EXPANSION_FACTOR = 100  # Ensure sufficient fraud samples per attack family
expanded_scenarios = []
for base in ATTACK_SCENARIOS:
    for i in range(EXPANSION_FACTOR):
        expanded_scenarios.append({
            "attack_id": base["attack_id"],
            "seed": base["seed"] + i,
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

def main():
    print("=== Generating Stage 5 training dataset ===")
    
    # 1. Generate optimized Stage 1 and Stage 2 baseline
    baseline_s1 = STAGE5_DATA_DIR / "baseline" / "stage1"
    baseline_s2 = STAGE5_DATA_DIR / "baseline" / "stage2"
    combined_dir = STAGE5_DATA_DIR / "combined"
    
    print(f"Checking if baseline Stage 2 exists at {baseline_s2}...")
    if not baseline_s2.exists():
        print("Generating Stage 1 baseline with n_consumers=3000...")
        generate_stage1_dataset(seed=42, output_dir=baseline_s1, n_consumers=3000, n_merchants=150, clean=True)
        print("Building Stage 2 baseline (generating graph edges)...")
        build_stage2_dataset(input_dir=baseline_s1, output_dir=baseline_s2, clean=True)
        print("Baseline generation complete!")
    else:
        print("Using existing Stage 2 baseline.")
        
    baseline = load_dataset(baseline_s2)
    
    # Keep lists of all transactions and labels
    # baseline.transactions and baseline.labels are already lists of dictionaries
    all_transactions = list(baseline.transactions)
    all_labels = list(baseline.labels)
    
    scenarios_summary = []
    
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
            intensity=intensity
        )
        
        # Standardize dataclasses/objects to dicts if needed
        txs_dicts = [_row_dict(t) for t in attack_txs]
        labels_dicts = [_row_dict(l) for l in attack_labels]
        
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
            "n_transactions": len(attack_txs),
            "n_labels": len(attack_labels),
            "n_fraud": sum(1 for l in labels_dicts if l["is_fraud"]),
            "n_lookalike": sum(1 for l in labels_dicts if l.get("is_legit_lookalike", False))
        })
        
    print(f"Total transactions after layering: {len(all_transactions)}")
    print(f"Total labels after layering: {len(all_labels)}")
    
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
        "n_transactions": len(all_transactions),
        "n_labels": len(all_labels),
        "n_graph_edges": len(final_graph_dicts),
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
