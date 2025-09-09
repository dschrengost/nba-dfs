# PRP-FS-05 Field Sampler Unification

## GitHub Workflow Actions
- **Branch**: create feature branch `feat/fs-05-sampler-unification`
- **Commit**: add this PRP to `docs/PRPs/`
- **PR**: open PR against `main`
- **Review**: verify alignment with optimizer → variant builder → sampler → simulator pipeline


---

## Context & Inventory

### Current Sampler Implementations
- `field_sampler/engine.py`
  - Modular engine with components: `PositionAllocator`, `SalaryManager`, `TeamLimiter`, `RejectionSampler`
  - Outputs JSONL + metrics artifacts
  - Imports: `pandas`, `validators.lineup_rules`

- `processes/field_sampler/injection_model.py`
  - Pipeline-specific sampler
  - Shuffles players, supports variant injection
  - Imports: `pandas`, `validators.lineup_rules`, `random`

- `processes/field_sampler/_legacy/field_sampler.py`
  - Legacy infrastructure
  - YAML-driven bucket/weight configs
  - Imports: `yaml`, `numpy`, `paths`

- `processes/field_sampler/adapter.py`
  - Dispatcher requiring env var `FIELD_SAMPLER_IMPL`
  - No default fallback; raises error otherwise
  - Imports: `os`, `pipeline.io.*`

- `tests/fixtures/stub_field_sampler.py`
  - Minimal stub used in adapter tests

### Tests & Consumers
- `tests/test_field_sampler_engine.py` → `field_sampler.engine`
- `tools/sample_field.py` → `field_sampler.engine.run_sampler`
- `tests/test_field_sampler_injection.py` → `processes.field_sampler.injection_model`
- `tests/test_field_adapter_smoke.py` → adapter + stub

---

## Problem Statement
- Multiple sampler engines exist, leading to duplication and maintenance overhead.
- Adapter (`processes/field_sampler/adapter.py`) lacks a default, breaking pipeline cohesion.
- Tests are fragmented across different engines and stubs.
- Violates project charter goal: **Single Source of Truth** for data pipeline.

---

## Detailed Action Plan

### Step 1. Adapter Default Update
- Modify `processes/field_sampler/adapter.py`:
  - Default implementation → `field_sampler.engine.run_sampler`
  - Retain `FIELD_SAMPLER_IMPL` env override for experimentation
- Add clear error messages if overridden engine cannot be loaded

### Step 2. Feature Consolidation
- Audit `injection_model.py` for **variant injection** logic
  - Migrate this feature into `engine.py`
  - Ensure injection is optional and configurable
- Audit `_legacy/field_sampler.py`
  - Identify still-relevant bucket/weight logic
  - Migrate minimal viable subset if needed
  - Otherwise mark deprecated

### Step 3. Deprecation
- Add `DeprecationWarning` to:
  - `processes/field_sampler/injection_model.py`
  - `processes/field_sampler/_legacy/field_sampler.py`
- Remove after compatibility verified (target: next minor release)

### Step 4. Test Unification
- Route all sampler tests through adapter → canonical engine
- Remove `stub_field_sampler.py` once adapter integration tests are comprehensive
- Update/merge:
  - `tests/test_field_sampler_engine.py`
  - `tests/test_field_sampler_injection.py`
  - `tests/test_field_adapter_smoke.py`
- Ensure 100% coverage of engine features (position, salary, team, rejection, injection)

### Step 5. Documentation
- Publish canonical sampler API in `docs/`:
  - Inputs: projections CSV, player IDs
  - Outputs: JSONL, metrics, DK-compliant CSV
- Update pipeline diagram to reflect **single sampler implementation**
- Document adapter usage and `FIELD_SAMPLER_IMPL` override

---

## Acceptance Criteria
- Adapter loads `field_sampler.engine.run_sampler` by default
- Variant injection available in canonical engine
- Legacy files marked deprecated
- All sampler tests unified and passing
- Documentation updated with canonical API
- No redundant sampler implementations remain in active use

---

### 2025 Update
- Adapter ships with built-in engine (`processes.field_sampler.engine.run_sampler`).
- Engine returns entrants/telemetry and is deterministic via a `seed` knob.
- Tests moved under `tests/field_sampler/` covering adapter, engine and injection model.
- No migration needed; `FIELD_SAMPLER_IMPL` still overrides the default.

---

## Expected Benefits
- Single Source of Truth across optimizer → variant builder → sampler → simulator
- Cleaner adapter UX: users don’t manually select engines
- Reduced maintenance cost from eliminating duplicates
- Full compliance with project charter requirement for unified data pipeline
