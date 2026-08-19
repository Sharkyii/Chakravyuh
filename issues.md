# Issues

Defects and gaps against docs/master-project-brief.md's deliverables and rules.
Status: `OPEN` | `IN PROGRESS` | `FIXED`. Update this file as issues are found or closed --
it's the source of truth for "what's left," not the conversation history.

## Log

| ID | Status | Severity | Area | Summary |
|---|---|---|---|---|
| I1 | FIXED (47ada1e) | high | detector | Train/val/test split was random (shuffled campaign/payer id), not temporal -- violated brief section 6 rule 2 |
| I2 | FIXED (47ada1e) | high | detector | No attack family held out entirely for generalisation testing |
| I3 | FIXED (47ada1e) | high | detector | Evaluation reported only the F1-optimal threshold, no precision@fixed-FPR (0.1%/1%) |
| I4 | FIXED (47ada1e) | high | attacks | `make_legit_lookalike_rows` existed but was never called anywhere -- every attack generator emitted fraud-only rows |
| I5 | FIXED (47ada1e) | medium | stage5 config | Baseline population (3k consumers) too small relative to `EXPANSION_FACTOR=100` -- fraud+lookalike rows swamped the legitimate baseline |
| I6 | FIXED | high | attacks | `legit_lookalike` rows are shallow copies of their source fraud row -- same payer/payee pair, same timestamp, only amount/session fields tweaked |
| I7 | FIXED | high | attacks + generators | Attack campaigns route multiple transactions through the same new counterparty within a short window, a pattern the legitimate generator doesn't produce on its own -- campaign shape alone is close to a perfect tell |
| I8 | FIXED (54615a7) | medium | validation | No validation report comparing generated data against IEEE-CIS/PaySim/BankSim/ULB reference marginals -- `data/reference/` is empty |
| I9 | IN PROGRESS | medium | detector | `train_attack_classifier.py` splits by random shuffled `campaign_id`, not temporally -- same bug class as I1, lower stakes (auxiliary model, not the judged detector) |
| I10 | OPEN | low | attacks | `LLMScenarioGenerator`/`HybridScenarioGenerator` call the Gemini API when `SCENARIO_GENERATOR_MODE` is `llm`/`hybrid` -- off by default but undocumented in AGENTS.md |
| I11 | OPEN | high | deliverable | Closed-loop iteration doc (misses -> new attack variant -> improved detector) doesn't exist |
| I12 | OPEN | high | deliverable | Web prototype -- mandatory submission artifact -- not started |
| I13 | OPEN | high | deliverable | Walkthrough deck -- mandatory submission artifact -- not started |
| I14 | FIXED (pending commit) | low | docs | The catalogue's "Outstanding before freeze" checklist now reflects the D3 rail-limit verification, completed D5 evidence pass, remaining UPI P2M primary-circular retrieval, 14 missing expanded cards, and the structural lookalike gap (I6/I7). |
| I15 | OPEN | medium | generators | Day-of-week histogram is perfectly flat (0.142-0.143 every day) -- `_timestamp()` in `src/generators/legitimate.py` draws uniformly across the 12-week window with an hour-of-day nudge only, no weekday effect. Contradicts the brief's own spec ("salary-day spikes, weekend patterns") and I8's committed reference stats. Found by I8's validation report. |
| I16 | OPEN | medium | generators | Amount medians are statistically indistinguishable across MCCs (~265-268 INR for grocery, fuel, and hotels alike) -- `_amount_for_rail()` in `src/generators/legitimate.py` conditions amount only on `rail` and `income_type`, never on `mcc`. BankSim's reference data (data/reference/banksim.json) documents category-conditioned amount shape (everyday categories cheap, travel/hotel expensive) that this doesn't reproduce. Found by I8's validation report. |
| I17 | FIXED | high | attacks + generators | `_transaction_row`'s default `ip_asn="AS55836"` (`src/attacks/framework.py`) meant every attack row carried the exact same ASN while `legitimate.py` drew from five -- became a new 81%-importance near-perfect tell the moment I6/I7 closed the campaign-shape leak. Found by re-inspecting feature importances after the I6/I7 fix. |

## Detail

## Next tasks

Work in this order; each item should be independently tested and committed before moving on.

1. **P0 — Build I12, the mandatory web prototype:** wire a demonstrable analyst flow to the
   Stage 6 inference pipeline using only decision-time fields and a reproducible sample dataset.
2. **P0 — Build I13, the mandatory walkthrough deck:** include the corrected D2 statistic,
   the D3 sources, confidence-tier labels from the evidence pass, and the post-I6/I7/I17
   detector numbers from `docs/model-choice.md`. Do not quote the UPI P2M higher-limit
   figures until the primary circular is retrieved.
3. **P1 — Close I11:** add a closed-loop iteration document showing a detector miss, the
   corresponding new synthetic variant, retraining, and the measured improvement.
4. **P1 — Finish I9:** imports for the temporal split are in place in
   `stage5/training/train_attack_classifier.py`; the split logic itself still needs
   swapping from the random campaign shuffle to `assign_split`/`split_windows`, matching
   `train_fraud_model.py`'s pattern (see that file's step 3).
5. **P1 — Close I15/I16:** calibrate weekday and MCC-conditioned amount distributions, then
   extend the fidelity report/tests with the target tolerances.
6. **P2 — Complete catalogue documentation:** retrieve the primary UPI P2M circular; audit
   remaining catalogue statistics in phased source-backed research notes; append the 14
   remaining expanded attack cards.
7. **P2 — Close I10:** document the optional Gemini-backed scenario-generator modes, their
   required credentials, data-handling constraints, and the deterministic default.
8. **P3 — stage5 artifacts:** `stage5/models/attack_classifier.pkl` and
   `attack_class_mapping.json` need regenerating against the post-I6/I7/I17 combined
   dataset (`uv run python -m stage5.training.train_attack_classifier`) -- until then,
   `tests/stage5/test_stage6.py`'s 4 artifact-loading tests fail on a stale/missing file,
   not a logic bug. Heavier task, deliberately deferred.

### I6/I7/I17 -- resolved, see docs/model-choice.md for the full writeup

All three were the same underlying problem approached from different angles, found in
sequence as each fix surfaced the next leak:

- **I6** (`make_legit_lookalike_rows` in `src/attacks/generators.py`) used to shallow-copy
  the source fraud row -- same payer/payee pair, same timestamp -- so lookalikes inherited
  the fraud row's structural graph anomaly instead of being a genuine near-neighbour.
- **I7** (campaign routing across most of the 13 generators) hammered one fixed brand-new
  counterparty per campaign, making "did >1 txn happen between this pair recently" close to
  a perfect tell by itself. Fixed for the families whose catalogue entry requires normal-
  looking velocity/graph behaviour (e.g. `adversarial_evasion`) by routing across a small
  pool of the payer's genuinely pre-existing counterparties instead.
- **I17** (`_transaction_row`'s `ip_asn="AS55836"` default in `src/attacks/framework.py`) was
  found only *after* I6/I7 closed the bigger leak -- feature importance immediately shifted to
  ip_asn at 81%, because every attack row defaulted to one ASN while `legitimate.py` drew from
  five. Fixed by centralising the pool in `calibration.IP_ASN_POOL`.

A duplicate-seed bug was also caught and fixed along the way in
`generate_training_data.py`'s campaign expansion (adjacent base seeds colliding across
unrelated families, ~3.2k duplicate `txn_id` rows corrupting merges).

Post-fix numbers (temporal split, held-out `synthetic_identity_bustout` family): PR-AUC
0.9866, recall 0.9775 @0.1% FPR / 0.9902 @1% FPR -- genuinely imperfect for the first time,
with feature importance spread across plausible graph/behavioural signals (`edge_count` 34%,
`beneficiary_added_ago_s` 15%, `edge_value_total` 6%) rather than one dominant proxy. The
held-out family is still caught 100% of the time, but this is no longer suspicious on its
own given the overall recall is no longer perfect -- flagged in `docs/model-choice.md` as a
plausible genuine generalisation result that a second held-out-family run should confirm,
not proof there's nothing left to find.

## Agents

2026-08-18: I8 done, merged as 54615a7 -- surfaced I15/I16 as a byproduct. D3
regulatory-limit verification done (merged) -- findings in
`docs/research/d3-regulatory-limits.md`; `docs/attack-catalogue.md`'s `⚠VERIFY` markers
resolved (UPI Lite, min-KYC PPI, mandate AFA confirmed against dated NPCI/RBI sources;
UPI P2M higher-limit circular number is the one remaining soft spot, flagged in the D3
fix-log row, not blocking). Evidence pass on high-confidence catalogue entries (D5)
done and merged. I6/I7 done and merged, plus I17 found and fixed along the way (see the
I6/I7/I17 detail section above) -- worktree agent-a904152c83fccef4d cleaned up.

I9's imports are in on main but the split-logic swap in
`train_attack_classifier.py` is not done yet -- next session should finish that rather
than re-verify the imports.

Remaining work is now genuinely new ground (I12/I13 mandatory deliverables, I11 closed
loop, I15/I16 generator calibration) rather than fixes to something already attempted --
check this file's "Next tasks" list before dispatching new agents.
