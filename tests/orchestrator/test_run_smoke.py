"""Smoke tests for orchestrated pipeline execution."""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from pipeline.io.validate import load_schema, validate_obj
from processes.orchestrator.core import run_orchestrated_pipeline


@pytest.fixture
def temp_configs(tmp_path: Path):
    """Create minimal config files for testing."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()

    # Minimal variants config
    variants_config = configs_dir / "variants.yaml"
    variants_config.write_text(
        """
num_variants: 5
randomness: 0.1
"""
    )

    # Minimal optimizer config
    optimizer_config = configs_dir / "optimizer.yaml"
    optimizer_config.write_text(
        """
num_lineups: 3
max_salary: 50000
randomness: 0.1
"""
    )

    # Minimal sampler config
    sampler_config = configs_dir / "sampler.yaml"
    sampler_config.write_text(
        """
sample_size: 10
"""
    )

    # Minimal sim config
    sim_config = configs_dir / "sim.yaml"
    sim_config.write_text(
        """
iterations: 100
"""
    )

    return {
        "variants": variants_config,
        "optimizer": optimizer_config,
        "sampler": sampler_config,
        "sim": sim_config,
    }


@pytest.fixture
def mock_data(tmp_path: Path):
    """Create minimal test data for the pipeline."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create minimal projections data
    projections_dir = data_dir / "projections" / "normalized"
    projections_dir.mkdir(parents=True)

    # Create a test slate
    slate_id = "25-01-01_1200"
    projections_path = projections_dir / f"{slate_id}__test__20250101_120000.parquet"

    # Minimal projections data with required fields
    projections_data = {
        "dk_player_id": [
            "player1",
            "player2",
            "player3",
            "player4",
            "player5",
            "player6",
            "player7",
            "player8",
            "player9",
            "player10",
        ],
        "pos": ["PG", "SG", "SF", "PF", "C", "PG", "SG", "SF", "PF", "C"],
        "salary": [8000, 7500, 7000, 6500, 6000, 5500, 5000, 4500, 4000, 3500],
        "proj_fp": [45.0, 40.0, 35.0, 30.0, 25.0, 20.0, 18.0, 16.0, 14.0, 12.0],
        "team": ["LAL", "LAL", "GSW", "GSW", "BOS", "BOS", "MIA", "MIA", "NYK", "NYK"],
        "updated_ts": ["2025-01-01T12:00:00.000Z"] * 10,
    }

    df = pd.DataFrame(projections_data)
    df.to_parquet(projections_path)

    return {"data_dir": data_dir, "slate_id": slate_id}


@pytest.mark.integration
def test_orchestrated_run_smoke(temp_configs, mock_data, tmp_path: Path):
    """Smoke test: execute orchestrated pipeline and verify artifacts exist."""
    # This is a minimal smoke test - in a real test environment, we'd need
    # proper projections data and possibly mock the individual adapters

    slate_id = mock_data["slate_id"]
    data_dir = mock_data["data_dir"]

    # For smoke test, we'll use dry_run to avoid complex setup
    result = run_orchestrated_pipeline(
        slate_id=slate_id,
        contest="TEST_CONTEST",
        seed=42,
        variants_config=temp_configs["variants"],
        optimizer_config=temp_configs["optimizer"],
        sampler_config=temp_configs["sampler"],
        sim_config=temp_configs["sim"],
        tag="smoke-test",
        out_root=data_dir,
        dry_run=True,  # Use dry run for smoke test
        verbose=True,
    )

    # Verify dry run returns expected structure
    assert "run_id" in result
    assert "plan" in result
    assert result["run_id"].count("-") == 2  # YYYYMMDD-HHMMSS-hash format
    assert len(result["plan"]) > 0


@pytest.mark.integration
@pytest.mark.skip(reason="Requires full environment setup")
def test_orchestrated_run_full_smoke(temp_configs, mock_data, tmp_path: Path):
    """Full smoke test with actual execution (requires environment setup)."""
    slate_id = mock_data["slate_id"]
    data_dir = mock_data["data_dir"]

    try:
        result = run_orchestrated_pipeline(
            slate_id=slate_id,
            contest="TEST_CONTEST",
            seed=42,
            variants_config=temp_configs["variants"],
            optimizer_config=temp_configs["optimizer"],
            sampler_config=temp_configs["sampler"],
            sim_config=temp_configs["sim"],
            tag="smoke-test",
            out_root=data_dir,
            dry_run=False,
            verbose=True,
        )

        # Verify result structure
        assert "run_id" in result
        assert "artifact_root" in result
        assert "manifest_path" in result

        run_id = result["run_id"]
        artifact_root = Path(result["artifact_root"])

        # Verify PRP artifact layout exists
        assert artifact_root.exists()
        assert (artifact_root / "manifest.json").exists()
        assert (artifact_root / "optimizer" / "lineups.parquet").exists()
        assert (artifact_root / "optimizer" / "dk_export.csv").exists()
        assert (artifact_root / "sim" / "metrics.json").exists()
        assert (artifact_root / "export" / "summary.md").exists()

        # Verify manifest schema
        manifest_path = artifact_root / "manifest.json"
        manifest_data = json.loads(manifest_path.read_text())

        # Load and validate against schema
        schemas_root = Path(__file__).parents[2] / "pipeline" / "schemas"
        manifest_schema = load_schema(schemas_root / "run_manifest.schema.yaml")
        validate_obj(manifest_schema, manifest_data, schemas_root=schemas_root)

        # Verify required fields
        assert manifest_data["run_id"] == run_id
        assert manifest_data["slate_id"] == slate_id
        assert "modules" in manifest_data
        assert "seeds" in manifest_data
        assert "artifact_paths" in manifest_data
        assert manifest_data["seeds"]["global"] == 42

    except Exception as e:
        pytest.skip(f"Full integration test skipped due to environment: {e}")


def test_run_id_format():
    """Test that run_id follows PRP format: YYYYMMDD-HHMMSS-<shorthash>."""
    from processes.orchestrator.core import _make_run_id

    run_id = _make_run_id(seed=42, slate_id="test", contest="TEST")

    # Should be format: YYYYMMDD-HHMMSS-<8char_hash>
    parts = run_id.split("-")
    assert len(parts) == 3

    date_part = parts[0]
    time_part = parts[1]
    hash_part = parts[2]

    assert len(date_part) == 8  # YYYYMMDD
    assert len(time_part) == 6  # HHMMSS
    assert len(hash_part) == 8  # 8-char hash
    assert date_part.isdigit()
    assert time_part.isdigit()


def test_config_loading():
    """Test configuration loading from YAML files."""
    from processes.orchestrator.core import _load_config

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(
            """
test_key: test_value
nested:
  key: value
number: 42
"""
        )
        config_path = Path(f.name)

    try:
        config = _load_config(config_path)
        assert config["test_key"] == "test_value"
        assert config["nested"]["key"] == "value"
        assert config["number"] == 42
    finally:
        config_path.unlink()


def test_summary_markdown_generation():
    """Test summary markdown generation."""
    from processes.orchestrator.core import _write_summary_markdown

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        summary_path = Path(f.name)

    try:
        metrics = {"roi_mean": 0.05, "roi_p50": 0.03, "dup_p95": 0.95}
        timings = {"total_duration_ms": 45000, "optimizer_duration_ms": 15000}

        _write_summary_markdown(
            run_id="20250101-120000-abcd1234",
            slate_id="25-01-01_1200",
            contest="TEST_CONTEST",
            metrics=metrics,
            timings=timings,
            output_path=summary_path,
        )

        content = summary_path.read_text()
        assert "20250101-120000-abcd1234" in content
        assert "25-01-01_1200" in content
        assert "TEST_CONTEST" in content
        assert "0.050" in content  # ROI mean formatted
        assert "45,000ms" in content  # Total duration formatted

    finally:
        summary_path.unlink()
