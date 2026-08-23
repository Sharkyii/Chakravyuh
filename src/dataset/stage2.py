"""Stage 2 graph/dataset harness CLI."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import fields
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from src.dataset.loader import EXPECTED_TABLES, load_dataset
from src.graph.builder import GraphBuildConfig, build_graph_edges
from src.schema import TABLE_ARROW_SCHEMAS
from src.validation.stage2 import Stage2ValidationReport, validate_stage2_dataset

STAGE2_DATASET_VERSION = "stage2-graph-harness-v1"
DEFAULT_INPUT_DIR = Path("data/generated/stage1")
DEFAULT_OUTPUT_DIR = Path("data/generated/stage2")


def _row_dict(row: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in fields(row):
        value = getattr(row, field.name)
        out[field.name] = value.value if hasattr(value, "value") else value
    return out


def _write_rows(path: Path, table_name: str, rows: list[Any]) -> None:
    pylist = [_row_dict(row) if not isinstance(row, dict) else row for row in rows]
    pq.write_table(pa.Table.from_pylist(pylist, schema=TABLE_ARROW_SCHEMAS[table_name]), path)


def _stage2_manifest(
    source_manifest: dict[str, Any], graph_edges: int, input_dir: Path
) -> dict[str, Any]:
    return {
        "dataset_version": STAGE2_DATASET_VERSION,
        "source_dataset_version": source_manifest.get("dataset_version"),
        "seed": source_manifest.get("seed"),
        "simulation_start": source_manifest.get("simulation_start"),
        "simulation_end": source_manifest.get("simulation_end"),
        "simulation_weeks": source_manifest.get("simulation_weeks"),
        "source_dir": str(input_dir.as_posix()),
        "n_consumer_parties": source_manifest.get("n_consumer_parties"),
        "n_merchants": source_manifest.get("n_merchants"),
        "n_devices": source_manifest.get("n_devices"),
        "n_transactions": source_manifest.get("n_transactions"),
        "n_graph_edges": graph_edges,
        "generator": "src.graph.builder.build_graph_edges",
        "notes": "Stage 2 legitimate baseline with derived full-window graph_edges; no attacks or ML.",
    }


def build_stage2_dataset(
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    clean: bool = True,
) -> Stage2ValidationReport:
    """Read Stage 1 data, derive graph_edges, write and validate Stage 2 output."""
    source = load_dataset(input_dir)
    from src.dataset.loader import clear_dataset_cache

    clear_dataset_cache(output_dir)
    graph_edges = build_graph_edges(source.transactions, GraphBuildConfig())

    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for table_name in EXPECTED_TABLES:
        if table_name == "graph_edges":
            _write_rows(output_dir / "graph_edges.parquet", "graph_edges", graph_edges)
        else:
            shutil.copy2(input_dir / f"{table_name}.parquet", output_dir / f"{table_name}.parquet")

    (output_dir / "manifest.json").write_text(
        json.dumps(
            _stage2_manifest(source.manifest, len(graph_edges), input_dir), indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )

    dataset = load_dataset(output_dir)
    report = validate_stage2_dataset(dataset)
    (output_dir / "validation_report.json").write_text(
        json.dumps(
            {"ok": report.ok, "errors": report.errors, "summary": report.summary},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if not report.ok:
        raise ValueError("Stage 2 validation failed: " + "; ".join(report.errors[:10]))
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Stage 2 graph/dataset harness artifacts")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--no-clean", action="store_true", help="do not remove output dir before writing"
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = build_stage2_dataset(args.input_dir, args.output_dir, clean=not args.no_clean)
    summary = report.summary
    print(
        "Stage 2 dataset written "
        f"transactions={summary['table_row_counts']['transactions']} "
        f"graph_edges={summary['graph_edge_count']} "
        f"train={summary['temporal_split_sizes']['train']} "
        f"validation={summary['temporal_split_sizes']['validation']} "
        f"test={summary['temporal_split_sizes']['test']} "
        f"leakage_ok={summary['leakage_checks']['ok']}"
    )


if __name__ == "__main__":
    main()
