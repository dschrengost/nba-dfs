# FS-04 Field Sampler Duplication Report

**Date:** 2025-09-??
**Author:** Agent

---

## 1. Inventory of sampler files

| Path | Description | Key imports |
|---|---|---|
| `field_sampler/engine.py` | Standalone sampler engine with position, salary and team constraints | `pandas`, `validators.lineup_rules` |
| `processes/field_sampler/injection_model.py` | Pipeline-specific sampler that shuffles players and supports variant injection | `pandas`, `validators.lineup_rules`, `random` |
| `processes/field_sampler/_legacy/field_sampler.py` | Legacy sampler with extensive config and weight logic | `yaml`, `numpy`, `paths` |
| `processes/field_sampler/adapter.py` | Headless adapter that dynamically loads a sampler implementation | `os`, `pipeline.io.*` |
| `tests/fixtures/stub_field_sampler.py` | Minimal stub implementation used in adapter tests | — |

## 2. Differences between implementations

- **`field_sampler/engine.py`** implements modular components (`PositionAllocator`, `SalaryManager`, `TeamLimiter`, `RejectionSampler`) and writes JSONL + metrics outputs【F:field_sampler/engine.py†L21-L91】【F:field_sampler/engine.py†L94-L169】
- **`processes/field_sampler/injection_model.py`** builds lineups by shuffling players, then optionally injects variants before emitting artifacts【F:processes/field_sampler/injection_model.py†L27-L99】
- **`processes/field_sampler/_legacy/field_sampler.py`** contains older bucket/weight infrastructure and YAML-driven configuration, diverging significantly from newer engines【F:processes/field_sampler/_legacy/field_sampler.py†L1-L66】

## 3. Usage across modules and tests

| Consumer | Engine used |
|---|---|
| `tests/test_field_sampler_engine.py` | imports `SamplerEngine` from `field_sampler.engine`【F:tests/test_field_sampler_engine.py†L1-L8】 |
| `tools/sample_field.py` | CLI utility calling `run_sampler` from `field_sampler.engine`【F:tools/sample_field.py†L1-L40】 |
| `tests/test_field_sampler_injection.py` | exercises `build_field` in `processes.field_sampler.injection_model`【F:tests/test_field_sampler_injection.py†L7-L35】 |
| `tests/test_field_adapter_smoke.py` and related adapter tests | patch `_load_sampler` in `processes.field_sampler.adapter` to stub implementations【F:tests/test_field_adapter_smoke.py†L1-L26】 |

## 4. Pipeline impact

`processes/field_sampler/adapter.py` does not ship with a default sampler; it requires `FIELD_SAMPLER_IMPL` to point at a runtime implementation and otherwise raises an error【F:processes/field_sampler/adapter.py†L54-L72】. The adapter therefore acts as a dispatcher, and whichever engine is injected (often the stub or injection model) becomes the source feeding downstream artifacts. The standalone `field_sampler/engine.py` is currently not wired into this adapter, leading to split implementations.

## 5. Recommendation and migration plan

**Single Source of Truth (SSOT):** promote `field_sampler/engine.py` as the canonical engine.

**Migration steps:**
1. Update `processes/field_sampler/adapter.py` to load `field_sampler.engine.run_sampler` by default, keeping env override for future experimentation.
2. Deprecate `processes/field_sampler/injection_model.py` and `_legacy/field_sampler.py` after integrating any missing features (e.g. variant injection) into the core engine.
3. Consolidate tests to target the unified engine via the adapter, removing stubs where possible.
4. Document the canonical API and delete redundant implementations once downstream modules verify compatibility.

---
