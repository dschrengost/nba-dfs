# feat(validators): shared DK lineup validator (SSOT)

## Summary
Implements a single-source DraftKings lineup validator and refactors all stages to use it. This removes drift, ensures identical rule enforcement across the pipeline, and exposes structured diagnostics.

## Key Changes
- **validators/** module (typed, pure functions)
- **Optimizer / Variant Builder / Field Sampler** now import shared validator
- **Complete DK rule set**: roster size, slot eligibility, salary cap, team limits, no duplicates, active/injury checks
- **Backtracking slot assignment** for optimal position mapping
- **ValidationResult** model with detailed diagnostics + aggregated metrics per stage
- **Docs**: migration guide + usage

## Checks
- ✅ Tests: 20 unit + integration pass
- ✅ Lint: ruff clean
- ✅ Types: mypy (strict) clean
- ✅ Functionality: integration tests confirm correct operation

## Why
Repomix audit flagged missing SSOT validator and scattered/duplicated logic. This PR centralizes rules to align the entire pipeline and reduce maintenance.

## How to Test
\`\`\`bash
uv sync
uv run ruff .
uv run black --check .
uv run mypy .
uv run pytest -q
\`\`\`
Smoke an end-to-end mini-slate and confirm \`validation_metrics.json\` is written under each stage's run directory.

## Acceptance Criteria
- Single \`validators/lineup_rules.py\` API used by optimizer, VB, FS
- No duplicate validation code remains
- All tests green; gates pass via \`uv run\`
- Artifacts include validation metrics and preserve \`dk_player_id\`

## Notes
- Non-goal: sampler algorithm changes (coming in PRP-FS-01)
- Backward compatibility preserved; interfaces unchanged

---
Reviewer focus:
- Rule correctness vs. DK constraints
- Determinism (no hidden globals/randomness)
- Clear error reasons and metrics usability
