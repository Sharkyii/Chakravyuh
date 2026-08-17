"""Stage 1 dataset writer and CLI for the legitimate payment world."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import fields
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from src.generators import calibration as cal
from src.generators.legitimate import LegitimateDataset, generate_legitimate_transactions
from src.generators.population import PopulationBundle, generate_population
from src.schema import TABLE_ARROW_SCHEMAS
from src.validation.legitimate import ValidationReport, validate_legitimate_dataset

DATASET_VERSION = "stage1-legitimate-v1"
DEFAULT_OUTPUT_DIR = Path("data/generated/stage1")


def _row_dict(row: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in fields(row):
        value = getattr(row, field.name)
        out[field.name] = value.value if hasattr(value, "value") else value
    return out


def _write_table(path: Path, table_name: str, rows: list[Any]) -> None:
    table = pa.Table.from_pylist([_row_dict(r) for r in rows], schema=TABLE_ARROW_SCHEMAS[table_name])
    pq.write_table(table, path)


def _empty_table(path: Path, table_name: str) -> None:
    pq.write_table(pa.Table.from_pylist([], schema=TABLE_ARROW_SCHEMAS[table_name]), path)


def _manifest(seed: int, population: PopulationBundle, dataset: LegitimateDataset) -> dict[str, Any]:
    return {
        "dataset_version": DATASET_VERSION,
        "seed": seed,
        "simulation_start": cal.SIM_START.isoformat(),
        "simulation_end": cal.SIM_END.isoformat(),
        "simulation_weeks": cal.SIM_WEEKS,
        "n_consumer_parties": len(population.parties),
        "n_merchants": len(population.merchants),
        "n_devices": len(population.devices),
        "n_transactions": len(dataset.transactions),
        "generator": "src.generators.legitimate.generate_legitimate_transactions",
        "notes": "Stage 1 legitimate baseline only; labels are separate ground truth.",
    }


def write_legitimate_dataset(
    output_dir: Path,
    seed: int,
    population: PopulationBundle,
    dataset: LegitimateDataset,
    report: ValidationReport,
    *,
    clean: bool = True,
) -> None:
    """Write Stage 1 tables, manifest and validation report to Parquet/JSON."""
    from src.dataset.loader import clear_dataset_cache
    clear_dataset_cache(output_dir)

    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_table(output_dir / "parties.parquet", "parties", population.all_party_rows())
    _write_table(output_dir / "devices.parquet", "devices", population.devices)
    _write_table(output_dir / "merchants.parquet", "merchants", population.all_merchant_rows())
    _write_table(output_dir / "transactions.parquet", "transactions", dataset.transactions)
    _write_table(output_dir / "labels.parquet", "labels", dataset.labels)
    _empty_table(output_dir / "mandates.parquet", "mandates")
    _empty_table(output_dir / "disputes.parquet", "disputes")
    _empty_table(output_dir / "graph_edges.parquet", "graph_edges")

    (output_dir / "manifest.json").write_text(
        json.dumps(_manifest(seed, population, dataset), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "validation_report.json").write_text(
        json.dumps({"ok": report.ok, "errors": report.errors, "summary": report.summary}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def generate_stage1_dataset(
    seed: int,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    n_consumers: int | None = None,
    n_merchants: int | None = None,
    clean: bool = True,
) -> ValidationReport:
    """Generate, validate and write the Stage 1 legitimate dataset."""
    original_consumers = cal.N_CONSUMER_PARTIES
    original_merchants = cal.N_MERCHANTS
    try:
        if n_consumers is not None:
            cal.N_CONSUMER_PARTIES = n_consumers
        if n_merchants is not None:
            cal.N_MERCHANTS = n_merchants
        population = generate_population(seed)
    finally:
        cal.N_CONSUMER_PARTIES = original_consumers
        cal.N_MERCHANTS = original_merchants

    dataset = generate_legitimate_transactions(seed, population)
    report = validate_legitimate_dataset(population, dataset)
    if not report.ok:
        raise ValueError("Stage 1 validation failed: " + "; ".join(report.errors[:10]))
    write_legitimate_dataset(output_dir, seed, population, dataset, report, clean=clean)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Stage 1 legitimate payment-world data")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--n-consumers", type=int, default=None)
    parser.add_argument("--n-merchants", type=int, default=None)
    parser.add_argument("--no-clean", action="store_true", help="do not remove output dir before writing")
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = generate_stage1_dataset(
        args.seed,
        args.output_dir,
        n_consumers=args.n_consumers,
        n_merchants=args.n_merchants,
        clean=not args.no_clean,
    )
    summary = report.summary
    print(
        "Stage 1 dataset written "
        f"transactions={summary['n_transactions']} "
        f"parties={summary['n_parties']} "
        f"devices={summary['n_devices']} "
        f"known_device_rate={summary['known_device_rate']:.4f}"
    )


if __name__ == "__main__":
    main()
