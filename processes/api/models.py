from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class IngestConfig(BaseModel):
    source: str = "manual"
    projections: str | None = None
    player_ids: str | None = None
    mapping: str | None = None


class OptimizerConfig(BaseModel):
    site: Literal["DK"] = "DK"
    engine: str | None = None
    config: dict[str, Any] | None = None


class VariantsConfig(BaseModel):
    config: dict[str, Any] | None = None


class FieldConfig(BaseModel):
    config: dict[str, Any] | None = None


class Payout(BaseModel):
    rank_start: int
    rank_end: int
    prize: float


class ContestConfig(BaseModel):
    field_size: int
    entry_fee: float
    rake: float
    site: Literal["DK"]
    payout_curve: list[Payout]
    contest_id: str | None = None
    name: str | None = None


class SimConfig(BaseModel):
    config: dict[str, Any] | None = None
    contest: ContestConfig | None = None


class Seeds(BaseModel):
    optimizer: int | None = None
    variants: int | None = None
    field: int | None = None
    sim: int | None = None


class OrchestratorConfig(BaseModel):
    ingest: IngestConfig
    optimizer: OptimizerConfig
    variants: VariantsConfig
    field: FieldConfig
    sim: SimConfig
    seeds: Seeds | None = None


class OrchestratorRunRequest(BaseModel):
    slate_id: str
    config: OrchestratorConfig
    out_root: str = "data"
    schemas_root: str = "pipeline/schemas"
    validate: bool = True
    dry_run: bool = False
    verbose: bool = False


class StageSummary(BaseModel):
    name: Literal["ingest", "optimizer", "variants", "field", "sim", "metrics"]
    run_id: str
    primary_output: str | None = None


class OrchestratorRunResponse(BaseModel):
    bundle_id: str
    bundle_path: str
    stages: dict[str, str]
    run_registry_path: str | None = None


class BundleStage(BaseModel):
    name: str
    run_id: str
    primary_output: str | None = None


class BundleManifest(BaseModel):
    bundle_id: str
    slate_id: str
    created_ts: str
    stages: list[BundleStage]


class RunRegistryRow(BaseModel):
    run_id: str
    run_type: str
    slate_id: str
    status: str
    primary_outputs: list[str] | None = None
    metrics_path: str | None = None
    created_ts: str
    tags: list[str] | None = None


class RunsListResponse(BaseModel):
    runs: list[RunRegistryRow]


# PRP-ORCH-01 Models for One-Command End-to-End API


class OrchestratedRunRequest(BaseModel):
    slate: str
    contest: str
    seed: int
    variants_config: str  # Path to variants config YAML
    optimizer_config: str  # Path to optimizer config YAML
    sampler_config: str  # Path to sampler config YAML
    sim_config: str  # Path to sim config YAML
    tag: str | None = None
    out_root: str = "data"
    schemas_root: str | None = None
    dry_run: bool = False
    verbose: bool = False


class MetricsHead(BaseModel):
    roi_mean: float | None = None
    roi_p50: float | None = None
    dup_p95: float | None = None


class OrchestratedRunResponse(BaseModel):
    run_id: str
    artifact_path: str
    metrics_head: MetricsHead
