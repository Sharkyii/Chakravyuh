import json
from pathlib import Path

from stage5.training.generate_training_data import check_baseline_cache

def test_cache_miss_when_missing_dir(tmp_path):
    assert check_baseline_cache(tmp_path / "missing", 1000, 100) is False

def test_cache_miss_when_missing_manifest(tmp_path):
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    assert check_baseline_cache(baseline, 1000, 100) is False

def test_cache_miss_on_corrupt_manifest(tmp_path):
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    (baseline / "cache_manifest.json").write_text("{corrupted:", encoding="utf-8")
    assert check_baseline_cache(baseline, 1000, 100) is False

def test_cache_miss_on_mismatched_settings(tmp_path):
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    (baseline / "cache_manifest.json").write_text(json.dumps({
        "n_consumers": 500,  # Does not match 1000
        "n_merchants": 100,
        "seed": 42
    }), encoding="utf-8")
    
    assert check_baseline_cache(baseline, 1000, 100) is False
    assert check_baseline_cache(baseline, 500, 200) is False  # Merchant mismatch
    assert check_baseline_cache(baseline, 500, 100, seed=43) is False  # Seed mismatch

def test_cache_hit_on_exact_match(tmp_path):
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    (baseline / "cache_manifest.json").write_text(json.dumps({
        "n_consumers": 1000,
        "n_merchants": 100,
        "seed": 42
    }), encoding="utf-8")
    
    assert check_baseline_cache(baseline, 1000, 100) is True
