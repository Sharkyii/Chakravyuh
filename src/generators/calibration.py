"""Every distribution parameter used by the generators lives here, nowhere
else. Each constant carries a comment saying where it comes from: a cited
public figure, or an explicit "reasoned assumption" when no public dataset
gives us the number. Assumptions get checked for plausibility in the
validation report (src/validation/) against IEEE-CIS / PaySim / BankSim /
ULB marginals -- that comparison is what earns the fidelity score, not the
citation alone.

Anything with a regulatory limit attached carries the date it was true as
of. UPI limits moved more than once in 2025; a stale number here is a
defect, not a style issue.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.schema.common import IST

# ---------------------------------------------------------------------------
# Simulation window
# ---------------------------------------------------------------------------

# 12-week synthetic window. The exact calendar dates are arbitrary -- nothing
# in the brief ties the dataset to real elapsed time -- but datetime.weekday()
# still needs concrete dates to derive day-of-week effects from.
SIM_START = datetime(2026, 3, 2, 0, 0, 0, tzinfo=IST)  # a Monday
SIM_WEEKS = 12
SIM_END = SIM_START + timedelta(weeks=SIM_WEEKS)

# How far before SIM_START the population already exists. Devices, merchants
# and account ages are drawn as if the population had a history before the
# window starts, not as if everyone opened their account on day 1.
POPULATION_LOOKBACK_DAYS = 365 * 6  # six years covers UPI's mainstream era (launched 2016)

# ---------------------------------------------------------------------------
# Population scale
# ---------------------------------------------------------------------------

# Sized so that at ~30 transactions/party over the 12-week window (see
# legitimate.py, step 3) the total lands inside the 5-10M scale target.
N_CONSUMER_PARTIES = 220_000

# Reasoned assumption: roughly one merchant party per ~25 consumer parties,
# in line with a long-tail SME-heavy merchant base rather than a 1:1000
# enterprise-only base. Tuned in validation, not sourced.
N_MERCHANTS = 9_000

# ---------------------------------------------------------------------------
# Party -- account age
# ---------------------------------------------------------------------------

# Mixture: most active parties have a multi-year tenure (UPI/bank accounts
# opened well before the window), with a steady tail of new accounts --
# India's registered-user base has grown continuously rather than saturating.
# Reasoned assumption, not fit to a specific published age histogram.
ACCOUNT_AGE_NEW_FRACTION = 0.18
ACCOUNT_AGE_NEW_MAX_DAYS = 180

# Established-account ages: Gamma(shape, scale) in days, right-skewed with a
# ~3 year mean. Reasoned assumption.
ACCOUNT_AGE_ESTABLISHED_GAMMA_SHAPE = 2.2
ACCOUNT_AGE_ESTABLISHED_GAMMA_SCALE = 480.0
ACCOUNT_AGE_ESTABLISHED_MAX_DAYS = POPULATION_LOOKBACK_DAYS

# ---------------------------------------------------------------------------
# Party -- KYC
# ---------------------------------------------------------------------------

# Reasoned from RBI's tiered KYC structure for bank accounts / PPIs (full KYC
# required for full-limit accounts; min-KYC and video-KYC common for
# wallet-style onboarding); not a specific cited statistic.
KYC_LEVEL_WEIGHTS: dict[str, float] = {
    "full": 0.68,
    "min_kyc": 0.16,
    "video_kyc": 0.11,
    "none": 0.05,
}

# ---------------------------------------------------------------------------
# Party -- income / spend persona
# ---------------------------------------------------------------------------

# The three archetypes the brief names explicitly: salaried, gig/irregular,
# none (students and dependents). Weights are a reasoned assumption.
INCOME_TYPE_WEIGHTS: dict[str, float] = {
    "salaried": 0.35,
    "gig": 0.40,
    "none": 0.25,
}

# Per-archetype persona targets. These seed parties.organic_spend_ratio,
# parties.throughput_ratio_24h and parties.distinct_counterparties_30d as
# *persistent targets* the legitimate transaction generator (step 3) is
# built to realise -- see population.py's module docstring for why these
# fields are generated now even though their schema definition is an
# aggregate over transactions that don't exist yet.
#
# organic_spend_ratio: Beta(alpha, beta) -- P2M spend share of outflow.
# throughput_ratio_24h: Beta(alpha, beta) -- outflow/inflow; higher means
#   more pass-through.
PERSONA_TARGETS: dict[str, dict[str, tuple[float, float]]] = {
    "salaried": {"organic_spend_ratio": (5.5, 4.5), "throughput_ratio_24h": (3.0, 7.0)},
    "gig": {"organic_spend_ratio": (4.5, 5.0), "throughput_ratio_24h": (4.0, 6.0)},
    "none": {"organic_spend_ratio": (6.0, 4.0), "throughput_ratio_24h": (6.0, 4.0)},
}

DISTINCT_COUNTERPARTIES_30D_MEAN: dict[str, float] = {
    "salaried": 9.0,
    "gig": 14.0,
    "none": 6.0,
}

# Legitimate parties incorrectly flagged by the (reactive, laggy) DoT FFRI.
# Reasoned low base rate for a false-positive on a genuine account.
FFRI_FALSE_POSITIVE_RATE = 0.004

# ---------------------------------------------------------------------------
# Party -- geography
# ---------------------------------------------------------------------------

# (city, pincode prefix, weight). Weight is a reasoned approximation of
# relative UPI-active population share across metros/tier-2 cities, not a
# census figure. "other" spreads across a broad tier-3/rural prefix range.
CITY_PINCODE_WEIGHTS: list[tuple[str, str, float]] = [
    ("Mumbai", "400", 0.11),
    ("Delhi", "110", 0.10),
    ("Bengaluru", "560", 0.09),
    ("Hyderabad", "500", 0.07),
    ("Chennai", "600", 0.06),
    ("Kolkata", "700", 0.06),
    ("Pune", "411", 0.06),
    ("Ahmedabad", "380", 0.05),
    ("Jaipur", "302", 0.04),
    ("Lucknow", "226", 0.04),
    ("Surat", "395", 0.03),
    ("Indore", "452", 0.03),
    ("other", "0", 0.26),  # tier-3/rural: prefix drawn from full 100-999 range
]

# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

# StatCounter's India mobile OS share has run ~95/4 Android/iOS for years;
# rounded and treated as approximate, not a point-in-time citation.
DEVICE_TYPE_WEIGHTS: dict[str, float] = {
    "android": 0.90,
    "ios": 0.05,
    "desktop": 0.04,
    "pos_terminal": 0.0,  # pos_terminal devices belong to merchants, not consumers
    "other": 0.01,
}

# Device-history pattern per consumer party. Reasoned assumption: most people
# keep one stable device; a real minority changes device or shares one.
DEVICE_PATTERN_WEIGHTS: dict[str, float] = {
    "stable_single": 0.80,
    "upgraded_during_window": 0.10,
    "shared_household": 0.07,
    "multi_device": 0.03,
}

# (os_name, os_version) pairs kept together so desktop's mixed Windows/macOS
# population never produces an inconsistent name/version combination.
OS_NAME_VERSION: dict[str, list[tuple[str, str]]] = {
    "android": [("Android", v) for v in ["11", "12", "13", "14", "15"]],
    "ios": [("iOS", v) for v in ["16", "17", "18"]],
    "desktop": [
        ("Windows", "11"), ("Windows", "10"), ("macOS", "15"), ("macOS", "14"),
    ],
    "other": [("unknown", "unknown")],
}

DEVICE_MODELS: dict[str, list[str]] = {
    "android": [
        "Samsung Galaxy M14", "Samsung Galaxy S23", "Redmi Note 13",
        "Redmi 12", "realme narzo 60", "Vivo Y28", "OPPO A78", "Pixel 8",
        "OnePlus Nord CE4", "Motorola Edge 50",
    ],
    "ios": ["iPhone 13", "iPhone 14", "iPhone 15", "iPhone SE (3rd gen)"],
    "desktop": ["Desktop PC", "Laptop"],  # OS-agnostic; os_name/os_version carry the OS
    "other": ["Unknown device"],
}

# ---------------------------------------------------------------------------
# Merchants
# ---------------------------------------------------------------------------

# MCC weights for what Indian consumers actually transact with. Reasoned
# ranking (grocery/food/fuel/ecommerce dominate by transaction count), not a
# sourced MCC-level breakdown.
MCC_WEIGHTS: dict[int, float] = {
    5411: 0.16,  # grocery stores / supermarkets
    5812: 0.14,  # restaurants
    5541: 0.09,  # fuel / service stations
    5964: 0.10,  # direct marketing / ecommerce marketplaces
    4900: 0.06,  # utilities
    5912: 0.06,  # pharmacies
    5651: 0.05,  # family clothing stores
    5999: 0.06,  # misc retail
    4121: 0.05,  # taxi / rideshare
    5732: 0.04,  # electronics
    7011: 0.02,  # hotels
    5813: 0.02,  # bars / drinking places
    8299: 0.03,  # education services
    6300: 0.02,  # insurance
    5983: 0.02,  # fuel dealers (LPG etc.)
    4814: 0.04,  # telecom services
    5262: 0.04,  # direct marketing / marketplaces (secondary bucket)
}

# Multiplier applied to the rail-level amount draw (issues.md I16 -- amounts
# used to be MCC-independent, contradicting BankSim's documented shape:
# "high-frequency categories skew toward small amounts; low-frequency
# categories skew toward much larger amounts" (data/reference/banksim.json,
# amount_by_category_shape). Everyday/high-frequency MCCs get multipliers
# below 1.0, travel/insurance/electronics-adjacent low-frequency MCCs above
# it. Reasoned relative scale, not a per-MCC cited figure -- the shape is
# what's sourced, not the exact ratios.
MCC_AMOUNT_MULTIPLIER: dict[int, float] = {
    5411: 0.55,  # grocery -- frequent, small basket
    5812: 0.70,  # restaurants
    5541: 0.90,  # fuel
    5964: 1.10,  # ecommerce marketplaces
    4900: 0.65,  # utilities -- regular bill size
    5912: 0.45,  # pharmacies -- small, frequent
    5651: 1.30,  # clothing
    5999: 0.80,  # misc retail
    4121: 0.50,  # taxi / rideshare
    5732: 2.20,  # electronics -- BankSim's es_tech is low-frequency/high-value
    7011: 4.50,  # hotels -- BankSim's es_hotelservices/es_travel are the clearest high-value tail
    5813: 0.60,  # bars
    8299: 1.80,  # education services
    6300: 2.50,  # insurance -- premium-sized, infrequent
    5983: 1.00,  # fuel dealers (LPG etc.)
    4814: 0.40,  # telecom -- small, frequent
    5262: 1.10,  # marketplaces (secondary bucket)
}
DEFAULT_MCC_AMOUNT_MULTIPLIER = 1.0

# Day-of-week weights, Monday=0 .. Sunday=6 (Python's datetime.weekday()).
# issues.md I15 -- the generator previously drew timestamps uniformly across
# the whole window with only an hour-of-day nudge, producing a perfectly flat
# day-of-week histogram, contradicting the brief's own spec ("salary-day
# spikes, weekend patterns"). Weekend lift sized to actually register against
# src/validation/marginals.py's non-uniformity check (needs max-min > 0.5/7 ≈
# 0.071) -- an earlier, gentler version of this table was directionally
# correct but too subtle to clear that bar. Reasoned shape (weekend
# leisure/grocery spend meaningfully above weekday troughs is a standard,
# well-documented retail pattern), not fit to a cited per-weekday statistic.
DAY_OF_WEEK_WEIGHTS: list[float] = [0.11, 0.11, 0.11, 0.12, 0.15, 0.20, 0.20]

# Pareto shape for merchant transaction-volume share: low alpha -> heavier
# tail -> a few large merchants dominate volume while most are small.
# Reasoned assumption (typical of retail/payments merchant bases generally),
# tuned in validation against reference merchant-cardinality stats.
MERCHANT_VOLUME_PARETO_ALPHA = 1.4

# Doc gives merchants.kyb_level no explicit enum values; these two tiers are
# a reasoned choice, not taken from the schema doc.
KYB_LEVEL_WEIGHTS: dict[str, float] = {"full": 0.62, "basic": 0.38}
KYB_DOCS_VERIFIED_AGAINST_REGISTRY_PROB = 0.55  # format-valid-only is common; full registry check less so

VOLUME_GROWTH_CURVE_WEIGHTS: dict[str, float] = {"organic": 0.75, "step": 0.15, "spike": 0.10}

# Merchant onboarding spread: most merchants predate the window; a minority
# onboard organically during it (see brief: "onboarding dates spread across
# and before the window").
MERCHANT_ONBOARDED_BEFORE_WINDOW_FRACTION = 0.85
MERCHANT_ONBOARDING_LOOKBACK_DAYS = 365 * 4

# Baseline 30-day rates, small merchant-level jitter applied on top (Beta
# distributions keep them in [0, 1] and right-skewed toward low values, which
# is what real decline/chargeback/refund rates look like).
CHARGEBACK_RATE_30D_BETA = (1.2, 400.0)  # mean ~0.003
REFUND_RATE_30D_BETA = (2.0, 60.0)  # mean ~0.032
DECLINE_RATE_30D_BETA = (3.0, 45.0)  # mean ~0.062

SETTLEMENT_OUTFLOW_LATENCY_H_MEAN = 30.0  # T+1-ish, typical PSP settlement cycle
SETTLEMENT_OUTFLOW_LATENCY_H_SD = 10.0

# ---------------------------------------------------------------------------
# Legitimate transaction generation
# ---------------------------------------------------------------------------

# Mean 12-week transaction count by persona. These are deliberately modest so
# production scale lands in the 5-10M transaction target when combined with the
# 220k consumer population. Reasoned assumption; validation checks realised
# distributions rather than treating these as sourced facts.
LEGIT_TXN_MEAN_BY_INCOME_TYPE: dict[str, float] = {
    "salaried": 34.0,
    "gig": 40.0,
    "none": 24.0,
}

# Rail mix for legitimate P2M and P2P outflow. Reasoned India-focused payment
# mix for a synthetic challenge dataset, not a claim about production shares.
LEGIT_P2M_RAIL_WEIGHTS: dict[str, float] = {
    "upi_p2m": 0.72,
    "card_cnp": 0.12,
    "card_cp": 0.08,
    "wallet": 0.08,
}

LEGIT_P2P_RAIL_WEIGHTS: dict[str, float] = {
    "upi_p2p": 0.76,
    "imps": 0.13,
    "neft": 0.06,
    "wallet": 0.05,
}

# Legitimate sessions are usually on a known device, but normal edge cases
# exist: a borrowed household phone, browser checkout on desktop, or a replaced
# device before reputation has caught up.
LEGIT_KNOWN_DEVICE_PROB = 0.985

# Non-fraud operational outcomes: ordinary declines and authentication failures
# must exist so later models do not learn that all legitimate traffic approves.
LEGIT_DECLINE_PROB = 0.018
LEGIT_AUTH_FAILURE_PROB = 0.006

# Beneficiary setup for first-use legitimate payments. These are not regulatory
# limits; they are behavioural ranges used to make first-use timing plausible.
LEGIT_FIRST_BENEFICIARY_ADDED_MIN_S = 30
LEGIT_FIRST_BENEFICIARY_ADDED_MAX_S = 45 * 24 * 60 * 60
LEGIT_EXISTING_BENEFICIARY_MIN_AGE_S = 7 * 24 * 60 * 60
LEGIT_EXISTING_BENEFICIARY_MAX_AGE_S = 2 * 365 * 24 * 60 * 60

# Five representative Indian consumer/mobile ISP ASNs, drawn uniformly. Shared
# between src/generators/legitimate.py and src/attacks/framework.py so that
# fraud rows can't be trivially separated from legitimate ones by a single
# hardcoded ASN value never appearing in the other population (issues.md I17
# -- found via feature-importance inspection after fixing I6/I7: with the
# structural campaign-shape leak closed, ip_asn immediately became a new
# near-perfect proxy at 81% feature importance, because every attack row
# defaulted to the same one ASN while legitimate rows chose among five).
IP_ASN_POOL: list[str] = ["AS55836", "AS45609", "AS9829", "AS9498", "AS4755"]
