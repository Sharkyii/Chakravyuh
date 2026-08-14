# Attack catalogue — GenAI-enabled payment fraud

**Status:** defects D1, D2, D4 fixed. D3 (stale rail parameters) marked inline as `⚠VERIFY` — resolve before any number reaches code or deck.
**Freeze date:** 17 August 2026.

---

## Fix log

| ID | Defect | Resolution |
|---|---|---|
| D1 | Four entries treated UPI P2P collect as live; it was discontinued 1 Oct 2025 (NPCI circular 29 Jul 2025) | Entries relabelled `HISTORICAL`. Card 7 rewritten as merchant-collect impersonation |
| D2 | Card 1 claimed ₹1,750+ cr lost to digital arrest Jan–Apr 2024 | Corrected to **₹120.30 cr**. The ~₹1,776 cr figure was total cyber fraud losses across all categories in that window. Nine-month 2024 digital arrest figure: ₹1,616 cr across 63,481 complaints |
| D3 | UPI Lite, min-KYC PPI, and mandate AFA thresholds are stale | Marked `⚠VERIFY` at every occurrence. Do not hardcode until checked against current NPCI/RBI pages |
| D4 | Five scam entries share identical observable signals | Retained as separate catalogue rows for diversity scoring; merged into one generator with a `pretext` parameter. See merge map below |

---

## Generator merge map — 58 entries → 13 generators

**This is the section Phase 2 reads.** Catalogue rows are for the deck; generators are for the code. Two attacks producing the same data signature are one generator.

| # | Generator | Catalogue entries covered | Distinguishing data signature |
|---|---|---|---|
| G01 | `scam_induced_push` | DIGITALARREST-01, VOICEMIMIC-01, KYCEXPIRY-01, SE-DEEPFAKEBANK-01, SE-ROMANCE-01, SE-JOBSCAM-01, UPI-COLLECT-VOICECLONE-01 | Genuine device, correct PIN, new beneficiary, escalating amounts, coercion session fields. `pretext` param varies narrative only |
| G02 | `mule_network` | MULEAI-01, BANK-IMPS-MULESPLIT-01, XBORDER-HAWALA-01 | Graph topology: fan-in, pass-through, throughput ratio →1, no salary credit |
| G03 | `card_testing_probe` | BINAUTO-01, AGENT-BROWSER-01, WALLET-GIFTCARD-01 | Micro-amounts, high decline rate, card rotation, grid-search feature variation |
| G04 | `adversarial_evasion` | ADVEVASION-01, ADVMODEL-PROBE-01 | Probe phase then optimised phase; features inside legit distribution; segment-level model degradation |
| G05 | `first_party_dispute` | CNP-FIRSTPARTY-01, DISPUTE-AINARRATIVE-01, DISPUTE-FRIENDLY-01, UPI-P2M-CHARGEBACK-01, BNPL-FIRSTPARTY-01 | Transaction fully genuine; signal lives entirely in claimant dispute history |
| G06 | `stealth_mandate` | UPI-MANDATE-STEALTH-01, UPI-MANDATE-CANCELEVADE-01, UPI-MANDATE-SYNTHSETUP-01 | Uniform small recurring amounts, merchant fan-in, enrollment burst, `max_amount` ≫ `actual_amount` |
| G07 | `synthetic_merchant` | KYB-SYNTHDOC-01, KYB-SHELLNET-01, UPI-P2M-FAKEMERCHANT-01, BNPL-MERCHANT-01 | New merchant, step volume curve, registry-unverified KYB, fast settlement outflow |
| G08 | `transaction_laundering` | CARD-CNP-TRANSLAUND-01, UPI-P2M-MISCODE-01, XBORDER-TRADE-01 | `mcc_declared` ≠ `mcc_inferred_from_basket`; otherwise normal traffic |
| G09 | `credential_takeover` | 3DSDEEPFAKE-01, PHISHOTP-01, SIMSWAP-01, ATO-DEEPFAKECALL-01, ATO-KYCRESET-01, CARD-CP-RELAY-01 | Auth succeeds but device/session anomalous; high-risk account change precedes transfer |
| G10 | `synthetic_identity_bustout` | BNPL-SYNTHFARM-01, CARD-CNP-SYNTHID-01, XBORDER-REMIT-SYNTHID-01, WALLET-KYCBOUNCE-01 | Perfect repayment then simultaneous utilisation spike; shared device/phone/address cluster |
| G11 | `subthreshold_fragmentation` | UPI-P2P-LITESPLIT-01 ⚠VERIFY, WALLET-CARDLOAD-01 | Uniform amounts just under a limit; rapid load-drain cycle; two-hop funnel |
| G12 | `agentic_injection` | AGENT-PROMPTINJECT-01, AGENT-DELEGATED-01, AGENT-AGENT-01, UPI-MANDATE-AGENT-01 | `is_agent_initiated`, beneficiary ≠ seller of record, VPA not in biller directory |
| G13 | `insider_abuse` | KYB-INSIDER-01, BANK-NEFT-INSIDER-01, CARD-CP-REFUNDABUSE-01, ADVMODEL-POISON-01 | No external anomaly; approval velocity and access-pattern signals only |

**Not simulatable, deck-only:** CARD-CNP-TOKENRACE-01, CARD-CP-CLONESYNTH-01, UPI-P2P-QRREPLACE-01, UPI-P2M-REFUNDRING-01, BANK-RTGS-FORGEDINV-01, UPI-COLLECT-MANDATEBLUR-01 (HISTORICAL). These lack a distinct in-log signature or depend on physical-world events the payment log never sees. Keep them in the taxonomy; do not build generators.

Every generator must also emit its `legit_lookalike` population. A generator without one is incomplete.

---

## Summary table — 58 entries

DD = detection difficulty 1–5 · NV = novelty 1–5 · E = O observed / EM emerging / SP speculative · G = generator

| ID | Name | Rail | Phase | Trust anchor broken | GenAI capability | DD | NV | E | G |
|---|---|---|---|---|---|---|---|---|---|
| CARD-CNP-BINAUTO-01 | Automated BIN attack, LLM-optimised testing | Card CNP | Authorise | Card data is secret | Autonomous browser | 3 | 2 | O | G03 |
| CARD-CNP-3DSDEEPFAKE-01 | Deepfake bypass of 3DS biometric | Card CNP | Authenticate | Biometric matches cardholder | Deepfake video | 5 | 4 | EM | G09 |
| CARD-CNP-SYNTHID-01 | Synthetic identity card farming | Card CNP | Initiate | Identity is a real person | Synthetic identity | 4 | 3 | O | G10 |
| CARD-CNP-PHISHOTP-01 | LLM-personalised OTP interception | Card CNP | Authenticate | OTP reaches only cardholder | LLM text at scale | 3 | 3 | O | G09 |
| CARD-CNP-ADVEVASION-01 | Adversarial feature perturbation | Card CNP | Authorise | Features match baseline | Adversarial evasion | 5 | 5 | EM | G04 |
| CARD-CNP-FIRSTPARTY-01 | First-party fraud, AI dispute narratives | Card CNP | Dispute | Cardholder did not authorise | LLM text | 4 | 3 | EM | G05 |
| CARD-CNP-TOKENRACE-01 | Tokenised card race condition | Card CNP | Authorise | Token bound to one device | Code generation | 3 | 4 | SP | — |
| CARD-CNP-TRANSLAUND-01 | Laundering via AI-generated storefront | Card CNP | Settle | Merchant sells what it claims | LLM text + fake reviews | 4 | 3 | O | G08 |
| CARD-CP-RELAY-01 | Contactless relay, ML-optimised timing | Card present | Authenticate | Card is physically present | Adversarial optimisation | 4 | 3 | EM | G09 |
| CARD-CP-CLONESYNTH-01 | Cloned card + synthetic ID at POS | Card present | Authorise | Card belongs to presenter | Synthetic identity | 3 | 2 | O | — |
| CARD-CP-REFUNDABUSE-01 | POS refund manipulation | Card present | Settle | Refund is legitimate | — (insider) | 3 | 2 | O | G13 |
| UPI-P2P-DIGITALARREST-01 | "Digital arrest" coercion | UPI P2P | Initiate | Payer voluntarily authorises | Voice clone + deepfake | 4 | 4 | O | G01 |
| UPI-P2P-VOICEMIMIC-01 | Voice clone of known contact | UPI P2P | Initiate | Caller is the known person | Voice clone | 4 | 4 | EM | G01 |
| UPI-P2P-KYCEXPIRY-01 | KYC expiry scam | UPI P2P | Authenticate | KYC request is genuine | Synthetic documents | 3 | 3 | O | G01 |
| UPI-P2P-SIMSWAP-01 | SIM swap + UPI re-registration | UPI P2P | Authenticate | Device + SIM = owner | Synthetic docs | 3 | 2 | O | G09 |
| UPI-P2P-MULEAI-01 | AI-managed mule network | UPI P2P | Settle | Holder transacts for self | LLM behavioural scripting | 5 | 5 | EM | G02 |
| UPI-P2P-LITESPLIT-01 ⚠VERIFY | UPI Lite sub-threshold fragmentation | UPI Lite | Authorise | Small txn = low risk | LLM orchestration | 4 | 4 | SP | G11 |
| UPI-COLLECT-FLOOD-01 `HISTORICAL` | Mass collect requests | UPI collect | Initiate | Collect is from known payee | LLM text at scale | 3 | 3 | O | — |
| UPI-COLLECT-MASSPERS-01 `HISTORICAL` | Mass personalised collect | UPI collect | Initiate | Collect from known party | LLM text at scale | 3 | 3 | EM | — |
| UPI-COLLECT-MANDATEBLUR-01 `HISTORICAL` | Collect disguised as mandate | UPI collect | Initiate | User understands approval | LLM text | 3 | 4 | SP | — |
| UPI-COLLECT-VOICECLONE-01 | Voice clone + merchant collect *(rewritten, see Card 7)* | UPI collect (merchant) | Initiate | Collect payee is the real merchant | Voice clone | 4 | 4 | EM | G01 |
| UPI-P2M-QRREPLACE-01 | QR overlay substitution | UPI P2M | Initiate | QR belongs to the shop | Synthetic identity | 3 | 3 | O | — |
| UPI-P2M-FAKEMERCHANT-01 | Fake merchant QR, synthetic KYB | UPI P2M | Initiate | Merchant is a real business | Synthetic documents | 4 | 3 | O | G07 |
| UPI-P2M-MISCODE-01 | MCC miscoding | UPI P2M | Settle | MCC reflects the business | — | 3 | 2 | O | G08 |
| UPI-P2M-CHARGEBACK-01 | Fake dispute, AI evidence | UPI P2M | Dispute | Payer was deceived | LLM text + images | 3 | 3 | EM | G05 |
| UPI-P2M-REFUNDRING-01 | Refund ring | UPI P2M | Settle | Refund matches original | LLM orchestration | 4 | 3 | EM | — |
| UPI-MANDATE-SYNTHSETUP-01 | Synthetic e-mandate enrollment | UPI mandate | Initiate | Enrollment is voluntary | Synthetic docs + LLM | 4 | 3 | O | G06 |
| UPI-MANDATE-STEALTH-01 ⚠VERIFY | Low-amount recurring under threshold | UPI mandate | Settle | Small recurring = legitimate | LLM orchestration | 5 | 4 | EM | G06 |
| UPI-MANDATE-CANCELEVADE-01 | Cancellation evasion by re-registration | UPI mandate | Settle | Cancelled stays cancelled | LLM orchestration | 4 | 4 | SP | G06 |
| UPI-MANDATE-AGENT-01 | Agent mandate enrollment via injection | UPI mandate | Initiate | Agent acts per user intent | Prompt injection | 5 | 5 | SP | G12 |
| BANK-IMPS-MULESPLIT-01 | IMPS mule splitting | IMPS | Settle | Transfers are legitimate | LLM behavioural scripting | 4 | 4 | O | G02 |
| BANK-NEFT-INSIDER-01 | Insider NEFT reversal fraud | NEFT | Settle | Reversal is system-generated | — | 3 | 2 | O | G13 |
| BANK-RTGS-FORGEDINV-01 | Forged invoice RTGS | RTGS | Initiate | Invoice is genuine | Synthetic documents | 3 | 3 | EM | — |
| XBORDER-REMIT-SYNTHID-01 | Synthetic identity remittance | Cross-border | Initiate | Sender identity is real | Synthetic identity | 4 | 3 | O | G10 |
| XBORDER-TRADE-01 | Trade-based ML, AI trade docs | Cross-border | Settle | Trade documents genuine | Synthetic documents | 4 | 3 | O | G08 |
| XBORDER-HAWALA-01 | AI-coordinated hawala layering | Cross-border | Settle | Formal ≠ informal transfer | LLM orchestration | 5 | 4 | SP | G02 |
| WALLET-CARDLOAD-01 ⚠VERIFY | Stolen card → wallet → UPI offload | Wallet/PPI | Settle | Loader is the cardholder | LLM orchestration | 3 | 2 | O | G11 |
| WALLET-GIFTCARD-01 | Bulk gift card purchase | Gift card | Authorise | Purchase is genuine | Autonomous browser | 3 | 2 | O | G03 |
| WALLET-KYCBOUNCE-01 | PPI KYC bypass | Wallet/PPI | Authenticate | KYC docs genuine | Synthetic documents | 3 | 3 | O | G10 |
| BNPL-SYNTHFARM-01 | Synthetic identity BNPL farming | BNPL | Initiate | Identity real and creditworthy | Synthetic identity | 4 | 4 | EM | G10 |
| BNPL-FIRSTPARTY-01 | BNPL default, AI hardship narratives | BNPL | Dispute | Hardship claim genuine | LLM text | 3 | 3 | EM | G05 |
| BNPL-MERCHANT-01 | BNPL merchant fraud | BNPL | Settle | Merchant is legitimate | LLM text + fake reviews | 4 | 3 | EM | G07 |
| KYB-SYNTHDOC-01 | Synthetic document onboarding | Merchant KYB | Initiate | Business is real | Synthetic documents | 4 | 4 | EM | G07 |
| KYB-SHELLNET-01 | Shell network, AI financials | Merchant KYB | Initiate | Financials reflect business | LLM + synthetic docs | 4 | 3 | O | G07 |
| KYB-INSIDER-01 | Insider onboarding approval | Merchant KYB | Initiate | Approver follows policy | — | 3 | 2 | O | G13 |
| AGENT-PROMPTINJECT-01 | Prompt injection of shopping agent | Agentic | Authorise | Agent follows user intent | Prompt injection | 5 | 5 | SP | G12 |
| AGENT-DELEGATED-01 | Delegated credential abuse | Agentic | Authorise | Agent has user's authority | Autonomous browser | 4 | 5 | SP | G12 |
| AGENT-AGENT-01 | Agent-to-agent manipulation | Agentic | Authorise | Both agents act per principal | Prompt injection | 5 | 5 | SP | G12 |
| AGENT-BROWSER-01 | Autonomous browser card testing | Card CNP | Authorise | Human operates browser | Autonomous browser | 3 | 4 | EM | G03 |
| DISPUTE-AINARRATIVE-01 | AI chargeback narratives at scale | Card CNP | Dispute | Narrative is genuine | LLM text at scale | 4 | 3 | EM | G05 |
| DISPUTE-FRIENDLY-01 | Friendly fraud, synthetic evidence | Card CNP | Dispute | Non-receipt evidence real | Synthetic images | 3 | 3 | EM | G05 |
| SE-DEEPFAKEBANK-01 | Deepfake video call as bank official | UPI/Bank | Initiate | Caller is bank official | Deepfake video | 5 | 4 | EM | G01 |
| SE-ROMANCE-01 | LLM romance scam → payment | UPI/Xborder | Initiate | Relationship is genuine | LLM text at scale | 3 | 3 | O | G01 |
| SE-JOBSCAM-01 | Job/task scam | UPI/Wallet | Initiate | Employment offer genuine | Synthetic docs + LLM | 3 | 3 | O | G01 |
| ATO-DEEPFAKECALL-01 | Deepfake voice for call-centre ATO | Bank/Card | Authenticate | Voice matches voiceprint | Voice clone | 5 | 4 | EM | G09 |
| ATO-KYCRESET-01 | KYC reset with synthetic docs | Bank/UPI | Authenticate | KYC docs genuine | Synthetic documents | 3 | 3 | O | G09 |
| ADVMODEL-PROBE-01 | Model probing and adaptive evasion | All | Authorise | Model score trustworthy | Adversarial evasion | 5 | 5 | EM | G04 |
| ADVMODEL-POISON-01 | Poisoning via dispute feedback | All | Dispute | Dispute labels genuine | Adversarial ML | 5 | 5 | SP | G13 |

---

## Card 7 — rewritten (D1 fix)

### UPI-COLLECT-VOICECLONE-01 — Voice clone + merchant collect impersonation

| Field | Value |
|---|---|
| **rail** | UPI merchant collect |
| **phase** | Initiate |
| **trust_anchor_broken** | The collect request comes from the merchant the payer believes they are dealing with. P2P collect was discontinued from 1 October 2025, so the attacker must now hold or impersonate a merchant identity — the mental-model inversion survived the regulatory fix, it just moved into merchant onboarding. Depends on G07. |
| **attacker_role** | Fraudulent merchant with a voice-cloning capability, or an outsider using a rented/compromised merchant account |
| **genai_capability** | Voice clone from 3–10s of audio, real-time conversion, natural prosody. Combined with a merchant-collect push notification this creates dual-channel deception: the victim hears a familiar or authoritative voice *and* sees a legitimate-looking collect request arrive in their UPI app. Pre-GenAI this needed a skilled human caller working one victim at a time. |
| **attack_chain** | 1. Attacker onboards a merchant identity via synthetic KYB (see KYB-SYNTHDOC-01) or rents a dormant one. 2. Attacker identifies victims with a plausible relationship to the merchant category — recent customers, utility subscribers, insurance holders. 3. Voice cloned from public audio of a service representative, or a generic authoritative persona. 4. Merchant collect request sent to victim with attacker-controlled remarks framing it as a renewal, refund verification, or pending dues. 5. Simultaneous call in the cloned voice walks the victim through approving. 6. Victim approves with UPI PIN — the approval is a debit. 7. Merchant settlement account drained within the settlement window. |
| **observable_signals** | Collect request from a merchant with no prior relationship to the payer. Merchant age <90 days with a step volume curve. High collect send volume with an unusually high approval rate — legitimate merchants have low approval rates from cold VPAs. Approval within minutes of receipt (victim is on the phone). Bursty send pattern across many payers. Settlement outflow latency near zero. On the victim side: short `time_on_confirm_screen_s`, `call_active_during_txn` true, `beneficiary_first_time` true. |
| **legit_lookalike** | Genuine merchant collect for subscription renewals, insurance premiums, utility dues — millions daily, often from merchants the payer hasn't transacted with recently. |
| **detection_difficulty** | 4 |
| **novelty** | 4 — the P2P variant is documented; the post-October-2025 migration into merchant collect is not yet in industry reporting |
| **real_world_evidence** | Emerging. Voice clone fraud targeting Indian banking customers reported through 2024. P2P collect abuse is documented and led to the discontinuation. The merchant-collect migration is inferred from the regulatory change, not yet independently evidenced — label as such. |
| **mitigation_direction** | Merchant collect risk score combining merchant age, collect approval rate, payer-merchant relationship history, and settlement outflow latency. Cooling period on collect from merchants with no prior relationship to the payer. Registry verification at KYB rather than format validation. |

---

## Coverage matrix — rails × phases

| Rail \ Phase | Initiate | Authenticate | Authorise | Settle | Dispute |
|---|---|---|---|---|---|
| Card CNP | SYNTHID | 3DSDEEPFAKE, PHISHOTP | BINAUTO, ADVEVASION, TOKENRACE, AGENT-BROWSER | TRANSLAUND | FIRSTPARTY, AINARRATIVE, FRIENDLY |
| Card present | — *(structural)* | RELAY | CLONESYNTH | REFUNDABUSE | — *(structural)* |
| UPI P2P | DIGITALARREST, VOICEMIMIC | KYCEXPIRY, SIMSWAP | — | MULEAI | — *(structural)* |
| UPI P2M | FAKEMERCHANT, QRREPLACE | — | — | MISCODE, REFUNDRING | CHARGEBACK |
| UPI collect | VOICECLONE *(merchant)* | — | — | — | — |
| UPI mandate | SYNTHSETUP, AGENT | — | — | STEALTH, CANCELEVADE | — |
| UPI Lite | — | — | LITESPLIT | — | — |
| IMPS/NEFT/RTGS | FORGEDINV | — | — | MULESPLIT, INSIDER | — |
| Cross-border | REMIT-SYNTHID | — | — | TRADE, HAWALA | — |
| Wallet/PPI | — | KYCBOUNCE | GIFTCARD | CARDLOAD | — |
| BNPL | SYNTHFARM | — | — | MERCHANT | FIRSTPARTY |
| Agentic | — | — | PROMPTINJECT, DELEGATED, AGENT-AGENT | — *(immature)* | — *(immature)* |
| Merchant KYB | SYNTHDOC, SHELLNET, INSIDER | — | — | — | — |

**Structural gaps, reported not hidden:** UPI has no consumer dispute remedy, so UPI × dispute is genuinely empty. Card-present initiate has no information exchange to exploit. Agentic settle/dispute infrastructure does not exist yet.

---

## Inversion pass — attacks inside the legitimate distribution

Conventional signals: velocity, new beneficiary, amount thresholds, geo mismatch, device change, time-of-day, known-bad lists, MCC anomaly, IP reputation. These attacks keep all of them normal.

| Attack | Why conventional detection fails |
|---|---|
| ADVEVASION / PROBE | Every feature optimised to sit inside the legitimate distribution by construction |
| MULEAI | Per-mule behavioural profiles matched to real user distributions; only graph topology betrays it |
| STEALTH mandate | Amounts below every threshold; beneficiary is a merchant, not a new P2P payee |
| LITESPLIT | Sub-threshold transactions may not be scored at all |
| FIRSTPARTY | The transaction is genuine. There is nothing to detect at transaction time |
| DIGITALARREST | Own device, own PIN, correct entry. Only session-level coercion fields and mule graph carry signal |
| SYNTHFARM | Credit-building phase is indistinguishable from a good customer; bust-out is a temporal shift, not a feature anomaly |
| TRANSLAUND | Real storefront, valid MCC, normal customer behaviour |
| CANCELEVADE | Re-registration looks like fresh legitimate enrollment |
| INSIDER | Follows internal policy on paper; no external anomaly exists |

**This table is the novelty argument.** Conventional models assume the attacker is not the customer. In a scam-induced payment everything is genuine — real customer, real device, real location, correct PIN. The only anomaly is intent, which appears in no standard column.

---

## Confidence tiers

**Observed, multiple sources:** DIGITALARREST, KYCEXPIRY, CARDLOAD, BINAUTO, MULESPLIT, SHELLNET, TRANSLAUND, SYNTHID

**Emerging, component evidence:** 3DSDEEPFAKE, MULEAI, ADVMODEL-PROBE, ATO-DEEPFAKECALL, BNPL-SYNTHFARM, KYB-SYNTHDOC, VOICECLONE (merchant variant)

**Speculative but plausible:** all G12 agentic entries, LITESPLIT, TOKENRACE, ADVMODEL-POISON, CANCELEVADE

Label these honestly in the deck. A judge respects a clearly-marked speculative attack far more than an overclaimed one.

---

## Outstanding before freeze

- [ ] Resolve every `⚠VERIFY` against current NPCI/RBI sources, with dated citations
- [ ] Audit remaining statistics the way D2 was audited
- [ ] Append the 14 remaining expanded cards from the research output below this line
- [ ] Confirm each of the 13 generators has a defined `legit_lookalike` population
