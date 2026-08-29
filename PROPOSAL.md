# Chakravyuh - Solution Proposal

**Mastercard Innovation Challenge 2026 - AI Defense Lab for Payment Security**
Global Fintech Fest 2026, Mumbai

This document is the full, chronological account of how Chakravyuh was built: what
problem we were actually solving, the order we solved it in, the decisions we made
at each step and why, the alternatives we rejected and why, and the evidence that
what we built works. It is written to be turned into the mandatory Solution
Walkthrough submission (.docx/.pptx/.pdf), so it is deliberately complete rather
than brief - every claim below is backed by a real file, a real number, or a real
test in this repository.

---

## 0. The brief, and the trap inside it

The challenge asks for one closed-loop system that plays both attacker and
defender against GenAI-enabled payment fraud, scored on three pillars:

| Pillar | What it must do | Scored on |
|---|---|---|
| **Identify** | Map emerging GenAI-powered payment fraud vectors | Diversity of attacks |
| **Generate** | Simulate those attacks at scale as synthetic data | Fidelity to real payment data |
| **Defend** | Detect them with an ML model | Precision, recall, F1/AUC, low false-positive rate |

Plus two cross-cutting criteria: novelty of the overall solution, and real-world
feasibility in live payments.

The brief itself names the trap directly: *"Most submissions will do 'fake fraud →
train model → 0.98 AUC,' which is circular and judges know it."* If you write the
fraud generator and the detector yourself, of course the detector looks good - it
was trained on exactly the patterns it's being tested against. A 99% accuracy
number produced this way proves nothing except that the two halves of your own
code agree with each other.

We treated this as the central design constraint, not a footnote. Three decisions
followed directly from taking it seriously, and they shape everything below:

1. **The attack catalogue had to be derived from how payment rails actually work,
   not invented.** If attacks come from imagination, "diversity" is just however
   many ideas we had time to write down. If attacks come from systematically
   breaking down where each payment rail's trust assumptions are weak, diversity
   becomes a measurable property of the rail itself, not of our creativity.
2. **The detector had to be evaluated in a way that could fail.** A held-out attack
   family, a temporal (not random) train/test split, and precision reported at a
   fixed, tight false-positive rate - all three make it possible for the numbers to
   come back bad. We report them anyway, including the times they did.
3. **The loop had to actually run, not just be described.** "The defence's blind
   spots generate new attacks" is a sentence in the brief. We built the code path
   that makes it literally true: a script reads the current model's feature
   importances, derives a harder attack configuration from them, and the next
   training run uses it automatically. Section 5 shows this measured, twice.

---

## Phase 1 - Identify: deriving attacks instead of imagining them

### 1.1 The method

Rather than brainstorming a list of "AI fraud ideas," we ran a five-step
derivation process against the actual mechanics of each payment rail (full detail
in [`docs/master-project-brief.md`](docs/master-project-brief.md)):

1. **Decompose the rail** into its lifecycle steps across five phases: initiate →
   authenticate → authorise → settle → dispute.
2. **Build the trust map** - at every step, who trusts whom, on what assumption,
   verified by what mechanism.
3. **Break each trust anchor** - can the human be manipulated? Can the automated
   check be fooled, flooded, or probed? What did generative AI just make cheap?
4. **Apply the actor lens** - re-run every flow for each kind of attacker: an
   outsider with stolen credentials, an outsider with only a phone, the genuine
   customer themself (acting under deception), a fraudulent merchant, a
   compromised merchant, an insider, an AI agent, a coordinated network.
5. **Invert** - deliberately look for attacks that keep every conventional fraud
   signal (velocity, new beneficiary, geography, device, amount) looking
   completely normal. This is where the genuinely novel attacks live, because it's
   exactly what a signal-based detector can't see by construction.

We rated every trust anchor on a four-level verification-strength ladder - this
turned out to be the single most useful output of the whole research phase,
because it tells you *where* to look instead of leaving it to intuition:

| Code | Meaning |
|---|---|
| **V3** | Cryptographic or deterministic |
| **V2** | Probabilistic - a rules engine or ML model scores it |
| **V1** | One-shot or self-asserted, checked once and never re-verified |
| **V0** | Nothing verifies it at all |

V0 and V1 anchors are where conventional fraud attacks concentrate. V2 is the
adversarial-ML surface - the part an attacker probes and adapts against. V3 is
almost never attacked directly. You attack the human holding the key instead.

### 1.2 Why this matters more than it sounds like it should

Running this ladder against UPI produced the finding that shaped the entire rest
of the project: **the UPI PIN proves the wrong thing.**

The cryptography behind PIN entry is sound - V3, genuinely unbreakable at that
layer. It proves that someone who knew the PIN pressed the keys on the bound
device. It says *nothing* about whether that person understood what they were
authorising, or was doing it freely. Every major Indian scam pattern - the fake
"digital arrest" call, the fake KYC-expiry message, the fake refund reversal, the
romance scam, the fake job-task payment - converges on exactly this gap. A V3
mechanism is sitting on top of a V0 inference. Generative AI's cheapest new
capability (persuasion and impersonation at scale, via cloned voices and
personalised scripts) points directly at the one part of the system that was never
verifying intent in the first place.

This single finding produces a genuinely hard detection problem, and it's why the
project's framing is "intent detection," not "anomaly detection": in a
scam-induced payment, the customer is real, the device is real, the location is
real, and the PIN is correct. Every column a conventional fraud model checks comes
back normal. **The only thing wrong is why the person is sending the money - and
that appears in no standard transaction-table column.** Section 2.3 explains what
we did about that.

Two more findings from the same pass shaped the evaluation design, not just the
attack list:

- **UPI credits are irreversible.** There is no chargeback mechanism. Recovery
  depends on a lien being placed faster than the funds move on. This means a
  detector that only flags fraud *after* the fact is a reporting tool, not a
  control - so the whole system had to be designed around pre-authorisation,
  sub-second decisioning, not post-hoc analysis.
- **Authorised-but-deceived payments fall outside India's zero-liability
  framework.** RBI's zero-liability rules cover *unauthorised* transactions. A
  push payment made under deception is, on the record, authorised by the account
  holder. This is a real structural gap in the rail, and it's also why there's
  little economic pressure on the ecosystem to have already solved this - which
  is exactly the kind of gap a challenge like this should be pointed at.

### 1.3 What came out: 58 catalogue entries → 16 generator families

The raw research pass produced 58 distinct catalogue entries across card
(card-not-present and card-present), UPI (P2P, P2M, mandates, Lite), IMPS/NEFT/RTGS,
wallets, and BNPL. Several of those entries turned out to produce **identical
observable data signatures** under different cover stories - a "digital arrest"
call and a "KYC expiry" message look the same in the transaction log: genuine
device, correct PIN, a brand-new beneficiary, an escalating amount, and coercion
session fields. Building five separate simulators for five stories that produce
the same data would inflate the catalogue's diversity number without adding
anything a detector could actually learn to tell apart.

**Decision: keep all catalogue rows for the diversity count (the stories are
genuinely different, and a judge can see that), but collapse them into one
generator per distinct data signature, parameterised by a `pretext` field where
the story differs.** This produced 13 initial generator families. Three more were
added later, grounded directly in well documented fraud mechanisms rather than
invented from scratch - `device_fan_out` (one compromised device draining
several distinct cards in a tight window, a documented top-tier predictive
signal in fraud detection research), `balance_drain_exit` (receive-then-drain,
a well documented account-takeover mechanism: transfer in, then rapid
cash-out), and `tpap_account_switch` (a single UPI handle drained across several of its linked
bank accounts by rotating between third-party payment apps - a structural gap
that exists because NPCI's own UPI architecture deliberately allows one VPA to
route through multiple apps to multiple linked accounts, which means no single
bank's fraud system ever sees the whole pattern). **Final count: 16 distinct
generator families**, listed with their reasoning in
[`docs/attack-catalogue.md`](docs/attack-catalogue.md) and implemented in
[`src/attacks/generators.py`](src/attacks/generators.py).

### 1.4 We audited our own research, and found real mistakes

Before freezing the catalogue we ran a defect pass against the first draft, and it
surfaced genuine errors - the kind that would have cost real credibility with a
judge who knows the domain:

- **A structural change we'd missed.** UPI P2P collect requests were discontinued
  across the network on 1 October 2025 (NPCI circular, 29 July 2025) after a ₹2,000
  cap and 50/day limit failed to stop abuse. Four catalogue entries were built on
  an attack surface that no longer exists. We rewrote the affected entry as
  merchant-collect impersonation (the trust anchor didn't disappear, it moved -
  see 1.2's framing) and relabelled the rest historical rather than quietly
  deleting the evidence that we caught it.
- **A wrong headline statistic.** An early draft cited "₹1,750+ crore lost to
  digital arrest scams, Jan–Apr 2024." The correct I4C-reported figure for that
  category in that window is ₹120.30 crore. The larger number was total cyber
  fraud losses across *all* categories, not digital arrest specifically. Getting
  a citation like this wrong in front of judges who follow this space would have
  cost more credibility than three missing attack types - so we corrected it and
  documented the correction rather than papering over it.
- **Stale regulatory limits.** An early entry was built on "sub-₹200
  transactions" and a "₹2,000 wallet cap" for UPI Lite, both outdated by the time
  we checked. We re-verified every hardcoded regulatory number against current
  NPCI/RBI sources:
  - UPI Lite: ₹1,000/transaction, ₹5,000/wallet
  - Minimum-KYC PPI: ₹10,000/month and balance
  - Mandate AFA: ₹15,000 general, ₹1,00,000 for mutual-fund/insurance/credit-card-bill categories

  We also added a rule to the project's own coding standards: no hardcoded
  regulatory limit without a dated comment citing its source, because these
  change and a stale number silently becomes a defect later.

Full defect log in `docs/attack-catalogue.md`'s fix table. We're including this
section deliberately: a submission that shows its own error-correction process is
more credible than one that presents a first draft as if it arrived correct.

---

## Phase 2 - Generate: making the fraud believable, not just labelled

### 2.1 Why the *background* traffic matters more than the attacks

The single most common mistake in a fraud-simulation submission - and something we
kept front-of-mind throughout - is spending all the effort on the attacks and
treating the legitimate traffic as an afterthought. If the legitimate population
is a crude approximation, an attack doesn't need to be realistic to stand out from
it. It just needs to be *different*, and the detector learns to separate two
trivially distinguishable distributions rather than learning to catch fraud.

**Decision: build the legitimate base population first, and calibrate its amount
and category distributions to plausible real-world shapes before writing a
single attack generator.** This is the opposite of the natural build order (attacks
are the interesting part), and it's slower up front, but it's what makes the
"fidelity to real payment data" score defensible rather than assumed.

### 2.2 The seven-table schema, and the rule that constrains every field

Generator and detector share one canonical schema -
[`docs/data-schema-v1.md`](docs/data-schema-v1.md) - seven tables:
`transactions`, `parties`, `merchants`, `mandates`, `disputes`, `graph_edges`,
`labels`.

One rule governs every field that goes into it: **only include a field a real
payment system would actually have at the moment of scoring a transaction.** If an
issuer or PSP wouldn't have it available at decision time, it doesn't belong,
because otherwise the detector learns from information a live system never sees,
and the "real-world feasibility" score collapses the moment a judge asks how this
would actually be deployed. This ruled out several tempting shortcuts - e.g. no
field that encodes the *outcome* of a dispute investigation on a transaction that
hasn't been disputed yet.

The fields that turned out to matter most are exactly the ones the Phase 1 finding
about intent predicts: `time_on_confirm_screen_s`, `screen_share_active`,
`call_active_during_txn`, `accessibility_service_active`, `beneficiary_added_ago_s`.
These are the only place in the schema where the V0 inference above the PIN
becomes something a model can actually measure.

### 2.3 Generating fraud that doesn't look like fraud

For every attack generator, we also generate its **lookalike population** - a
matched set of legitimate transactions that share the attack's surface shape (same
rail, same amount range, same general pattern) but are genuinely not fraud: a real
emergency transfer, a real first-time merchant, a real thin-file BNPL borrower.

This is not optional polish. Without it, a classifier separates two trivially
different distributions and reports a 0.99 AUC that means nothing - any judge with
payments experience catches this within thirty seconds. We treated "every
generator must emit its own lookalikes" as a hard requirement, not a nice-to-have,
enforced by test coverage.

### 2.4 We found and fixed three ways our own generator was cheating

Partway through building the detector (Phase 3), the numbers looked *too* good -
suspiciously good, in the specific way the brief warns about. Rather than treating
that as success, we went looking for why, and found three real, compounding
leaks in the generator code (documented in full in
[`docs/model-choice.md`](docs/model-choice.md)):

1. **Shallow-copy lookalikes.** `make_legit_lookalike_rows` was reusing the source
   fraud row's *exact* payer/payee pair and timestamp for its "legitimate"
   counterpart - meaning the lookalike wasn't actually an independent legitimate
   transaction, it was the fraud row with the label flipped. Fixed: lookalikes now
   draw an independently plausible counterparty and an independently resampled
   timestamp, keeping only the surface shape.
2. **Campaign structure as a near-perfect tell.** Several generators - including
   `adversarial_evasion`, the family specifically built to *avoid* looking
   detectable - were routing every event through one fixed, brand-new
   payer/payee pair, which is itself a dead giveaway pattern no real evasive
   attacker would use. Fixed to route through a small pool of the payer's
   genuinely pre-existing counterparties instead. Finding this also surfaced a
   duplicate-seed bug in the scenario expansion logic that was silently
   corrupting ~3,200 rows across unrelated families via colliding `txn_id`s -
   fixed at the same time.
3. **A hardcoded IP field.** Every attack row (and, transitively, every
   shallow-copy-era lookalike) was defaulting to the exact same `ip_asn` value,
   while the legitimate generator drew from five. Any row with a *different* ASN
   was, by pure accident of the code, guaranteed legitimate - a leak invisible
   until we inspected feature importances directly and asked why one field was
   doing so much work.

**We're describing our own bugs in this document on purpose.** The alternative -
quietly fixing them and presenting only the final numbers - would have made the
submission look cleaner but would have hidden the actual engineering rigor: we
didn't just build a pipeline that produces a good number, we caught the pipeline
lying to us and fixed it before trusting the result. Section 3.3 shows the honest
before/after.

---

## Phase 3 - Defend: building a detector that can be wrong, and knowing where

### 3.1 Why XGBoost, and what we tested it against

`stage5/training/train_fraud_model.py` fits Logistic Regression, Random Forest,
and XGBoost side-by-side on the *same* temporal split and picks a winner on
validation PR-AUC, rather than assuming a model choice. Full comparison in
[`docs/model-choice.md`](docs/model-choice.md).

The most informative result wasn't the two tree models - it was how far behind
Logistic Regression finished. A linear model can't combine
`screen_share_active`, `call_active_during_txn`, and `beneficiary_first_time`
into the joint condition that actually signals coercion. It can only weight each
one independently. The gap between linear and tree-based models is empirical
confirmation of something Phase 1 already argued qualitatively: **detecting a
scam-induced payment is an interaction-detection problem, not a linear-scoring
problem.**

Random Forest and XGBoost came out close on raw validation PR-AUC. We picked
XGBoost anyway, for reasons the validation number alone doesn't capture, all of
which trace back to the real deployment constraints Phase 1 established:

- **Latency.** UPI detection has to be pre-authorisation and sub-second (section
  1.2). A gradient-boosted ensemble at 150 shallow trees scores a row in
  microseconds. A Random Forest matching the same accuracy typically needs a
  larger, deeper forest for no accuracy gain here.
- **Class imbalance.** Fraud prevalence is well under 1%. XGBoost's
  `scale_pos_weight` reweights the loss function directly, while Random Forest's
  `class_weight="balanced"` is a coarser per-tree adjustment.
- **Explainability.** The system generates a per-transaction analyst narrative
  (Phase 4). XGBoost has fast, mature SHAP support for turning a score into "these
  specific features drove this decision" - the exact evidence a fraud analyst
  needs to act on an alert, and cheaper to compute than SHAP over an
  equivalently-sized Random Forest.
- **Calibrated operating points.** The evaluation harness is built around
  precision/recall at *fixed* false-positive-rate thresholds (0.1%, 1%), not a
  single classification boundary. Gradient-boosting probability outputs hold up
  better under threshold sweeps than Random Forest's vote-fraction estimates,
  which cluster and make fine-grained FPR targeting noisier.

We're explicit in our own documentation that XGBoost is not a novel choice - it
isn't, and claiming otherwise would be exactly the kind of unearned novelty claim
that hurts credibility. It's the standard, defensible choice for tabular fraud
data under extreme class imbalance with a hard latency budget, picked via a real
side-by-side comparison rather than assumed.

### 3.2 The evaluation design - built to be able to fail

Three rules govern how the detector is evaluated, chosen specifically because each
one closes off a way the numbers could look better than the system actually is:

1. **Temporal split, never random.** Train on the earlier portion of the
   simulation window, test on the later portion. A random split leaks campaign
   structure across the train/test boundary and inflates every metric.
2. **Precision reported at fixed, low false-positive rate - not just AUC.**
   Because UPI credits are final (section 1.2), a detector that's only good "on
   average" isn't good enough. What matters is how well it performs at the tight
   operating point a real deployment would actually use. We report precision and
   recall at 0.1% and 1% FPR as the headline numbers, with ROC-AUC as secondary
   only.
3. **One attack family held out entirely from training.** `synthetic_identity_bustout`
   never appears in train or validation data - it exists purely to answer "does
   this model generalise to a structurally unseen attack, or did it just memorise
   the families it was shown?"

### 3.3 The honest numbers, including the ones that got worse before they got better

After the three generator leaks in section 2.4 were fixed, the detector's numbers
became **genuinely imperfect for the first time** - and we treat that as the
correct outcome, not a regression to explain away:

| Model | Validation PR-AUC (before fixes) | Validation PR-AUC (after fixes) |
|---|---|---|
| Logistic Regression | 0.6367 | 0.8487 |
| Random Forest | 0.9994 | 0.9410 |
| XGBoost | 0.9983 | 0.9710 |

Test set (post-fix, current model): PR-AUC 0.9866. At 0.1% FPR: precision 0.8406,
recall 0.9775. At 1% FPR: precision 0.4384, recall 0.9902. At the F1-optimal
threshold: precision 0.9942, recall 0.9663, 4.99 alerts per 1,000 transactions.

The held-out `synthetic_identity_bustout` family is still caught at 100% (307/307)
at both fixed-FPR thresholds - but unlike the pre-fix numbers, this is no longer
suspicious on its own, *because the overall recall is now genuinely imperfect*
(0.9775 / 0.9902, not 1.0). The model demonstrably can miss fraud. It simply isn't
missing this particular held-out family, which is a plausible result if bust-out's
graph and behavioural signature (a credit-building phase followed by a sudden
utilisation spike) genuinely transfers from the patterns learned on the other 15
families. We report this as a headline generalisation result without overselling
it as proof there's nothing left to find.

Feature importance after the fixes is spread across plausible signals rather than
concentrated in one dominant proxy - `edge_count` (34%), `beneficiary_added_ago_s`
(15%), `edge_value_total` (6%), `is_two_hop_passthrough` (4.6%), then a long tail
of session and behavioural features. These are exactly the graph-based mule
discriminators Phase 1's research named as strongest - not an artifact of a
leaky pipeline, because the leaks that would have produced an artifact like this
are the ones we found and closed in section 2.4.

---

## Phase 4 - Making the detector's decisions legible

A model that outputs a probability is not, by itself, something a fraud analyst
can act on. Two things had to sit on top of the raw score before this became a
usable system:

- **SHAP-based per-transaction attribution.** Every scored transaction returns
  not just a probability but the specific features that drove it - exactly the
  "these fields, this direction, this magnitude" evidence an analyst needs to
  decide whether to act on an alert, and part of why XGBoost was chosen over
  Random Forest in the first place (section 3.1).
- **An optional GenAI-written analyst narrative.** `stage5/inference/pipeline.py`
  can turn the SHAP output into a plain-language explanation via the Gemini API,
  with a deterministic template fallback when no key is configured or the call
  fails. This is explicitly optional and off by default (see
  [`README.md`](README.md)'s caveats section) - the fraud-detection pipeline
  itself never depends on it, only the narrative layer does, and it never
  touches real payment or personal data.

These two pieces are what turn "a model scored this 0.94" into something a human
analyst can actually use to decide what to do next - which is the actual point
of the "real-world feasibility" criterion, not just a UI nicety.

---

## Phase 5 - Closing the loop: measured, not just described

This is the part of the brief that most submissions treat as a diagram rather
than working code: *"Attacks become training data for the defence; the defence's
blind spots generate new attacks."* Full detail and the raw numbers are in
[`docs/closed-loop.md`](docs/closed-loop.md). This section summarises the
mechanism and the result.

### 5.1 Finding the actual blind spot

Section 3.3's feature-importance table said the model had effectively become a
graph-relationship detector first, everything else second. That's defensible -
graph structure genuinely is the strongest mule-fraud signal - but it also
predicts the model's own blind spot precisely: **any attack that keeps its graph
footprint (`edge_count`, `beneficiary_added_ago_s`) inside the range a legitimate
transaction would show is under-weighted by everything else the model has to work
with.**

Two families are structurally exempt from this discussion, and we say so
explicitly rather than quietly filing them as future work: `first_party_dispute`
(the transaction is fully genuine at the time it happens - there is nothing to
detect at transaction time, by the attack's own definition) and `insider_abuse`
(no external anomaly exists by construction). No amount of transaction-time
feature engineering closes those. They need routing to an entirely different
detection stage (post-settlement dispute-history analysis, access-pattern
monitoring) - and the schema's `labels.detectable_at` field already models this
distinction. Chasing them with the fraud-scoring model would mean chasing a
result the schema itself says isn't available at that stage.

### 5.2 Closing it automatically, not manually

`adversarial_evasion` - the family explicitly built to probe and evade detection
- is the natural vehicle for the next generation, rather than inventing a new
attack. `stage5/training/build_adaptive_attack_config.py` is the piece of code
that actually closes the loop end-to-end: it loads whichever model is currently
saved, checks its `feature_importances_` against a 10% threshold, and derives two
config values from whatever clears that bar:

- `adaptive_top_counterparty=True` - route every campaign event through the
  payer's single busiest existing relationship, rather than spreading across a
  small pool. A relationship that already has a high `edge_count` barely moves,
  proportionally, when a few more fraudulent transactions land on it.
- `beneficiary_age_floor_s` - push the minimum beneficiary age toward the
  legitimate population's typical maximum, directly countering the
  second-ranked feature.

On the very first run, no model exists yet, the function returns `{}`, and static
defaults apply - the mechanism degrades gracefully rather than requiring a
bootstrapped model to exist first. On every subsequent run, the next batch of
`adversarial_evasion` campaigns automatically targets whatever the *current*
detector actually leans on. No manual step, no human deciding what the next
attack should look like.

### 5.3 The measured result

**Generation 1** (no prior model, static defaults applied): test PR-AUC 0.9972,
recall at 0.10% FPR 0.9942. Consistent with section 5.1's diagnosis, the gap was
driven by `adversarial_evasion` hiding inside the legitimate graph footprint.

**Generation 2**: `build_adaptive_config()` read generation 1's saved model and
correctly derived `{adaptive_top_counterparty: True, beneficiary_age_floor_s:
50578560}` (≈585 days - both features cleared the threshold). The next data-
generation run applied this automatically to every `adversarial_evasion`
campaign, and the retrained model was evaluated the same way.

**Result: test PR-AUC improved to 0.9997, and recall at 0.10% FPR reached a
perfect 1.0000.** The detector, without a human writing a new attack by hand,
adapted to close the exact gap its own feature importances had identified.

**A bug the measurement itself caught.** During this comparison, an earlier
measurement run showed `adversarial_evasion`'s test-window sample size drop from
38 rows to 7 between generations - a shared-RNG-state desync between two parts of
the generator that happened to collide. We found it because the loop-closing
measurement looked wrong, traced it to the root cause, fixed it by giving the
payee-pool selection its own independently seeded random stream, and re-ran the
comparison clean. **We're including this because it's the loop working on our own
code, not only on the detector** - the discipline of measuring before and after
a change caught a real correctness bug that would otherwise have silently
under-sampled one attack family in every future run.

---

## What we chose not to build, and why

A submission that only lists what it built is less trustworthy than one that also
says what it looked at and declined, with reasons. Three examples:

**A rule-based patch for the mule-network blind spot, instead of retraining.**
Stress-testing the deployed model with the two textbook mule signatures
(`is_two_hop_passthrough=1.0` and heavy beneficiary fan-in, `payee_in_degree=85`)
while keeping the payer's own out-degree unremarkable scored the transaction at
**0.02% fraud probability** - essentially undetected. We investigated a
threshold-based rule on `payee_in_degree` as a quick fix and rejected it: the real
training distribution's legitimate merchant fan-in has a median of 266 and a max
over 10,000, so any threshold tight enough to catch the mule pattern would flag
enormous numbers of legitimate merchants. `is_two_hop_passthrough` alone occurs in
16.9% of *all* edges - routine legitimate P2P activity routinely looks two-hop.
Neither field is usable as a standalone rule without a much more expensive
rail-conditioned analysis we couldn't safely verify in the time available. The
honest fix - retraining with class-weighted sampling or explicit feature-masking
on `mule_network` rows to force reliance on graph structure - is documented as
deferred, not silently shipped as "solved."

**Building a 17th attack family for AutoPay dark-pattern mandate renewal.** This
is a real, GenAI-era attack shape: an LLM-generated mandate-renewal prompt worded
to obscure that a recurring payment is being extended or its cap raised. We
identified it during Phase 1's derivation process and chose not to build it,
because doing so honestly would require either real captured consent-UI copy (which
we don't have and won't fabricate) or an invented "disclosure clarity" score with
no grounding in any published dataset - unlike all 16 built families, which trace
to a real structural signature or a reference dataset. We'd rather document a real
gap than ship a weakly-grounded family that looks like padding.

**Leaving the live demo API's explainability surface undefended.** Probing our
own `/api/analyze` endpoint surfaced a real model-extraction exposure: no rate
limiting, full floating-point-precision probabilities on every response, and
complete per-feature SHAP contributions on every call - together enough for an
attacker to binary-search the decision boundary or approximately reconstruct
feature weights via query access alone. We fixed one related bug found during the
same probe (a CORS misconfiguration that would reflect any origin with
credentials enabled) but left the extraction surface itself undefended
deliberately: full SHAP output is the entire point of the public explainability
demo, and rate limiting or response quantization are infrastructure changes better
scoped as a deliberate follow-up than bolted on under deadline pressure. We red-
teamed our own prototype the same way we red-team the payment rails, and we're
documenting what we found rather than assuming judges won't probe it.

---

## Where we believe the marks actually are, and why

- **Diversity** - 16 generator families, each traced to a documented trust-anchor
  break or a well documented fraud mechanism, not invented. The catalogue's
  coverage matrix shows genuine structural gaps (UPI has no consumer dispute
  remedy, card-present has no initiate-phase information exchange to exploit) and
  reports them as structural rather than papering over them as missing work.
- **Fidelity** - calibrated on the *background* traffic, not the attacks, because
  a detector's numbers only mean something if the population it's tested against
  resembles reality.
- **Detection efficacy** - precision and recall reported at a fixed, tight
  false-positive rate, on a temporal split, with one attack family held out
  entirely and caught at 100% - plus the honest admission that overall recall is
  genuinely imperfect (0.9775–0.9902, not 1.0) since the generator-leak fixes in
  Phase 2.4. An honest 0.98 is worth more than a suspicious 0.999.
- **Novelty** - the intent-detection framing (section 1.2): conventional models
  assume the attacker isn't the customer. In a scam-induced payment, everything
  about the transaction is genuine except the reason for it, and that reason
  appears in no standard column. And separately, a closed loop that's measured
  end-to-end (Phase 5), including a real correctness bug the measurement itself
  caught - not a diagram of a loop that was never actually run twice.
- **Real-world feasibility** - sub-second, CPU-only inference (XGBoost, ~450KB
  model, sub-2ms p99 latency), a pre-authorisation-first design driven directly by
  UPI's irrevocability (section 1.2), and an honest account of what a live
  deployment would cost in review-queue volume at a given operating point.

---

## Repository map

```
src/            Population + legitimate-traffic generator, attack injectors (Pillar 1 & 2)
stage5/         Feature engineering, model training, evaluation, closed-loop mechanism (Pillar 3)
web/            FastAPI backend + Next.js analyst-portal prototype (the "working web prototype" deliverable)
docs/           The full research trail - master brief, attack catalogue, data schema,
                model-choice comparison, closed-loop write-up
```

See [`README.md`](README.md) for how to actually run any of this.
