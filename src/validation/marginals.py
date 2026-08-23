"""Compare the generated legitimate dataset's marginal distributions against
the hand-authored reference statistics in `data/reference/` (IEEE-CIS, PaySim,
BankSim, ULB -- see `data/reference/README.md` for what each one can and
cannot inform).

This module only *computes* statistics from the generated dataset and *loads*
the reference files; it does not fetch or store any raw external dataset --
see the project's "no runtime downloads" rule. `src/validation/report.py`
turns this module's output into the markdown report and plots.

Because the reference datasets are denominated in different currencies (USD,
EUR, PaySim's own simulator unit) and cover different populations/time spans
than our INR/India-focused generator, most amount comparisons here are
scale-invariant (ratios, coefficients of variation) rather than value-for-
value. Where no numeric reference exists at all for an area, the comparison
says so explicitly instead of inventing a target -- see each reference file's
`not_usable_for` list.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

DEFAULT_REFERENCE_DIR = Path("data/reference")

REFERENCE_DATASETS: tuple[str, ...] = (
    "ieee_cis",
    "paysim",
    "banksim",
    "ulb_creditcard",
    "general_notes",
)

# Rough MCC -> BankSim `category` analog, used only to compare *relative*
# amount ordering (do our high-frequency, everyday-spend MCCs land at lower
# median amounts than our low-frequency, big-ticket MCCs, matching the shape
# BankSim's category breakdown documents) -- not a claim that an Indian MCC
# and a Spanish BankSim category are the same merchant type. See
# data/reference/banksim.json's `category_distribution_approx` and
# `amount_by_category_shape` for what this is checked against.
MCC_TO_BANKSIM_CATEGORY: dict[int, str] = {
    5411: "es_food",  # grocery/supermarket
    5812: "es_barsandrestaurants",  # restaurants
    5541: "es_transportation",  # fuel/service stations
    5964: "es_home",  # ecommerce marketplace -- no close analog, nearest general-retail bucket
    4900: "es_home",  # utilities -- no analog, nearest general bucket
    5912: "es_health",  # pharmacies
    5651: "es_fashion",  # family clothing
    5999: "es_home",  # misc retail
    4121: "es_transportation",  # taxi / rideshare
    5732: "es_tech",  # electronics
    7011: "es_hotelservices",  # hotels
    5813: "es_barsandrestaurants",  # bars
    8299: "es_otherservices",  # education
    6300: "es_otherservices",  # insurance
    5983: "es_transportation",  # fuel dealers (LPG etc.)
    4814: "es_tech",  # telecom
    5262: "es_home",  # marketplace secondary bucket
}

# BankSim categories the reference file documents as low-frequency/high-amount
# vs high-frequency/low-amount -- used for an ordinal (not absolute) check.
BANKSIM_HIGH_VALUE_CATEGORIES = frozenset({"es_travel", "es_leisure", "es_hotelservices"})
BANKSIM_EVERYDAY_CATEGORIES = frozenset({"es_transportation", "es_food"})


@dataclass(slots=True)
class Finding:
    """One row of the validation report: a statistic computed from the
    generated dataset, alongside whatever reference basis exists for it.

    `reference_confidence` is `None` when no reference dataset publishes
    anything usable for this metric at all -- that is reported honestly
    rather than silently omitted or backed by an invented number.
    """

    area: str
    metric: str
    generated_value: Any
    reference_value: Any | None = None
    reference_dataset: str | None = None
    reference_confidence: str | None = None
    reference_source: str | None = None
    note: str = ""


@dataclass(slots=True)
class MarginalsResult:
    """Computed marginal statistics from one generated dataset."""

    n_transactions: int
    amount_overall: dict[str, float]
    amount_by_mcc: dict[int, dict[str, float]]
    inter_arrival_by_party_s: dict[str, float]
    cardinality: dict[str, Any]
    transactions_per_party: dict[str, float]
    transactions_per_merchant: dict[str, float]
    temporal: dict[str, dict[int, float]]
    graph_degree: dict[str, Any]


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated percentile, `q` in [0, 1], on an already-sorted list."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_values[0]
    idx = q * (n - 1)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return sorted_values[int(idx)]
    frac = idx - lo
    return sorted_values[int(lo)] * (1 - frac) + sorted_values[int(hi)] * frac


def summary_stats(values: Iterable[float]) -> dict[str, float]:
    """Compact, dependency-free summary (count/mean/percentiles/CV) for a
    list of numeric values. Shared by every "distribution" computed below so
    generated-vs-reference comparisons always line up on the same fields."""
    vals = sorted(float(v) for v in values)
    n = len(vals)
    if n == 0:
        return {
            "n": 0,
            "mean": 0.0,
            "median": 0.0,
            "p25": 0.0,
            "p75": 0.0,
            "p90": 0.0,
            "p99": 0.0,
            "min": 0.0,
            "max": 0.0,
            "cv": 0.0,
        }
    mu = sum(vals) / n
    median = _percentile(vals, 0.5)
    variance = sum((v - mu) ** 2 for v in vals) / n
    sd = math.sqrt(variance)
    return {
        "n": n,
        "mean": mu,
        "median": median,
        "p25": _percentile(vals, 0.25),
        "p75": _percentile(vals, 0.75),
        "p90": _percentile(vals, 0.90),
        "p99": _percentile(vals, 0.99),
        "min": vals[0],
        "max": vals[-1],
        "cv": (sd / mu) if mu else 0.0,
        "mean_to_median": (mu / median) if median else 0.0,
        "p75_to_median": (_percentile(vals, 0.75) / median) if median else 0.0,
        "p99_to_median": (_percentile(vals, 0.99) / median) if median else 0.0,
    }


def gini(values: Iterable[float]) -> float:
    """Gini coefficient of inequality (0 = perfectly even, ->1 = maximally
    concentrated). Used for the graph degree distribution, where the
    qualitative reference expectation (see data/reference/general_notes.json)
    is a heavy-tailed, unequal distribution."""
    vals = sorted(float(v) for v in values)
    n = len(vals)
    total = sum(vals)
    if n == 0 or total == 0:
        return 0.0
    weighted_sum = sum((i + 1) * v for i, v in enumerate(vals))
    return (2 * weighted_sum) / (n * total) - (n + 1) / n


def amount_quantiles(amounts: Iterable[Any]) -> dict[str, float]:
    """Summary stats for a collection of transaction amounts (Decimal or float)."""
    return summary_stats(float(a) for a in amounts)


def amount_distribution_by_mcc(transactions: list[dict[str, Any]]) -> dict[int, dict[str, float]]:
    """Amount summary stats grouped by MCC (P2P rows, which carry no MCC, are excluded)."""
    by_mcc: dict[int, list[float]] = defaultdict(list)
    for txn in transactions:
        mcc = txn.get("mcc")
        if mcc is None:
            continue
        by_mcc[int(mcc)].append(float(txn["amount"]))
    return {mcc: amount_quantiles(vals) for mcc, vals in sorted(by_mcc.items())}


def inter_arrival_seconds_by_party(transactions: list[dict[str, Any]]) -> dict[str, float]:
    """Summary stats of inter-arrival gaps (seconds) between consecutive
    transactions of the same payer, pooled across all payers with 2+
    transactions. No reference dataset publishes a comparable distribution
    (see each reference file's `not_usable_for`); this is reported
    descriptively, not benchmarked against an external number."""
    by_payer: dict[str, list] = defaultdict(list)
    for txn in transactions:
        by_payer[txn["payer_id"]].append(txn["timestamp"])
    gaps: list[float] = []
    for timestamps in by_payer.values():
        timestamps.sort()
        for earlier, later in zip(timestamps, timestamps[1:]):
            gaps.append((later - earlier).total_seconds())
    return summary_stats(gaps)


def categorical_cardinality(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Distinct-value counts and per-party device counts."""
    mcc_values = {txn["mcc"] for txn in transactions if txn.get("mcc") is not None}
    merchant_values = {
        txn["merchant_id"] for txn in transactions if txn.get("merchant_id") is not None
    }
    devices_per_party: dict[str, set[str]] = defaultdict(set)
    merchants_per_party: dict[str, set[str]] = defaultdict(set)
    for txn in transactions:
        devices_per_party[txn["payer_id"]].add(txn["device_id"])
        if txn.get("merchant_id") is not None:
            merchants_per_party[txn["payer_id"]].add(txn["merchant_id"])
    return {
        "n_distinct_mcc": len(mcc_values),
        "n_distinct_merchants_transacted": len(merchant_values),
        "devices_per_party": summary_stats(len(v) for v in devices_per_party.values()),
        "distinct_merchants_per_party": summary_stats(len(v) for v in merchants_per_party.values()),
    }


def transactions_per_entity(transactions: list[dict[str, Any]], key: str) -> dict[str, float]:
    """Summary stats of transaction counts grouped by `key` (e.g. payer_id, merchant_id)."""
    counts = Counter(txn[key] for txn in transactions if txn.get(key) is not None)
    return summary_stats(counts.values())


def temporal_patterns(transactions: list[dict[str, Any]]) -> dict[str, dict[int, float]]:
    """Hour-of-day (0-23) and day-of-week (0=Monday..6=Sunday) histograms, as
    fractions of total transaction count."""
    total = len(transactions)
    hour_counts: Counter[int] = Counter()
    dow_counts: Counter[int] = Counter()
    for txn in transactions:
        ts = txn["timestamp"]
        hour_counts[ts.hour] += 1
        dow_counts[ts.weekday()] += 1
    return {
        "hour_of_day": {h: hour_counts.get(h, 0) / total for h in range(24)} if total else {},
        "day_of_week": {d: dow_counts.get(d, 0) / total for d in range(7)} if total else {},
    }


def graph_degree_distribution(graph_edges: list[dict[str, Any]]) -> dict[str, Any]:
    """Summary stats + Gini coefficient of the party out/in-degree distribution.

    `graph_edges` rows already carry `src_out_degree`/`dst_in_degree` per edge
    (see src/graph/builder.py); this collapses that to one value per party.
    """
    out_degree: dict[str, int] = {}
    in_degree: dict[str, int] = {}
    for edge in graph_edges:
        out_degree[edge["src_party_id"]] = edge["src_out_degree"]
        in_degree[edge["dst_party_id"]] = edge["dst_in_degree"]
    out_vals = list(out_degree.values())
    in_vals = list(in_degree.values())
    return {
        "src_out_degree": summary_stats(out_vals),
        "dst_in_degree": summary_stats(in_vals),
        "gini_src_out_degree": gini(out_vals),
        "gini_dst_in_degree": gini(in_vals),
        "n_parties_with_out_edges": len(out_vals),
        "n_parties_with_in_edges": len(in_vals),
    }


def compute_marginals(
    transactions: list[dict[str, Any]], graph_edges: list[dict[str, Any]]
) -> MarginalsResult:
    """Compute every statistic the validation report needs from one dataset."""
    return MarginalsResult(
        n_transactions=len(transactions),
        amount_overall=amount_quantiles(txn["amount"] for txn in transactions),
        amount_by_mcc=amount_distribution_by_mcc(transactions),
        inter_arrival_by_party_s=inter_arrival_seconds_by_party(transactions),
        cardinality=categorical_cardinality(transactions),
        transactions_per_party=transactions_per_entity(transactions, "payer_id"),
        transactions_per_merchant=transactions_per_entity(transactions, "merchant_id"),
        temporal=temporal_patterns(transactions),
        graph_degree=graph_degree_distribution(graph_edges),
    )


def load_reference(name: str, reference_dir: Path = DEFAULT_REFERENCE_DIR) -> dict[str, Any]:
    """Load one hand-authored reference-statistics file by dataset name (no extension)."""
    path = Path(reference_dir) / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_all_references(reference_dir: Path = DEFAULT_REFERENCE_DIR) -> dict[str, dict[str, Any]]:
    """Load every reference file listed in REFERENCE_DATASETS."""
    return {name: load_reference(name, reference_dir) for name in REFERENCE_DATASETS}


def compare_amount_distribution(
    result: MarginalsResult, references: dict[str, Any]
) -> list[Finding]:
    """Overall amount shape vs ULB (numeric ratio comparison) and IEEE-CIS/
    PaySim/BankSim (qualitative "is it right-skewed" comparison), plus a
    per-MCC ordinal check against BankSim's category shape."""
    findings: list[Finding] = []
    overall = result.amount_overall

    ulb = references["ulb_creditcard"]["stats"]["amount_summary"]
    ulb_ratios = {
        "mean_to_median": ulb["value"]["mean"] / ulb["value"]["median"],
        "p75_to_median": ulb["value"]["p75"] / ulb["value"]["median"],
    }
    findings.append(
        Finding(
            area="amount_distribution",
            metric="mean_to_median ratio (scale-invariant right-skew check)",
            generated_value=round(overall["mean_to_median"], 3),
            reference_value=round(ulb_ratios["mean_to_median"], 3),
            reference_dataset="ulb_creditcard",
            reference_confidence=ulb["confidence"],
            reference_source=ulb["source"],
            note=(
                "Both should be well above 1.0 for a right-skewed amount distribution "
                "(mean pulled above the median by a long tail of large transactions); "
                "currencies differ (INR vs EUR) so only the ratio, not the absolute values, is compared."
            ),
        )
    )
    findings.append(
        Finding(
            area="amount_distribution",
            metric="p75_to_median ratio (scale-invariant right-skew check)",
            generated_value=round(overall["p75_to_median"], 3),
            reference_value=round(ulb_ratios["p75_to_median"], 3),
            reference_dataset="ulb_creditcard",
            reference_confidence=ulb["confidence"],
            reference_source=ulb["source"],
            note="Same scale-invariant logic as mean_to_median, using the 75th percentile instead of the mean.",
        )
    )

    for dataset_name in ("ieee_cis", "paysim"):
        shape = references[dataset_name]["stats"].get("amount_shape") or references[dataset_name][
            "stats"
        ].get("transaction_amt_shape")
        findings.append(
            Finding(
                area="amount_distribution",
                metric="qualitative shape (right-skewed?)",
                generated_value=f"CV={overall['cv']:.2f}, mean/median={overall['mean_to_median']:.2f}",
                reference_value=shape["value"] if shape else None,
                reference_dataset=dataset_name,
                reference_confidence=shape["confidence"] if shape else None,
                reference_source=shape["source"] if shape else None,
                note="No numeric percentile table is published for this dataset; compared qualitatively only.",
            )
        )

    for mcc, stats in result.amount_by_mcc.items():
        category = MCC_TO_BANKSIM_CATEGORY.get(mcc)
        if category is None:
            continue
        expected_tier = (
            "high_value"
            if category in BANKSIM_HIGH_VALUE_CATEGORIES
            else "everyday"
            if category in BANKSIM_EVERYDAY_CATEGORIES
            else None
        )
        if expected_tier is None:
            continue
        findings.append(
            Finding(
                area="amount_distribution_per_mcc",
                metric=f"MCC {mcc} median amount, mapped to BankSim category {category!r} ({expected_tier} tier)",
                generated_value=round(stats["median"], 2),
                reference_value=expected_tier,
                reference_dataset="banksim",
                reference_confidence=references["banksim"]["stats"]["amount_by_category_shape"][
                    "confidence"
                ],
                reference_source=references["banksim"]["stats"]["amount_by_category_shape"][
                    "source"
                ],
                note=(
                    "Ordinal check only: BankSim documents everyday categories (transportation, food) as "
                    "low-amount and high-value categories (travel, leisure, hotels) as high-amount. "
                    "The MCC-to-category mapping is a reasoned analogy, not a claimed equivalence."
                ),
            )
        )
    return findings


def compare_inter_arrival(result: MarginalsResult, references: dict[str, Any]) -> list[Finding]:
    """No reference dataset publishes a comparable inter-arrival distribution
    (see each file's `not_usable_for`); report the generated statistic
    descriptively and say so explicitly rather than fabricate a target."""
    return [
        Finding(
            area="inter_arrival_time",
            metric="per-payer inter-arrival time (seconds), pooled",
            generated_value={
                k: round(v, 1) if isinstance(v, float) else v
                for k, v in result.inter_arrival_by_party_s.items()
            },
            reference_value=None,
            reference_dataset=None,
            reference_confidence=None,
            reference_source=None,
            note=(
                "None of IEEE-CIS/PaySim/BankSim/ULB publish per-row timestamps or a summarized "
                "inter-arrival distribution (see data/reference/README.md's coverage-gaps section). "
                "Reported descriptively for the walkthrough deck; not benchmarked against an external number."
            ),
        )
    ]


def compare_cardinality(result: MarginalsResult, references: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    paysim_types = references["paysim"]["stats"]["type_distribution_approx"]
    findings.append(
        Finding(
            area="categorical_cardinality",
            metric="n_distinct_mcc",
            generated_value=result.cardinality["n_distinct_mcc"],
            reference_value=len(paysim_types["value"]),
            reference_dataset="paysim",
            reference_confidence="reasoned_approximation",
            reference_source="PaySim's `type` field has 5 values; not an MCC, only comparable as 'a small closed categorical vocabulary'.",
            note="PaySim's `type` (5 values) is a transaction-type taxonomy, not an MCC; compared only as an order-of-magnitude cardinality sanity check.",
        )
    )
    banksim_categories = references["banksim"]["stats"]["category_distribution_approx"]
    findings.append(
        Finding(
            area="categorical_cardinality",
            metric="n_distinct_mcc",
            generated_value=result.cardinality["n_distinct_mcc"],
            reference_value=len(banksim_categories["value"]),
            reference_dataset="banksim",
            reference_confidence=banksim_categories["confidence"],
            reference_source=banksim_categories["source"],
            note="BankSim's `category` (15 values) is the closest MCC analog of the four reference datasets.",
        )
    )
    findings.append(
        Finding(
            area="categorical_cardinality",
            metric="devices_per_party",
            generated_value=result.cardinality["devices_per_party"],
            reference_value=None,
            reference_dataset=None,
            reference_confidence=None,
            reference_source=None,
            note="No reference dataset publishes a device-per-customer field; reported descriptively only.",
        )
    )
    return findings


def compare_transactions_per_party(
    result: MarginalsResult, references: dict[str, Any]
) -> list[Finding]:
    return [
        Finding(
            area="transactions_per_party",
            metric="transactions per payer",
            generated_value=result.transactions_per_party,
            reference_value=None,
            reference_dataset=None,
            reference_confidence=None,
            reference_source=None,
            note=(
                "None of the four reference datasets publish a trustworthy per-customer transaction-count "
                "distribution (IEEE-CIS's card1-based UID is an unofficial reconstruction; BankSim's customer "
                "population size was not independently reconfirmed in this pass -- see each reference file's "
                "applicability_notes). Reported descriptively only."
            ),
        )
    ]


def compare_temporal_patterns(result: MarginalsResult, references: dict[str, Any]) -> list[Finding]:
    general = references["general_notes"]["temporal_patterns"]
    hour_hist = result.temporal.get("hour_of_day", {})
    dow_hist = result.temporal.get("day_of_week", {})
    hour_values = list(hour_hist.values())
    is_nonuniform_hour = (
        (max(hour_values) - min(hour_values)) > (0.5 / 24) if hour_values else False
    )
    dow_values = list(dow_hist.values())
    is_nonuniform_dow = (max(dow_values) - min(dow_values)) > (0.5 / 7) if dow_values else False
    return [
        Finding(
            area="temporal_patterns",
            metric="hour-of-day histogram is non-uniform",
            generated_value=is_nonuniform_hour,
            reference_value=True,
            reference_dataset="general_notes",
            reference_confidence=general["confidence"],
            reference_source=general["source"],
            note=general["qualitative_expectation"],
        ),
        Finding(
            area="temporal_patterns",
            metric="day-of-week histogram is non-uniform",
            generated_value=is_nonuniform_dow,
            reference_value=True,
            reference_dataset="general_notes",
            reference_confidence=general["confidence"],
            reference_source=general["source"],
            note=general["qualitative_expectation"],
        ),
    ]


def compare_graph_degree(result: MarginalsResult, references: dict[str, Any]) -> list[Finding]:
    general = references["general_notes"]["graph_degree_distribution"]
    findings: list[Finding] = []
    for direction, gini_key in (("out", "gini_src_out_degree"), ("in", "gini_dst_in_degree")):
        findings.append(
            Finding(
                area="graph_degree_distribution",
                metric=f"Gini coefficient of {direction}-degree",
                generated_value=round(result.graph_degree[gini_key], 3),
                reference_value="materially > 0 (heavy-tailed, not close to 0/uniform)",
                reference_dataset="general_notes",
                reference_confidence=general["confidence"],
                reference_source=general["source"],
                note=general["qualitative_expectation"],
            )
        )
    return findings


def run_all_comparisons(
    result: MarginalsResult, reference_dir: Path = DEFAULT_REFERENCE_DIR
) -> list[Finding]:
    """Run every comparison area and return the combined findings list, in
    the order the six required report sections are listed in the brief."""
    references = load_all_references(reference_dir)
    findings: list[Finding] = []
    findings += compare_amount_distribution(result, references)
    findings += compare_inter_arrival(result, references)
    findings += compare_cardinality(result, references)
    findings += compare_transactions_per_party(result, references)
    findings += compare_temporal_patterns(result, references)
    findings += compare_graph_degree(result, references)
    return findings
