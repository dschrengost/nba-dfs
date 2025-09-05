Pipeline Schema Pack (SSOT)

Overview
- Purpose: Define strict, versioned JSON Schemas for all NBA-DFS pipeline artifacts (ingest → normalize → optimize → variants → field → sim).
- Storage targets: Parquet (primary), with 1:1 JSON/CSV exporters mapping to the same contracts.
- Strictness: All schemas set additionalProperties: false. Required fields and numeric ranges are enforced where expressible in JSON Schema. Some cross-field and cross-table rules are documented as validator notes.
- JSON Schema: Draft 2020-12 is used and pinned via `$schema` in each file.

Files
- common.types.yaml
- players.schema.yaml
- slates.schema.yaml
- projections_raw.schema.yaml
- projections_normalized.schema.yaml
- optimizer_lineups.schema.yaml
- optimizer_metrics.schema.yaml
- variant_catalog.schema.yaml
- variant_metrics.schema.yaml
- field.schema.yaml
- field_metrics.schema.yaml
- contest_structure.schema.yaml
- sim_results.schema.yaml
- sim_metrics.schema.yaml
- manifest.schema.yaml
- runs_registry.schema.yaml

Conventions
- Timestamps: UTC ISO-8601 (e.g., 2025-11-01T23:59:59.000Z). JSON Schema uses format: date-time; a stricter Z-suffix pattern is documented in common types.
- Money: integers in DK dollars (e.g., salary: 5400), never floats.
- Floats/probabilities: numbers with explicit ranges; probabilities in [0,1].
- IDs: dk_player_id travels end-to-end; slate_id matches ^\d{8}_NBA$.
- Enums: positions {PG, SG, SF, PF, C, G, F, UTIL}; site {DK}; run types {ingest, optimizer, variants, field, sim}.
- Lineage: normalization carries a lineage object with source, mapping notes, and content_sha256.

Run IDs
- Format: `YYYYMMDD_HHMMSS_<shorthash>` (lowercase), e.g., `20251101_180000_deadbee`.
- Enforced via `common.types.yaml#/definitions/RunId`; all run-linked schemas reference this.

Validator Notes (beyond JSON Schema)
- projections_normalized: ceil_fp ≥ proj_fp ≥ floor_fp. JSON Schema cannot enforce cross-field comparisons; implement in validator.
- optimizer_lineups: roster validity (8 players; positions compatible; total_salary ≤ 50000) — array length and salary max are enforced; full DK roster logic should be checked in validator.
- Contest payout: payout ranges must be contiguous, non-overlapping, and cover field_size exactly; enforce in validator.
- Cross-table checks:
  - projections_normalized.dk_player_id ⊆ players.dk_player_id
  - lineup/variant/field players ∈ players.dk_player_id
  - sim_results.entrant_id ∈ field.entrant_id for the referenced run

Parquet Type Mapping
- strings → UTF8; integers → INT32/INT64 as needed; numbers → DOUBLE (or FLOAT where appropriate).
- arrays → LIST; structs → STRUCT. Nested objects (e.g., dk_positions_filled, payout_curve) map to STRUCT or LIST<STRUCT>.
- Timestamps stored as strings (UTC ISO) at this layer for simplicity; adapters may project to TIMESTAMP(UTC) if desired.

Versioning
- Each schema includes a version string. Use semver-ish rules:
  - patch: description/metadata changes; no structural changes
  - minor: additive fields (optional) or relaxed bounds
  - major: breaking changes (removed/renamed fields, stricter bounds)
- Maintain a changelog section in this README when bumping versions.

Usage
- Validate a file using a future CLI (spec only):
  - `validate-table --schema pipeline/schemas/<name>.schema.yaml --input <parquet|json|csv>`
- JSON Schema draft: use Draft 2020-12. Python snippet:
  - `from jsonschema import Draft202012Validator as V` then `V.check_schema(schema)`
- Fail on: missing fields, out-of-range values, additionalProperties, enum mismatches, roster invalidity (as applicable).

Tiny Golden Dataset (for future tests)
- players: 3 rows, teams {BOS, LAL, MIA}, positions covering PG, SF/PF, C; valid timestamps
- projections_normalized: 3 rows (one per player) for a single `slate_id`, consistent `dk_player_id`, salary ≥ 3000, minutes ≤ 60; includes `lineage.content_sha256`
- optimizer_lineups: 1 lineup with 8 players drawn from players; `total_salary` ≤ 50000; `export_csv_row` matches DK header order
- contest_structure: field_size 10; payout_curve [1,1], [2,2], [3,3], [4,10] with prizes
- manifest: lists projections_normalized input (with content_sha256) and optimizer_lineups output kind

DK CSV Export
- Header/order for DraftKings NBA Classic upload: `PG,SG,SF,PF,C,G,F,UTIL` (8 columns, comma-separated).
- Fields named `export_csv_row` (optimizer_lineups, variant_catalog, field) must serialize rows matching this header order; exact player token format is site-proprietary and validated in adapters/tooling.

Change Log Template
- One-line entries: `YYYY-MM-DD – vX.Y.Z – who – why/impact`
- Example: `2025-09-04 – v0.1.1 – dschrengost – add RunId pattern and DK export notes (non-breaking)`

Changelog
- 0.1.0: Initial schema pack scaffolding
- 0.2.0: Add RunTypeEnum value `ingest`; bump manifest and runs_registry versions; align examples
