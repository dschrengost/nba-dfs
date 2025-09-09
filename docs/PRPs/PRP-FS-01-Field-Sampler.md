# PRP-FS-01 — Field Sampler Engine Build-Out

**Owner:** Agent  
**Repo:** `nba-dfs`  
**Status:** Proposed  
**Depends on:** Shared validator (PRP-VAL-01), schema pack, optimizer/variant builder outputs

---

## 1) Summary
Implement a complete field sampling engine that generates realistic DraftKings-compliant contest fields. Currently, the sampler stubs exist but core logic is missing. This PRP delivers a deterministic, configurable engine aligned with the shared validator and schemas.

---

## 2) Goals / Non-Goals
### Goals
- Implement `SamplerEngine` with modular sub-engines:
  - `PositionAllocator` — assign slots via validator eligibility
  - `SalaryManager` — enforce cap distributions
  - `TeamLimiter` — respect per-team limits
  - `OwnershipBias` — weight variants by projected ownership
  - `Randomizer` — RNG with seed for reproducibility
- Configurable knobs for salary spread, ownership skew, uniqueness
- Output: parquet/CSV of sampled lineups, all validator-passing
- Metrics: duplication %, ownership distribution, salary histograms
- Integration with run registry (PRP-RUN-01)

### Non-Goals
- New ownership models (just wiring; model quality later)
- Advanced late-swap features

---

## 3) Deliverables
- `processes/field_sampler/engine.py` (SamplerEngine + submodules)
- Tests: `tests/test_field_sampler_engine.py`
- Docs: `docs/field_sampler/README.md` (usage, configs, metrics)
- Updated run artifacts: `runs/<slate>/field_sampler/<run_id>/`

---

## 4) Public API
```python
class SamplerEngine:
    def __init__(self, rules: Rules, config: SamplerConfig, seed: int = 42): ...
    def sample(self, variants: list[Lineup], size: int) -> list[Lineup]: ...
```

---

## 5) Tests
- Unit: slot allocation, salary spread, team limits, ownership skew
- Integration: sample N entrants, assert DK validity via validator
- Metrics snapshot

---

## 6) Acceptance Criteria
- Generates DK-valid sampled fields
- Reproducible with seed
- Produces metrics JSON + lineups parquet
- Runs complete without TypeError or drift
