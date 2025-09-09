"""Tests for simulation metrics schema compliance and invariants."""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from pipeline.io.validate import load_schema, validate_obj


@pytest.fixture
def schemas_root():
    """Get the schemas root directory."""
    return Path(__file__).parents[2] / "pipeline" / "schemas"


@pytest.fixture
def sample_sim_results():
    """Create sample simulation results data."""
    return pd.DataFrame(
        {
            "lineup_id": ["L1", "L2", "L3"],
            "contest_id": ["CONTEST_1"] * 3,
            "roi": [0.05, -0.10, 0.15],
            "ev": [1.05, 0.90, 1.15],
            "finish_position": [10, 50, 5],
            "prize": [100.0, 0.0, 500.0],
            "entry_fee": [20.0] * 3,
        }
    )


def test_sim_metrics_schema_validation(schemas_root):
    """Test that sim metrics conform to schema."""
    # Load the schema
    sim_metrics_schema = load_schema(schemas_root / "sim_metrics.schema.yaml")

    # Create valid metrics object
    valid_metrics = {
        "run_id": "20250101_120000_abcd1234",
        "aggregates": {
            "ev_mean": 1.05,
            "roi_mean": 0.025,
            "sharpe": 0.6,
            "sortino": 0.8,
        },
        "convergence": {
            "rmse_by_batch": [
                {"bin_start": 0, "bin_end": 1000, "count": 1},
                {"bin_start": 1000, "bin_end": 2000, "count": 2},
            ]
        },
    }

    # Should validate successfully
    validate_obj(sim_metrics_schema, valid_metrics, schemas_root=schemas_root)

    # Test required fields
    invalid_metrics = {
        "run_id": "20250101_120000_abcd1234",
        "aggregates": {
            "ev_mean": 1.05,
            # Missing roi_mean (required)
        },
    }

    with pytest.raises(ValueError):  # Should fail validation
        validate_obj(sim_metrics_schema, invalid_metrics, schemas_root=schemas_root)


def test_metrics_computation_invariants(sample_sim_results):
    """Test that computed metrics satisfy expected invariants."""
    from processes.orchestrator.core import _compute_sim_metrics

    metrics = _compute_sim_metrics(sample_sim_results)

    # ROI should be computed correctly
    expected_roi_mean = sample_sim_results["roi"].mean()
    expected_roi_p50 = sample_sim_results["roi"].median()

    assert abs(metrics["roi_mean"] - expected_roi_mean) < 1e-6
    assert abs(metrics["roi_p50"] - expected_roi_p50) < 1e-6

    # ROI should be in reasonable range for typical DFS
    assert -1.0 <= metrics["roi_mean"] <= 2.0  # -100% to +200%
    assert -1.0 <= metrics["roi_p50"] <= 2.0

    # Duplication should be between 0 and 1
    assert 0.0 <= metrics["dup_p95"] <= 1.0


def test_empty_results_handling():
    """Test metrics computation with empty results."""
    from processes.orchestrator.core import _compute_sim_metrics

    empty_df = pd.DataFrame()
    metrics = _compute_sim_metrics(empty_df)

    # Should handle empty gracefully
    assert metrics["roi_mean"] == 0.0
    assert metrics["roi_p50"] == 0.0
    assert metrics["dup_p95"] == 0.0
    assert metrics["finish_percentiles"] == []


def test_single_lineup_metrics():
    """Test metrics computation with single lineup."""
    from processes.orchestrator.core import _compute_sim_metrics

    single_df = pd.DataFrame(
        {
            "roi": [0.05],
            "ev": [1.05],
            "finish_position": [10],
        }
    )

    metrics = _compute_sim_metrics(single_df)

    # Single value should be both mean and median
    assert metrics["roi_mean"] == 0.05
    assert metrics["roi_p50"] == 0.05


def test_metrics_json_serialization():
    """Test that metrics can be serialized to JSON."""
    from processes.orchestrator.core import _compute_sim_metrics

    sample_df = pd.DataFrame(
        {
            "roi": [0.05, -0.10, 0.15],
            "ev": [1.05, 0.90, 1.15],
        }
    )

    metrics = _compute_sim_metrics(sample_df)

    # Should be JSON serializable
    json_str = json.dumps(metrics)
    deserialized = json.loads(json_str)

    assert deserialized == metrics

    # Check data types are JSON-compatible
    for _key, value in metrics.items():
        assert isinstance(value, int | float | str | list | dict | type(None))


def test_roi_calculation_accuracy():
    """Test ROI calculation accuracy with known values."""
    # ROI = (prize - entry_fee) / entry_fee
    test_data = pd.DataFrame(
        {
            "roi": [0.0, 0.5, -0.5, 1.0],  # 0%, 50%, -50%, 100%
            "prize": [10.0, 15.0, 5.0, 20.0],
            "entry_fee": [10.0, 10.0, 10.0, 10.0],
        }
    )

    from processes.orchestrator.core import _compute_sim_metrics

    metrics = _compute_sim_metrics(test_data)

    expected_mean = (0.0 + 0.5 + (-0.5) + 1.0) / 4  # 0.25
    expected_median = (0.0 + 0.5) / 2  # 0.25

    assert abs(metrics["roi_mean"] - expected_mean) < 1e-6
    assert abs(metrics["roi_p50"] - expected_median) < 1e-6


def test_extreme_values_handling():
    """Test metrics computation with extreme values."""
    from processes.orchestrator.core import _compute_sim_metrics

    extreme_df = pd.DataFrame(
        {
            "roi": [-0.99, 10.0, -1.0, 0.0],  # Include extreme losses and wins
        }
    )

    metrics = _compute_sim_metrics(extreme_df)

    # Should handle extreme values without errors
    assert isinstance(metrics["roi_mean"], float)
    assert isinstance(metrics["roi_p50"], float)

    # Mean should be influenced by extreme values
    expected_mean = (-0.99 + 10.0 + (-1.0) + 0.0) / 4
    assert abs(metrics["roi_mean"] - expected_mean) < 1e-6


def test_nan_handling():
    """Test metrics computation with NaN values."""
    import numpy as np

    from processes.orchestrator.core import _compute_sim_metrics

    nan_df = pd.DataFrame(
        {
            "roi": [0.05, np.nan, 0.15, np.nan],
        }
    )

    metrics = _compute_sim_metrics(nan_df)

    # Should handle NaN gracefully (pandas should skip NaN in mean/median)
    # Expected: mean of [0.05, 0.15] = 0.1, median = 0.1
    assert abs(metrics["roi_mean"] - 0.1) < 1e-6
    assert abs(metrics["roi_p50"] - 0.1) < 1e-6


def test_run_manifest_schema_validation(schemas_root):
    """Test that run manifest conforms to its schema."""
    manifest_schema = load_schema(schemas_root / "run_manifest.schema.yaml")

    valid_manifest = {
        "schema_version": "0.1.0",
        "run_id": "20250101-120000-abcd1234",
        "slate_id": "25-01-01_1200",
        "created_ts": "2025-01-01T12:00:00.123Z",
        "contest": "TEST_CONTEST",
        "modules": {
            "variants": {
                "version": "deadbeef",
                "run_id": "20250101_120001_var1",
                "manifest_path": "runs/variants/manifest.json",
                "config": {},
            },
            "optimizer": {
                "version": "deadbeef",
                "run_id": "20250101_120002_opt1",
                "manifest_path": "runs/optimizer/manifest.json",
                "config": {},
            },
            "field_sampler": {
                "version": "deadbeef",
                "run_id": "20250101_120003_field1",
                "manifest_path": "runs/field_sampler/manifest.json",
                "config": {},
            },
            "gpp_sim": {
                "version": "deadbeef",
                "run_id": "20250101_120004_sim1",
                "manifest_path": "runs/gpp_sim/manifest.json",
                "config": {},
            },
        },
        "seeds": {"global": 42},
        "artifact_paths": {
            "optimizer_lineups": "runs/optimizer/lineups.parquet",
            "optimizer_dk_export": "runs/optimizer/dk_export.csv",
            "sim_metrics": "runs/sim/metrics.json",
            "summary": "runs/export/summary.md",
        },
    }

    # Should validate successfully
    validate_obj(manifest_schema, valid_manifest, schemas_root=schemas_root)

    # Test missing required field
    invalid_manifest = valid_manifest.copy()
    del invalid_manifest["modules"]

    with pytest.raises(ValueError):
        validate_obj(manifest_schema, invalid_manifest, schemas_root=schemas_root)


def test_metrics_aggregation_consistency():
    """Test that aggregated metrics are consistent across computations."""
    from processes.orchestrator.core import _compute_sim_metrics

    # Same data should produce same metrics
    test_df = pd.DataFrame(
        {
            "roi": [0.1, 0.2, 0.3, 0.4, 0.5],
        }
    )

    metrics1 = _compute_sim_metrics(test_df)
    metrics2 = _compute_sim_metrics(test_df.copy())

    assert metrics1 == metrics2

    # Test that order doesn't matter
    shuffled_df = test_df.sample(frac=1, random_state=42)
    metrics3 = _compute_sim_metrics(shuffled_df)

    assert metrics1["roi_mean"] == metrics3["roi_mean"]
    assert metrics1["roi_p50"] == metrics3["roi_p50"]


def test_percentile_computation():
    """Test percentile calculations are correct."""
    # Create data with known percentiles
    roi_values = list(range(1, 101))  # 1 to 100
    test_df = pd.DataFrame({"roi": roi_values})

    from processes.orchestrator.core import _compute_sim_metrics

    metrics = _compute_sim_metrics(test_df)

    # For values 1-100, median should be 50.5
    assert abs(metrics["roi_p50"] - 50.5) < 1e-6

    # Mean should be 50.5
    assert abs(metrics["roi_mean"] - 50.5) < 1e-6
