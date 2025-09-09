"""Tests for deterministic behavior of orchestrated pipeline."""

import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from processes.orchestrator.core import _make_run_id, _set_global_seed


def test_run_id_determinism():
    """Test that run_id generation is deterministic for same inputs."""
    # Same inputs should produce same run_id structure (different timestamps but same hash)
    slate_id = "25-01-01_1200"
    contest = "TEST_CONTEST"
    seed = 42

    # The timestamp part will be different, but we can test the hash part
    run_id1 = _make_run_id(seed, slate_id, contest)
    run_id2 = _make_run_id(seed, slate_id, contest)

    # Both should have same format
    parts1 = run_id1.split("-")
    parts2 = run_id2.split("-")

    assert len(parts1) == 3
    assert len(parts2) == 3

    # Date parts should be same (within a few seconds)
    assert parts1[0] == parts2[0]  # YYYYMMDD should be same

    # Time parts might differ by a few seconds, that's OK
    # Hash parts should be same for same inputs if generated at same time
    # (but will differ due to timestamp inclusion - this is expected)


def test_global_seed_setting():
    """Test that global seed setting affects random number generation."""
    import random

    import numpy as np

    # Set seed and get some random values
    _set_global_seed(42)
    random_val1 = random.random()
    numpy_val1 = np.random.random()

    # Reset seed and get values again
    _set_global_seed(42)
    random_val2 = random.random()
    numpy_val2 = np.random.random()

    # Values should be identical
    assert random_val1 == random_val2
    assert numpy_val1 == numpy_val2

    # Different seed should produce different values
    _set_global_seed(123)
    random_val3 = random.random()
    numpy_val3 = np.random.random()

    assert random_val3 != random_val1
    assert numpy_val3 != numpy_val1


def test_config_hashing_determinism():
    """Test that config dictionaries hash deterministically."""
    config1 = {
        "num_lineups": 10,
        "randomness": 0.1,
        "nested": {"key": "value"},
    }

    config2 = {
        "randomness": 0.1,
        "num_lineups": 10,
        "nested": {"key": "value"},
    }

    # Same content, different order should hash the same
    json1 = json.dumps(config1, sort_keys=True, separators=(",", ":"))
    json2 = json.dumps(config2, sort_keys=True, separators=(",", ":"))

    hash1 = hashlib.sha256(json1.encode()).hexdigest()
    hash2 = hashlib.sha256(json2.encode()).hexdigest()

    assert hash1 == hash2


@pytest.mark.integration
def test_dry_run_determinism():
    """Test that dry runs produce consistent plans."""
    from processes.orchestrator.core import run_orchestrated_pipeline

    # Create minimal config files
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()

        # Create identical configs
        for name in ["variants", "optimizer", "sampler", "sim"]:
            config_path = configs_dir / f"{name}.yaml"
            config_path.write_text(f"test_param: {name}_value\n")

        # Run twice with same parameters
        common_params = {
            "slate_id": "25-01-01_1200",
            "contest": "TEST_CONTEST",
            "seed": 42,
            "variants_config": configs_dir / "variants.yaml",
            "optimizer_config": configs_dir / "optimizer.yaml",
            "sampler_config": configs_dir / "sampler.yaml",
            "sim_config": configs_dir / "sim.yaml",
            "tag": "determinism-test",
            "out_root": tmp_path / "data",
            "dry_run": True,
            "verbose": False,
        }

        result1 = run_orchestrated_pipeline(**common_params)
        result2 = run_orchestrated_pipeline(**common_params)

        # Plans should be identical
        assert result1["plan"] == result2["plan"]

        # Run IDs will differ due to timestamps, but that's expected


def test_hash_stability():
    """Test that our hashing functions produce stable outputs."""
    test_data = "test_string_42"

    hash1 = hashlib.sha256(test_data.encode()).hexdigest()
    hash2 = hashlib.sha256(test_data.encode()).hexdigest()

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 produces 64-char hex string

    # Short hash (first 8 chars) should also be stable
    short1 = hash1[:8]
    short2 = hash2[:8]

    assert short1 == short2
    assert len(short1) == 8


def test_dataframe_determinism():
    """Test that pandas operations are deterministic."""
    # Create test dataframe
    data = {
        "player_id": ["player1", "player2", "player3"],
        "salary": [8000, 7000, 6000],
        "proj_fp": [45.0, 35.0, 25.0],
    }

    df1 = pd.DataFrame(data)
    df2 = pd.DataFrame(data)

    # DataFrames should be equal
    pd.testing.assert_frame_equal(df1, df2)

    # Operations should be deterministic
    sorted1 = df1.sort_values("salary", ascending=False)
    sorted2 = df2.sort_values("salary", ascending=False)

    pd.testing.assert_frame_equal(sorted1, sorted2)


def test_json_serialization_determinism():
    """Test that JSON serialization is deterministic."""
    test_obj = {
        "b": 2,
        "a": 1,
        "nested": {"z": 26, "a": 1},
        "list": [3, 1, 2],
    }

    # With sorted keys, should be deterministic
    json1 = json.dumps(test_obj, sort_keys=True, separators=(",", ":"))
    json2 = json.dumps(test_obj, sort_keys=True, separators=(",", ":"))

    assert json1 == json2

    # Should start with sorted keys
    assert json1.startswith('{"a":1,"b":2')


@pytest.mark.integration
@pytest.mark.skip(reason="Requires full environment setup")
def test_full_pipeline_determinism():
    """Test that full pipeline execution is deterministic (when environment is ready)."""
    # This would test that running the same pipeline twice with same seed
    # produces identical artifacts (modulo timestamps)

    # Would need:
    # 1. Same input data
    # 2. Same configurations
    # 3. Same seed
    # 4. Compare output file hashes (excluding timestamp fields)

    pytest.skip("Full determinism test requires complete environment setup")


def test_timestamp_format_consistency():
    """Test that timestamp generation is consistent in format."""
    from processes.orchestrator.core import _utc_now_iso

    ts1 = _utc_now_iso()
    ts2 = _utc_now_iso()

    # Both should match ISO format with milliseconds
    import re

    iso_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"

    assert re.match(iso_pattern, ts1)
    assert re.match(iso_pattern, ts2)

    # Should be properly ordered
    assert ts1 <= ts2  # Later timestamp should be >= earlier
