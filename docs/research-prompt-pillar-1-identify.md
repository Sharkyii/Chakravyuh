# Research prompt — Pillar 1 (Identify)

Paste the block below into your research tool (Claude Research, ChatGPT Deep Research, Perplexity, or run it yourself section by section). Everything inside the fenced block is the prompt.

---

```
ROLE

You are a payments fraud research analyst with expertise in card networks, UPI/instant payment
rails, acquiring, KYC/onboarding, and adversarial machine learning. You are producing the
research foundation for a red-team/blue-team system that will simulate payment fraud attacks
and train a detector against them.


OBJECTIVE

Produce an exhaustive, structured catalogue of emerging and plausible GenAI-enabled payment
fraud attack vectors. The catalogue must be detailed enough that a software engineer can read
any single entry and immediately implement a simulator that generates synthetic transaction
data matching that attack's signature.

Target: 40-60 distinct attack vectors. Breadth and depth are both scored. Do not stop at the
obvious ten.


SCOPE

IN SCOPE — fraud where money moves through a payment rail:
  - Card payments: card-present, card-not-present, tokenized, contactless, recurring
  - UPI and instant rails: P2P, P2M, collect requests, QR, mandates, UPI Lite, UPI Circle
  - Bank transfers: IMPS, NEFT, RTGS, cross-border remittance
  - Wallets, prepaid instruments, BNPL, gift cards
  - Merchant-side: onboarding/KYB, settlement, refunds, chargebacks, transaction laundering
  - Consumer-side: social engineering, account takeover, mule networks, first-party fraud
  - Agentic commerce: AI shopping agents, delegated payment credentials, agent-to-agent payments

OUT OF SCOPE — do not include:
  - Securities, stock market, or insider trading fraud
  - Loan/credit underwriting fraud not involving a payment rail
  - Generic cybersecurity (ransomware, DDoS) unless it directly produces a fraudulent payment
  - Pure data breaches with no payment execution step

GEOGRAPHIC EMPHASIS: Global coverage, with deliberate over-weighting toward India (UPI, RBI
and NPCI regulatory context, Indian scam typologies such as digital arrest, KYC-expiry scams,
and mule account networks). Note explicitly which attacks are India-specific and which are
universal.


METHODOLOGY — derive attacks systematically, do not brainstorm

Step 1 — Decompose the rails.
For each rail in scope, write out the payment lifecycle as a numbered sequence of steps from
intent through to dispute resolution. Use the five-phase frame: initiate, authenticate,
authorise, settle, dispute. Identify every point where information or value changes hands.

Step 2 — Build the trust map.
For every numbered step, state explicitly:
  (a) who is trusting whom
  (b) what assumption that trust rests on
  (c) what mechanism verifies the assumption (and note where nothing verifies it)

Step 3 — Break each trust anchor.
For each trust anchor, ask:
  - Can the human in this step be manipulated into deciding wrongly?
  - Can the automated check be fooled, flooded, probed, or evaded?
  - What information asymmetry exists that an attacker can exploit?
  - What is harmless once but harmful at scale?
  - What did GenAI just make cheap that used to be expensive?
    (Consider: convincing text at scale; impersonating a specific known human by voice or video;
     generating documents, faces, and identities; autonomously operating a browser or app;
     probing and optimising against an ML model.)

Step 4 — Apply the actor lens.
Re-run each flow for each attacker type and record what changes:
  - outsider holding stolen credentials
  - outsider holding no data, only a phone and an LLM
  - the legitimate customer themselves (first-party / friendly fraud)
  - a fraudulent merchant created for the purpose
  - a legitimate merchant turned malicious or compromised
  - an insider at a bank, PSP, or merchant
  - an AI agent holding delegated payment authority
  - a coordinated network (mule rings, fraud-as-a-service operators)

Step 5 — Inversion for novelty.
List what conventional rule-based and ML defences look for: velocity, new beneficiary,
amount thresholds, geo mismatch, device change, time-of-day, known-bad lists. Then explicitly
derive attacks that keep every one of those signals looking normal. Attacks that sit inside
the legitimate distribution are the highest-value entries in this catalogue — flag them.


OUTPUT FORMAT

Deliver as a markdown table, plus one expanded card per attack for the top 15 by
novelty × feasibility. Every attack gets these fields:

  id                    Short slug, e.g. UPI-COLLECT-VOICECLONE-01
  name                  Plain-language name
  rail                  Which payment rail
  phase                 initiate | authenticate | authorise | settle | dispute
  trust_anchor_broken   The specific assumption that fails
  attacker_role         From the actor lens above
  genai_capability      Which AI capability makes this newly viable, and why it was hard before
  attack_chain          3-8 numbered steps, concrete and operational
  observable_signals    THE CRITICAL FIELD. Which fields in a transaction/session log move,
                        and in which direction. Be quantitative: amount distribution shape,
                        inter-arrival timing, beneficiary account age, device consistency,
                        session duration, channel, MCC, decline-to-approve ratio, graph
                        structure (fan-in / fan-out). If you cannot fill this field
                        concretely, mark the attack as NOT SIMULATABLE and say why.
  legit_lookalike       Which legitimate behaviour this most resembles — i.e. the false
                        positive risk a detector will face
  detection_difficulty  1-5 with one-line justification
  novelty               1-5, where 5 = not yet widely documented in industry reporting
  real_world_evidence   Has this been observed in the wild? Cite. If speculative, say so
                        plainly and justify plausibility from how the rail actually works.
  mitigation_direction  What signal or control would catch it
  sources               Citations


COVERAGE REQUIREMENT

Before finalising, verify the catalogue against this matrix and report any empty cells as a
gap rather than silently omitting them:

  Rails: card CNP · card present · UPI P2P · UPI P2M · UPI collect · UPI mandate · IMPS/NEFT ·
         cross-border · wallet/PPI · BNPL · e-mandate/recurring · agentic checkout

  Phases: initiate · authenticate · authorise · settle · dispute

  GenAI capability: voice clone · deepfake video · LLM text at scale · synthetic documents ·
         synthetic identity · autonomous browser agent · prompt injection · adversarial
         evasion of the fraud model · code generation · fake reviews and social proof


SOURCE PRIORITY

Tier 1 (how the rails actually work): NPCI UPI Procedural Guidelines and operating circulars;
  RBI Master Directions on digital payment security, KYC, and PPIs; RBI customer liability
  framework; EMVCo specifications including 3-D Secure; PCI DSS; Mastercard and Visa
  chargeback reason code lists and product rulebooks; ISO 8583 and ISO 20022 field
  definitions; payment gateway developer documentation (Razorpay, Stripe, Adyen, Cashfree)
  including their error code tables.

Tier 2 (what is actually happening): FBI IC3 annual report; Europol IOCTA; FinCEN advisories;
  FATF typologies; NPCI and RBI fraud statistics; Indian Cybercrime Coordination Centre (I4C)
  reporting; bank customer-warning pages; enforcement actions and court records describing
  scheme mechanics; fraud vendor research (Sardine, Feedzai, Featurespace, BioCatch, Group-IB).

Tier 3 (leading edge): arXiv and conference papers on adversarial ML for fraud detection,
  graph neural networks for transaction fraud, synthetic tabular data generation, LLM agent
  security and prompt injection; consumer scam forums and complaint boards for scams that
  have not yet reached industry reporting.

Note that NPCI circulars are a de facto history of UPI attacks — a control is issued because
something was being abused. Mine the circular archive chronologically for this reason.


QUALITY BAR

  - Every attack must be grounded in a real mechanism of a real rail. No science fiction.
  - Distinguish clearly between observed-in-the-wild, emerging, and speculative-but-plausible.
  - Two attacks that produce an identical data signature are ONE attack. Merge them and say so.
  - Do not pad the count with variations of phishing. Diversity means distinct trust anchors.
  - Flag anything where public documentation is thin, rather than inventing detail.
  - Cite sources. Never fabricate a citation, a statistic, or a case.

CONSTRAINT

This research supports a defensive security exercise using entirely synthetic data. Describe
attacks at the level of mechanism and data signature — enough to build a detector and a
simulator. Do not produce operational scripts, working code, live targeting information, or
step-by-step instructions that would function as a usable attack playbook against real systems.
```

---

## How to run this

Do not paste it as one giant request. Split it, or the tool will return shallow coverage of everything:

1. **Run 1 — rails and trust map.** Steps 1 and 2 only, for two rails (card CNP and UPI). This gives you the skeleton.
2. **Run 2 — attack derivation.** Steps 3 and 4 against that skeleton.
3. **Run 3 — the remaining rails.** Repeat for wallets, mandates, onboarding, agentic.
4. **Run 4 — inversion pass.** Step 5 alone. This is where your novelty score comes from; give it its own run.
5. **Run 5 — evidence pass.** Take the assembled list and hunt real-world citations for each.

Merge outputs into a single spreadsheet. One row per attack, columns matching the output schema.

## Follow-on prompts

**Pillar 2 (Generate) research:** "For the attack catalogue attached, identify the statistical properties a synthetic payment dataset must reproduce to be credible: amount distributions by MCC and rail, inter-arrival time distributions, class imbalance ratios, categorical cardinality, device and session field structure, and graph topology of mule networks. Ground in the published schemas of IEEE-CIS Fraud Detection, PaySim, BankSim, the ULB credit card dataset, and Elliptic. Then survey generation approaches — agent-based simulation, CTGAN/TVAE, diffusion for tabular data, LLM-driven behavioural agents — with trade-offs for fidelity versus controllability."

**Pillar 3 (Defend) research:** "Survey detection architectures for payment fraud under extreme class imbalance: gradient boosting baselines, graph neural networks over transaction graphs, sequence models over user session history, and anomaly detection for unseen attack types. Include evaluation methodology appropriate to payments — precision at fixed low false-positive rate, PR-AUC over ROC-AUC, temporal validation splits, and concept drift handling. Cover adversarial robustness: how a detector degrades when an attacker can query it."

## Hard stop

Freeze this catalogue on **day 5**. Whatever you have on 17 August is what you build. The catalogue can grow later if the code finishes early — it never works in the other direction.
