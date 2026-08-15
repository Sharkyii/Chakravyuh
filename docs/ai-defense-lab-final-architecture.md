# Mastercard Innovation Challenge 2026 — Final Project Architecture

## AI Defense Lab for Payment Security

**Project concept:** An adaptive adversarial payment-security platform that uses GenAI to generate evolving synthetic fraud campaigns, simulates them inside a realistic payment environment, detects transaction risk and compromised user intent, correlates fraud across payment networks, and continually improves its defense using verified feedback.

---

## 1. Final product thesis

The system is built as one closed loop:

```text
ATTACK
  ↓
SIMULATE
  ↓
DETECT
  ↓
EXPLAIN
  ↓
MITIGATE
  ↓
VERIFY
  ↓
LEARN
  ↓
ATTACK AGAIN
```

The product is not simply a fraud classifier or an attack generator. It is an **adaptive Red Team / Blue Team payment-security system**.

The Red Team creates new, controlled fraud scenarios and variants. The Blue Team detects them using multiple intelligence layers. The learning loop captures verified outcomes, identifies blind spots and evaluates challenger models.

---

## 2. Problem definition

The challenge requires one system that:

- identifies emerging GenAI-powered payment fraud vectors;
- generates those attacks at scale as synthetic data;
- detects them using AI/ML;
- demonstrates real-world feasibility in payment environments; and
- shows an evolving attacker/defender loop.

The final system asks three questions:

```text
1. Is this transaction statistically unusual?
2. Is the payment session consistent with legitimate user intent?
3. Is this event connected to a larger fraud campaign?
```

The second question is particularly important for scam-induced or coerced payments where the payment itself may look legitimate.

---

## 3. Design philosophy

### 3.1 Payment-first, not generic cybersecurity

The scope is payment activity across relevant rails and lifecycle stages:

```text
Initiate
   ↓
Authenticate
   ↓
Authorize
   ↓
Settle
   ↓
Dispute
```

Generic cybersecurity attacks that do not affect a payment rail are outside the core scope.

### 3.2 Trust-anchor thinking

Use a verification ladder:

| Level | Meaning |
|---|---|
| V3 | Cryptographic or deterministic verification |
| V2 | Probabilistic verification through rules or ML |
| V1 | One-shot or self-asserted verification |
| V0 | No meaningful verification |

V0/V1 assumptions are major attack surfaces; V2 controls are also exposed to adversarial probing.

### 3.3 Intent as a first-class signal

The system must not reduce fraud to transaction abnormality. It should separately estimate whether the payment session is consistent with deliberate, informed user behavior.

Important examples include:

- unusually short or long confirmation behavior;
- active call during the payment;
- screen sharing;
- accessibility-service activity;
- newly created beneficiary;
- time between beneficiary creation and payment;
- authentication latency;
- repeated PIN attempts;
- amount-entry behavior.

These signals are evidence, not automatic proof of fraud.

### 3.4 Decision-time realism

Only include features that a real issuer, PSP, merchant, payment application or other authorized decisioning component could actually have at scoring time.

Do not use future information such as confirmed fraud, future chargeback outcomes, investigation results or human labels as inference features.

---

## 4. Final high-level architecture

```text
                         ┌─────────────────────────────┐
                         │          NEXT.JS UI          │
                         │                             │
                         │  Command Center             │
                         │  Red Team Lab               │
                         │  Live Incidents             │
                         │  Attack Replay              │
                         │  Network Intelligence       │
                         │  Model Intelligence         │
                         │  Learning Center            │
                         └──────────────┬──────────────┘
                                        │
                                   API / WebSocket
                                        │
                         ┌──────────────▼──────────────┐
                         │           FASTAPI           │
                         │      Security Control Plane │
                         └──────────────┬──────────────┘
                                        │
             ┌──────────────────────────┼───────────────────────────┐
             │                          │                           │
             ▼                          ▼                           ▼
    ┌─────────────────┐       ┌────────────────────┐       ┌─────────────────┐
    │    RED TEAM     │       │     BLUE TEAM      │       │ AI INVESTIGATOR │
    │                 │       │                    │       │                 │
    │ GenAI scenario  │       │ Transaction model  │       │ LLM analyst     │
    │ generator       │       │ Intent/session     │       │ Explanation     │
    │ Attack variants │       │ Identity/merchant  │       │ Investigation   │
    │ Campaign engine │       │ Graph intelligence │       │ Summaries       │
    └────────┬────────┘       └──────────┬─────────┘       └─────────────────┘
             │                           │
             ▼                           ▼
    ┌─────────────────┐        ┌────────────────────┐
    │ Synthetic       │        │    Risk Fusion     │
    │ Payment World   │───────►│                    │
    │                 │        │ Transaction risk   │
    │ Parties         │        │ Intent risk        │
    │ Devices         │        │ Identity risk      │
    │ Merchants       │        │ Graph risk         │
    │ Transactions    │        └─────────┬──────────┘
    └─────────────────┘                  │
                                         ▼
                                ┌───────────────────┐
                                │   POLICY ENGINE   │
                                │                   │
                                │ ALLOW             │
                                │ MONITOR           │
                                │ STEP-UP           │
                                │ HOLD / BLOCK      │
                                └─────────┬─────────┘
                                          │
                                          ▼
                                ┌───────────────────┐
                                │ INCIDENT ENGINE   │
                                │                   │
                                │ Correlation       │
                                │ Campaigns         │
                                │ Alerts            │
                                │ Evidence          │
                                └─────────┬─────────┘
                                          │
                 ┌────────────────────────┼─────────────────────────┐
                 │                        │                         │
                 ▼                        ▼                         ▼
            PostgreSQL                 Redis              Event / Audit Store
                 │
                 ▼
         ┌──────────────────┐
         │ FEEDBACK SYSTEM  │
         │                  │
         │ Human labels     │
         │ Outcomes         │
         │ False positives  │
         │ Missed attacks   │
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ DRIFT MONITOR    │
         │                  │
         │ Feature drift    │
         │ Distribution     │
         │ Attack mix       │
         │ Error rates      │
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ MODEL LIFECYCLE  │
         │                  │
         │ Challenger       │
         │ Temporal tests   │
         │ Shadow testing   │
         │ Promotion        │
         └────────┬─────────┘
                  │
                  ▼
              RED TEAM
             AGAIN
```

---

## 5. Core system components

### 5.1 Payment-world generator

Create a believable background population of parties, devices, merchants, accounts, beneficiaries and normal payment behavior. Normal traffic must exist before attack injection.

The goal is not to claim that the generated world is Mastercard production data. The goal is to produce realistic observable payment behavior inside a controlled environment.

### 5.2 Legitimate-lookalike generator

Every meaningful attack family must have legitimate near-neighbours.

```text
New beneficiary
├── fraudulent new beneficiary
└── genuine emergency beneficiary

New merchant
├── fraudulent merchant
└── genuine new merchant

Large transfer
├── fraud-induced transfer
└── legitimate remittance
```

This prevents simplistic rules from appearing artificially strong.

### 5.3 GenAI Red Team

The GenAI layer is responsible for controlled attack scenario generation, variation and evolution.

It should generate:

- attack scenario;
- social-engineering pretext;
- attack intensity;
- victim context;
- campaign strategy;
- behavioral variation; and
- combinations of attack signals.

GenAI generates scenario specifications. The simulator converts them into controlled payment events with known ground truth.

### 5.4 Attack generator design

The catalogue should be mechanism-oriented rather than creating one generator per social pretext. Target roughly 12–15 distinct generator families.

Possible families:

```text
Intent / Social Engineering
Account Takeover
Synthetic Identity
Synthetic Merchant / KYB
Merchant Impersonation
Transaction Laundering
Mandate Abuse
Mule Network
Compromised Device / Session
Adaptive Low-and-Slow Fraud
Model Probing
Coordinated Multi-Account Campaign
```

One generator can contain multiple pretexts such as digital arrest, KYC expiry, romance, job-task and bank-official impersonation when their observable behavior is equivalent.

---

## 6. Canonical data contract

Use a fixed seven-table contract between the simulator, detector, evaluation harness and prototype:

```text
transactions
parties
merchants
mandates
disputes
graph_edges
labels
```

Every attack generator writes this structure. The detector reads it. The web prototype visualizes derived results.

### 6.1 `transactions`

One row per payment attempt, including declines.

Important fields:

```text
Identity/routing:
txn_id, timestamp, rail, channel, direction, payer_id, payee_id, merchant_id

Money:
amount, currency, amount_is_round, MCC, purpose_code

Authentication:
auth_method, auth_result, auth_latency_ms, ECI,
liability_shift, exemption_claimed

Decision:
decision, decline_reason, incumbent issuer risk score

Session/device:
device_id, device_is_known_for_payer, session_id,
session_duration_s, time_on_confirm_screen_s,
beneficiary_first_time, beneficiary_added_ago_s,
pin_attempts, screen_share_active,
call_active_during_txn, accessibility_service_active,
paste_used_in_amount, agent fields where applicable

Geo:
IP country, ASN, proxy indicator, relevant location comparisons
```

### 6.2 `parties`

Important features:

```text
account_age_days
KYC level
KYC completion time
salary credit indicator
organic spend ratio
throughput ratio
distinct counterparties
home pincode
relevant risk-indicator history
```

Ground-truth party types must never leak as model features.

### 6.3 `merchants`

Important merchant intelligence:

```text
declared MCC
inferred MCC
MCC divergence
onboarding time
KYB level
registry verification
time to first transaction
growth pattern
chargeback rate
refund rate
decline rate
settlement account age
settlement outflow latency
```

### 6.4 `mandates`

Important fields:

```text
mandate identity
payer
merchant
maximum amount
actual amount
frequency
creation time
enrollment channel
biller-directory match
notification interaction
cancellation
re-registration
```

### 6.5 `disputes`

Important fields:

```text
dispute identity
transaction
claim timing
reason
claimant history
device continuity
evidence availability
```

Post-event dispute outcomes are ground truth and must not leak into pre-authorization inference.

### 6.6 `graph_edges`

Materialize relationships explicitly.

Important graph statistics:

```text
edge count
edge value
inter-arrival time
source out-degree
destination in-degree
two-hop pass-through
shared devices
shared counterparties
```

### 6.7 `labels`

Ground truth only:

```text
txn_id
is_fraud
attack_id
campaign_id
pretext
is_legit_lookalike
detectable_at
```

`labels` are never inference features.

`detectable_at` distinguishes:

```text
pre_auth
post_auth
post_settlement
only_in_hindsight
```

---

## 7. Blue Team detection architecture

### Layer A — Transaction Intelligence

Primary model:

```text
XGBoost / LightGBM
```

Uses transaction amount, rail, channel, merchant, velocity, device, geo, authentication, beneficiary and historical behavior.

Output:

```text
transaction_risk
```

### Layer B — Intent / Session Intelligence

Purpose: detect behavior consistent with scam-induced, coached or unusual authorization sessions.

Key signals:

```text
time_on_confirm_screen_s
session_duration_s
auth_latency_ms
call_active_during_txn
screen_share_active
accessibility_service_active
beneficiary_added_ago_s
pin_attempts
paste_used_in_amount
device familiarity
```

Initial implementation can use gradient boosting over engineered features. Sequence models can be added only if justified by data and evaluation.

Output:

```text
intent_risk
```

### Layer C — Identity / Merchant Intelligence

Detect:

- synthetic identities;
- mule-like parties;
- suspicious merchants;
- synthetic KYB;
- transaction-laundering indicators.

Output:

```text
identity_risk
merchant_risk
```

### Layer D — Graph Intelligence

Build a graph across parties, devices, merchants, beneficiaries and accounts.

Initial implementation:

```text
NetworkX
+
graph feature engineering
+
tree-based model
```

Potential extension:

```text
GraphSAGE / GAT / other GNN
```

Output:

```text
network_risk
campaign_probability
```

---

## 8. Risk fusion

Conceptually:

```text
Transaction Risk
       +
Intent Risk
       +
Identity/Merchant Risk
       +
Network Risk
       ↓
Overall Risk
```

The first prototype may use calibrated weighted fusion. Later iterations can use a learned meta-model if justified by validation.

The product layer converts the overall score into:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

---

## 9. Policy engine

The policy engine converts risk into an operational action.

```text
LOW
→ approve

MEDIUM
→ approve / monitor

HIGH
→ step-up verification / review

CRITICAL
→ hold / block / create incident
```

The ML layer supplies risk and evidence. The policy engine determines the operational action.

---

## 10. Incident and campaign engine

Individual transactions should be correlated into incidents.

Example:

```text
14 suspicious accounts
7 devices
3 beneficiaries
1 merchant cluster
37 transactions
₹6.2L attempted
```

The system should create:

```text
INCIDENT
Coordinated Mule Campaign
```

Correlation can use graph relationships, temporal proximity, attack family, pretext and shared entities.

---

## 11. Explainability layer

The default UI should answer:

```text
WHY DID WE INTERVENE?

1. Payment session strongly deviates from user baseline
2. Beneficiary was created seconds before payment
3. Active call detected during authorization
4. Destination belongs to a suspicious payment cluster
5. Transaction behavior is inconsistent with historical pattern
```

Detailed evidence can be placed behind an evidence drawer.

For tree-based models, SHAP can provide feature attribution.

The explanation layer must distinguish model evidence from verified ground truth.

---

## 12. GenAI analyst layer

The LLM is not the primary fraud decision-maker.

It acts as an analyst assistant using:

```text
incident summary
risk outputs
model explanations
graph relationships
timeline
attack classification
verified evidence
```

Outputs can include incident summaries, investigation timelines, likely attack mechanisms and concise case notes.

The LLM must not independently override the policy engine.

---

## 13. Learning and feedback loop

The production detector must not train blindly on its own predictions.

Analyst interface:

```text
CONFIRMED FRAUD
FALSE POSITIVE
NEEDS INVESTIGATION
```

Store:

```text
incident_id
prediction
confidence
model_version
analyst label
attack family
timestamp
supporting evidence
```

### 13.1 Active learning

Prioritize labels for:

- uncertain predictions;
- false positives;
- missed attacks;
- new attack variants; and
- drifted populations.

### 13.2 Drift detection

Monitor:

```text
feature distribution
class balance
attack mix
error rate
false-positive rate
false-negative rate
risk-score distribution
```

Potential approaches include PSI, KS-style monitoring and streaming drift detectors such as ADWIN.

### 13.3 Challenger model

Never overwrite the production model immediately.

```text
Current Champion
       │
New verified data
       ↓
Challenger Model
       ↓
Temporal Evaluation
       ↓
Shadow Test
       ↓
Promotion Decision
```

Promotion requires improvement on payment-relevant metrics.

### 13.4 Closed-loop adversarial improvement

```text
Blue Team detects
       ↓
Identify blind spots
       ↓
Red Team generates variants targeting blind spot
       ↓
Run fresh attack simulation
       ↓
Verify labels
       ↓
Update training set
       ↓
Train challenger
       ↓
Shadow evaluation
       ↓
Promote if materially better
       ↓
Red Team attacks again
```

This is the central novelty of the final architecture.

---

## 14. Data strategy

Synthetic data should be heavily used, but not as the only source of truth.

### Public benchmark data

Potential sources:

```text
IEEE-CIS Fraud Detection
PaySim
BankSim
ULB Credit Card Fraud
Elliptic, where graph experiments are relevant
Fraud Detection Handbook benchmark/simulator
```

These anchor the background distributions and provide baselines.

### Synthetic background data

Generate realistic parties, devices, merchants and payment behavior for scale, temporal control, rare-event coverage and reproducibility.

### Synthetic attack data

Use the GenAI Red Team for rare-event generation, attack diversity, campaign simulation and adversarial evaluation.

### Training/evaluation separation

Do not use identical attack templates and distributions for train and test.

```text
Training
→ earlier temporal periods
→ selected attack families

Validation
→ later temporal periods
→ known families with changed parameters

Adversarial test
→ later temporal periods
→ held-out attack family and/or novel combinations
```

---

## 15. Evaluation philosophy

Primary metrics:

```text
Precision @ 0.1% FPR
Precision @ 1% FPR
PR-AUC
Recall
F1
```

Secondary metrics:

```text
ROC-AUC
decision latency
coverage
blocked fraud amount
false-positive cost
```

Business-facing metrics:

```text
fraud value detected
fraud value prevented
false positives
decision latency
attack detection coverage
unseen-attack detection
```

### Anti-circular evaluation

The system must demonstrate that the Blue Team is not merely learning simulator rules.

Required tests:

```text
Temporal split
Held-out attack family
Legitimate lookalikes
Attack parameter shift
Campaign structure shift
```

---

## 16. Web prototype design

The UI should look like a payment-security operations platform, not a metadata viewer.

### Command Center

Show:

```text
Threat level
Active incidents
Fraud detected
Fraud prevented
Precision
Precision @ low FPR
False positives
Current model version
Drift status
```

### Red Team Lab

Controls:

```text
Attack family
Pretext
Population
Attack intensity
Campaign size
Adaptive / fixed mode

[ LAUNCH CAMPAIGN ]
```

The raw generator metadata stays behind the system.

### Live Incidents

Display:

```text
incident type
risk
confidence
affected entities
estimated amount
current action
```

### Incident Investigation

Show:

```text
Incident summary
Timeline
Risk score
Attack classification
Top evidence
Entity relationships
Mitigation
Analyst feedback
```

### Attack Replay

Display a live timeline:

```text
T+00  campaign begins
T+08  session manipulation
T+16  beneficiary added
T+24  payment initiated
T+25  intent risk rises
T+26  graph risk rises
T+27  payment blocked
```

### Network Intelligence

Show relationships between users, devices, accounts, beneficiaries and merchants, highlighting suspicious communities.

### Model Intelligence

Show:

```text
precision
recall
F1
PR-AUC
precision at low FPR
model version
feature drift
attack coverage
champion/challenger comparison
```

### Learning Center

Show:

```text
verified labels
false positives corrected
missed attacks
new attack variants
drift alerts
retraining candidates
challenger performance
promotion history
```

---

## 17. Product abstraction principle

The system has three information layers:

```text
PRODUCT LAYER
Human-readable incident
      ↓
ANALYST LAYER
Evidence, timeline, graph, actions
      ↓
ML LAYER
Features, SHAP, scores, raw signals
```

The default UI should live in the first two layers. The third layer exists for technical inspection, debugging and judging/demo depth.

This keeps the interface professional without hiding the ML evidence.

---

## 18. Safety and operational constraints

All attack generation must remain inside a controlled synthetic environment.

Do not:

- target real people;
- attack real banks or payment systems;
- send real phishing messages;
- conduct real credential harvesting;
- use real cardholder data;
- use real production payment infrastructure; or
- test against third parties.

Use synthetic identities, fictional merchants, synthetic accounts, synthetic transactions and authorized local infrastructure.

---

## 19. Recommended technology stack

### Frontend

```text
Next.js
TypeScript
Tailwind CSS
shadcn/ui
Recharts / ECharts
```

### Backend

```text
FastAPI
Python
WebSockets
```

### Machine learning

```text
scikit-learn
XGBoost or LightGBM
SHAP
```

### NLP / GenAI

```text
LLM API through an OpenAI-compatible client
Structured JSON outputs
```

### Graph

```text
NetworkX
```

Potential extension:

```text
PyTorch Geometric
GraphSAGE / GAT
```

### Persistence

```text
PostgreSQL
Redis
```

### Deployment

```text
Docker
Docker Compose
```

---

## 20. Recommended repository structure

```text
ai-defense-lab/
│
├── README.md
├── docker-compose.yml
├── .env.example
├── requirements.txt
│
├── apps/
│   ├── frontend/
│   └── backend/
│
├── ml/
│   ├── transaction/
│   ├── intent/
│   ├── identity/
│   ├── graph/
│   ├── fusion/
│   ├── explainability/
│   └── evaluation/
│
├── simulation/
│   ├── population/
│   ├── legitimate/
│   ├── lookalikes/
│   ├── attacks/
│   ├── campaigns/
│   └── engine/
│
├── genai/
│   ├── scenario_generation/
│   ├── attack_mutation/
│   └── analyst/
│
├── learning/
│   ├── feedback/
│   ├── active_learning/
│   ├── drift/
│   ├── retraining/
│   └── model_registry/
│
├── graph/
│
├── database/
│   ├── schema/
│   ├── migrations/
│   └── seeds/
│
├── configs/
├── notebooks/
├── tests/
└── docs/
    ├── attack_catalogue.md
    ├── data_dictionary.md
    └── evaluation.md
```

---

## 21. Definition of done

The final system is complete when it can demonstrate this end-to-end flow:

```text
Start a controlled Red Team campaign
        ↓
Generate synthetic payment activity
        ↓
Inject attack + legitimate lookalikes
        ↓
Score with the Blue Team stack
        ↓
Correlate events into incidents/campaigns
        ↓
Generate explainable risk decisions
        ↓
Apply allow / monitor / step-up / block
        ↓
Capture verified analyst feedback
        ↓
Identify detector blind spots
        ↓
Generate a new attack variant
        ↓
Train/evaluate a challenger
        ↓
Compare champion vs challenger
        ↓
Promote only when justified
        ↓
Replay the entire loop
```

---

## 22. Core engineering principles

### Principle 1 — Background before attack

The legitimate payment world must be believable before attack injection.

### Principle 2 — Intent is not the same as anomaly

A legitimate customer can be unusual. The detector must learn the difference between unusual behavior and malicious/coerced behavior.

### Principle 3 — Ground truth is separate

Labels never become inference features.

### Principle 4 — The LLM is not the fraud judge

Use GenAI for scenario generation, controlled attack evolution and analyst assistance.

### Principle 5 — Do not trust synthetic evaluation alone

Use public data, temporal splits, lookalikes and held-out attack families.

### Principle 6 — Human feedback must be verified

Do not blindly train on model self-predictions.

### Principle 7 — Production is champion/challenger

Never overwrite the production model simply because a new model trained successfully.

### Principle 8 — Every decision must be explainable

The system should be able to answer: **Why did we intervene?**

### Principle 9 — All attack activity stays inside the controlled synthetic environment.

### Principle 10 — The loop is the product

The strongest demonstration is:

```text
attack
→ detection
→ failure analysis
→ evolved attack
→ improved defense
```

---

## 23. Final positioning

# An Adaptive Adversarial AI Defense Lab for Payment Security

### Red Team

Uses GenAI to create and evolve controlled payment-fraud campaigns.

### Blue Team

Uses transaction, intent/session, identity/merchant and graph intelligence to detect them.

### Control Plane

Converts risk into explainable operational actions.

### Learning Loop

Uses verified feedback, active learning, drift monitoring and challenger models to improve the defense.

### Product

Presents the entire system as a payment-security operations center rather than a collection of raw model outputs.

The central differentiator is:

> **The system does not only learn to detect yesterday's fraud. It repeatedly attacks its own defense with controlled, unseen synthetic campaigns and uses the resulting blind spots to improve the next defense.**
