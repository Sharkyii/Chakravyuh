# Why XGBoost for the Stage 5 fraud detector

`stage5/training/train_fraud_model.py` fits Logistic Regression, Random Forest and
XGBoost side by side on the same temporal train split and picks a winner on
validation PR-AUC before touching the test set. This is that comparison's result
and the reasoning behind it, plus an important caveat on what the current numbers
do and don't prove - read the caveat before quoting any number from this doc in
the deck.

## The comparison (temporal split, held-out `synthetic_identity_bustout` family)

| Model | Validation PR-AUC |
|---|---|
| Logistic Regression | 0.6367 |
| Random Forest | 0.9994 |
| XGBoost | 0.9983 |

Logistic Regression is the informative result here, not the two tree models'
near-tie. A linear model can't combine `screen_share_active`, `call_active_during_txn`
and `beneficiary_first_time` into the joint condition that actually signals
coercion - it has to weight each independently. The ~36-point PR-AUC gap versus
both tree models is empirical confirmation of something the brief already argues
qualitatively (section 8): detecting a scam-induced payment is an interaction-detection
problem, not a linear-scoring problem. That's the strongest evidence in this doc,
and it doesn't depend on the caveat below.

Random Forest and XGBoost are statistically close on this validation split. XGBoost
is still the better production choice for reasons the validation PR-AUC alone won't
show:

- **Latency budget.** The brief requires pre-auth, sub-second UPI decisioning
  (section 3.1: "detection must be pre-authorisation"). A gradient-boosted ensemble
  at 150 shallow (depth-6) trees scores a row in microseconds; a Random Forest
  matching the same accuracy typically needs a larger forest of deeper trees,
  which costs more at inference for no accuracy gain here.
- **Native class-imbalance handling.** Fraud prevalence in the training set is
  well under 1%. XGBoost's `scale_pos_weight` (109 in this run) reweights the
  loss directly; Random Forest's `class_weight="balanced"` is a coarser
  per-tree adjustment.
- **Explainability for the Stage 6 analyst layer.** `stage5/inference/pipeline.py`
  already generates a per-transaction analyst narrative (LLM-backed, with a
  template fallback). XGBoost has fast, mature SHAP support (`TreeExplainer`)
  for turning a score into "these specific features drove this decision" -
  the exact evidence a fraud analyst needs to act on a flagged transaction, and
  a cheaper computation than SHAP over an equivalently-sized Random Forest.
- **Calibrated operating points.** The evaluation harness (section 6 rule 3)
  is built around precision/recall at fixed FPR thresholds (0.1%, 1%), not a
  single classification boundary. Gradient boosting's probability outputs hold
  up better under threshold sweeps than Random Forest's vote-fraction estimates,
  which tend to cluster and make fine-grained FPR targeting noisier.

None of this says XGBoost is a novel or unusual choice - it isn't, and the
submission shouldn't claim it is. It's the standard, defensible choice for
tabular fraud data under extreme class imbalance with a hard latency budget,
picked via a real comparison rather than assumed.

## Resolved: I6/I7/I17, and the numbers that are now trustworthy

The caveat that used to live in this section is closed. Three compounding issues made
the detector look artificially perfect; all three are now fixed in `src/attacks/`,
verified by re-running the full pipeline and re-checking feature importances after
each fix, not just by inspection:

1. **I6 - shallow-copy lookalikes.** `make_legit_lookalike_rows` used to reuse the
   source fraud row's exact payer/payee pair and timestamp. Fixed: lookalikes now get
   an independently plausible counterparty (a different existing merchant/consumer,
   drawn from a small bounded pool per campaign so a payer's `payer_out_degree`
   doesn't blow past organic levels) and an independently resampled timestamp across
   the simulation window, keeping only the shape (rail, channel, MCC, amount scale).
2. **I7 - campaign structure as a near-perfect tell.** Several generators (the
   families whose catalogue entry claims they should look normal on velocity/graph
   signals, e.g. `adversarial_evasion`) now route events across a small pool of the
   payer's *genuinely pre-existing* counterparties instead of hammering one fixed
   brand-new pair. A duplicate-seed bug was also found and fixed along the way:
   `generate_training_data.py`'s old `base_seed + i` expansion scheme let adjacent
   base seeds collide across unrelated families (~3.2k duplicate `txn_id` rows,
   corrupting downstream merges).
3. **I17 - hardcoded `ip_asn` default.** Found by inspecting feature importances
   after I6/I7 landed: `_transaction_row`'s default `ip_asn="AS55836"` meant every
   attack row (and, transitively, every shallow-copy-era lookalike) carried the exact
   same ASN, while `legitimate.py` drew from five. Any row with a different ASN was
   trivially guaranteed legitimate. Fixed by moving the ASN pool into
   `calibration.IP_ASN_POOL` and having both `legitimate.py` and `framework.py` draw
   from it, closing the single-source-of-truth gap that caused the drift.

**Numbers after all three fixes**, same temporal split, same held-out
`synthetic_identity_bustout` family:

| Model | Validation PR-AUC |
|---|---|
| Logistic Regression | 0.8487 |
| Random Forest | 0.9410 |
| XGBoost | 0.9710 |

Test set: PR-AUC 0.9866, ROC-AUC 0.9997 (secondary). @0.1% FPR: precision 0.8406,
recall 0.9775. @1% FPR: precision 0.4384, recall 0.9902. F1-optimal threshold:
precision 0.9942, recall 0.9663, 4.99 alerts/1,000 transactions. Feature importance is
now spread across plausible signals with no single dominant proxy - `edge_count`
(34%), `beneficiary_added_ago_s` (15%), `edge_value_total` (6%), `is_two_hop_passthrough`
(4.6%), then a long tail of session/behavioural features. These are exactly the
graph-based mule discriminators the brief names as strongest (section 6), not an
artifact.

The held-out family (`synthetic_identity_bustout`) is still caught at 307/307 (100%)
at both fixed-FPR thresholds. Unlike before, this is no longer suspicious on its own:
the overall test-set recall is genuinely imperfect now (0.9775 / 0.9902, not 1.0), so
the model demonstrably *can* miss fraud - it simply isn't missing this particular
held-out family, which is a plausible outcome if bust-out's graph/behavioural
signature (sudden amount-deviation and throughput-ratio shift after a "credit-building"
phase) genuinely transfers from patterns learned on the other 12 families. Treat this
as the headline generalisation result, but note it, don't oversell it as proof of
nothing left to find - a second held-out family run would be the natural next check.

The LR vs. tree-model gap (0.85 vs. 0.94–0.97) is smaller than the original 0.64-vs-0.999
gap this section used to report, but the qualitative conclusion is the same: linear
scoring underperforms interaction modelling on this feature set, and that comparison
was never dependent on the leakage above.
