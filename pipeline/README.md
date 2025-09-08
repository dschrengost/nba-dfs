# Pipeline Module

The pipeline module provides the foundational data infrastructure for the NBA-DFS system, handling data ingestion, normalization, validation, and run registry management.

## Overview

The pipeline module is the first stage of the DFS data pipeline, responsible for:
- Ingesting raw CSV projections from various sources
- Normalizing data into canonical schemas with strict validation
- Managing run registry for tracking all pipeline executions
- Providing JSON Schema definitions for all data contracts
- Ensuring data lineage and content integrity

## Architecture

```
pipeline/
├── ingest/           # Data ingestion and normalization
├── schemas/          # JSON Schema definitions (SSOT)
├── registry/         # Run registry management
└── io/              # File I/O utilities and validation
```

## Data Flow

1. **Raw CSV Input** → **Ingest Module** → **Normalized Parquet**
2. **Normalized Data** → **Processes** → **Optimized Results**
3. **All Operations** → **Registry** → **Audit Trail**

## Core Components

### Ingest (`pipeline/ingest/`)
- **Purpose**: Convert raw projection CSVs into normalized parquet files
- **Input**: CSV projections + player IDs + YAML mapping
- **Output**: Normalized parquet with lineage tracking
- **CLI**: `python -m pipeline.ingest`

**Key Features:**
- Header mapping via YAML configuration files
- Deterministic priority resolution for duplicate players
- Content hashing for change detection
- Strict schema validation

**Example Usage:**
```bash
python -m pipeline.ingest \
  --slate-id 20251101_NBA \
  --source primary \
  --projections data/raw/projections.csv \
  --player-ids data/raw/player_ids.csv \
  --mapping pipeline/ingest/mappings/dk_source.yaml \
  --out-root data
```

### Schemas (`pipeline/schemas/`)
- **Purpose**: Define strict JSON Schema contracts for all data
- **Format**: JSON Schema Draft 2020-12
- **Validation**: `additionalProperties: false` for strict enforcement

**Core Schemas:**
- `players.schema.yaml` - Player reference data
- `projections_normalized.schema.yaml` - Canonical projections
- `optimizer_lineups.schema.yaml` - Optimized lineup results
- `manifest.schema.yaml` - Run metadata
- `runs_registry.schema.yaml` - Registry entries

**Data Types:**
- **Timestamps**: UTC ISO-8601 (`2025-11-01T23:59:59.000Z`)
- **Money**: Integers in DK dollars (`5400`, never floats)
- **IDs**: `dk_player_id` flows end-to-end
- **Positions**: `{PG, SG, SF, PF, C, G, F, UTIL}`

### Registry (`pipeline/registry/`)
- **Purpose**: Track all pipeline runs for audit and discovery
- **Storage**: Append-only parquet file
- **Schema**: `runs_registry.schema.yaml`

**Run ID Format**: `YYYYMMDD_HHMMSS_<shorthash>`
- Example: `20251101_180000_deadbee`
- UTC timestamps for consistency
- Short hash for uniqueness

### I/O (`pipeline/io/`)
- **Purpose**: File operations and validation utilities
- **Features**: Content hashing, path validation, parquet I/O
- **Used by**: All pipeline components

## Integration with DFS Pipeline

The pipeline module serves as the foundation for the entire DFS workflow:

```
Raw CSVs → [Pipeline/Ingest] → Normalized Data
                                    ↓
[Processes/Optimizer] → Lineups → [Processes/Variants] → Variant Catalog
                                    ↓
[Processes/Field Sampler] → Contest Field → [Processes/GPP Simulator] → Results
```

**Key Integration Points:**
- **Output**: Normalized projections consumed by optimizer
- **Registry**: All processes append to shared registry
- **Schemas**: All outputs validated against pipeline schemas
- **Lineage**: Content hashing enables change detection

## Dependencies

### External Dependencies
```python
# Core data processing
"pandas"         # DataFrame operations
"pyarrow"        # Parquet I/O
"pydantic"       # Data validation

# Schema validation  
"jsonschema"     # JSON Schema validation
"pyyaml"         # YAML configuration parsing
```

### Internal Dependencies
- **No internal dependencies** - Pipeline is foundational layer
- **Consumed by**: `processes/` modules for normalized data

## Configuration

### Mapping Files (`pipeline/ingest/mappings/*.yaml`)
Define how source CSV headers map to canonical fields:

```yaml
name: dk_primary_source
map:
  DK_ID: dk_player_id
  Name: name
  Team: team
  Pos: pos
  Salary: salary
  Minutes: minutes
  FP: proj_fp
  Own: own_proj
```

### Schema Validation
- **Default**: All operations validate against schemas
- **Override**: Use `--no-validate` to disable (not recommended)
- **Location**: `pipeline/schemas/` (configurable with `--schemas-root`)

## Output Structure

```
data/
├── reference/
│   └── players.parquet              # Player reference data
├── projections/
│   ├── raw/
│   │   └── {slate_id}__{source}__{ts}.parquet     # Raw import snapshot
│   └── normalized/
│       └── {slate_id}__{source}__{ts}.parquet     # Canonical projections
├── runs/
│   └── ingest/
│       └── {run_id}/
│           └── manifest.json        # Run metadata
└── registry/
    └── runs.parquet                 # Append-only run log
```

## Quality Assurance

### Data Integrity
- **Content Hashing**: SHA-256 of all inputs tracked
- **Schema Validation**: Strict JSON Schema enforcement
- **Duplicate Resolution**: Deterministic priority rules
- **Lineage Tracking**: Source mapping and transformation history

### Error Handling
- **Validation Failures**: Exit non-zero, write nothing
- **Missing Dependencies**: Graceful fallbacks where possible
- **Schema Mismatches**: Detailed error reporting with context

## Development

### Running Tests
```bash
pytest tests/pipeline/ -v
```

### Code Quality
```bash
ruff check pipeline/
black pipeline/
mypy pipeline/
```

### Adding New Schemas
1. Create `{name}.schema.yaml` in `pipeline/schemas/`
2. Include version, description, and strict validation
3. Add to schema test suite
4. Update this README

## Troubleshooting

**Common Issues:**

1. **Schema Validation Errors**
   - Check field names match schema exactly
   - Verify data types (int vs float, string formats)
   - Ensure required fields are present

2. **Mapping Configuration**
   - Verify YAML syntax in mapping files
   - Check header names match source CSV exactly
   - Confirm canonical field names are correct

3. **File Permissions**
   - Ensure output directories are writable
   - Check file locks on Windows systems

4. **Python Environment**
   - Use `uv sync --extra dev` for complete setup
   - Verify Python 3.11+ is active
   - Check that parquet dependencies are installed

## Future Enhancements

- **Stream Processing**: Real-time ingestion capabilities
- **Multi-Site Support**: Extend beyond DraftKings
- **Advanced Validation**: Cross-table constraint checking
- **Performance Optimization**: Batch processing for large datasets