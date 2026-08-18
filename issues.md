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
| I6 | OPEN | high | attacks | `legit_lookalike` rows are shallow copies of their source fraud row -- same payer/payee pair, same timestamp, only amount/session fields tweaked |
| I7 | OPEN | high | attacks + generators | Attack campaigns route multiple transactions through the same new counterparty within a short window, a pattern the legitimate generator doesn't produce on its own -- campaign shape alone is close to a perfect tell |
| I8 | FIXED (54615a7) | medium | validation | No validation report comparing generated data against IEEE-CIS/PaySim/BankSim/ULB reference marginals -- `data/reference/` is empty |
| I9 | OPEN | medium | detector | `train_attack_classifier.py` splits by random shuffled `campaign_id`, not temporally -- same bug class as I1, lower stakes (auxiliary model, not the judged detector) |
| I10 | OPEN | low | attacks | `LLMScenarioGenerator`/`HybridScenarioGenerator` call the Gemini API when `SCENARIO_GENERATOR_MODE` is `llm`/`hybrid` -- off by default but undocumented in AGENTS.md |
| I11 | OPEN | high | deliverable | Closed-loop iteration doc (misses -> new attack variant -> improved detector) doesn't exist |
| I12 | OPEN | high | deliverable | Web prototype -- mandatory submission artifact -- not started |
| I13 | OPEN | high | deliverable | Walkthrough deck -- mandatory submission artifact -- not started |
| I14 | OPEN | low | docs | `docs/attack-catalogue.md`'s "Outstanding before freeze" checklist is stale (D3 `⚠VERIFY` entries unresolved, evidence pass incomplete, legit_lookalike checkbox now actually true as of I4) |
| I15 | OPEN | medium | generators | Day-of-week histogram is perfectly flat (0.142-0.143 every day) -- `_timestamp()` in `src/generators/legitimate.py` draws uniformly across the 12-week window with an hour-of-day nudge only, no weekday effect. Contradicts the brief's own spec ("salary-day spikes, weekend patterns") and I8's committed reference stats. Found by I8's validation report. |
| I16 | OPEN | medium | generators | Amount medians are statistically indistinguishable across MCCs (~265-268 INR for grocery, fuel, and hotels alike) -- `_amount_for_rail()` in `src/generators/legitimate.py` conditions amount only on `rail` and `income_type`, never on `mcc`. BankSim's reference data (data/reference/banksim.json) documents category-conditioned amount shape (everyday categories cheap, travel/hotel expensive) that this doesn't reproduce. Found by I8's validation report. |

## Detail

### I6 -- legit_lookalike rows are structurally shallow

`src/attacks/generators.py`, `make_legit_lookalike_rows` (~line 85): builds each lookalike as
`variant = dict(row)` from the source fraud row, then overrides only `txn_id`, `amount`,
`beneficiary_first_time`, `time_on_confirm_screen_s`, `session_duration_s`,
`issuer_risk_score`, `decision`. `payer_id`, `payee_id`, and `timestamp` are untouched --
so the lookalike lands on the exact same counterparty pair at the exact same moment as
the fraud row it's shadowing, and inherits the same graph/temporal shape. It cannot serve
as the genuinely-hard negative the brief's "generate the lookalikes" rule assumes.

**Direction:** lookalike generation needs its own plausible counterparty and timing --
not derived from the attack row's identity, just its rough shape (similar amount scale,
similar rail/channel). Coordinate with I7 since they're the same underlying gap.

### I7 -- campaign structure is a near-perfect tell independent of family

Found via ablation (see conversation / `docs/model-choice.md`): dropping the dominant
feature (`inter_txn_time_min`, 92.5% importance) barely moved PR-AUC (0.999 -> 0.998);
`edge_count` and `beneficiary_added_ago_s` immediately took over as equally-perfect
substitutes. Root cause: most of the 13 generators route several transactions through
the same new counterparty within a tight window (minutes to low hours for most families;
see the `timedelta(...)` spacing in each `generate()`), a pattern the legitimate
generator's organic-counterparty model in `src/generators/legitimate.py` essentially
never produces. This makes "did >1 transaction happen between this pair recently"
close to a perfect classifier by itself, for any family, regardless of that family's
actual real-world detection difficulty per `docs/attack-catalogue.md`'s own ratings --
directly contradicts the catalogue's inversion-pass claims for STEALTH mandate,
FIRSTPARTY dispute, and ADVMODEL-PROBE, which are supposed to keep velocity/timing
signals looking normal.

**Direction:** either vary campaign event routing (not always the same fixed payee)
per family to match each attack's actual claimed signature, or accept that campaign
structure is a legitimate signal for some families (mule_network, card_testing_probe)
and explicitly exclude/soften it for the families whose catalogue entry claims it
should look normal.

## Agents

2026-08-18: four agents dispatched -- I6/I7 (combined, in progress), I8 (done, merged as
54615a7 -- surfaced I15/I16 as a byproduct), and two research agents (D3 regulatory-limit
verification, evidence pass on high-confidence catalogue entries) that were killed by
environment restarts before making any committed progress and will be re-dispatched.
Check worktree branches (`git branch | grep worktree-agent`) for status before starting
new work on the same files.
