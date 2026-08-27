import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to python path to resolve imports
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.dataset.loader import PaymentDataset

class BehavioralFeatureTracker:
    """Tracks state per payer sequentially to compute behavioral features without lookahead bias."""
    
    def __init__(self):
        # Maps payer_id -> list of (timestamp, amount)
        self.payer_history = {}
        # Maps payer_id -> (running_sum, count)
        self.payer_stats = {}
        # Maps payer_id -> last_timestamp
        self.payer_last_time = {}
        # Maps payer_id -> set of merchant_ids
        self.payer_merchants = {}
        # Maps payer_id -> set of device_ids
        self.payer_devices = {}
        # Maps payer_id -> set of ip_asns
        self.payer_ips = {}
        # Maps payer_id -> list of (timestamp, tpap_app) for windowed distinct-app counts
        self.payer_tpap_history = {}
        # Maps payer_id -> list of (timestamp, linked_account_id) for windowed distinct-account counts
        self.payer_linked_account_history = {}
        # Maps payer_id -> list of transaction dicts for sequence features
        self.payer_full_history = {}
        # Maps payer_id -> last agent timestamp
        self.payer_last_agent_time = {}
        # Maps payee_id -> list of (timestamp, payer_id) for windowed fan-in
        # burst detection. The static graph_edges dst_in_degree is a whole-
        # dataset-window aggregate, so a mule account that receives from many
        # distinct payers all concentrated inside a short burst looks
        # identical, feature-wise, to one that received the same distinct
        # count spread across the whole simulation -- this tracks recency so
        # the burst itself becomes visible.
        self.payee_history = {}

    def get_and_update(
        self,
        payer_id: str,
        ts: datetime,
        amount: float,
        merchant_id: str,
        device_id: str,
        ip_asn: str,
        rail: str = "",
        channel: str = "",
        is_agent_initiated: bool = False,
        beneficiary_first_time: bool = True,
        beneficiary_added_ago_s: float = 0.0,
        tpap_app: str | None = None,
        linked_account_id: str | None = None,
    ) -> dict:
        payer_id = str(payer_id)
        merchant_id = str(merchant_id) if merchant_id else ""
        device_id = str(device_id) if device_id else ""
        ip_asn = str(ip_asn) if ip_asn else ""
        tpap_app = str(tpap_app) if tpap_app else ""
        linked_account_id = str(linked_account_id) if linked_account_id else ""
        
        # 1. Initialize states if new payer
        if payer_id not in self.payer_history:
            self.payer_history[payer_id] = []
            self.payer_stats[payer_id] = (0.0, 0)
            self.payer_last_time[payer_id] = None
            self.payer_merchants[payer_id] = set()
            self.payer_devices[payer_id] = set()
            self.payer_ips[payer_id] = set()
            self.payer_full_history[payer_id] = []
            self.payer_tpap_history[payer_id] = []
            self.payer_linked_account_history[payer_id] = []

        # 2. Get history list
        hist = self.payer_history[payer_id]
        
        # 3. Clean history of transactions older than 24h to keep list small
        cutoff_24h = ts - timedelta(hours=24)
        hist = [x for x in hist if x[0] >= cutoff_24h]
        self.payer_history[payer_id] = hist
        
        # 4. Compute 1h and 24h aggregates
        cutoff_1h = ts - timedelta(hours=1)
        txns_1h = [x for x in hist if x[0] >= cutoff_1h]
        
        txn_count_last_1h = len(txns_1h)
        txn_count_last_24h = len(hist)
        
        amount_spent_last_1h = sum(x[1] for x in txns_1h)
        amount_spent_last_24h = sum(x[1] for x in hist)

        # 4b. Windowed distinct TPAP-app / linked-account counts (TPAP
        # cross-app fraud signature: legitimate parties rarely switch, so
        # these stay near 1 outside an attack window -- see calibration.py's
        # TPAP_APP_POOL comment for why the raw fields alone aren't the
        # signal, only the rate of switching is).
        tpap_hist = [x for x in self.payer_tpap_history[payer_id] if x[0] >= cutoff_24h]
        self.payer_tpap_history[payer_id] = tpap_hist
        tpap_hist_1h = [x for x in tpap_hist if x[0] >= cutoff_1h]
        distinct_tpap_count_last_1h = float(len({x[1] for x in tpap_hist_1h if x[1]}))
        distinct_tpap_count_last_24h = float(len({x[1] for x in tpap_hist if x[1]}))

        acct_hist = [x for x in self.payer_linked_account_history[payer_id] if x[0] >= cutoff_24h]
        self.payer_linked_account_history[payer_id] = acct_hist
        acct_hist_1h = [x for x in acct_hist if x[0] >= cutoff_1h]
        distinct_linked_account_count_last_1h = float(len({x[1] for x in acct_hist_1h if x[1]}))
        distinct_linked_account_count_last_24h = float(len({x[1] for x in acct_hist if x[1]}))

        # 4c. Payee-side fan-in burst velocity (pre-transaction, no
        # lookahead): computed BEFORE this transaction is recorded below.
        # Skipped for blank payee ids so untagged transactions don't collide
        # into one shared "" bucket and inflate fan-in counts falsely.
        if merchant_id:
            if merchant_id not in self.payee_history:
                self.payee_history[merchant_id] = []
            payee_hist = [x for x in self.payee_history[merchant_id] if x[0] >= cutoff_24h]
            self.payee_history[merchant_id] = payee_hist
            payee_hist_1h = [x for x in payee_hist if x[0] >= cutoff_1h]
            payee_distinct_payer_count_last_1h = float(len({x[1] for x in payee_hist_1h}))
            payee_distinct_payer_count_last_24h = float(len({x[1] for x in payee_hist}))
            payee_txn_count_last_1h = float(len(payee_hist_1h))
            payee_txn_count_last_24h = float(len(payee_hist))
        else:
            payee_distinct_payer_count_last_1h = 0.0
            payee_distinct_payer_count_last_24h = 0.0
            payee_txn_count_last_1h = 0.0
            payee_txn_count_last_24h = 0.0

        # 5. Compute historical averages (based on transactions BEFORE this one)
        run_sum, count = self.payer_stats[payer_id]
        if count > 0:
            historical_average_amount = run_sum / count
            amount_deviation = abs(amount - historical_average_amount)
        else:
            historical_average_amount = 0.0
            amount_deviation = 0.0
            
        # 6. Compute velocity features
        last_ts = self.payer_last_time[payer_id]
        if last_ts is not None:
            time_since_prev_txn = (ts - last_ts).total_seconds()
        else:
            time_since_prev_txn = 999999.0 # large fallback value
            
        # 7. New indicator checks
        new_merchant_indicator = 1.0 if (merchant_id and merchant_id not in self.payer_merchants[payer_id]) else 0.0
        new_device_indicator = 1.0 if (device_id and device_id not in self.payer_devices[payer_id]) else 0.0
        new_ip_indicator = 1.0 if (ip_asn and ip_asn not in self.payer_ips[payer_id]) else 0.0
        
        # 8. Update state WITH the current transaction
        self.payer_history[payer_id].append((ts, amount))
        self.payer_stats[payer_id] = (run_sum + amount, count + 1)
        self.payer_last_time[payer_id] = ts
        self.payer_tpap_history[payer_id].append((ts, tpap_app))
        self.payer_linked_account_history[payer_id].append((ts, linked_account_id))
        if merchant_id:
            self.payee_history[merchant_id].append((ts, payer_id))
            self.payer_merchants[payer_id].add(merchant_id)
        if device_id:
            self.payer_devices[payer_id].add(device_id)
        if ip_asn:
            self.payer_ips[payer_id].add(ip_asn)
            
        # 9. Compute sequence features
        self.payer_full_history[payer_id].append({
            "ts": ts,
            "amount": amount,
            "payee_id": merchant_id or "unknown",
            "is_merchant": bool(merchant_id),
            "rail": rail,
            "channel": channel,
            "is_agent_initiated": bool(is_agent_initiated),
            "beneficiary_first_time": bool(beneficiary_first_time),
            "beneficiary_added_ago_s": float(beneficiary_added_ago_s)
        })
        
        full_hist = self.payer_full_history[payer_id]
        timestamps = [x["ts"] for x in full_hist]
        diffs = [(t_c - t_p).total_seconds() for t_p, t_c in zip(timestamps[:-1], timestamps[1:])]
        
        if diffs:
            inter_txn_time_mean = float(np.mean(diffs))
            inter_txn_time_std = float(np.std(diffs))
            inter_txn_time_min = float(np.min(diffs))
            inter_txn_time_max = float(np.max(diffs))
        else:
            inter_txn_time_mean = 999999.0
            inter_txn_time_std = 0.0
            inter_txn_time_min = 999999.0
            inter_txn_time_max = 999999.0
            
        if (inter_txn_time_std + inter_txn_time_mean) > 0:
            txn_burstiness = float((inter_txn_time_std - inter_txn_time_mean) / (inter_txn_time_std + inter_txn_time_mean))
        else:
            txn_burstiness = 0.0
            
        active_days = {t.date() for t in timestamps}
        active_days_count = float(len(active_days))
        active_hours = {t.hour for t in timestamps}
        active_hours_count = float(len(active_hours))
        txns_per_active_day = float(len(timestamps)) / active_days_count if active_days_count > 0 else 1.0
        
        amounts = [x["amount"] for x in full_hist]
        mean_amount = float(np.mean(amounts))
        amount_std = float(np.std(amounts))
        amount_cv = amount_std / mean_amount if mean_amount > 0.0 else 0.0
        
        subthreshold_txn_ratio = float(sum(1 for a in amounts if a < 100.0)) / len(amounts)
        aggregate_to_threshold_ratio = float(sum(amounts)) / 10000.0
        
        sum_amounts = sum(amounts)
        if sum_amounts > 0:
            amount_concentration = float(sum((a / sum_amounts)**2 for a in amounts))
        else:
            amount_concentration = 1.0
            
        payees = [x["payee_id"] for x in full_hist]
        unique_payee_count = float(len(set(payees)))
        merchant_diversity = unique_payee_count / len(payees) if len(payees) > 0 else 0.0
        same_payee_ratio = float(max(payees.count(p) for p in set(payees))) / len(payees) if len(payees) > 0 else 1.0
        merchant_txn_ratio = float(sum(1 for x in full_hist if x["is_merchant"])) / len(payees)
        
        first_times = [x["beneficiary_first_time"] for x in full_hist]
        beneficiary_reuse_ratio = float(sum(1 for ft in first_times if not ft)) / len(first_times)
        txn_regularity = inter_txn_time_std / inter_txn_time_mean if inter_txn_time_mean > 0 else 0.0
        
        rails = [x["rail"] for x in full_hist]
        mandate_txn_ratio = float(sum(1 for r in rails if r == "upi_mandate")) / len(rails)
        
        ben_added_agos = [x["beneficiary_added_ago_s"] for x in full_hist]
        mean_beneficiary_added_ago = float(np.mean(ben_added_agos))
        max_beneficiary_added_ago = float(np.max(ben_added_agos))
        
        agent_flags = [x["is_agent_initiated"] for x in full_hist]
        agent_txn_ratio = float(sum(1 for a in agent_flags if a)) / len(agent_flags)
        
        agent_timestamps = [x["ts"] for x in full_hist if x["is_agent_initiated"]]
        agent_diffs = [(t_c - t_p).total_seconds() for t_p, t_c in zip(agent_timestamps[:-1], agent_timestamps[1:])]
        if agent_diffs:
            a_mean = np.mean(agent_diffs)
            a_std = np.std(agent_diffs)
            agent_txn_burstiness = float((a_std - a_mean) / (a_std + a_mean)) if (a_std + a_mean) > 0 else 0.0
        else:
            agent_txn_burstiness = 0.0
            
        last_agent_ts = self.payer_last_agent_time.get(payer_id)
        if is_agent_initiated:
            if last_agent_ts is not None:
                time_since_prev_agent_txn = (ts - last_agent_ts).total_seconds()
            else:
                time_since_prev_agent_txn = 999999.0
            self.payer_last_agent_time[payer_id] = ts
        else:
            if last_agent_ts is not None:
                time_since_prev_agent_txn = (ts - last_agent_ts).total_seconds()
            else:
                time_since_prev_agent_txn = 999999.0
        
        return {
            "txn_count_last_1h": float(txn_count_last_1h),
            "txn_count_last_24h": float(txn_count_last_24h),
            "amount_spent_last_1h": float(amount_spent_last_1h),
            "amount_spent_last_24h": float(amount_spent_last_24h),
            "historical_average_amount": float(historical_average_amount),
            "amount_deviation": float(amount_deviation),
            "time_since_prev_txn": float(time_since_prev_txn),
            "new_merchant_indicator": float(new_merchant_indicator),
            "new_device_indicator": float(new_device_indicator),
            "new_ip_indicator": float(new_ip_indicator),
            "distinct_tpap_count_last_1h": distinct_tpap_count_last_1h,
            "distinct_tpap_count_last_24h": distinct_tpap_count_last_24h,
            "distinct_linked_account_count_last_1h": distinct_linked_account_count_last_1h,
            "distinct_linked_account_count_last_24h": distinct_linked_account_count_last_24h,
            "payee_distinct_payer_count_last_1h": payee_distinct_payer_count_last_1h,
            "payee_distinct_payer_count_last_24h": payee_distinct_payer_count_last_24h,
            "payee_txn_count_last_1h": payee_txn_count_last_1h,
            "payee_txn_count_last_24h": payee_txn_count_last_24h,
            "inter_txn_time_mean": inter_txn_time_mean,
            "inter_txn_time_std": inter_txn_time_std,
            "inter_txn_time_min": inter_txn_time_min,
            "inter_txn_time_max": inter_txn_time_max,
            "txn_burstiness": txn_burstiness,
            "active_days_count": active_days_count,
            "active_hours_count": active_hours_count,
            "txns_per_active_day": txns_per_active_day,
            "amount_std": amount_std,
            "amount_cv": amount_cv,
            "subthreshold_txn_ratio": subthreshold_txn_ratio,
            "aggregate_to_threshold_ratio": aggregate_to_threshold_ratio,
            "amount_concentration": amount_concentration,
            "unique_payee_count": unique_payee_count,
            "merchant_diversity": merchant_diversity,
            "same_payee_ratio": same_payee_ratio,
            "merchant_txn_ratio": merchant_txn_ratio,
            "beneficiary_reuse_ratio": beneficiary_reuse_ratio,
            "txn_regularity": txn_regularity,
            "mandate_txn_ratio": mandate_txn_ratio,
            "mean_beneficiary_added_ago": mean_beneficiary_added_ago,
            "max_beneficiary_added_ago": max_beneficiary_added_ago,
            "agent_txn_ratio": agent_txn_ratio,
            "agent_txn_burstiness": agent_txn_burstiness,
            "time_since_prev_agent_txn": time_since_prev_agent_txn,
        }

def build_features(dataset: PaymentDataset) -> pd.DataFrame:
    """Processes raw tables and returns a merged pandas DataFrame containing all features."""
    
    # 1. Load tables as pandas DataFrames
    txs_df = pd.DataFrame(dataset.transactions)
    labels_df = pd.DataFrame(dataset.labels)
    parties_df = pd.DataFrame(dataset.tables["parties"])
    graph_df = pd.DataFrame(dataset.tables["graph_edges"])
    
    # Check for empty/missing columns and format types
    txs_df["timestamp"] = pd.to_datetime(txs_df["timestamp"])
    txs_df["amount"] = txs_df["amount"].astype(float)
    
    # Sort chronologically to compute behavioral features correctly
    txs_df = txs_df.sort_values(by=["timestamp", "txn_id"]).reset_index(drop=True)
    
    # 2. Extract basic time features
    txs_df["tx_hour"] = txs_df["timestamp"].dt.hour
    txs_df["tx_dayofweek"] = txs_df["timestamp"].dt.dayofweek
    
    # 3. Compute behavioral features sequentially
    print("Computing sequential behavioral features...")
    tracker = BehavioralFeatureTracker()
    beh_list = []
    for idx, row in txs_df.iterrows():
        beh = tracker.get_and_update(
            payer_id=row["payer_id"],
            ts=row["timestamp"],
            amount=row["amount"],
            merchant_id=row.get("payee_id", ""),
            device_id=row.get("device_id", ""),
            ip_asn=row.get("ip_asn", ""),
            rail=row.get("rail", ""),
            channel=row.get("channel", ""),
            is_agent_initiated=row.get("is_agent_initiated", False),
            beneficiary_first_time=row.get("beneficiary_first_time", True),
            beneficiary_added_ago_s=row.get("beneficiary_added_ago_s", 0.0),
            tpap_app=row.get("tpap_app"),
            linked_account_id=row.get("linked_account_id"),
        )
        beh_list.append(beh)
        
    beh_df = pd.DataFrame(beh_list)
    txs_df = pd.concat([txs_df, beh_df], axis=1)
    
    # 4. Merge Party / Account features
    print("Merging party/account features...")
    parties_sub = parties_df[["party_id", "account_age_days"]].copy()
    parties_sub["party_id"] = parties_sub["party_id"].astype(str)
    txs_df["payer_id"] = txs_df["payer_id"].astype(str)
    txs_df = txs_df.merge(parties_sub, left_on="payer_id", right_on="party_id", how="left").drop(columns=["party_id"])
    
    # 5. Look up Graph features from baseline edges
    print("Merging graph features...")
    if not graph_df.empty:
        # Build out-degree and in-degree maps per party from graph edges
        out_deg_map = graph_df.groupby("src_party_id")["src_out_degree"].first().to_dict()
        in_deg_map = graph_df.groupby("dst_party_id")["dst_in_degree"].first().to_dict()
        
        # Build edge-specific maps for count, total value, and passthrough
        edge_count_map = {}
        edge_value_map = {}
        edge_passthrough_map = {}
        
        for _, row in graph_df.iterrows():
            key = (str(row["src_party_id"]), str(row["dst_party_id"]))
            edge_count_map[key] = float(row["edge_count"])
            edge_value_map[key] = float(row["edge_value_total"])
            edge_passthrough_map[key] = bool(row["is_two_hop_passthrough"])
            
        # Apply lookups
        txs_df["payer_out_degree"] = txs_df["payer_id"].map(out_deg_map).fillna(0.0).astype(float)
        txs_df["payee_in_degree"] = txs_df["payee_id"].map(in_deg_map).fillna(0.0).astype(float)
        
        counts = []
        values = []
        passthroughs = []
        for idx, row in txs_df.iterrows():
            key = (str(row["payer_id"]), str(row["payee_id"]))
            counts.append(edge_count_map.get(key, 0.0))
            values.append(edge_value_map.get(key, 0.0))
            passthroughs.append(float(edge_passthrough_map.get(key, False)))
            
        txs_df["edge_count"] = counts
        txs_df["edge_value_total"] = values
        txs_df["is_two_hop_passthrough"] = passthroughs
    else:
        # Fallbacks if graph edges table is empty
        txs_df["payer_out_degree"] = 0.0
        txs_df["payee_in_degree"] = 0.0
        txs_df["edge_count"] = 0.0
        txs_df["edge_value_total"] = 0.0
        txs_df["is_two_hop_passthrough"] = 0.0
        
    # 6. Merge target labels
    print("Merging target labels...")
    txs_df = txs_df.merge(labels_df, on="txn_id", how="left")
    
    # Fill target variables default values
    txs_df["is_fraud"] = txs_df["is_fraud"].fillna(False)
    txs_df["is_legit_lookalike"] = txs_df["is_legit_lookalike"].fillna(False)
    
    return txs_df
