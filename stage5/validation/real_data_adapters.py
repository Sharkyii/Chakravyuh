"""
Feature adapters to map real-world datasets to Chakravyuh features.
Enables cross-dataset validation against IEEE and Cifer benchmarks.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class RealDataAdapter:
    """Base adapter for mapping external datasets to Chakravyuh features."""

    CHAKRAVYUH_FEATURES = [
        'amount', 'velocity_amount', 'velocity_count', 'device_is_known',
        'ip_is_proxy', 'email_domain_risk', 'user_age_days', 'mcc_category',
        'known_beneficiary', 'cross_border', 'high_amount_flag', 'time_of_day',
        'velocity_distinct_merchants', 'balance_drop_pct', 'repeat_transaction',
        'device_to_location_mismatch', 'email_phone_mismatch', 'behavioral_anomaly',
        'multi_currency', 'rapid_location_change', 'account_creation_risk',
        'card_velocity', 'beneficiary_risk'
    ]

    @staticmethod
    def _safe_divide(numerator, denominator, fill_value=0):
        """Safely divide avoiding division by zero."""
        result = pd.Series(fill_value, index=numerator.index)
        mask = denominator != 0
        result[mask] = numerator[mask] / denominator[mask]
        return result


class IEEEAdapter(RealDataAdapter):
    """Map IEEE Fraud Detection dataset to Chakravyuh features."""

    @staticmethod
    def compute_features(transactions_df, identity_df=None):
        """
        Compute Chakravyuh features from IEEE dataset.

        Args:
            transactions_df: IEEE train_transaction.csv
            identity_df: IEEE train_identity.csv (optional)

        Returns:
            DataFrame with Chakravyuh features
        """
        df = transactions_df.copy()
        features = pd.DataFrame(index=df.index)

        # 1. Direct mappings
        features['amount'] = df['TransactionAmt'].fillna(0)
        features['time_of_day'] = (df['TransactionDT'] % 86400) / 86400.0  # Normalize to 0-1

        # 2. Velocity features (per card)
        card_col = 'card1' if 'card1' in df.columns else 'Card'
        window = 10

        features['velocity_amount'] = df.groupby(card_col)['TransactionAmt'].transform(
            lambda x: x.rolling(window, min_periods=1).sum().fillna(0)
        )
        features['velocity_count'] = df.groupby(card_col).cumcount().fillna(0)

        # 3. Device features
        if 'DeviceInfo' in df.columns:
            features['device_is_known'] = (~df['DeviceInfo'].isna()).astype(int)
        else:
            features['device_is_known'] = 1  # Assume known by default

        # 4. IP/Email risk (IEEE has anonymized risk columns V1-V339)
        # Map to proxy/high-risk indicator
        if 'id_31' in df.columns:  # Browser type
            features['ip_is_proxy'] = (df['id_31'].astype(str).str.contains('proxy', case=False, na=False)).astype(int)
        else:
            features['ip_is_proxy'] = 0

        if 'id_20' in df.columns:  # Signature
            features['email_domain_risk'] = (df['id_20'].astype(str).str.len() < 3).astype(int)
        else:
            features['email_domain_risk'] = 0

        # 5. User age (days since account creation)
        if 'D1' in df.columns:
            features['user_age_days'] = df['D1'].fillna(0)
        else:
            features['user_age_days'] = 30  # Assume 30 days if unknown

        # 6. MCC category (product type)
        if 'ProductCD' in df.columns:
            mcc_map = {
                'W': 0.3, 'H': 0.5, 'C': 0.7, 'S': 0.2, 'R': 0.4
            }
            features['mcc_category'] = df['ProductCD'].map(mcc_map).fillna(0.5)
        else:
            features['mcc_category'] = 0.5

        # 7. Known beneficiary (check if repeated target)
        if 'Card' in df.columns or 'card1' in df.columns:
            target_col = 'Card' if 'Card' in df.columns else 'card1'
            features['known_beneficiary'] = df.groupby(target_col).cumcount().fillna(0)
            features['known_beneficiary'] = (features['known_beneficiary'] > 2).astype(int)
        else:
            features['known_beneficiary'] = 0

        # 8. Cross-border (assume US-based, ID columns indicate geography)
        if 'id_01' in df.columns:
            features['cross_border'] = 0  # IEEE doesn't have clear geo data
        else:
            features['cross_border'] = 0

        # 9. High amount flag
        amt_75 = df['TransactionAmt'].quantile(0.75)
        features['high_amount_flag'] = (df['TransactionAmt'] > amt_75).astype(int)

        # 10. Velocity distinct merchants
        if 'Card' in df.columns or 'card1' in df.columns:
            card_col = 'Card' if 'Card' in df.columns else 'card1'
            features['velocity_distinct_merchants'] = df.groupby(card_col)[card_col].transform(
                lambda x: x.rolling(20, min_periods=1).nunique().fillna(1)
            )
        else:
            features['velocity_distinct_merchants'] = 1

        # 11. Balance drop (not in IEEE, simulate)
        features['balance_drop_pct'] = 0

        # 12. Repeat transaction (same amount within short window)
        features['repeat_transaction'] = (
            df['TransactionAmt'].groupby(card_col if 'card1' in df.columns else 'Card')
            .transform(lambda x: x.duplicated(keep=False)).astype(int)
        ) if 'card1' in df.columns or 'Card' in df.columns else 0

        # 13. Device to location mismatch (simulate from risk columns)
        features['device_to_location_mismatch'] = (
            np.random.rand(len(df)) > 0.9
        ).astype(int)  # 10% anomaly rate

        # 14. Email/phone mismatch
        features['email_phone_mismatch'] = (
            (df['id_28'].astype(str) != df['id_29'].astype(str)).astype(int)
            if 'id_28' in df.columns and 'id_29' in df.columns else 0
        )

        # 15. Behavioral anomaly (detect outliers in amount)
        features['behavioral_anomaly'] = (
            np.abs(df['TransactionAmt'] - df['TransactionAmt'].mean()) > 2 * df['TransactionAmt'].std()
        ).astype(int)

        # 16. Multi-currency
        features['multi_currency'] = 0  # IEEE is single currency

        # 17. Rapid location change
        features['rapid_location_change'] = 0  # No location data in IEEE

        # 18. Account creation risk (new accounts)
        if 'D1' in df.columns:
            features['account_creation_risk'] = (df['D1'] < 7).astype(int)
        else:
            features['account_creation_risk'] = 0

        # 19. Card velocity
        if 'card1' in df.columns:
            features['card_velocity'] = df.groupby('card1').cumcount()
        else:
            features['card_velocity'] = 0

        # 20. Beneficiary risk (simulate)
        features['beneficiary_risk'] = (np.random.rand(len(df)) > 0.7).astype(int)

        # Fill NaNs
        for col in features.columns:
            features[col] = features[col].fillna(0)

        return features


class CiferAdapter(RealDataAdapter):
    """Map Cifer Mobile Money dataset to Chakravyuh features."""

    @staticmethod
    def compute_features(df):
        """
        Compute Chakravyuh features from Cifer dataset.

        Args:
            df: Cifer CSV as DataFrame

        Returns:
            DataFrame with Chakravyuh features
        """
        df = df.copy()
        features = pd.DataFrame(index=df.index)

        # 1. Direct mapping: amount
        features['amount'] = df['amount'].fillna(0)

        # 2. Velocity features (per payer)
        features['velocity_amount'] = df.groupby('nameOrig')['amount'].transform(
            lambda x: x.rolling(10, min_periods=1).sum().fillna(0)
        )
        features['velocity_count'] = df.groupby('nameOrig').cumcount().fillna(0)

        # 3. Device (simulate based on step - higher step = known device)
        features['device_is_known'] = (df['step'] > 100).astype(int)

        # 4. IP proxy (simulate from type variation)
        type_entropy = df.groupby('nameOrig')['type'].transform(
            lambda x: (x.value_counts(normalize=True).max())
        )
        features['ip_is_proxy'] = (type_entropy < 0.3).astype(int)

        # 5. Email domain risk (simulate)
        features['email_domain_risk'] = 0

        # 6. User age (approximate from cumulative volume)
        user_age = df.groupby('nameOrig').cumcount()
        features['user_age_days'] = (user_age / 100).clip(0, 365)  # Normalize

        # 7. MCC category (transaction type)
        type_map = {
            'TRANSFER': 0.3, 'CASH_OUT': 0.6, 'CASH_IN': 0.2,
            'DEBIT': 0.4, 'PAYMENT': 0.5
        }
        features['mcc_category'] = df['type'].map(type_map).fillna(0.5)

        # 8. Known beneficiary (repeat payee)
        features['known_beneficiary'] = df.groupby(['nameOrig', 'nameDest']).cumcount()
        features['known_beneficiary'] = (features['known_beneficiary'] > 2).astype(int)

        # 9. Cross-border (all P2P in Cifer, but flag new payees)
        features['cross_border'] = (features['known_beneficiary'] == 0).astype(int)

        # 10. High amount flag
        amt_75 = df['amount'].quantile(0.75)
        features['high_amount_flag'] = (df['amount'] > amt_75).astype(int)

        # 11. Time of day (convert step to hour 0-23)
        # Assume ~400-500 steps per day in Cifer
        hours_per_step = 24.0 / 500.0
        features['time_of_day'] = ((df['step'] * hours_per_step) % 24) / 24.0

        # 12. Velocity distinct merchants
        features['velocity_distinct_merchants'] = df.groupby('nameOrig')['nameDest'].transform(
            lambda x: x.rolling(20, min_periods=1).nunique().fillna(1)
        )

        # 13. Balance drop percentage
        features['balance_drop_pct'] = (
            (df['oldbalanceOrg'] - df['newbalanceOrig']) / (df['oldbalanceOrg'] + 1)
        ).abs().clip(0, 1)

        # 14. Repeat transaction (same amount, same payee)
        features['repeat_transaction'] = (
            df[['nameOrig', 'nameDest', 'amount']].duplicated(keep=False).astype(int)
        )

        # 15. Device to location mismatch (not in Cifer)
        features['device_to_location_mismatch'] = 0

        # 16. Email/phone mismatch (not in Cifer)
        features['email_phone_mismatch'] = 0

        # 17. Behavioral anomaly (amount outliers)
        user_mean = df.groupby('nameOrig')['amount'].transform('mean')
        user_std = df.groupby('nameOrig')['amount'].transform('std').fillna(1)
        features['behavioral_anomaly'] = (
            np.abs(df['amount'] - user_mean) > 2 * user_std
        ).astype(int)

        # 18. Multi-currency (not in Cifer)
        features['multi_currency'] = 0

        # 19. Rapid location change (not in Cifer)
        features['rapid_location_change'] = 0

        # 20. Account creation risk (new accounts start at step 1)
        features['account_creation_risk'] = (df['step'] < 20).astype(int)

        # 21. Card velocity (per payee transaction count)
        features['card_velocity'] = df.groupby('nameOrig').cumcount()

        # 22. Beneficiary risk (payees with high fraud rate)
        fraud_rate_per_dest = df.groupby('nameDest')['isFraud'].transform('mean')
        features['beneficiary_risk'] = (fraud_rate_per_dest > 0.05).astype(int)

        # Fill NaNs
        for col in features.columns:
            features[col] = features[col].fillna(0)

        return features
