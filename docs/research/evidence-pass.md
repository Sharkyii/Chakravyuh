# Evidence pass - citation verification for high-confidence catalogue entries

**Last verified:** 18 August 2026
**Scope:** the 15 entries listed in `docs/attack-catalogue.md`'s "Confidence tiers" section under
**Observed, multiple sources** and **Emerging, component evidence** - the entries claiming the
strongest evidence backing, and therefore the most damaging to get wrong. "Speculative but
plausible" entries are out of scope (already honestly labeled).

**Method:** for each entry, web search for a real, dated, checkable source for its core factual
claim. Verdicts:
- **Verified** - a specific, checkable primary or reputable secondary source exists for the claim
  as stated.
- **Partially verified** - the general phenomenon is real and sourced, but the specific claim in
  the catalogue (a named pattern, a specific chaining of steps, a specific sub-context) is not
  independently documented - only its components are.
- **Could not verify** - no checkable source found for the specific claim; treat as an honest gap,
  not grounds to fabricate one.

**Result summary:** 15 entries reviewed. 13 confirmed in their current tier (2 of those with
wording corrections/softening below). 2 downgraded from "Observed, multiple sources" to "Emerging,
component evidence": `WALLET-CARDLOAD-01` and `KYB-SHELLNET-01`. One embedded statistic in the fix
log (the nine-month digital-arrest figure attached to `DIGITALARREST-01`'s evidence trail) could
not be verified and should be corrected.

---

## Observed, multiple sources

### UPI-P2P-DIGITALARREST-01 - "Digital arrest" coercion

**Verdict: Verified** (core claim), **one embedded statistic could not be verified - needs fixing**.

The ₹120.30 crore figure for January–April 2024, already used in the catalogue's D2 fix, is
solid: it traces to a direct quote from I4C CEO Rajesh Kumar, reported identically across multiple
outlets on the same day.
- [Indians Lost Rs 120 Crore in Digital Arrest Frauds in First Quarter of 2024: Report - The Wire](https://m.thewire.in/article/news/indians-lost-rs-120-crore-in-digital-arrest-frauds-in-first-quarter-of-2024-report)
- ['Digital Arrest' Scam: Indians Lost Rs 120 Crore ... - Oneindia](https://www.oneindia.com/india/digital-arrest-scam-indians-lost-rs-120-crore-to-online-fraudsters-between-january-april-2024-3972107.html)
- ['Digital arrest' frauds cost Indians ₹120 crore in January-April - NewsBytes](https://www.newsbytesapp.com/news/science/indians-lost-rs120cr-to-digital-arrest-frauds-between-january-april-2024/story)

The scam mechanism (fraudsters impersonating CBI/ED/RBI/police officials, video call coercion,
operators traced to Myanmar/Laos/Cambodia) is corroborated by numerous individually reported cases
(Deccan Herald, News on Air) throughout 2025–2026, e.g. a ₹1.6 crore case CBI charge-sheeted in
August 2026 naming a bank officer as accomplice.

**Problem found:** the fix log's second figure - "the nine-month 2024 digital-arrest figure was
₹1,616 crore across 63,481 complaints" - does **not** appear in any source found across five
separate search attempts, including exact-phrase searches for "₹1,616 crore" and "63,481". What
*does* exist for later 2024 periods, from different outlets, is inconsistent:
- Jan–Oct 2024 (10 months): ~₹2,140 crore
- Full year 2024: ₹1,935.5 crore across 123,672 cases (one source), OR ₹1,918 crore after a
  reported 465% spike (The Print, citing MHA data)
- Full period 2022–May 2026: ₹4,057.7 crore across 297,727 incidents (news4hackers, aggregating a
  longer window)

None of these match "₹1,616 crore / 63,481 complaints" for a nine-month window. This looks like
exactly the kind of unverified specific the brief's Run 5 status warns about - a number that
*sounds* precise and checkable but isn't traceable to a real release. It should not go in the deck
as stated.

**Recommended action:** in `docs/attack-catalogue.md`'s fix log (D2 row) and anywhere else this
nine-month figure is repeated, either (a) drop it and keep only the well-verified ₹120.30 crore
Jan–Apr 2024 figure, or (b) replace it with one of the figures above, cited to its specific source,
with an explicit note that different outlets report different totals for overlapping windows
because the underlying I4C releases themselves are inconsistent period-to-period. Keep the entry in
the "Observed, multiple sources" tier - the core scam mechanism and the headline statistic are
solid.

---

### UPI-P2P-KYCEXPIRY-01 - KYC expiry scam

**Verdict: Verified.**

RBI itself has issued public warnings against fake "your KYC will expire / your account will be
blocked in 2 hours" SMS/link scams, and repeatedly clarified banks never request KYC updates via
link, app install, or call.
- [RBI issues warning on KYC fraud - IBS Intelligence](https://ibsintelligence.com/ibsi-news/rbi-issues-warning-on-kyc-fraud-urges-vigilance-and-direct-bank-contact/)
- [Rs 2 lakh KYC Update scam - Business Standard](https://www.business-standard.com/finance/personal-finance/rs-2-lakh-kyc-update-scam-what-is-it-how-it-happened-and-how-to-avoid-it-124082800231_1.html)

**Action:** keep as-is. This is one of the better-sourced entries in the catalogue - the regulator
itself is the source.

---

### CARD-CNP-BINAUTO-01 - Automated BIN attack

**Verdict: Verified.**

BIN/enumeration attacks are a well-documented, named fraud category with direct card-network
guidance. Visa attributes roughly $1.1 billion in ecosystem losses in a single year to enumeration
attacks specifically, and publishes formal merchant guidance.
- [Visa Guidance to Guard Against Enumeration Attacks (PDF)](https://usa.visa.com/content/dam/VCOM/global/support-legal/documents/visa-guidance-to-guard-against-enumeration-attacks.pdf)
- [What is a BIN Attack? - cSide](https://cside.com/blog/what-is-a-bin-attack)

**Action:** keep as-is.

---

### BANK-IMPS-MULESPLIT-01 - IMPS mule splitting

**Verdict: Verified** (mule structuring/layering as a general phenomenon in India, with a live
regulatory response); **IMPS-specific chaining is inferred, not separately documented**.

Mule account layering - funds passed through several accounts in a short window to break the
trace - is extensively documented, including RBI's own AI countermeasure:
- [Explained: RBI's MuleHunter.AI - Business Standard](https://www.business-standard.com/amp/finance/personal-finance/explained-rbi-has-a-new-ai-tool-mulehunter-ai-to-reduce-digital-frauds-124120900250_1.html)
- [RBI Strengthens Framework on Unauthorised Electronic Banking Transactions - PIB](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2244478&reg=3&lang=2)
- [Mule accounts decoded - Business Standard](https://www.business-standard.com/finance/news/what-are-mule-accounts-cybercrime-banking-layer-india-fraud-rbi-126062400855_1.html)

MuleHunter.AI reportedly studies 19 distinct behavioural patterns and detects ~20,000 mule accounts
per month - solid evidence the structuring pattern is real and at scale. No source specifically
isolates IMPS as the rail (vs. UPI/NEFT) for the splitting pattern, but this is a reasonable
generator-level abstraction, not an overclaim.

**Action:** keep as-is in "Observed, multiple sources"; optionally soften `real_world_evidence` to
say "mule account layering/structuring is documented at scale across bank rails including IMPS"
rather than implying IMPS-specific reporting exists.

---

### KYB-SHELLNET-01 - Shell network, AI financials

**Verdict: Partially verified - recommend downgrade.**

Shell company fraud as a general AML phenomenon is extremely well documented (ACFE, FinCEN CDD
rule, multiple industry glossaries), including the use of fabricated financial statements to
secure credit or pass onboarding:
- [Shell Companies - ACFE](https://www.acfe.com/fraud-resources/shell-companies)
- [What Is a Shell Company in Money Laundering? - Alessa](https://alessa.com/blog/what-is-a-shell-company-in-money-laundering/)

What is **not** found anywhere in search: a specific reported case, report, or advisory tying
**AI-generated** financial statements/documents to a **payment merchant onboarding (KYB)** fraud
incident. The entry's core mechanism (shell company + fabricated financials to pass KYB) is real
and documented; the "AI-generated" qualifier that gives it its GenAI relevance is an inference by
extension from adjacent evidence (general AI document-fraud tooling - see `KYB-SYNTHDOC-01` below),
not a directly observed case.

**Recommended action:** move `KYB-SHELLNET-01` from "Observed, multiple sources" to "Emerging,
component evidence" in `docs/attack-catalogue.md`. Soften its `real_world_evidence` text (where a
card/expanded entry exists) to something like: "Shell-company fraud using fabricated financials to
pass business onboarding is a long-documented AML pattern. The AI-generated-documents component is
inferred from general synthetic-document fraud tooling (see KYB-SYNTHDOC), not from a specific
reported shell-network case using AI-generated financials."

---

### CARD-CNP-TRANSLAUND-01 - Laundering via AI-generated storefront

**Verdict: Verified** on both components.

Transaction laundering (aka factoring/undisclosed aggregation) is a formally recognized card-network
violation category with compliance requirements from Visa/Mastercard:
- [What is Transaction Laundering - LegitScript](https://www.legitscript.com/transaction-laundering/)

The "AI-generated storefront" specific angle is independently and freshly documented via multiple
2024–2025 FTC enforcement actions against AI-storefront scam operations, plus reporting on
AI-generated scam stores using fake reviews and deepfakes:
- [FTC Announces Crackdown on Deceptive AI Claims and Schemes (Sept 2024) - FTC](https://www.ftc.gov/news-events/news/press-releases/2024/09/ftc-announces-crackdown-deceptive-ai-claims-schemes)
- [AI-driven scam stores put retailers on alert - Yahoo Finance](https://finance.yahoo.com/markets/crypto/articles/ai-driven-scam-stores-put-090404213.html)

**Action:** keep as-is; this is one of the stronger-evidenced entries - both the base typology and
the GenAI-specific escalation have real, dated, checkable sources.

---

### CARD-CNP-SYNTHID-01 - Synthetic identity card farming

**Verdict: Verified.**

Synthetic identity fraud is one of the best-quantified fraud categories in the catalogue, with
consistent (if wide-ranging) loss estimates across multiple independent sources over several years:
- [Understanding Synthetic ID Fraud - Experian](https://www.experian.com/blogs/insights/understanding-synthetic-id-fraud/)
- [Gen AI is ramping up the threat of synthetic identity fraud - Federal Reserve Bank of Boston (Apr 2025)](https://www.bostonfed.org/news-and-events/news/2025/04/synthetic-identity-fraud-financial-fraud-expanding-because-of-generative-artificial-intelligence.aspx)
- TransUnion: $3.3B US lender exposure to synthetic identities across cards/auto/personal loans at
  end of 2024.

Note this evidence base is heavily US-centric; the catalogue doesn't claim India-specificity for
this entry, so that's not a mismatch.

**Action:** keep as-is.

---

### WALLET-CARDLOAD-01 ⚠VERIFY - Stolen card → wallet → UPI offload

**Verdict: Partially verified - recommend downgrade.**

Each component is independently real:
- Wallets are targeted with phished/stolen card details (general digital wallet fraud is
  documented: [How Fraudsters Bypass Facial Recognition - Sumsub](https://sumsub.com/blog/how-fraudsters-bypass-facial-recognition/) and general wallet-fraud writeups).
- Money is laundered through intermediary "mule" hops to obscure trail (see MULESPLIT sources
  above).
- RBI's own PPI fraud-liability rules assume third-party breach scenarios are common enough to need
  a formal three-day reporting window.

What is **not** found: a specific reported case or advisory describing the exact three-step chain
in the entry - stolen card loads a wallet, wallet then offloads via UPI as a cash-out step. This is
a plausible composite built from real, separately-documented components, but it is not itself an
independently observed pattern the way BINAUTO or KYCEXPIRY are. This entry is also already flagged
`⚠VERIFY` for stale rail-parameter reasons (D3) - that's a separate, still-open issue about the
wallet cap number, not resolved here.

**Recommended action:** move `WALLET-CARDLOAD-01` from "Observed, multiple sources" to "Emerging,
component evidence." Its D3 `⚠VERIFY` flag on rail parameters remains open and separate - this
finding is about the evidentiary strength of the pattern itself, not the numeric limits.

---

## Emerging, component evidence

### CARD-CNP-3DSDEEPFAKE-01 - Deepfake bypass of 3DS biometric

**Verdict: Confirmed - well-supported component evidence, appropriately in "Emerging" not
"Observed."**

Strong, recent, dated evidence for deepfake bypass of biometric/liveness identity checks broadly:
- Group-IB documented 1,100+ deepfake fraud attempts bypassing digital KYC at an Indonesian
  financial institution (Aug 2024), ~$138.5M potential losses over three months.
- Sumsub Q1 2025 fraud report: deepfake fraud surged 1,100%.
- iProov: native virtual camera attacks up 2,665% across 2024.
- [FinCEN Nov 2024 alert on deepfake media circumventing identity verification](https://www.forbes.com/sites/daveywinder/2024/12/04/ai-bypasses-biometric-security-in-1385-million-financial-fraud-risk/)

All of this evidence is about biometric/liveness KYC checks generally, not specifically the EMV 3DS
transaction-time biometric challenge the entry names. The distinction matters - 3DS challenge flows
and onboarding-KYC liveness checks are different checkpoints - so "component evidence" (the
technique is proven against biometric checks broadly) rather than "observed" (a documented 3DS-
specific bypass) is the right tier.

**Action:** keep as-is; the evidence base is strong enough that this entry could be defended
confidently in a judge Q&A, provided the deck is precise that the cited incidents are KYC-liveness,
not literally 3DS challenge, bypasses.

---

### UPI-P2P-MULEAI-01 - AI-managed mule network

**Verdict: Confirmed - component evidence, correctly tiered.**

Real evidence that AI/LLM tooling is being applied to mule account operations at the "as-a-service"
level:
- [Exposing the Underground Mule-as-a-Service Economy - KELA Cyber](https://www.kelacyber.com/blog/mule-as-a-service-money-laundering/) - describes LLMs/agentic AI industrializing mule account
  creation and "warming" (simulating legitimate behaviour via low-risk transactions).
- Academic pipeline work on money-mule identification acknowledges the arms-race framing
  ([arxiv 2607.17586](https://arxiv.org/pdf/2607.17586)).

This supports the mechanism (AI lowers the cost of running larger, more behaviourally-realistic
mule networks) without yet constituting a documented, attributed real-world incident of a fully
autonomous AI-managed network - exactly what "emerging, component evidence" is supposed to mean.

**Action:** keep as-is.

---

### ADVMODEL-PROBE-01 - Model probing and adaptive evasion

**Verdict: Confirmed - component evidence from academic literature, correctly tiered.**

Multiple recent papers demonstrate adversarial evasion attacks against fraud-detection ML models,
including a GNN-based fraud detector with an 87.5% attack success rate under PGD evasion, reduced to
32% with adversarial training:
- [Adversarial Machine Learning in Finance - ResearchGate](https://www.researchgate.net/publication/398936161_Adversarial_Machine_Learning_in_Finance_Developing_Resilient_AI_Models_to_Counter_Fraudster_Evasion_Attacks_on_US_Bank_Security_Systems)
- [Adversarial Learning in Real-World Fraud Detection: Challenges and Perspectives (arXiv 2307.01390)](https://arxiv.org/pdf/2307.01390)

This is academic/lab evidence of feasibility, not a reported in-the-wild incident of a real fraud
ring probing a production model - again, correctly an "emerging, component evidence" claim rather
than "observed."

**Action:** keep as-is.

---

### ATO-DEEPFAKECALL-01 - Deepfake voice for call-centre ATO

**Verdict: Confirmed - strong evidence, arguably under-cited relative to how well-supported it is.**

This is one of the best-evidenced entries in the "Emerging" tier:
- Deepfake fraud attempts in contact centres reportedly rose >1,300% in 2024 (roughly one/month to
  ~seven/day) - [FIS Global](https://www.fisglobal.com/insights/how-ai-voice-cloning-is-increasing-call-center-fraud).
- University of Waterloo researchers demonstrated voice-authentication bypass with up to 99% success
  within six attempts.
- Hong Kong police intercepted a deepfake-enabled bank-account-opening fraud network (April 2025).
- Well-known named incident: a cloned "CEO voice" convinced a finance executive to wire $243,000
  (widely reported since 2019, still cited as the canonical case).

**Action:** keep in "Emerging, component evidence" (still no fully attributed *UPI/Indian
call-centre-specific* incident found), but this entry could carry stronger citations than it
currently does in the catalogue - recommend adding at least the FIS Global contact-centre statistic
to its `real_world_evidence` field.

---

### BNPL-SYNTHFARM-01 - Synthetic identity BNPL farming

**Verdict: Confirmed - component evidence, correctly tiered.**

- ACI Worldwide's 2024 holiday-season report flagged synthetic identity fraud as the emerging top
  threat alongside BNPL growth.
- Experian: 60% increase in synthetic identity fraud cases in 2024 vs. 2023.
- Industry reporting: 41% of BNPL fraud cases globally linked to identity theft.
- [Global Holiday Season Spending... BNPL Surges While Synthetic Identity Fraud Emerges as Top Threat - ACI Worldwide](https://investor.aciworldwide.com/news-releases/news-release-details/global-holiday-season-spending-expected-grow-16-2024-bnpl-surges)

This is US/global BNPL market evidence, not India-specific - reasonable given the catalogue doesn't
claim India-specificity here either.

**Action:** keep as-is.

---

### KYB-SYNTHDOC-01 - Synthetic document onboarding

**Verdict: Partially verified - keep tier, soften wording.**

Strong evidence for AI-generated *identity* document fraud broadly:
- Sumsub: synthetic identity document fraud surged 300%+ in the US (2025), citing generation costs
  as low as $15 and 30 minutes using generative AI tools.
- [Synthetic Identity Document Fraud Surges 300% - Sumsub](https://sumsub.com/newsroom/synthetic-identity-document-fraud-surges-300-in-the-u-s-sumsub-warns-e-commerce-healthtech-and-fintech-at-risk/)

This evidence is almost entirely about *individual* identity documents used in consumer KYC (e.g.
onboarding a person), not specifically *business* documents used in merchant KYB (the entry's actual
context - incorporation certificates, GST registration, bank statements for a shell business). The
inferential leap - "if generative AI can fabricate a convincing government ID for $15, it can
similarly fabricate business registration documents" - is reasonable but unverified by any specific
reported merchant-KYB incident.

**Recommended action:** keep in "Emerging, component evidence" (correct tier already), but soften
`real_world_evidence` text to make the individual-KYC-vs-business-KYB distinction explicit, e.g.:
"AI-generated synthetic identity documents are a documented and rapidly growing fraud vector in
consumer KYC (Sumsub: +300% in the US, 2025). Extension to business-registration documents in a
merchant KYB context is inferred by capability, not yet independently reported."

---

### UPI-COLLECT-VOICECLONE-01 - Voice clone + merchant collect impersonation (Card 7, rewritten)

**Verdict: Confirmed - the entry's own existing caveat holds up; strengthen citations.**

Two claims underlie this entry:

1. **P2P collect was discontinued 1 October 2025 per a 29 July 2025 NPCI circular.** Verified
   independently across five separate outlets, all agreeing on both dates and the fraud-reduction
   rationale:
   - [NPCI To End UPI Person To Person Collect Requests From October - Angel One](https://www.angelone.in/news/market-updates/npci-to-end-upi-person-to-person-collect-requests-from-october-to-curb-fraud)
   - [NPCI To Stop P2P Collect Payments From Oct 1 - MediaNama](https://www.medianama.com/2025/08/223-npci-p2p-collect-payments-oct-1-what-it-means/)
   - [NPCI to end P2P 'collect' requests on UPI from October - YourStory](https://yourstory.com/2025/08/npci-to-ends-p2p-collect-requests-on-upi-by-october-amid-fraud-concerns)
   - Merchant collect (Amazon, Flipkart, Swiggy, Zomato, IRCTC etc.) explicitly continues unchanged
     - directly supports the entry's premise that the attack must migrate into merchant-identity
     impersonation.

2. **Voice-clone fraud targeting Indian banking/payment customers is reported.** Verified: CERT-In
   issued a specific, dated, named advisory - **CIAD-2024-0084** - on voice-clone fraud awareness.
   A high-profile named incident also exists: a cloned voice of Bharti Airtel chairman Sunil Bharti
   Mittal was used in an attempted fraud targeting a senior executive.
   - [AI Voice Cloning Scams Raise Alarm Over India's Digital Payment Safety - The420.in](https://the420.in/ai-voice-cloning-scams-india-upi-cyber-fraud-threat/)

The entry's own `real_world_evidence` field already says the merchant-collect migration specifically
"is inferred from the regulatory change, not yet independently evidenced - label as such." That
self-assessment is correct and should not be changed. What should change: add the CERT-In advisory
ID and the specific outlet citations above so the two verified halves (P2P discontinuation; voice
clone fraud existing) are traceable, leaving only the migration inference explicitly flagged as
inference.

**Action:** keep tier and overall framing; strengthen citations in the expanded card as above.

---

## Summary of recommended catalogue changes

| Entry | Current tier | Action |
|---|---|---|
| DIGITALARREST-01 | Observed | Keep tier. Fix/replace the unverifiable "₹1,616 cr / 63,481 complaints, nine months" figure in the D2 fix-log row |
| KYCEXPIRY-01 | Observed | Keep as-is |
| BINAUTO-01 | Observed | Keep as-is |
| MULESPLIT-01 | Observed | Keep tier; soften IMPS-specificity wording |
| SHELLNET-01 | Observed | **Downgrade to Emerging, component evidence**; soften wording |
| TRANSLAUND-01 | Observed | Keep as-is |
| SYNTHID-01 | Observed | Keep as-is |
| CARDLOAD-01 | Observed | **Downgrade to Emerging, component evidence** |
| 3DSDEEPFAKE-01 | Emerging | Keep as-is |
| MULEAI-01 | Emerging | Keep as-is |
| ADVMODEL-PROBE-01 | Emerging | Keep as-is |
| ATO-DEEPFAKECALL-01 | Emerging | Keep tier; add stronger citation |
| BNPL-SYNTHFARM-01 | Emerging | Keep as-is |
| KYB-SYNTHDOC-01 | Emerging | Keep tier; soften individual-KYC-vs-KYB wording |
| VOICECLONE-01 (merchant) | Emerging | Keep as-is; strengthen citations in expanded card |
