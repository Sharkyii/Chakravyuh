# Model Validation Strategy: Gen 5 Against Real Datasets

## Overview
Validate Chakravyuh Gen 5 model against two real-world fraud datasets:
1. **IEEE Fraud Detection** (Kaggle) - 590k transactions, card/identity features
2. **Cifer Dataset** (Mobile money) - 1.5M transactions, P2P payment flows

---

## Dataset Characteristics

### IEEE Fraud Detection
- **Size:** ~590k transactions (train: 590k, test: ~404k)
- **Fraud Rate:** ~3.5% (realistic)
- **Features:** 434 columns (identity + transaction features)
  - Transaction: amount, time, product type, card/device info
  - Identity: email domain, IP, device type, email/phone verified
- **Challenge:** High-dimensional (many anonymized features V1-V339)
- **Kaggle Baseline:** Best public LB score ~0.95 AUC

### Cifer Dataset (Payment Fraud)
- **Size:** 1.5M transactions
- **Fraud Rate:** ~0.13% (lower than realistic, but real distribution)
- **Features:** 11 columns (simpler schema)
  - Transaction: step, type, amount, balance changes
  - Parties: payer, payee (anonymized)
  - Flag: isFraud, isFlaggedFraud
- **Attack Type:** All types (TRANSFER, CASH_OUT, PAYMENT, etc.)
- **Realistic:** Real payment network behavior

---

## Validation Approach

### Phase 1: Feature Mapping (Offline)
**Goal:** Map Chakravyuh's 23 features → Real dataset features

| Chakravyuh Feature | IEEE Column | Cifer Column | Type |
|---|---|---|---|
| amount | TransactionAmt | amount | Direct |
| device_is_known | DeviceType | (none) | Engineered |
| ip_is_proxy | IP_risk | (none) | Engineered |
| velocity_amount | (none) | (infer from step) | Engineered |
| user_age_days | dist_days | (none) | Engineered |
| mcc_category | ProductCD | type | Direct |

**Challenge:** IEEE and Cifer don't have identical features.
**Solution:** Build feature adapters that compute Chakravyuh features from raw data.

---

### Phase 2: Cross-Dataset Evaluation
**Goal:** Test Gen 5 model on real fraud patterns

#### Scenario A: IEEE Fraud Detection
```python
# Load IEEE training data
ieee_train = pd.read_csv('train_transaction.csv').merge(
    pd.read_csv('train_identity.csv'), 
    on='TransactionID'
)

# Compute Chakravyuh features
chakravyuh_features = compute_features(ieee_train)

# Score with Gen 5 model
gen5_scores = gen5_model.predict_proba(chakravyuh_features)

# Evaluate
ieee_auc = roc_auc_score(ieee_train['isFraud'], gen5_scores[:, 1])
ieee_pr_auc = average_precision_score(ieee_train['isFraud'], gen5_scores[:, 1])

# Expected: PR-AUC 75-85% (lower than synthetic Gen 5 attacks, but good)
```

#### Scenario B: Cifer Mobile Money
```python
# Load Cifer data
cifer_df = pd.read_csv('Cifer-Fraud-Detection-Dataset-AF-part-2-14.csv')

# Compute features
chakravyuh_features = compute_features(cifer_df)

# Score
cifer_scores = gen5_model.predict_proba(chakravyuh_features)

# Evaluate
cifer_auc = roc_auc_score(cifer_df['isFraud'], cifer_scores[:, 1])
cifer_recall_at_fpr = recall_at_fpr(cifer_df['isFraud'], cifer_scores[:, 1], 0.001)

# Expected: PR-AUC 70-80%, Recall @ 0.1% FPR 50-70%
```

---

### Phase 3: Evasion Analysis
**Goal:** Test if real fraud uses same evasion patterns as Gen 3/4/5

```python
# Identify real fraud that Gen 5 misses
missed_fraud = cifer_df[
    (cifer_df['isFraud'] == 1) & 
    (gen5_scores[:, 1] < 0.5)  # Threshold 50%
]

# Analyze patterns
for idx, row in missed_fraud.head(20).iterrows():
    features = chakravyuh_features.iloc[idx]
    
    # Is it feature-hiding? (Gen 3)
    if high_velocity(features) and balanced_amounts(features):
        print(f"Case {idx}: Feature-hiding pattern (Gen 3)")
    
    # Is it ensemble trading? (Gen 4)
    if conflicting_signals(features):
        print(f"Case {idx}: Ensemble trading pattern (Gen 4)")
    
    # Is it multi-family? (Gen 5)
    if multi_stage_pattern(features):
        print(f"Case {idx}: Multi-family pattern (Gen 5)")
```

**Validation Question:** Do real frauds match our simulated attack families?
- If YES → Gen 5 curriculum is realistic
- If NO → Need to identify new attack families for Gen 6

---

### Phase 4: Fairness & Bias Check
**Goal:** Ensure model doesn't discriminate

```python
# By transaction amount
small_amt = cifer_df[cifer_df['amount'] < 100]
large_amt = cifer_df[cifer_df['amount'] > 100000]

small_auc = roc_auc_score(small_amt['isFraud'], gen5_scores[small_amt.index])
large_auc = roc_auc_score(large_amt['isFraud'], gen5_scores[large_amt.index])

# Acceptable if diff < 5%

# By transaction type (TRANSFER, CASH_OUT, etc.)
by_type = cifer_df.groupby('type').apply(
    lambda df: roc_auc_score(df['isFraud'], gen5_scores[df.index])
)
print(by_type)  # Should be balanced across types
```

---

### Phase 5: Production Readiness Score
**Goal:** Quantify real-world readiness

| Metric | Target | IEEE | Cifer |
|---|---|---|---|
| PR-AUC | >75% | ? | ? |
| Recall @ 0.1% FPR | >50% | ? | ? |
| False Positive Rate @ 95% Recall | <2% | ? | ? |
| Attack Family Coverage | >80% | ? | ? |

**Pass if:** All metrics hit targets on BOTH datasets

---

## Implementation Plan

### Step 1: Build Feature Adapters
```python
# stage5/validation/real_data_adapters.py
class IEEEAdapter:
    @staticmethod
    def compute_features(ieee_df):
        # Map IEEE columns → Chakravyuh features
        features = pd.DataFrame()
        features['amount'] = ieee_df['TransactionAmt']
        features['device_is_known'] = (ieee_df['DeviceType'] != 'unknown')
        # ... 21 more features
        return features

class CiferAdapter:
    @staticmethod
    def compute_features(cifer_df):
        # Map Cifer columns → Chakravyuh features
        features = pd.DataFrame()
        features['amount'] = cifer_df['amount']
        features['velocity_amount'] = cifer_df.groupby('nameOrig')['amount'].rolling(10).sum()
        # ... 21 more features
        return features
```

### Step 2: Run Cross-Dataset Evaluation
```bash
python3 stage5/validation/cross_dataset_evaluation.py \
    --gen5-model stage5/data/gen5_evaluation_report.json \
    --ieee data/reference/ieee-fraud-detection.zip \
    --cifer data/reference/Cifer-Fraud-Detection-Dataset-AF-part-2-14.csv \
    --output stage5/validation/real_data_results.json
```

### Step 3: Generate Report
```
Real Data Validation Report
===========================
IEEE Dataset: PR-AUC 78%, Recall @ 0.1% FPR 62%
Cifer Dataset: PR-AUC 72%, Recall @ 0.1% FPR 58%
Attack Family Match: 85% (17/20 patterns found)
Production Ready: YES ✅
```

---

## Success Criteria

✅ **Model Generalizes**
- Performs >70% on both real datasets
- Pattern matches Gen 3/4/5 attacks

✅ **No Bias**
- AUC within 3% across transaction amounts
- AUC within 5% across payment types

✅ **Production Ready**
- False positives <2% at 95% recall
- Inference latency <50ms

❌ **Failure Cases**
- PR-AUC <60% on real data (model overfit to synthetic)
- New attack patterns not seen in Gen 3/4/5 (need Gen 6)
- Significant bias by amount/type (retrain with stratification)

---

## Next: Raise Questions to Mastercard

When you submit, you can note:
1. **"How should we handle domain shift?"** (synthetic vs. real)
2. **"What fraud families matter most?"** (prioritize Gen 6)
3. **"Should we optimize for recall or precision?"** (business tradeoff)

This shows judges you understand the gap between lab and production.
