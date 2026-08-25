# Known limitation: legit-lookalike fidelity

**Status:** Confirmed, documented, deferred. Not fixed this cycle -- see rationale below.

## What we checked

The brief warns that without a hard-negative legitimate population, "the classifier
separates two trivially different distributions, reports 0.99 AUC, and any judge who
has worked in payments knows the number is meaningless within thirty seconds." The
held-out-family generalisation metric in `stage5/data/baseline_evaluation_report.json`
showed **100% recall with a zero-width 95% CI [1.0, 1.0]** on the held-out attack
family -- exactly the shape of result that warning predicts, so we checked it rather
than reported it at face value.

`stage5/validation/lookalike_fidelity_check.py` compares fraud rows, their paired
legit-lookalike rows, and the general legitimate population on the model's 50 numeric
features (std-scaled Euclidean centroid distances). Result
(`lookalike_fidelity_report.json`):

- Fraud <-> Lookalike distance: 8.79
- Lookalike <-> Legit distance: 4.15
- **Separation ratio: 2.12** (lookalikes sit over twice as close to the general
  legitimate population as to fraud)
- 98% of individual features have overlapping marginal ranges between fraud and
  lookalike -- the gap is in the *joint* combination, not any single feature

**Verdict: FAIL.** Lookalikes are not the hard negative the design intends.

## Root cause

`make_legit_lookalike_rows()` (`src/attacks/generators.py`) already does the right
thing at the row level: it matches the source fraud row's rail/channel/MCC/amount
scale, then gives it an independent counterparty and timestamp rather than a shallow
copy (this itself was a fix for an earlier, worse bug -- see the function's own
docstring, "I6").

What it can't do at the row level is replicate *behavioural context*. Fraud rows sit
inside a campaign that builds anomalous velocity/graph history over multiple prior
transactions -- `edge_count` and `beneficiary_added_ago_s` are the model's top two
features by importance precisely because that buildup is the strongest signal. A
lookalike is one shape-matched transaction dropped into an otherwise ordinary,
quiet account with no campaign behind it. The single row resembles fraud; the
account it's attached to doesn't.

## The correct fix (not attempted this cycle)

Lookalikes need their own synthetic pre-history threaded through the same
campaign-shaping logic fraud rows get -- not a fully separate campaign, but enough
synthetic prior activity that their velocity/graph features land in a similar range
to fraud's, instead of matching the ambient legitimate population. This is a
rearchitecture of how lookalikes relate to campaigns, not a parameter tweak.

## Why deferred rather than fixed now

Given the submission deadline, a rushed change to campaign/lookalike generation risks
introducing a new, less-understood bug in a part of the codebase that has already
been iterated on carefully once (see the "I6" and `payer_out_degree` regression notes
in `make_legit_lookalike_rows()`'s own docstring). Documenting the gap honestly --
what we measured, why it happens, and what the correct fix looks like -- is the
better use of remaining time than a same-day rearchitecture.

## How to read the model's current metrics in light of this

Any "held-out recall" or PR-AUC number from this codebase should be read as an
upper bound on real-world performance, not a calibrated estimate -- the detector has
not yet been tested against fraud that is behaviourally, not just superficially,
close to legitimate activity.
