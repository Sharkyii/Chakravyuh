# Phase 2: Full Adversarial Retraining Pipeline
## Gen 3 → Gen 4 → Gen 5 Attack Escalation

---

## Overview

**Goal**: Build a curriculum-learning retraining pipeline where each generation of attacks targets the detector's top weaknesses, forcing continuous improvement.

```
Gen 1 (Static)           Gen 2 (Adaptive)          Gen 3 (Feature-Hide)     Gen 4 (Ensemble)       Gen 5 (Multi-Family)
├─ Basic patterns        ├─ Top 2 features         ├─ Top 5 features        ├─ Hide top 10 features ├─ Combine families
├─ 99.42% recall         ├─ 100% recall            ├─ Target <95%           ├─ Target <85%          ├─ Target <70%
└─ Evasion: 0.58%        └─ Evasion: 0%            └─ Evasion: ~5%          └─ Evasion: ~15%        └─ Evasion: ~30%
```

---

## Phase 2A: Gen 3 Attack Generation

### Goal
Generate attacks that hide the **top 5 SHAP features** from the retrained Gen 2 model.

### Files to Create

#### 1. `stage5/adversarial/feature_targeting.py`

```python
def get_top_features(model, threshold=0.10):
    """Extract top N features that exceed 10% importance threshold."""
    importances = model.feature_importances_
    # Sort and return top features
    
def calculate_feature_hiding_difficulty(feature_name):
    """
    How hard is it to hide this feature without looking suspicious?
    
    Easy (score 1.0): 
      - amount (can be varied naturally)
      - txn_hour (transaction time)
    
    Medium (score 0.5):
      - beneficiary_added_ago_s (requires long-term planning)
      - edge_count (requires distributed network)
    
    Hard (score 0.1):
      - is_fraud (can't hide if caught)
      - geo_matches_billing (requires legal address match)
    """
```

#### 2. `stage5/adversarial/gen3_attack_spec.py`

```python
def gen3_adversarial_evasion_spec(top_5_features, gen2_model):
    """
    Gen 3 spec: Hide top 5 features while maintaining campaign viability.
    
    For each feature in top_5:
      - Calculate hiding difficulty
      - Generate parameter overrides
      - Verify campaign stays detectable by legitimate patterns
    
    Example:
      top_features = ['edge_count', 'beneficiary_added_ago_s', 'txn_amount_deviation', ...]
      
      For edge_count (34% importance):
        - Hide by: Use single top counterparty (Gen 2 approach)
        - Plus: Randomize transaction timing (make edges less obvious)
        - Result: edge_count stays low but looks more natural
      
      For beneficiary_added_ago_s (15% importance):
        - Hide by: Add beneficiary weeks in advance (beneficiary_age_floor_s = 60 days)
        - Plus: Use existing receiver accounts instead of new ones
        - Result: beneficiary looks established, natural
    """
```

#### 3. `stage5/adversarial/curriculum_generator.py`

```python
class AdversarialCurriculum:
    """Generate attacks in curriculum order: easy → hard."""
    
    def __init__(self, model):
        self.model = model
        self.top_features = get_top_features(model)
    
    def generate_gen3_variants(self, attack_family='adversarial_evasion', intensity='medium'):
        """
        Generate Gen 3 attacks for each family.
        
        Returns:
          attacks_by_difficulty = {
            'level_1_easy': [...],      # Hide 1 feature
            'level_2_medium': [...],    # Hide 2 features
            'level_3_hard': [...],      # Hide 3+ features
            'level_4_extreme': [...]    # Hide all + ensemble evasion
          }
        """
    
    def estimate_evasion_rate(self, test_set, difficulty_level):
        """
        Estimate what % of attacks will slip through.
        Uses Gen 2 model to score Gen 3 attacks.
        """
```

### Implementation Details

#### Config: `stage5/config/gen3_params.py`

```python
GEN3_FEATURE_TARGETING = {
    'mule_network': {
        'hide_features': ['payer_out_degree', 'edge_count', 'is_two_hop_passthrough'],
        'strategy': 'distribute_across_established_network',
        'params': {
            'use_existing_payees': True,
            'min_beneficiary_age_days': 30,
            'max_transactions_per_counterparty': 2
        }
    },
    'adversarial_evasion': {
        'hide_features': ['edge_count', 'beneficiary_added_ago_s', 'txn_count_last_1h'],
        'strategy': 'blend_with_legitimate_patterns',
        'params': {
            'beneficiary_age_floor_s': 60*86400,  # 60 days
            'spread_transactions': True,
            'randomize_timing': True,
            'mimic_historical_behavior': True
        }
    },
    'account_takeover': {
        'hide_features': ['screen_share_active', 'call_active_during_txn', 'new_device_indicator'],
        'strategy': 'avoid_detection_channels',
        'params': {
            'use_known_device': True,
            'avoid_remote_access': True,
            'mimic_legitimate_session': True
        }
    }
}
```

---

## Phase 2B: Retraining on Gen 3 Attacks

### Files to Create

#### 1. `stage5/training/curriculum_retrain.py`

```python
def retrain_on_gen3_attacks(
    analyst_feedback,           # 50+ verdicts from analysts
    gen3_attacks,              # Generated Gen 3 attack variants
    gen2_model,                # Current model to beat
    curriculum_levels=['easy', 'medium', 'hard', 'extreme']
):
    """
    Retrain using curriculum learning:
    1. Start with easy Gen 3 attacks (1 feature hidden)
    2. Gradually increase difficulty
    3. Mix with analyst feedback + original synthetic data
    4. Measure improvement at each stage
    
    Returns:
      gen3_trained_model, training_log
    """
    
    for level in curriculum_levels:
        # Get attacks at this difficulty level
        level_attacks = gen3_attacks[f'level_{level}']
        
        # Mix with existing data
        training_df = pd.concat([
            original_synthetic_data,
            analyst_feedback_as_training_data,
            level_attacks
        ])
        
        # Retrain
        model = train_fraud_model(training_df)
        
        # Evaluate
        gen2_recall = eval_on_gen2_attacks(model)  # Should stay ~100%
        gen3_evasion = measure_evasion(model, level_attacks)
        
        print(f"Level {level}:")
        print(f"  Gen 2 recall: {gen2_recall:.1%}")
        print(f"  Gen 3 evasion rate: {gen3_evasion:.1%}")
        
        if gen3_evasion > 0.20:  # If >20% slip through, stay longer
            continue_training_at_level(level)
```

#### 2. `stage5/training/evasion_margin_calculator.py`

```python
def measure_evasion_margin(model, attack_variants, threshold=0.45):
    """
    Evasion margin = % of attacks that slip through detector.
    
    Formula:
      evasion_margin = (attacks_not_caught) / (total_attacks)
      
    Target by generation:
      Gen 2: <1% (essentially perfect)
      Gen 3: <5% (acceptable hardness)
      Gen 4: <15% (challenging)
      Gen 5: <30% (hard limit)
    
    Returns:
      {
        'evasion_margin': 0.032,
        'caught': 97,
        'slipped': 3,
        'total': 100,
        'threshold_used': 0.45,
        'status': 'PASS' if evasion < target else 'FAIL'
      }
    """
```

### Evaluation Report: `stage5/validation/gen3_evaluation_report.py`

```python
def generate_gen3_evaluation_report(
    gen2_model,
    gen3_model,
    analyst_feedback_count,
    gen3_attacks
):
    """
    Comprehensive report showing:
    
    1. MODEL PERFORMANCE COMPARISON
       ├─ Gen 2 metrics (baseline)
       │  ├─ PR-AUC: 99.97%
       │  ├─ Recall @ 0.1% FPR: 100.00%
       │  └─ Held-out recall: 100.00%
       └─ Gen 3 metrics (after retraining)
          ├─ PR-AUC: 99.95% (slight drop OK, needed to handle harder attacks)
          ├─ Recall @ 0.1% FPR: 99.80%
          └─ Held-out recall: 99.50% (more realistic)
    
    2. EVASION METRICS
       ├─ Gen 2 attacks on Gen 2 model: 0.0% evasion (should be perfect)
       ├─ Gen 3 attacks on Gen 2 model: 5.2% evasion (why we retrained)
       └─ Gen 3 attacks on Gen 3 model: 1.8% evasion (PASS <5% target)
    
    3. FEATURE IMPORTANCE SHIFT
       └─ Show how top features changed post-retrain
          (should still be meaningful, not random)
    
    4. CURRICULUM EFFECTIVENESS
       ├─ Easy Gen 3: 2.1% evasion → OK
       ├─ Medium Gen 3: 4.8% evasion → Close to limit
       ├─ Hard Gen 3: 7.2% evasion → Requires attention
       └─ Extreme Gen 3: 12.1% evasion → Edge case
    
    5. ANALYST FEEDBACK IMPACT
       └─ Verdicts: 50 collected
          Fraud: 23 confirmed
          Legitimate: 18 confirmed
          Unsure: 9 marked
          (Show how many helped improve model)
    """
```

---

## Phase 2C: Gen 4 Planning (Preview)

### Goal
Attacks that target **ensemble evasion**: hide from combination of top features, not individual ones.

### Gen 4 Spec

```python
GEN4_ENSEMBLE_EVASION = {
    'strategy': 'deceive_multiple_signals_simultaneously',
    'examples': [
        {
            'name': 'low_edge_count_but_high_velocity',
            'description': 'Keep edge_count low (hidden feature) but increase txn_count_last_1h',
            'hiding': ['edge_count', 'beneficiary_added_ago_s'],
            'exposing': ['txn_count_last_1h', 'amount_deviation'],
            'result': 'Model sees different signal pattern'
        },
        {
            'name': 'established_payee_but_new_behavior',
            'description': 'Use old payee (high beneficiary_age) but new amount/timing',
            'hiding': ['beneficiary_added_ago_s'],
            'exposing': ['amount_deviation', 'time_since_prev_txn'],
            'result': 'Trading off one dimension to expose another'
        }
    ]
}
```

### Gen 4 Target
- **Evasion margin**: 10-15%
- **Model recall**: Should drop to 96-98% (harder to maintain 100%)
- **Reason**: Ensemble attacks are structurally harder to defend against

---

## Phase 2D: Gen 5 Planning (Preview)

### Goal
**Multi-family attacks**: Combine attack techniques from different families to create novel patterns.

### Gen 5 Spec

```python
GEN5_MULTI_FAMILY_ATTACKS = {
    'mule_network_meets_account_takeover': {
        'description': 'Mule routing + Remote access control',
        'combines': ['mule_network', 'account_takeover'],
        'result': 'No single feature tells the full story'
    },
    'adversarial_evasion_meets_money_laundering': {
        'description': 'Slow evasion + Layering attacks',
        'combines': ['adversarial_evasion', 'layered_transfers'],
        'result': 'Low velocity but high value'
    }
}
```

### Gen 5 Target
- **Evasion margin**: 20-30%
- **Model recall**: ~90-95% (significant drop, expected)
- **Reason**: Cross-family attacks are rare but dangerous
- **Next step**: Would need new feature engineering, not just retrain

---

## Full Phase 2 Timeline

| Stage | File | Output | Evasion Target | Expected Time |
|-------|------|--------|---|---|
| **2A** | `gen3_attack_spec.py` | Gen 3 attack variants | N/A | 2-3 days |
| **2B** | `curriculum_retrain.py` | Gen 3-trained model | <5% | 3-5 days |
| **2B** | `gen3_evaluation_report.py` | Measurement + proof | <5% achieved | 1 day |
| **2C** | `gen4_attack_spec.py` | Gen 4 attack variants | N/A | 2-3 days |
| **2C** | `gen4_retrain.py` | Gen 4-trained model | <15% | 3-5 days |
| **2D** | `gen5_attack_spec.py` | Gen 5 attack variants | N/A | 2-3 days |
| **2D** | `gen5_retrain.py` | Gen 5-trained model | <30% | 3-5 days |

**Total**: ~3-4 weeks for full Gen 3→4→5 escalation

---

## Success Criteria

### Gen 3
- ✅ Evasion margin < 5% on Gen 3 attacks
- ✅ Gen 2 attacks still caught (no regression)
- ✅ Feature importances remain meaningful

### Gen 4
- ✅ Evasion margin < 15% on Gen 4 attacks
- ✅ Model recall ~96-98% (acceptable drop)
- ✅ Ensemble strategies identified in SHAP

### Gen 5
- ✅ Evasion margin < 30% on Gen 5 attacks
- ✅ Multi-family patterns detected
- ✅ Clear boundary: "This detector works well for known families, struggles with novel combinations"

---

## Why This Matters

**Shows judges**:
1. ✅ Closed-loop actually works (feedback → better detector)
2. ✅ Adversarial robustness measured (evasion margin < target)
3. ✅ Continuous improvement (Gen 1 → 5, each harder than last)
4. ✅ Honest evaluation (don't hide the 30% evasion at Gen 5)
5. ✅ Real arms race (attackers evolve, defender adapts)

---

## Files to Create (Summary)

```
stage5/adversarial/
├── feature_targeting.py               (Extract top features)
├── gen3_attack_spec.py                (Hide top 5 features)
├── gen4_attack_spec.py                (Ensemble evasion)
├── gen5_attack_spec.py                (Multi-family attacks)
└── curriculum_generator.py            (Easy → hard progression)

stage5/training/
├── curriculum_retrain.py              (Retrain with progressive difficulty)
├── evasion_margin_calculator.py       (Measure robustness)
└── automatic_retrain_trigger.py       (Kick off when Gen 3/4/5 ready)

stage5/validation/
├── gen3_evaluation_report.py          (Measurement + proof)
├── gen4_evaluation_report.py
├── gen5_evaluation_report.py
└── adversarial_comparison_suite.py    (Gen 1 vs 2 vs 3 vs 4 vs 5)
```

---

## Integration with Phase 1

**Already have**: Analyst feedback loop (50 verdicts → auto-retrain)

**Phase 2 adds**: Adversarial attack generation + evasion measurement

**Flow**:
```
Analyst feedback (50 verdicts)
  → Retrain on feedback
  → Generate Gen 3 attacks
  → Measure: evasion margin < 5%?
    ├─ YES → Deploy Gen 3 model
    └─ NO → Generate Gen 4 attacks
```

---

## Recommendation

**Build this if**:
- ✅ You want to show "arms race" (attacks evolving, detector adapting)
- ✅ You want honest evaluation (admit Gen 5 evasion is high)
- ✅ You want judges to see continuous improvement measured
- ✅ You have 2-4 weeks for full implementation

**Skip if**:
- You're time-constrained (Gen 3 alone = 5-7 days)
- You just want hackathon demo (Phase 1 is enough)

---

## My Recommendation for Hackathon

**Build Gen 3 only** (not Gen 4/5):
- Shows the loop works (feedback → harder attacks)
- Evasion margin proof (<5%)
- Reasonable 1-week timeline
- Complete story: "Analyst feedback improves detector, we prove it on harder attacks"

**Save Gen 4/5 for post-hackathon** (if you advance to finals)
