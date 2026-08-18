# Why XGBoost for the Stage 5 fraud detector

`stage5/training/train_fraud_model.py` fits Logistic Regression, Random Forest and
XGBoost side by side on the same temporal train split and picks a winner on
validation PR-AUC before touching the test set. This is that comparison's result
and the reasoning behind it, plus an important caveat on what the current numbers
do and don't prove — read the caveat before quoting any number from this doc in
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
coercion — it has to weight each independently. The ~36-point PR-AUC gap versus
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
  for turning a score into "these specific features drove this decision" —
  the exact evidence a fraud analyst needs to act on a flagged transaction, and
  a cheaper computation than SHAP over an equivalently-sized Random Forest.
- **Calibrated operating points.** The evaluation harness (section 6 rule 3)
  is built around precision/recall at fixed FPR thresholds (0.1%, 1%), not a
  single classification boundary. Gradient boosting's probability outputs hold
  up better under threshold sweeps than Random Forest's vote-fraction estimates,
  which tend to cluster and make fine-grained FPR targeting noisier.

None of this says XGBoost is a novel or unusual choice — it isn't, and the
submission shouldn't claim it is. It's the standard, defensible choice for
tabular fraud data under extreme class imbalance with a hard latency budget,
picked via a real comparison rather than assumed.

## Caveat: what the current absolute numbers do and don't prove

As of this write-up, the temporal split, the held-out attack family, and the
`legit_lookalike` companion population (previously never generated at all — see
the fix in `src/attacks/generators.py`) are all now genuinely wired in. Despite
that, the detector still scores PR-AUC ≈ 0.998–0.999 and recalls ~100% of fraud
at 1% FPR, including on the held-out family it never trained on.

An ablation (drop `inter_txn_time_min` and the rest of the timing/velocity
feature cluster, which held 92.5% of feature importance) barely moved these
numbers — `edge_count` and `beneficiary_added_ago_s` immediately took over as
the dominant features. That rules out "one leaky feature" as the explanation.
The more likely cause, not yet fixed: attack campaigns route several
transactions through the *same* counterparty pair within a short window, a
pattern the legitimate generator's organic-counterparty model essentially never
produces on its own — so campaign shape alone is close to a perfect tell,
independent of which specific feature a model happens to key on. Compounding
this, `make_legit_lookalike_rows` currently reuses the source fraud row's exact
payer/payee pair and timestamp, changing only a few numeric fields (amount,
confirm-screen time, issuer score) — so the lookalike population inherits the
same structural graph anomaly instead of presenting the genuinely hard,
independently-plausible case the brief's "generate the lookalikes" rule is
meant to force the model to learn from.

**Practical effect:** the model-choice ranking above (XGBoost over LR, XGBoost
over RF for the stated reasons) is sound and doesn't depend on this. The
*absolute* PR-AUC / precision-recall numbers are not yet meaningful and should
not go in the walkthrough deck until the generator-side fix — making
`legit_lookalike` rows structurally independent (a different, plausible
counterparty and timing, not a shallow copy of the fraud row) — lands and the
numbers are re-run.
