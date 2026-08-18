# Reference statistics

Hand-authored, cited summary statistics from four well-known public payment/fraud
datasets, used by `src/validation/marginals.py` to check the generated legitimate
dataset's marginal distributions for plausibility. Per the project's hard rule
against runtime downloads, **none of the raw datasets are fetched or stored here** --
these files hold only small, publicly-documented summary numbers (counts, rates,
percentiles, category shares), each with a `source` and a `confidence` tag.

`confidence` values:

- `published` — a number stated directly on the dataset's own card/paper.
- `derived` — arithmetic on two `published` numbers from the same source (e.g. a rate
  from a count and a total), not itself a directly quoted figure.
- `reasoned_approximation` — a number repeated consistently across multiple
  independent public write-ups of the same well-known dataset, but not printed
  verbatim on the primary source itself. Treated as approximate, not exact.
- `qualitative_literature` — a shape/direction claim from general literature, used
  only for a non-numeric sanity check (see `general_notes.json`).

## Files

| File | Dataset | Strongest for | Explicitly not usable for |
|---|---|---|---|
| `ieee_cis.json` | IEEE-CIS Fraud Detection (Kaggle, 2019) | overall amount shape, base fraud-rate context | MCC, cardinality, temporal (no calendar epoch), inter-arrival, graph |
| `paysim.json` | PaySim mobile-money simulator | categorical cardinality (`type`, 5 values), coarse hour-of-day (`step mod 24`) | per-MCC amount, transactions-per-party, inter-arrival, graph |
| `banksim.json` | BankSim agent-based bank simulator | amount-per-category (`category` is the closest real MCC analog of the four) | transactions-per-party (population counts not independently reconfirmed), inter-arrival (day-only granularity), graph |
| `ulb_creditcard.json` | Credit Card Fraud Detection (ULB/Worldline) | overall amount shape only | everything else — PCA-anonymized, no categorical/party/graph fields exist at all |
| `general_notes.json` | *(not one of the four)* | qualitative-only sanity checks for temporal patterns and graph degree distribution, where none of the four datasets publish anything usable | numeric comparison of any kind |

## Coverage gaps, stated plainly

The six areas the validation report must cover are not equally well served by these
four datasets:

- **Amount distribution per MCC**: only `banksim.json`'s `category` field is a real
  MCC analog. IEEE-CIS/PaySim/ULB contribute overall-shape comparisons only (and in
  ULB's case, EUR vs INR values are never compared directly — only scale-invariant
  shape statistics are).
- **Inter-arrival time distribution**: none of the four publish a per-transaction
  timestamp series or a summarized inter-arrival distribution. `marginals.py`
  reports the generated dataset's own inter-arrival distribution descriptively and
  only sanity-checks its order of magnitude against derived, clearly-labelled
  quantities (e.g. PaySim's published transaction count over its published step
  count).
- **Categorical cardinality**: PaySim (`type`, 5) and BankSim (`category`, 15) give
  real cardinalities to compare against merchant/MCC/device cardinality shape (not
  value-for-value, since our vocabulary is India-specific MCCs, not PaySim/BankSim's
  category names).
- **Transactions per party**: none of the four publish a trustworthy per-customer
  transaction-count distribution we can cite with confidence (see each file's
  `applicability_notes`).
- **Temporal patterns (hour-of-day, day-of-week)**: IEEE-CIS and ULB have no
  calendar epoch at all; BankSim has day-only granularity; PaySim gives an hour
  proxy via `step mod 24` but no day-of-week signal. See `general_notes.json` for
  the qualitative-only fallback used for this area.
- **Graph degree distribution**: none of the four datasets publish any network
  structure. See `general_notes.json` for the qualitative-only fallback.

This is intentional and disclosed rather than papered over — see
`docs/attack-catalogue.md`'s fix log (defects D2/D5) for why this project treats
overclaimed precision as a defect, not a style issue.
