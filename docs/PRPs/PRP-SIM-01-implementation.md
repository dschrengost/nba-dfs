# PRP-SIM-01 Implementation Notes

Initial implementation of minimal simulation metrics.

- Computes ROI distribution, finish percentiles, and duplication bins.
- Writes `sim/metrics.json` aligning with `sim_metrics.schema.yaml`.
- Propagates compact `metrics_head` into `manifest.json`.
- Added basic test coverage under `tests/sim/`.
