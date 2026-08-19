# Closing the loop: detector misses → new attack variant → detector improves

This is the loop the master brief names as the whole point of the submission (section 6:
"The loop is the point. Attacks become training data for the defence; the defence's blind
spots generate new attacks."). This document is the diagnostic half, grounded entirely in
real numbers already on disk (`stage5/models/model_metadata.json`, `docs/model-choice.md`),
and the concrete generator-side code that closes it -- `src/attacks/generators.py`'s new
`adaptive_top_counterparty`/`beneficiary_age_floor_s` config keys on `AdversarialEvasionAttack`,
and `stage5/training/build_adaptive_attack_config.py`, which derives them from a trained
model.

**What's verified vs. what's designed-and-pending:** the diagnosis (part 1) and the code
(part 3) are real and tested (`tests/attacks/test_attack_framework.py`,
`tests/stage5/test_build_adaptive_attack_config.py`). The retrain-and-measure step (part 4)
that would confirm the *quantitative* improvement is deliberately not run in this pass --
it's a multi-minute pipeline run (`generate_training_data` → `train_fraud_model`), and this
work was done under an explicit "don't run heavy tasks right now" constraint. Treat part 4
as the next concrete action, not a claimed result.

## 1. Where the current detector is weakest (the "miss")

After the I6/I7/I17 fixes closed three compounding structural leaks (see `issues.md` and
`docs/model-choice.md`), the detector's numbers became genuinely imperfect for the first
time: PR-AUC 0.9866, recall 0.9775 at 0.1% FPR, recall 0.9902 at 1% FPR. That gap -- roughly
2.25% of fraud missed at the tightest operating point -- is real signal to dig into, not
noise to explain away.

Feature importance is now spread across plausible signals rather than one dominant proxy:

| Feature | Importance |
|---|---|
| `edge_count` | 34% |
| `beneficiary_added_ago_s` | 15% |
| `edge_value_total` | 6% |
| `is_two_hop_passthrough` | 4.6% |
| (long tail of session/behavioural features) | remainder |

**Reading this**: the model has essentially become a graph-relationship detector first,
everything else second. That's defensible -- graph structure genuinely is the strongest
mule/fraud signal per the brief's own list of "strongest mule discriminators" (section 6)
-- but it also means the detector's remaining blind spot is predictable: **any attack that
keeps its graph footprint (edge_count, beneficiary age) inside the legitimate range is
under-weighted by everything else the model has available.** That's a narrower, more honest
description of the gap than "the model has a 2.25% miss rate" -- it names the *shape* of
the miss.

Two families are structurally exempt from this discussion entirely, and it's worth being
explicit about why rather than treating them as future work: `first_party_dispute` (the
transaction is fully genuine -- "there is nothing to detect at transaction time," per the
catalogue's own inversion-pass table) and `insider_abuse` (no external anomaly exists by
construction). No transaction-time feature engineering closes those; they need routing to
a different detection stage entirely (`labels.detectable_at` already models this: dispute
history, post-settlement, access-pattern analysis). Chasing them with the fraud model would
be chasing a result the schema itself says isn't available yet -- correctly identifying that
boundary is part of the loop, not a gap in it.

## 2. The new attack variant

`adversarial_evasion` (G04 in the catalogue) is the family explicitly built to probe and
evade detection -- the natural vehicle for the next generation, rather than inventing a new
attack family. Two config-driven refinements target the model's *current* top two features
directly, both now implemented in `AdversarialEvasionAttack.generate()`:

- **`adaptive_top_counterparty=True`** -- route every campaign event through the payer's
  single busiest existing relationship (found via `_top_counterparty_for_payer`) instead of
  spreading across a small pool of 2-3 prior contacts (the current default, from the I7
  fix). A relationship that already has a high `edge_count` barely moves, proportionally,
  when a few more fraudulent transactions land on it -- the default pool-based routing still
  nudges each of 2-3 relationships up measurably.
- **`beneficiary_age_floor_s`** -- push the minimum beneficiary age further from "recently
  added" toward the legitimate population's typical maximum, directly countering the
  second-ranked feature.

`stage5/training/build_adaptive_attack_config.py` is the mechanism that actually closes the
loop end to end: it loads whatever model is currently saved in `stage5/models/`, checks
`feature_importances_` against a 10% threshold, and returns the config keys above only for
features that clear it. First-ever pipeline run: no model exists yet, returns `{}`, static
defaults apply. Every run after a detector has been trained: the *next* batch of
`adversarial_evasion` campaigns generated by `generate_training_data.py` automatically
targets whatever that detector currently leans on -- wired into the main scenario loop
already, no manual step required.

## 3. What's implemented and tested right now

- `src/attacks/generators.py`: `_top_counterparty_for_payer` helper,
  `AdversarialEvasionAttack.generate()`'s `adaptive_top_counterparty` / `beneficiary_age_floor_s`
  config handling, `pretext="low_and_slow_adaptive"` for provenance in the labels table.
- `src/attacks/registry.py`: `generate_attack_dataset()` now actually passes `config` through
  to `generator.generate()` -- previously silently dropped, so no caller (including the
  `make attack` CLI) could reach this path at all.
- `stage5/training/build_adaptive_attack_config.py`: derives the config from a trained
  model, with a graceful `{}` fallback when none exists.
- `stage5/training/generate_training_data.py`: wired to call `build_adaptive_config()` once
  per run and apply it to `adversarial_evasion` scenarios only.
- Tests: `tests/attacks/test_attack_framework.py` (adaptive routing concentrates on one
  counterparty; the beneficiary-age floor override is respected; no-config/`{}`-config
  behavior is provably unchanged from before this work) and
  `tests/stage5/test_build_adaptive_attack_config.py` (threshold logic against a mocked
  model, no real training required).

## 4. What's next (the measurement step, deferred)

To actually close the loop with a number, not just a mechanism:

1. `uv run python -m stage5.training.generate_training_data` (regenerates the combined
   dataset; `build_adaptive_config()` will pick up the currently-saved model automatically
   since one now exists from the I6/I7/I17 work).
2. `uv run python -m stage5.training.train_fraud_model` (retrain against the
   adaptive-evasion-augmented dataset).
3. Compare `adversarial_evasion`'s per-family recall at fixed FPR before vs. after -- the
   honest expectation is a *drop* in recall specifically for this family immediately after
   the adaptive variant is introduced (that's the "miss" half of the loop actually landing),
   followed by a second retrain iteration to see whether the model recovers by learning a
   feature it wasn't relying on before. That two-step pattern (miss, then recovery on the
   *next* iteration) is the real evidence for a working closed loop -- a single retrain that
   already catches everything wouldn't demonstrate anything the earlier suspicious 100%
   numbers didn't already show was wrong.

Both steps are multi-minute pipeline runs; run them when heavy tasks are back in scope, and
update this document's part 4 with the actual before/after numbers once done -- don't
retrofit a number here without having run it.
