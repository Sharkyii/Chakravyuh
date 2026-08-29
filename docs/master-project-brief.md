# Mastercard Innovation Challenge 2026 - Master Project Brief

**AI Defense Lab for Payment Security** · Global Fintech Fest 2026, Mumbai
Status as of **13 August 2026** · Day 4 of 19

---

## 1. The challenge

Build **one closed-loop system** that plays both attacker and defender against GenAI-enabled payment fraud.

| Pillar | What it must do | Scored on |
|---|---|---|
| **Identify** | Map emerging GenAI-powered payment fraud vectors | Diversity of attacks |
| **Generate** | Simulate those attacks at scale as synthetic data | Fidelity to real payment data |
| **Defend** | Detect them with an ML model | Precision, recall, F1/AUC, low FPR |

Plus two cross-cutting criteria: **novelty of the overall solution** and **real-world feasibility in live payments**.

The loop is the point. Attacks become training data for the defence; the defence's blind spots generate new attacks. Most submissions will do "fake fraud → train model → 0.98 AUC," which is circular and judges know it.

### Scope

**In:** money moving through payment rails. Card CNP and card-present, UPI (P2P, P2M, collect, mandate, Lite, Circle), IMPS/NEFT/RTGS, cross-border remittance, wallets/PPI, BNPL, merchant onboarding and settlement, agentic commerce.

**Out:** securities and stock-market fraud, insider trading, credit underwriting fraud with no payment rail, generic cybersecurity.

### Deliverables - all three mandatory

1. **Code repository** - covering all three pillars, organised, documented, reproducible
2. **Solution walkthrough** - .pptx / .docx / .pdf: attacks found, generation method, detection results, real-world feasibility
3. **Working web prototype** - presentable UI demonstrating the closed loop live

Submitted through the **Writeups** section. Drafts do not count. Missing any one artifact invalidates the submission.

### Rules constraints

- Synthetic, anonymised or authorised sample data only. No real cardholder data, no PII, no production payment data.
- No adversarial testing against live systems, real payment infrastructure, or third parties.
- Team of 1–5, each member registered individually, one submission per team.
- Open-source dependencies must use an OSI-approved licence permitting commercial use.

### Prizes

₹2,56,000 / ₹1,28,000 / ₹64,000, plus a showcase slot at GFF 2026 (8–11 September, Jio World Centre, Mumbai).

---

## 2. Method - how the research was derived

Not brainstormed. Derived systematically, in five steps:

1. **Decompose the rails** into numbered lifecycle steps across five phases: initiate → authenticate → authorise → settle → dispute.
2. **Build the trust map** - for every step, who trusts whom, on what assumption, verified by what mechanism.
3. **Break each trust anchor** - can the human be manipulated? Can the automated check be fooled, flooded, probed? What did GenAI just make cheap?
4. **Apply the actor lens** - re-run each flow for outsider-with-credentials, outsider-with-only-a-phone, the customer themselves, fraudulent merchant, compromised merchant, insider, AI agent, coordinated network.
5. **Invert** - derive attacks that keep every conventional signal (velocity, new beneficiary, geo, device, amount) looking normal. This is where novelty lives.

### The verification-strength ladder

The single most useful output. Attacks concentrate where the rating is low.

| Code | Meaning |
|---|---|
| **V3** | Cryptographic or deterministic |
| **V2** | Probabilistic - a rules engine or ML model scores it |
| **V1** | One-shot or self-asserted; checked once and never re-run |
| **V0** | Nothing verifies it |

**V0 and V1 are the attack surface. V2 is the adversarial-ML surface. V3 is almost never attacked directly - you attack the human holding the key instead.**

---

## 3. What we found

### 3.1 The three findings that should shape the whole submission

**The UPI PIN proves the wrong proposition.** The cryptography is sound. It proves that someone who knows the PIN pressed the keys on the bound device. It says nothing about whether that person understood what they were authorising or was doing it freely. Every Indian scam typology - digital arrest, KYC expiry, refund reversal, investment, job task - converges on this one anchor. GenAI's cheapest new capability, persuasion and impersonation at scale, points directly at it. **V3 mechanism sitting on a V0 inference.**

**UPI credits are irreversible, so detection must be pre-authorisation.** There is no chargeback. Recovery depends on a lien placed faster than the funds are layered. A post-hoc detector on UPI is a reporting tool, not a control. This determines the entire Pillar 3 evaluation design.

**Authorised-but-deceived falls outside zero liability.** RBI's framework covers *unauthorised* transactions. A push payment made under deception is, on the record, authorised. This is the largest structural gap in the rail - and it removes the economic pressure that would otherwise force detection investment.

### 3.2 The five phases and what each trusts

| Phase | Core assumption | Typical strength |
|---|---|---|
| Initiate | The payer actually wants this | **V0** - nothing verifies intent |
| Authenticate | Possession proves identity | V1 - OTP is a bearer token a human can be talked into surrendering |
| Authorise | Past behaviour predicts intent | V2 - probabilistic, and cheaply queryable by an attacker |
| Settle | The merchant is who they claim | V1 - checked at onboarding, rarely re-verified |
| Dispute | The complainant is honest | **V0** - no verifier exists at claim time |

### 3.3 Card CNP - top V0 anchors

1. **CNP-06** self-asserted cardholder account data in the 3DS payload. Fields that directly raise the frictionless rate, filled in by the party who benefits from a high frictionless rate.
2. **CNP-08** challenge-UI authenticity. The OTP economy rests on a human distinguishing real from fake in a context engineered to be indistinguishable.
3. **CNP-18** the non-participation claim. No verifier, and the transaction sits perfectly inside the legitimate distribution because it *is* legitimate.
4. **CNP-10** the descriptor string. Enables both obscuring a fraudulent charge and manufacturing a plausible dispute against a real one.
5. **CNP-03** device fingerprint. Now cheap to synthesise *consistently across a fleet*, which is the part that used to be hard.

### 3.4 UPI - top V0 anchors

1. **UPI-P2P-05** the inference above the PIN (see 3.1).
2. **UPI-P2P-16** authorised-but-deceived outside zero liability.
3. **UPI-P2P-11** irrevocability.
4. **UPI-P2P-02** the resolved payee name. Authentic - it comes from the beneficiary bank's KYC record - but it proves nothing about whether that genuine person is who the payer meant to pay. Mule accounts are real accounts with real names.
5. **UPI-P2P-08** thin beneficiary-side controls relative to remitter-side. The structural reason mule accounts work.
6. **UPI Circle** delegation. First place in UPI where the authorising human and the account-owning human are deliberately different, and the log knows this only via a purpose code. Every attribution assumption in a fraud model breaks here.

### 3.5 Cross-rail: why this matters for the catalogue

| Dimension | Card CNP | UPI |
|---|---|---|
| Direction | Merchant pulls | Payer pushes |
| Auth vs authorisation | Separate; CAVV is a portable artifact | Fused; the PIN *is* the authorisation |
| Attacker needs | Stolen credentials or a merchant identity | The victim's cooperation, or a mule |
| Reversibility | High - months of chargeback rights | Effectively nil |
| Default liability | Issuer or merchant | Customer, whenever authorised |
| Detection timing | Can be post-hoc | Must be pre-authorisation, sub-second |

**Card CNP fraud is a credential and identity problem. UPI fraud is a persuasion problem.** GenAI's most disruptive capability maps far more directly onto UPI. Expect the India-weighted portion of the catalogue to cluster in initiate and authenticate; the card portion in authenticate, settle and dispute.

### 3.6 Structural change to account for

**P2P collect was discontinued across UPI from 1 October 2025** (NPCI circular 29 July 2025), after a ₹2,000 cap and 50/day limit failed to stop abuse. Merchant collect survives.

The trust anchor did not disappear - it moved. The mental-model inversion that made collect dangerous (payer believes they are receiving, and is in fact approving a debit) now requires the attacker to be or impersonate a merchant. That redirects a whole attack family into **merchant onboarding and merchant-identity spoofing**, which makes KYB more important than it looked at the start.

---

## 4. Research output status

Five runs were planned. Here is what came back.

| Run | Planned | Delivered |
|---|---|---|
| 1 - rails and trust map | Card CNP + UPI skeleton | **Done, high quality.** 22 CNP steps, 25 UPI steps, every anchor rated |
| 2 - attack derivation | Steps 3–4 against the skeleton | Collapsed into one pass with 3, 4, 5 |
| 3 - remaining rails | Wallets, mandates, onboarding, agentic | Covered, but shallower |
| 4 - inversion pass | Standalone novelty run | Present as a section, not a dedicated pass |
| 5 - evidence pass | Verified citations per attack | **Effectively did not happen.** Citations gesture at source categories, not verified specifics |

**Output:** 58 catalogue entries, 15 expanded cards, a coverage matrix across rails × phases and rails × GenAI capability, an inversion section, a confidence assessment.

**One document in the batch is not ours** - a generic research-plan template recommending climate adaptation in agriculture. A tool ran without the prompt attached. Discard; keep it out of the repo.

### Coverage achieved

Rails × phases matrix is populated with documented gaps. Genuinely sparse and correctly reported as structural rather than missing: UPI × dispute (the rail has no consumer dispute remedy), card-present × initiate (no information exchange to exploit), agentic × settle/dispute (infrastructure doesn't exist yet).

---

## 5. Known defects - fix before building

### D1 - Catalogue contradicts Run 1 on collect
Four entries treat P2P collect as live: `COLLECTFLOOD-01`, `VOICECLONE-01`, `MASSPERS-01`, `MANDATEBLUR-01`. Expanded Card 7's entire attack chain is a P2P collect flow. **Rewrite Card 7 as merchant-collect impersonation; label the rest historical.** A judge who knows UPI catches this immediately.

### D2 - Wrong statistic in the headline card
Card 1 claims ₹1,750+ crore lost to digital arrest in Jan–Apr 2024. The correct I4C figure is **₹120.30 crore**; ~₹1,776 crore was total cyber fraud losses across all categories in that window. If a larger number is wanted, the nine-month 2024 digital-arrest figure was ₹1,616 crore across 63,481 complaints. **Audit every other number the same way** - one wrong statistic costs more credibility than three missing attacks.

### D3 - Stale rail parameters
`LITESPLIT-01` is built on "sub-₹200" transactions and a "₹2,000 wallet cap" - both outdated. Verify against current NPCI/RBI pages before hardcoding: UPI Lite per-transaction and balance limits, minimum-KYC PPI caps, UPI AutoPay AFA thresholds by category, P2M daily limits.

### D4 - Unmerged pretexts
`DIGITALARREST-01`, `KYCEXPIRY-01`, `SE-DEEPFAKEBANK-01`, `ROMANCE-01`, `JOBSCAM-01` have effectively identical observable signals - victim authorises correctly from their own device, funds land in a young mule with fan-in. **One attack, five pretexts.** Keep all five rows for the deck's diversity score; the simulator gets one generator with a `pretext` parameter.

### D5 - Evidence pass incomplete
Assume more unverified claims. Every citation in the walkthrough deck must resolve to a real, dated source.

**Net effect on the build:** 58 catalogue entries should collapse to roughly **12–15 distinct generators**.

---

## 6. Architecture

```
attack catalogue (frozen)
        │
        ▼
base population generator ──► parties, devices, merchants
        │
        ▼
legitimate transaction generator ──► background traffic + legit lookalikes
        │
        ▼
attack injectors (12–15) ──► labelled fraud + campaign structure
        │
        ▼
canonical dataset (7 tables)
        │
        ├──► detector (GBM baseline + graph/sequence layer)
        │         │
        │         ▼
        │    evaluation harness ──► precision @ fixed FPR, PR-AUC
        │         │
        │         ▼
        │    failure analysis ──► which attacks slipped through
        │         │
        └─────────┘  feedback: misses drive new attack variants
                  │
                  ▼
            web prototype (visualises the loop)
```

### Data schema

Seven tables - `transactions`, `parties`, `merchants`, `mandates`, `disputes`, `graph_edges`, `labels`. Full field list in `data-schema-v1.md`.

**Design rule:** only fields a real payment system would have *at decision time*. If an issuer or PSP wouldn't have it at the moment of scoring, it doesn't belong - otherwise the detector learns from information a live system never sees, and real-world feasibility collapses under questioning.

**Highest-value fields**, because they are the only place the V0 inference above the PIN becomes measurable:
- `time_on_confirm_screen_s`
- `screen_share_active`
- `call_active_during_txn`
- `accessibility_service_active`
- `beneficiary_added_ago_s`

**Strongest mule discriminators:** `has_salary_credit`, `organic_spend_ratio`, `throughput_ratio_24h`, plus fan-in/fan-out from `graph_edges`.

### Three rules that decide whether this works

1. **Generate the lookalikes.** Every attack generator must also emit its legitimate near-neighbour population - genuine emergency transfers, festival remittances, honest new merchants, real thin-file BNPL users. Without them the classifier separates two trivially different distributions, reports 0.99 AUC, and any judge who has worked in payments knows the number is meaningless within thirty seconds.
2. **Split temporally, never randomly.** Train weeks 1–8, test 9–12. Random splits leak campaign structure across the boundary.
3. **Report precision at fixed low FPR.** Because UPI credits are final, lead with precision at 0.1% and 1% FPR, and PR-AUC. ROC-AUC secondary only.

---

## 7. Plan and timeline

**Today is 13 August. Submission closes 31 August, 11:59 PM IST. 18 days remain.**

| Dates | Phase | Output |
|---|---|---|
| 13–14 Aug | **Defect fixes + freeze prep** | D1–D5 resolved; every number sourced; catalogue collapsed to 12–15 generators |
| 15–17 Aug | **Base generator** | Party/device/merchant populations; legitimate traffic with credible marginals |
| **17 Aug** | **CATALOGUE FREEZE** | Whatever exists is what gets built |
| 18–21 Aug | **Attack injectors** | 12–15 generators, each emitting attack + lookalike + campaign structure + labels |
| 20 Aug | ⚠️ **Registration closes** | All team members registered on Kaggle |
| 22–24 Aug | **Detector + evaluation harness** | GBM baseline, then graph/sequence layer; harness reporting precision @ FPR |
| 25 Aug | **Close the loop** | One documented iteration: detector misses → new attack variant → detector improves |
| 25–29 Aug | **Web prototype** | Presentable UI demonstrating the closed loop live |
| 27–30 Aug | **Walkthrough deck** | Attacks, generation, detection results, feasibility |
| 30 Aug | **Buffer + dry run** | Full reproducibility check from a clean clone |
| **31 Aug** | **SUBMIT** | Do not aim for the deadline; aim for the 30th |
| 5 Sep | Results | |
| 8–11 Sep | GFF 2026, Mumbai | Shortlisted teams present |

### Effort split

Roughly **20% research, 50% build, 30% presentation**. Research is currently ~80% done and build is 0% done, which is the normal way this goes wrong. From here, everything produced should be code, not documents.

The prototype and deck are two of three required artifacts and consume a third of the calendar. Teams that treat them as an afterthought lose on completeness, not on modelling.

### Risks

| Risk | Mitigation |
|---|---|
| Research creep past the freeze date | Hard stop 17 Aug. Catalogue may grow only if code finishes early |
| Prototype rushed in the final 48h | Start it 25 Aug at the latest, in parallel with the deck |
| Circular evaluation (train and test on own attacks) | Lookalike populations; temporal splits; hold out one attack family entirely to test generalisation to unseen attacks |
| Unverified claims in the deck | Every number resolves to a dated source before it goes in a slide |
| Reproducibility failure at judging | Clean-clone run on 30 Aug; pinned dependencies; seeded randomness |

---

## 8. Where the marks actually are

**Diversity of attacks** - the coverage matrix, presented as a matrix. Show the gaps and explain which are structural.

**Fidelity** - the *background* traffic, not the attacks. Marginal distributions matching published datasets. Show the comparison plots.

**Detection efficacy** - precision at low FPR, on temporal splits, with a held-out attack family. An honest 0.82 beats a suspicious 0.99.

**Novelty** - two places. First, the inversion attacks that keep every conventional signal normal. Second, the intent-detection framing: conventional models assume the attacker is not the customer, and in a scam-induced payment everything is genuine - real customer, real device, real location, correct PIN. The only anomaly is intent, which appears in no standard column. Detecting it needs the session and coercion fields nobody puts in a transaction table.

**Real-world feasibility** - grounding in actual rail mechanics, correct current limits and regulations, sub-second pre-auth budget for UPI, and an honest account of what a live deployment would cost in false positives.

---

## 9. Immediate next actions

1. Fix D1–D5. Two hours, protects the whole submission.
2. Confirm all team members are registered before 20 August.
3. Stand up the repo skeleton with the seven-table schema.
4. Build the legitimate base generator - parties, devices, normal traffic - before any attack code.

Fidelity of the background is what makes the foreground believable. It is also the piece every team skips.
