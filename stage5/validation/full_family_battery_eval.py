"""Full per-family, per-intensity, multi-seed battery test of the actually-
deployed model.

Unlike cross_generation_eval.py (which only re-checks the 3 curriculum
generations' adversarial attacks), this generates every one of the 16
grounded attack families at LOW/MEDIUM/HIGH intensity, several seeds each,
via the real AttackGenerator classes -- not hand-picked single rows -- and
scores them through the real sequential BehavioralFeatureTracker, matching
training's exact feature pipeline. This is the test that actually answers
"is the deployed model good," as opposed to "does it pass its own held-out
test split" (evaluate_deployed_model.py) or "did this retrain regress an
already-solved evasion pattern" (cross_generation_eval.py).

Requires the baseline stage2 dataset to already be generated on disk (not
committed to git -- run stage5's data generation pipeline first if missing).
Run manually after any retrain that changes features or promotes a new model;
not part of the CI pipeline since it depends on that uncommitted dataset.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import pandas as pd
import joblib

from src.dataset.loader import load_dataset
from src.attacks.registry import build_attack_generator
from src.attacks.framework import AttackIntensity
from stage5.config.settings import ATTACK_FAMILIES, ALL_FEATURES, MODELS_DIR, STAGE5_DATA_DIR
from stage5.features.feature_engineering import BehavioralFeatureTracker

FAMILIES = [f["attack_id"] for f in ATTACK_FAMILIES]
INTENSITIES = [AttackIntensity.LOW, AttackIntensity.MEDIUM, AttackIntensity.HIGH]
N_SEEDS_PER_CELL = 10
N_LEGIT_SAMPLE = 5000
BASELINE_STAGE2_DIR = STAGE5_DATA_DIR / "baseline" / "stage2"
REPORT_PATH = Path(__file__).resolve().parent / "full_family_battery_results.json"


def _row_to_dict(r):
    if isinstance(r, dict):
        return dict(r)
    from dataclasses import fields
    out = {}
    for f in fields(r):
        v = getattr(r, f.name)
        out[f.name] = v.value if hasattr(v, "value") else v
    return out


def generate_all_campaigns(baseline):
    all_rows, all_meta = [], []
    for family in FAMILIES:
        gen = build_attack_generator(family)
        for intensity in INTENSITIES:
            for i in range(N_SEEDS_PER_CELL):
                seed = hash((family, intensity.value, i)) % 900000 + 100000
                try:
                    _campaign, rows, _labels = gen.generate(baseline, seed=seed, intensity=intensity)
                except Exception as e:
                    print(f"  SKIP {family}/{intensity.value}/seed={seed}: {e}", flush=True)
                    continue
                for r in rows:
                    all_rows.append(r)
                    all_meta.append({"family": family, "intensity": intensity.value, "seed": seed})
    return all_rows, all_meta


def build_scored_dataframe(baseline, all_rows, all_meta) -> pd.DataFrame:
    # Sample of pure legit baseline rows for false-positive-rate measurement.
    rng = np.random.default_rng(42)
    legit_txns = list(baseline.transactions)
    legit_sample_idx = rng.choice(len(legit_txns), size=min(N_LEGIT_SAMPLE, len(legit_txns)), replace=False)
    legit_sample = [legit_txns[i] for i in legit_sample_idx]
    print(f"Legit FPR sample: {len(legit_sample)} rows", flush=True)

    combined = [_row_to_dict(r) for r in legit_sample] + [_row_to_dict(r) for r in all_rows]
    combined_meta = [{"family": "__legit__", "intensity": "", "seed": 0}] * len(legit_sample) + all_meta

    df = pd.DataFrame(combined)
    # Attach meta as real columns BEFORE sorting so they travel with their
    # rows through the chronological sort below (looking them up by post-sort
    # positional index instead would silently misalign family <-> prediction).
    df["__family__"] = [m["family"] for m in combined_meta]
    df["__intensity__"] = [m["intensity"] for m in combined_meta]
    df["__seed__"] = [m["seed"] for m in combined_meta]
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(by=["timestamp"]).reset_index(drop=True)

    print("Computing behavioral features sequentially...", flush=True)
    tracker = BehavioralFeatureTracker()
    beh_list = []
    for _idx, row in df.iterrows():
        beh = tracker.get_and_update(
            payer_id=row["payer_id"], ts=row["timestamp"], amount=float(row["amount"]),
            merchant_id=row.get("payee_id", ""), device_id=row.get("device_id", ""),
            ip_asn=row.get("ip_asn", ""), rail=row.get("rail", ""), channel=row.get("channel", ""),
            is_agent_initiated=row.get("is_agent_initiated", False),
            beneficiary_first_time=row.get("beneficiary_first_time", True),
            beneficiary_added_ago_s=row.get("beneficiary_added_ago_s", 0.0),
            tpap_app=row.get("tpap_app"), linked_account_id=row.get("linked_account_id"),
        )
        beh_list.append(beh)
    beh_df = pd.DataFrame(beh_list)
    df = pd.concat([df, beh_df], axis=1)

    df["tx_hour"] = df["timestamp"].dt.hour
    df["tx_dayofweek"] = df["timestamp"].dt.dayofweek

    parties_df = pd.DataFrame(baseline.tables["parties"])
    parties_sub = parties_df[["party_id", "account_age_days"]].copy()
    parties_sub["party_id"] = parties_sub["party_id"].astype(str)
    df["payer_id"] = df["payer_id"].astype(str)
    df = df.merge(parties_sub, left_on="payer_id", right_on="party_id", how="left").drop(columns=["party_id"])

    graph_df = pd.DataFrame(baseline.tables["graph_edges"])
    out_deg_map = graph_df.groupby("src_party_id")["src_out_degree"].first().to_dict()
    in_deg_map = graph_df.groupby("dst_party_id")["dst_in_degree"].first().to_dict()
    edge_count_map, edge_value_map, edge_pt_map = {}, {}, {}
    for _, row in graph_df.iterrows():
        key = (str(row["src_party_id"]), str(row["dst_party_id"]))
        edge_count_map[key] = float(row["edge_count"])
        edge_value_map[key] = float(row["edge_value_total"])
        edge_pt_map[key] = bool(row["is_two_hop_passthrough"])

    df["payer_out_degree"] = df["payer_id"].map(out_deg_map).fillna(0.0).astype(float)
    df["payee_in_degree"] = df["payee_id"].map(in_deg_map).fillna(0.0).astype(float)
    counts, values, pts = [], [], []
    for _, row in df.iterrows():
        key = (str(row["payer_id"]), str(row["payee_id"]))
        counts.append(edge_count_map.get(key, 0.0))
        values.append(edge_value_map.get(key, 0.0))
        pts.append(float(edge_pt_map.get(key, False)))
    df["edge_count"] = counts
    df["edge_value_total"] = values
    df["is_two_hop_passthrough"] = pts

    return df


def score(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    print("Scoring with trained model...", flush=True)
    preprocessor = joblib.load(MODELS_DIR / "preprocessor.pkl")
    model = joblib.load(MODELS_DIR / "fraud_model.pkl")

    X_proc = preprocessor.transform(df[ALL_FEATURES])
    probs = model.predict_proba(X_proc)[:, 1]

    metadata = json.loads((MODELS_DIR / "model_metadata.json").read_text())
    points = {p["target_fpr"]: p["threshold"] for p in metadata["test_metrics"]["fixed_fpr_operating_points"]}
    thresholds = {
        "thresh_01pct": points[0.001],
        "thresh_1pct": points[0.01],
        "selected_threshold": metadata["selected_threshold"],
    }
    results = pd.DataFrame({"family": df["__family__"].values, "prob": probs})
    return results, thresholds


def summarize(results: pd.DataFrame, thresholds: dict) -> list[dict]:
    thresh_01pct = thresholds["thresh_01pct"]
    thresh_1pct = thresholds["thresh_1pct"]
    selected_threshold = thresholds["selected_threshold"]

    print()
    print("=" * 90)
    print(f"{'Family':<30} {'n':>6} {'mean_prob':>10} {'recall@0.1%FPR':>15} {'recall@1%FPR':>13} {'recall@sel':>11}")
    print("=" * 90)

    summary = []
    for family in ["__legit__"] + FAMILIES:
        sub = results[results["family"] == family]
        if len(sub) == 0:
            print(f"{family:<30} NO DATA")
            continue
        n = len(sub)
        mean_p = sub["prob"].mean()
        at_01 = (sub["prob"] >= thresh_01pct).mean()
        at_1 = (sub["prob"] >= thresh_1pct).mean()
        at_sel = (sub["prob"] >= selected_threshold).mean()
        label = "fpr" if family == "__legit__" else "recall"
        print(f"{family:<30} {n:>6} {mean_p:>10.4f} {at_01*100:>14.2f}% {at_1*100:>12.2f}% {at_sel*100:>10.2f}%")
        summary.append({
            "family": family, "n": n, "mean_prob": float(mean_p),
            f"{label}_01pct": float(at_01), f"{label}_1pct": float(at_1), f"{label}_selected": float(at_sel),
        })
    print("=" * 90)
    return summary


def main():
    print(f"Families: {len(FAMILIES)}, intensities: {len(INTENSITIES)}, seeds/cell: {N_SEEDS_PER_CELL}")
    print(f"Total campaigns to generate: {len(FAMILIES) * len(INTENSITIES) * N_SEEDS_PER_CELL}")

    print("Loading baseline dataset...", flush=True)
    baseline = load_dataset(BASELINE_STAGE2_DIR)

    all_rows, all_meta = generate_all_campaigns(baseline)
    print(f"Generated {len(all_rows)} total attack rows across {len(FAMILIES)} families", flush=True)

    df = build_scored_dataframe(baseline, all_rows, all_meta)
    results, thresholds = score(df)
    summary = summarize(results, thresholds)

    REPORT_PATH.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
