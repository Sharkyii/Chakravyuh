# Canonical data schema v1

The contract between Pillar 2 (generate) and Pillar 3 (defend). Freeze this before writing generator code — every attack simulator writes these tables, the detector reads only these tables, and the prototype visualises them.

**Design rule:** only include fields a real payment system would actually have at decision time. If a field wouldn't exist in an issuer's or PSP's data at the moment of scoring, it doesn't belong here — otherwise your detector learns from information a live system never sees, and "real-world feasibility" collapses under questioning.

---

## Table 1 — `transactions`

The core event table. One row per payment attempt, including declines.

### Identity and routing

| Field | Type | Notes |
|---|---|---|
| `txn_id` | uuid | |
| `timestamp` | datetime | Millisecond precision. Timezone IST. |
| `rail` | enum | `card_cnp` `card_cp` `upi_p2p` `upi_p2m` `upi_collect_merchant` `upi_mandate` `upi_lite` `imps` `neft` `wallet` `bnpl` |
| `channel` | enum | `web` `app` `pos` `qr_static` `qr_dynamic` `intent_link` `agent` |
| `direction` | enum | `push` `pull` |
| `payer_id` | fk → parties | |
| `payee_id` | fk → parties | |
| `merchant_id` | fk → merchants | Null for P2P. |

### Money

| Field | Type | Notes |
|---|---|---|
| `amount` | decimal | |
| `currency` | char(3) | |
| `amount_is_round` | bool | Derived, but store it — round-number clustering is a real signal and attackers deliberately avoid it. |
| `mcc` | int | Card and P2M. Null for P2P. |
| `purpose_code` | string | UPI. **Carries the Circle delegation flag** — the only place the log knows payer ≠ account owner. |

### Authentication

| Field | Type | Notes |
|---|---|---|
| `auth_method` | enum | `none` `cvv_only` `3ds_frictionless` `3ds_challenge_otp` `3ds_challenge_biometric` `upi_pin` `lite_none` `mandate_no_afa` |
| `auth_result` | enum | `success` `failure` `abandoned` `not_attempted` |
| `auth_latency_ms` | int | Time from challenge issued to completion. Both tails matter: too fast suggests automation, too slow suggests a relay or a coached victim. |
| `eci` | string | Card only. |
| `liability_shift` | bool | Card only. |
| `exemption_claimed` | enum | Card. `none` `tra` `low_value` `mit` `whitelist` `delegated`. |

### Decision

| Field | Type | Notes |
|---|---|---|
| `decision` | enum | `approved` `declined` `flagged_review` |
| `decline_reason` | string | Model this properly. Whether a reason code is returned to the merchant *is itself the control* against model probing. |
| `issuer_risk_score` | float | The incumbent baseline model's score. Your detector must beat this, not replace nothing. |

### Session and device

Where scam-induced payments actually reveal themselves. Do not skimp here.

| Field | Type | Notes |
|---|---|---|
| `device_id` | fk → devices | |
| `device_is_known_for_payer` | bool | |
| `session_id` | uuid | |
| `session_duration_s` | int | Time in app before submitting. |
| `time_on_confirm_screen_s` | float | **Highest-value single field in the schema.** A coached victim hesitates or is rushed; both differ from routine payment. |
| `beneficiary_first_time` | bool | |
| `beneficiary_added_ago_s` | int | Seconds between adding the payee and paying them. |
| `pin_attempts` | int | |
| `screen_share_active` | bool | Detectable by real apps. The single strongest coercion signal available. |
| `call_active_during_txn` | bool | Same — Indian banking apps have begun checking this. |
| `accessibility_service_active` | bool | Malware and remote-access proxy. |
| `paste_used_in_amount` | bool | Distinguishes typed from injected. |
| `is_agent_initiated` | bool | Agentic rail. |
| `agent_declared_principal` | string | Who the agent claims to act for. |

### Geo

| Field | Type | Notes |
|---|---|---|
| `ip_country`, `ip_asn`, `ip_is_proxy` | | |
| `geo_matches_billing` | bool | Card. |
| `geo_matches_payer_home` | bool | |

---

## Table 2 — `parties`

Accounts and VPAs, both sides. Mule detection lives here and in the graph.

| Field | Type | Notes |
|---|---|---|
| `party_id` | uuid | |
| `party_type` | enum | `consumer` `merchant` `mule_unknown` — last one is ground truth only, never a feature |
| `account_age_days` | int | |
| `kyc_level` | enum | `full` `min_kyc` `video_kyc` `none` |
| `kyc_completed_at` | datetime | |
| `has_salary_credit` | bool | **Strongest mule discriminator available.** Mules have no organic income. |
| `organic_spend_ratio` | float | P2M spend ÷ total outflow. Real people buy groceries; mules only forward. |
| `throughput_ratio_24h` | float | Outflow ÷ inflow. Approaching 1.0 means pass-through. |
| `distinct_counterparties_30d` | int | |
| `home_pincode` | string | |
| `flagged_by_ffri` | bool | DoT Financial Fraud Risk Indicator. Model its **lag** — reactive by construction, and the latency window is the exploit. |

---

## Table 3 — `merchants`

| Field | Type | Notes |
|---|---|---|
| `merchant_id`, `mcc_declared`, `mcc_inferred_from_basket` | | Divergence between these two is the transaction-laundering signal. |
| `onboarded_at`, `kyb_level`, `kyb_docs_verified_against_registry` | | Format-valid vs registry-verified is the whole synthetic-KYB attack. |
| `days_to_first_txn` | int | |
| `volume_growth_curve` | enum | `organic` `step` `spike` |
| `chargeback_rate_30d`, `refund_rate_30d`, `decline_rate_30d` | float | Decline rate is your probe detector. |
| `settlement_account_age_days`, `settlement_outflow_latency_h` | | Bust-out signal. |

---

## Table 4 — `mandates`

| Field | Type | Notes |
|---|---|---|
| `mandate_id`, `payer_id`, `merchant_id` | | |
| `max_amount`, `actual_amount` | decimal | The gap between these is the whole `STEALTH-01` attack. |
| `frequency`, `created_at`, `enrolled_via` | | `enrolled_via`: `app` `web` `agent` `link` |
| `vpa_matches_biller_directory` | bool | The `AGENT-01` detector. |
| `pre_debit_notification_opened` | bool | Notification ≠ consent. |
| `cancelled_at`, `re_registered_from_mandate_id` | | Cancellation-evasion. |

---

## Table 5 — `disputes`

| Field | Type | Notes |
|---|---|---|
| `dispute_id`, `txn_id`, `raised_at_offset_days`, `reason_code` | | |
| `claimant_prior_dispute_count`, `claimant_prior_dispute_rate` | | First-party fraud is only visible across a claimant's history. |
| `device_matched_original_txn`, `ce30_evidence_available` | bool | |

---

## Table 6 — `graph_edges`

Do not try to derive this at training time from `transactions` alone. Materialise it.

| Field | Notes |
|---|---|
| `src_party_id`, `dst_party_id`, `window_start`, `window_end` | |
| `edge_count`, `edge_value_total`, `mean_inter_arrival_s` | |
| `src_out_degree`, `dst_in_degree` | Fan-out and fan-in — the mule primitives. |
| `is_two_hop_passthrough` | bool | |

---

## Table 7 — `labels`

Ground truth. Never a feature. Never joined at inference.

| Field | Notes |
|---|---|
| `txn_id`, `is_fraud`, `attack_id`, `campaign_id` | `attack_id` matches your catalogue slug. |
| `pretext` | The merged-variant discriminator — `digital_arrest`, `kyc_expiry`, `romance`, `job_task`, `bank_official`. |
| `is_legit_lookalike` | **The most important label in the schema.** |
| `detectable_at` | `pre_auth` `post_auth` `post_settlement` `only_in_hindsight` — determines which model is even allowed to try. |

---

## Three rules that decide whether this works

**Generate the lookalikes.** Every attack generator must also emit its `legit_lookalike` population — genuine emergency transfers, real festival remittances, honest new merchants, actual thin-file BNPL users. Without them your classifier separates two trivially different distributions, reports 0.99 AUC, and any judge who has worked in payments will know within thirty seconds that the number is meaningless.

**Split temporally, never randomly.** Train on weeks 1–8, test on weeks 9–12. Random splits leak campaign structure across the boundary and inflate everything.

**Report precision at fixed low FPR.** Because UPI credits are final, a post-hoc detector is a reporting tool rather than a control — Run 1 established this and it should be the headline of your evaluation section. Lead with precision at 0.1% and 1% FPR, and PR-AUC. Show ROC-AUC only as a secondary number.

---

## Immediate next step

Build the **legitimate base generator first** — parties, devices, normal transactions, realistic amount and inter-arrival distributions, correct class balance headroom. Get that looking credible against the marginals in IEEE-CIS and PaySim before you inject a single attack. Fidelity of the background is what makes the foreground believable, and it's where most teams skip straight to the fun part and lose the fidelity score.
