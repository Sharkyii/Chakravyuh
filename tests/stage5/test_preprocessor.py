import sys
from pathlib import Path

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.dataset.loader import load_dataset
from stage5.config.settings import (
    STAGE5_DATA_DIR,
    CATEGORICAL_FEATURES,
    NUMERICAL_FEATURES,
    BOOLEAN_FEATURES,
    BEHAVIORAL_FEATURES,
    GRAPH_FEATURES,
    ALL_FEATURES
)
from stage5.features.feature_engineering import build_features

def test_preprocessor_includes_all_features():
    # 1. Load combined dataset if available (lightweight check/mock if not)
    combined_dir = STAGE5_DATA_DIR / "combined"
    assert combined_dir.exists(), f"Combined data directory not found at {combined_dir}"
    
    dataset = load_dataset(combined_dir)
    df = build_features(dataset)
    
    # Select first 100 rows for lightweight validation
    sample_df = df.head(100).copy()
    X = sample_df[ALL_FEATURES]
    
    # 2. Re-create the preprocessor pipeline exactly as in train_fraud_model.py
    cat_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
    ])
    
    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])
    
    preprocessor = ColumnTransformer(transformers=[
        ("cat", cat_pipeline, CATEGORICAL_FEATURES),
        ("num", num_pipeline, NUMERICAL_FEATURES + BOOLEAN_FEATURES + BEHAVIORAL_FEATURES + GRAPH_FEATURES)
    ])
    
    # 3. Fit and transform
    X_proc = preprocessor.fit_transform(X)
    
    # 4. Check feature names out
    feature_names = preprocessor.get_feature_names_out()
    
    # Verify that all behavioral features are present in the output
    for feat in BEHAVIORAL_FEATURES:
        expected_name = f"num__{feat}"
        assert expected_name in feature_names, f"Behavioral feature {feat} was dropped or has incorrect output name"
        
    # Verify that all graph features are present in the output
    for feat in GRAPH_FEATURES:
        expected_name = f"num__{feat}"
        assert expected_name in feature_names, f"Graph feature {feat} was dropped or has incorrect output name"
        
    # Verify total shapes and remainder
    assert preprocessor.remainder == "drop"
    print(f"Validation successful! Transformed shape: {X_proc.shape}")
    print(f"Total output features: {len(feature_names)}")
