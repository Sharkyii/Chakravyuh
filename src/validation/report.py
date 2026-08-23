"""Assemble marginals.py's comparisons into a markdown validation report with
plots. Written to `data/generated/validation/` (gitignored -- only this code
and the small `data/reference/*.json` files it compares against are
committed).

Run via `make validate` or `python -m src.validation.report`.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.dataset.loader import load_dataset
from src.validation.marginals import (
    DEFAULT_REFERENCE_DIR,
    Finding,
    MarginalsResult,
    compute_marginals,
    run_all_comparisons,
)

DEFAULT_INPUT_DIR = Path("data/generated/stage2")
DEFAULT_OUTPUT_DIR = Path("data/generated/validation")

# Plot sampling cap: exact summary statistics in marginals.py always run over
# the full dataset; only the plotted point clouds/histograms below this size
# are subsampled (deterministically) to keep PNG rendering fast at 5-10M rows.
PLOT_SAMPLE_SIZE = 250_000
PLOT_SAMPLE_SEED = 42

# Palette lifted from this repo's dataviz skill reference palette (validated
# categorical order; blue is the sequential default hue). Kept as plain hex,
# not a theme system, since this report is a static file for the deck.
_INK = "#0b0b0b"
_INK_SECONDARY = "#52514e"
_INK_MUTED = "#898781"
_GRID = "#e1e0d9"
_AXIS = "#c3c2b7"
_SURFACE = "#fcfcfb"
_SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#4a3aa7"]


def _style_axes(ax) -> None:
    ax.set_facecolor(_SURFACE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(_AXIS)
    ax.spines["bottom"].set_color(_AXIS)
    ax.tick_params(colors=_INK_SECONDARY, labelsize=9)
    ax.grid(axis="y", color=_GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.title.set_color(_INK)
    ax.xaxis.label.set_color(_INK_SECONDARY)
    ax.yaxis.label.set_color(_INK_SECONDARY)


def _sample(values: list[Any], n: int = PLOT_SAMPLE_SIZE) -> list[Any]:
    if len(values) <= n:
        return values
    rng = random.Random(PLOT_SAMPLE_SEED)
    return rng.sample(values, n)


def _savefig(fig, path: Path) -> str:
    fig.savefig(path, dpi=130, bbox_inches="tight", facecolor=_SURFACE)
    plt.close(fig)
    return path.name


def plot_amount_distribution(transactions: list[dict[str, Any]], plots_dir: Path) -> str:
    amounts = _sample([float(t["amount"]) for t in transactions])
    log_amounts = [math.log10(a) for a in amounts if a > 0]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(log_amounts, bins=60, color=_SERIES[0], edgecolor=_SURFACE, linewidth=0.3, zorder=2)
    ax.set_xlabel("log10(amount, INR)")
    ax.set_ylabel("transaction count")
    ax.set_title("Overall amount distribution (log scale)")
    _style_axes(ax)
    return _savefig(fig, plots_dir / "amount_distribution.png")


def plot_amount_by_mcc(transactions: list[dict[str, Any]], plots_dir: Path, top_n: int = 10) -> str:
    by_mcc: dict[int, list[float]] = defaultdict(list)
    for t in transactions:
        mcc = t.get("mcc")
        if mcc is not None:
            by_mcc[int(mcc)].append(float(t["amount"]))
    top_mccs = [
        mcc for mcc, _ in Counter({m: len(v) for m, v in by_mcc.items()}).most_common(top_n)
    ]
    data = [_sample(by_mcc[mcc], n=20_000) for mcc in top_mccs]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.boxplot(
        data,
        tick_labels=[str(m) for m in top_mccs],
        showfliers=False,
        patch_artist=True,
        medianprops={"color": _INK},
        boxprops={"facecolor": _SERIES[0], "edgecolor": _INK_SECONDARY, "linewidth": 0.8},
        whiskerprops={"color": _INK_SECONDARY},
        capprops={"color": _INK_SECONDARY},
    )
    ax.set_yscale("log")
    ax.set_xlabel("MCC (top 10 by transaction count)")
    ax.set_ylabel("amount, INR (log scale)")
    ax.set_title("Amount distribution per MCC")
    _style_axes(ax)
    fig.autofmt_xdate(rotation=45)
    return _savefig(fig, plots_dir / "amount_by_mcc.png")


def plot_inter_arrival(transactions: list[dict[str, Any]], plots_dir: Path) -> str:
    by_payer: dict[str, list] = defaultdict(list)
    for t in transactions:
        by_payer[t["payer_id"]].append(t["timestamp"])
    gaps: list[float] = []
    for timestamps in by_payer.values():
        timestamps.sort()
        for a, b in zip(timestamps, timestamps[1:]):
            gaps.append((b - a).total_seconds())
    gaps = _sample(gaps)
    log_gaps = [math.log10(g) for g in gaps if g > 0]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(log_gaps, bins=60, color=_SERIES[2], edgecolor=_SURFACE, linewidth=0.3, zorder=2)
    ax.set_xlabel("log10(inter-arrival time, seconds)")
    ax.set_ylabel("count")
    ax.set_title("Per-payer inter-arrival time (consecutive transactions)")
    _style_axes(ax)
    return _savefig(fig, plots_dir / "inter_arrival_time.png")


def plot_transactions_per_party(transactions: list[dict[str, Any]], plots_dir: Path) -> str:
    counts = list(Counter(t["payer_id"] for t in transactions).values())
    counts = _sample(counts)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(counts, bins=50, color=_SERIES[3], edgecolor=_SURFACE, linewidth=0.3, zorder=2)
    ax.set_xlabel("transactions per party (12-week window)")
    ax.set_ylabel("party count")
    ax.set_title("Transactions-per-party distribution")
    _style_axes(ax)
    return _savefig(fig, plots_dir / "transactions_per_party.png")


def plot_temporal_patterns(temporal: dict[str, dict[int, float]], plots_dir: Path) -> str:
    hour_hist = temporal.get("hour_of_day", {})
    dow_hist = temporal.get("day_of_week", {})
    dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    ax1.bar(range(24), [hour_hist.get(h, 0.0) for h in range(24)], color=_SERIES[0], zorder=2)
    ax1.set_xlabel("hour of day (IST)")
    ax1.set_ylabel("fraction of transactions")
    ax1.set_title("Hour-of-day")
    _style_axes(ax1)

    ax2.bar(range(7), [dow_hist.get(d, 0.0) for d in range(7)], color=_SERIES[1], zorder=2)
    ax2.set_xticks(range(7))
    ax2.set_xticklabels(dow_labels)
    ax2.set_ylabel("fraction of transactions")
    ax2.set_title("Day-of-week")
    _style_axes(ax2)

    fig.tight_layout()
    return _savefig(fig, plots_dir / "temporal_patterns.png")


def plot_graph_degree(graph_edges: list[dict[str, Any]], plots_dir: Path) -> str:
    out_degree: dict[str, int] = {}
    in_degree: dict[str, int] = {}
    for e in graph_edges:
        out_degree[e["src_party_id"]] = e["src_out_degree"]
        in_degree[e["dst_party_id"]] = e["dst_in_degree"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    ax1.hist(
        list(out_degree.values()),
        bins=40,
        color=_SERIES[4],
        edgecolor=_SURFACE,
        linewidth=0.3,
        zorder=2,
    )
    ax1.set_yscale("log")
    ax1.set_xlabel("out-degree (distinct payees)")
    ax1.set_ylabel("party count (log scale)")
    ax1.set_title("Out-degree distribution")
    _style_axes(ax1)

    ax2.hist(
        list(in_degree.values()),
        bins=40,
        color=_SERIES[5],
        edgecolor=_SURFACE,
        linewidth=0.3,
        zorder=2,
    )
    ax2.set_yscale("log")
    ax2.set_xlabel("in-degree (distinct payers)")
    ax2.set_ylabel("party count (log scale)")
    ax2.set_title("In-degree distribution")
    _style_axes(ax2)

    fig.tight_layout()
    return _savefig(fig, plots_dir / "graph_degree_distribution.png")


def generate_all_plots(
    transactions: list[dict[str, Any]],
    graph_edges: list[dict[str, Any]],
    temporal: dict[str, Any],
    plots_dir: Path,
) -> dict[str, str]:
    """Render every plot the report links to; return {logical_name: filename}."""
    plots_dir.mkdir(parents=True, exist_ok=True)
    return {
        "amount_distribution": plot_amount_distribution(transactions, plots_dir),
        "amount_by_mcc": plot_amount_by_mcc(transactions, plots_dir),
        "inter_arrival_time": plot_inter_arrival(transactions, plots_dir),
        "transactions_per_party": plot_transactions_per_party(transactions, plots_dir),
        "temporal_patterns": plot_temporal_patterns(temporal, plots_dir),
        "graph_degree_distribution": plot_graph_degree(graph_edges, plots_dir),
    }


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, dict):
        return "; ".join(f"{k}={_fmt(v)}" for k, v in value.items())
    return str(value)


def _findings_table(findings: list[Finding]) -> str:
    lines = [
        "| Metric | Generated | Reference | Reference dataset | Confidence | Note |",
        "|---|---|---|---|---|---|",
    ]
    for f in findings:
        lines.append(
            "| {metric} | {gen} | {ref} | {ds} | {conf} | {note} |".format(
                metric=f.metric,
                gen=_fmt(f.generated_value),
                ref=_fmt(f.reference_value)
                if f.reference_value is not None
                else "*no numeric reference published*",
                ds=f.reference_dataset or "-",
                conf=f.reference_confidence or "n/a",
                note=f.note.replace("\n", " "),
            )
        )
    return "\n".join(lines)


def render_markdown_report(
    result: MarginalsResult,
    findings: list[Finding],
    plots: dict[str, str],
    manifest: dict[str, Any],
    output_dir: Path,
) -> str:
    """Build the markdown report body (does not write it -- see write_report)."""
    by_area: dict[str, list[Finding]] = {}
    for f in findings:
        by_area.setdefault(f.area, []).append(f)

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines: list[str] = [
        "# Legitimate dataset fidelity validation",
        "",
        f"Generated {generated_at}. Source dataset: `{manifest.get('source_dir', manifest.get('dataset_version', 'unknown'))}`, "
        f"seed={manifest.get('seed')}, {result.n_transactions:,} transactions.",
        "",
        "Compares the generated Stage 1/2 legitimate payment dataset's marginal "
        "distributions against hand-authored reference statistics from four "
        "public payments/fraud datasets (IEEE-CIS, PaySim, BankSim, ULB Credit "
        "Card Fraud -- see `data/reference/README.md` for full citations and, "
        "importantly, for what each dataset genuinely cannot inform). Per the "
        "brief, fidelity is judged on this background traffic, not the attacks.",
        "",
        "**How to read this report**: not every metric has a numeric reference "
        "-- several rows say so explicitly rather than compare against an "
        "invented number. Where currencies/populations differ from the "
        "reference datasets, comparisons use scale-invariant ratios (CV, "
        "percentile ratios, Gini) rather than absolute values.",
        "",
        "## 1. Amount distribution (overall and per MCC)",
        "",
        f"![Amount distribution](plots/{plots['amount_distribution']})",
        "",
        f"![Amount by MCC](plots/{plots['amount_by_mcc']})",
        "",
        _findings_table(
            by_area.get("amount_distribution", []) + by_area.get("amount_distribution_per_mcc", [])
        ),
        "",
        "## 2. Inter-arrival time distribution",
        "",
        f"![Inter-arrival time](plots/{plots['inter_arrival_time']})",
        "",
        _findings_table(by_area.get("inter_arrival_time", [])),
        "",
        "## 3. Categorical cardinality (merchants, MCCs, devices per party)",
        "",
        _findings_table(by_area.get("categorical_cardinality", [])),
        "",
        "## 4. Transactions-per-party distribution",
        "",
        f"![Transactions per party](plots/{plots['transactions_per_party']})",
        "",
        _findings_table(by_area.get("transactions_per_party", [])),
        "",
        "## 5. Temporal patterns (hour-of-day, day-of-week)",
        "",
        f"![Temporal patterns](plots/{plots['temporal_patterns']})",
        "",
        _findings_table(by_area.get("temporal_patterns", [])),
        "",
        "## 6. Graph degree distribution",
        "",
        f"![Graph degree distribution](plots/{plots['graph_degree_distribution']})",
        "",
        _findings_table(by_area.get("graph_degree_distribution", [])),
        "",
        "## Reference coverage, stated plainly",
        "",
        "See `data/reference/README.md` for the full per-dataset breakdown of "
        "what is and is not usable. In short: BankSim's `category` field is the "
        "only genuine MCC analog among the four; ULB is PCA-anonymized down to "
        "just Time and Amount; none of the four publish a graph/network summary "
        "or a per-transaction timestamp series, so inter-arrival time and graph "
        "degree distribution are validated qualitatively, not against a cited "
        "number.",
    ]
    return "\n".join(lines)


def write_report(
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    reference_dir: Path = DEFAULT_REFERENCE_DIR,
) -> Path:
    """Load the generated dataset, compute marginals, compare to references,
    render plots, and write the markdown report. Returns the report path."""
    dataset = load_dataset(input_dir)
    transactions = dataset.transactions
    graph_edges = dataset.graph_edges

    result = compute_marginals(transactions, graph_edges)
    findings = run_all_comparisons(result, reference_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = output_dir / "plots"
    plots = generate_all_plots(transactions, graph_edges, result.temporal, plots_dir)

    report_md = render_markdown_report(result, findings, plots, dataset.manifest, output_dir)
    report_path = output_dir / "report.md"
    report_path.write_text(report_md, encoding="utf-8")

    findings_json = [
        {
            "area": f.area,
            "metric": f.metric,
            "generated_value": f.generated_value,
            "reference_value": f.reference_value,
            "reference_dataset": f.reference_dataset,
            "reference_confidence": f.reference_confidence,
            "reference_source": f.reference_source,
            "note": f.note,
        }
        for f in findings
    ]
    (output_dir / "findings.json").write_text(
        json.dumps(findings_json, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return report_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the legitimate-dataset fidelity validation report"
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--reference-dir", type=Path, default=DEFAULT_REFERENCE_DIR)
    return parser


def main() -> None:
    args = _parser().parse_args()
    path = write_report(args.input_dir, args.output_dir, args.reference_dir)
    print(f"Validation report written to {path}")


if __name__ == "__main__":
    main()
