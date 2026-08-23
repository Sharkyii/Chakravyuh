"""Integration test for src/validation/report.py: runs the full write_report
pipeline against a small (fast) generated dataset and the real, committed
data/reference/*.json files -- not mocked, since those files are small and
this is exactly what `make validate` runs end to end."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.dataset.stage2 import build_stage2_dataset
from src.generators.dataset import generate_stage1_dataset
from src.validation.marginals import DEFAULT_REFERENCE_DIR
from src.validation.report import write_report


@pytest.fixture(scope="module")
def small_stage2_dir(tmp_path_factory) -> Path:
    tmp_path = tmp_path_factory.mktemp("validation_report_data")
    stage1 = tmp_path / "stage1"
    stage2 = tmp_path / "stage2"
    generate_stage1_dataset(seed=42, output_dir=stage1, n_consumers=150, n_merchants=20)
    report = build_stage2_dataset(input_dir=stage1, output_dir=stage2)
    assert report.ok
    return stage2


def test_write_report_produces_markdown_and_plots(tmp_path: Path, small_stage2_dir: Path) -> None:
    output_dir = tmp_path / "validation"
    report_path = write_report(
        input_dir=small_stage2_dir, output_dir=output_dir, reference_dir=DEFAULT_REFERENCE_DIR
    )

    assert report_path == output_dir / "report.md"
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    for heading in [
        "Amount distribution",
        "Inter-arrival time distribution",
        "Categorical cardinality",
        "Transactions-per-party distribution",
        "Temporal patterns",
        "Graph degree distribution",
    ]:
        assert heading in content

    plots_dir = output_dir / "plots"
    expected_plots = [
        "amount_distribution.png",
        "amount_by_mcc.png",
        "inter_arrival_time.png",
        "transactions_per_party.png",
        "temporal_patterns.png",
        "graph_degree_distribution.png",
    ]
    for name in expected_plots:
        path = plots_dir / name
        assert path.exists()
        assert path.stat().st_size > 0

    findings_path = output_dir / "findings.json"
    assert findings_path.exists()


def test_write_report_findings_json_is_valid(tmp_path: Path, small_stage2_dir: Path) -> None:
    import json

    output_dir = tmp_path / "validation2"
    write_report(
        input_dir=small_stage2_dir, output_dir=output_dir, reference_dir=DEFAULT_REFERENCE_DIR
    )
    findings = json.loads((output_dir / "findings.json").read_text(encoding="utf-8"))
    assert isinstance(findings, list)
    assert len(findings) > 0
    for entry in findings:
        assert "area" in entry
        assert "metric" in entry
        assert "generated_value" in entry
