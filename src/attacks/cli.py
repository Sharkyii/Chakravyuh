from __future__ import annotations

import argparse
from pathlib import Path

from src.attacks.registry import generate_attack_dataset


def _parser() -> argparse.ArgumentParser:
    attack_ids = [
        "scam_induced_push",
        "mule_network",
        "card_testing_probe",
        "adversarial_evasion",
        "first_party_dispute",
        "stealth_mandate",
        "synthetic_merchant",
        "transaction_laundering",
        "credential_takeover",
        "synthetic_identity_bustout",
        "subthreshold_fragmentation",
        "agentic_injection",
        "insider_abuse",
    ]
    parser = argparse.ArgumentParser(description="Generate a synthetic Stage 3/4 attack scenario layered on the Stage 2 graph dataset")
    parser.add_argument("--attack", required=True, choices=attack_ids)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--intensity", choices=["LOW", "MEDIUM", "HIGH"], default="MEDIUM")
    parser.add_argument("--no-clean", action="store_true", help="do not remove the output directory before writing")
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = generate_attack_dataset(
        args.attack,
        seed=args.seed,
        baseline_dir=args.baseline_dir,
        intensity=args.intensity,
        output_dir=args.output_dir,
        clean=not args.no_clean,
    )
    print(
        "Attack dataset written "
        f"attack_id={args.attack} "
        f"campaign_id={result.campaign.campaign_id} "
        f"n_transactions={len(result.transactions)} "
        f"n_labels={len(result.labels)}"
    )


if __name__ == "__main__":
    main()
