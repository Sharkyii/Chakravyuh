# D3 — Regulatory limit verification (UPI Lite, min-KYC PPI, e-mandate AFA, UPI P2M)

**Last verified:** 18 August 2026, via web research (WebSearch/WebFetch — no NPCI/RBI account
access, PDF circulars on npci.org.in returned HTTP 403 to automated fetches; findings below
are cross-corroborated across multiple independent secondary sources that name a specific
dated primary circular/notification, rather than a single blog post).

This resolves catalogue defect D3 (see `docs/attack-catalogue.md` fix log). Each section below
gives: current value, primary source (circular/notification number + date), effective date, and
a confidence tier:

- **Confirmed** — primary-source circular/notification identified by number and date, and the
  figures are consistent across multiple independent secondary reports of that same circular.
  The raw PDF itself could not be fetched (NPCI blocks non-browser clients), so this is not
  "read the PDF myself" confirmation — treat as strong secondary corroboration of a named
  primary source, not a first-hand primary read.
- **Secondary-sourced estimate** — no specific primary circular number found; figures come from
  consistent reporting but the primary document was not identified.

---

## 1. UPI Lite — per-transaction and total wallet limit

**Current value:** ₹1,000 per transaction; ₹5,000 total wallet balance limit.

**Previous value (what the catalogue's "sub-₹200" / "₹2,000 wallet cap" language was based
on):** ₹500 per transaction, ₹2,000 total wallet limit (themselves already an increase from the
original 2022 launch limit of ₹200/transaction). So the catalogue text was stale by *two*
revisions, not one.

**Source:**
- Policy decision: RBI "Statement on Developmental and Regulatory Policies," 6 December 2024
  (announces the enhancement from ₹500→₹1,000 per-transaction and ₹2,000→₹5,000 wallet limit).
- Operational circular: NPCI, **UPI/OC No. 169-A/FY2024-25** ("Addendum to Enhancement in UPI
  LITE Limits"), issued **27 February 2025**, effective immediately. (Primary PDF:
  `npci.org.in/PDF/npci/upi/circular/2025/UPI-OC-No-169-A-FY202425-Addendum-to-Enhancement-in-UPI-LITE-Limits.pdf`
  — URL confirmed to exist via NPCI's own circular index; content could not be fetched directly,
  403.)
- Also raises the UPI123Pay per-transaction limit from ₹5,000 to ₹10,000 in the same round —
  not directly relevant to this catalogue but noted in case it's useful elsewhere.

**Effective date:** 27 February 2025 (NPCI circular), policy announced 6 December 2024.

**Confidence:** Confirmed (named primary circular + date, corroborated by Business Standard,
Deccan Herald, DD News, and a regulatory tracker (TeamLease RegTech) independently, all citing
the same circular number and figures).

---

## 2. Minimum-KYC PPI (Prepaid Payment Instrument) caps

**Current value:** ₹10,000 maximum monthly loading (cash and non-cash) and ₹10,000 maximum
outstanding balance at any point in time, for "Small PPIs" (the minimum-KYC / minimum-detail
category — OTP-verified mobile number only, no full KYC). Usable only for purchase of goods and
services; no cash withdrawal, no P2P transfer.

**This has NOT changed in 2025** — unlike the other three limits in this file, the min-KYC PPI
cap has been stable since the RBI consolidated Master Direction on PPIs was issued.

**Source:** Master Direction – Reserve Bank of India (Prepaid Payment Instruments) Directions,
2021 (as amended), issued **27 August 2021**, currently in force.

**Important caveat — a revision is pending but NOT yet in effect:** RBI released a **draft**
Master Direction on PPIs, 2026 for public comment (comment window closed **22 May 2026**). As of
this research date (18 August 2026) it has not been finalised/notified, so it is not yet
binding. The draft's own published text for the "Small PPI" category repeats the same ₹10,000
monthly-loading / ₹10,000 balance figures as the 2021 MD — i.e. even the pending draft does not
propose changing this particular number, only the Full-KYC PPI tier (proposed increase to a
₹2 lakh balance/monthly-debit cap, separate from what this catalogue entry needs). Re-check this
section if the 2026 draft is finalised before submission, in case the final text departs from
the draft.

**Effective date:** 27 August 2021 (still governing as of 18 August 2026).

**Confidence:** Confirmed for the currently-governing 2021 Master Direction figures. The
"unchanged going forward" claim is a secondary-sourced estimate (based on the draft 2026 text as
reported by law-firm trackers, not the RBI draft PDF itself) — flag if the final 2026 MD-PPI
diverges.

---

## 3. UPI AutoPay / e-mandate AFA (Additional Factor of Authentication) threshold

**Current value:**
- **General threshold:** ₹15,000 per transaction — recurring e-mandate debits at or below this
  amount can process without AFA (OTP) after the initial AFA-authenticated registration.
- **Category exemption:** ₹1,00,000 per transaction for three specified categories only —
  **mutual fund subscriptions, insurance premium payments, and credit card bill payments.**
  Transactions in these three categories can skip per-debit AFA up to ₹1 lakh; everything else
  (including EMIs/loan repayments) stays at the ₹15,000 general threshold.

So yes — it varies by merchant/payment category, but only via this specific three-category
carve-out, not a general per-MCC schedule.

**Source:** RBI, "Digital Payments – E-Mandate Framework, 2026," notified **21 April 2026**,
reference **RBI/CO.DPSS.POLC.No.S56/02.14.003/2026-27**. This framework consolidates/repeals
roughly eight earlier circulars issued 2019–2024 on e-mandates and recurring transactions (the
₹15,000 general threshold dates to a June 2022 RBI circular; the ₹1 lakh category exemption
dates to a December 2023 RBI announcement; both are now folded into this single 2026
consolidated framework, which is the current authoritative reference).

**Effective date:** 21 April 2026.

**Confidence:** Confirmed (specific RBI notification reference number identified, and the
₹15,000 / ₹1,00,000 figures and the three named categories are consistent across independent
legal/regulatory trackers — SCC Online, Conventus Law, and others reporting the same notification
number).

---

## 4. UPI P2M (person-to-merchant) daily transaction limits

**Current value:**
- **General/default UPI limit (P2P and ordinary P2M):** ₹1 lakh per transaction — unchanged,
  this has been NPCI's baseline ceiling for several years and was not touched by the 2025
  change described below.
- **Higher-limit P2M categories (verified merchants only), effective 15 September 2025:**
  per-transaction limit raised to **₹5 lakh**, with a **₹10 lakh** cumulative 24-hour cap, for:
  capital markets investments, insurance premium payments, travel and tourism, loan
  repayments/collections, and Government e-Marketplace (GeM) transactions. Credit card bill
  payments specifically: ₹5 lakh per transaction, ₹6 lakh cumulative in 24 hours (lower daily
  cap than the other categories).
  - Capital markets and insurance were previously capped at ₹2 lakh/transaction; GeM and travel
    were previously capped at ₹1 lakh/transaction — both raised in this round.

**Source:** NPCI circular, believed to be **UPI/OC No. 185-B/FY2025-26** ("Addendum to OC 185-A
— Implementation of higher per-transaction limit for specific categories in UPI"), issued around
**28 August 2025**, effective **15 September 2025**. The circular's existence, number, and title
were confirmed via NPCI's own circular index (URL:
`npci.org.in/uploads/UPI_OC_No185_B_FY_2025_26_Addendum_to_OC_185_A_Implementation_of_higher_per_transaction_limit_for_specific_categories_in_UPI_ba517a0902.pdf`)
but the PDF content itself could not be fetched (403 to automated clients), and no secondary
source explicitly quoted the OC number alongside the figures — the number-to-figures link here
is my inference from the filename/title matching the widely-reported effective date and category
list, not a direct primary-source read.

**Effective date:** 15 September 2025 (multiple independent outlets — Paytm, DD News, News on
Air, Outlook Money, HDFC Sky — agree on this date and the ₹5 lakh / ₹10 lakh / ₹6 lakh figures).

**Confidence:** Secondary-sourced estimate for the circular-number attribution specifically
(I'm confident in the figures and effective date — 5+ independent outlets converge — but the OC
185-B number-to-content link is inferred, not confirmed by reading the PDF). Treat the **values**
(₹5 lakh/₹10 lakh for the named categories, ₹1 lakh general baseline unchanged) as confirmed by
convergent reporting; treat the **specific circular number cited** as not fully verified.

---

## Summary table

| # | Limit | Current value | Effective | Confidence |
|---|---|---|---|---|
| 1 | UPI Lite per-transaction | ₹1,000 | 27 Feb 2025 | Confirmed |
| 1 | UPI Lite wallet balance | ₹5,000 | 27 Feb 2025 | Confirmed |
| 2 | Min-KYC PPI monthly loading | ₹10,000 | 27 Aug 2021 (unchanged) | Confirmed |
| 2 | Min-KYC PPI balance cap | ₹10,000 | 27 Aug 2021 (unchanged) | Confirmed |
| 3 | E-mandate AFA general threshold | ₹15,000 | 21 Apr 2026 (consolidated; threshold itself dates to Jun 2022) | Confirmed |
| 3 | E-mandate AFA — MF/insurance/credit-card-bill exemption | ₹1,00,000 | 21 Apr 2026 (consolidated; exemption itself dates to Dec 2023) | Confirmed |
| 4 | UPI P2M general/default | ₹1 lakh/txn | unchanged | Confirmed |
| 4 | UPI P2M higher-limit categories (capital markets, insurance, travel, loan repay, GeM) | ₹5 lakh/txn, ₹10 lakh/24hr | 15 Sep 2025 | Values confirmed; circular number inferred, not primary-read |
| 4 | UPI P2M credit card bill payment | ₹5 lakh/txn, ₹6 lakh/24hr | 15 Sep 2025 | Values confirmed; circular number inferred, not primary-read |

## What's still outstanding

- None of the four PDF circulars could be fetched directly (NPCI returns HTTP 403 to
  non-browser clients; RBI's site redirects to a JS-rendered homepage for old press-release
  URLs). All figures above rest on convergent secondary reporting that names a specific primary
  document, not a first-hand read of that document. If a judge or reviewer has direct NPCI/RBI
  portal access, a spot-check against the raw circulars would upgrade these from "strong
  secondary corroboration" to true primary-source confirmation.
- The UPI/OC No. 185-B circular number for the September 2025 P2M limit change (item 4) is the
  single weakest link in this file — re-derive it from NPCI's circular index directly if this
  number appears in the deck.
- The RBI Master Direction on PPIs, 2026 is still in draft as of this research date; if it is
  finalised before the Kaggle submission (31 Aug 2026), re-check section 2 against the final
  text — the draft's Small-PPI figures matched the 2021 status quo, but a final notification
  could still change them.
