# Processes Module

The processes module contains the core analysis engines for NBA Daily Fantasy Sports optimization, providing headless adapters for optimizer, variant builder, field sampler, and GPP simulator components.

## Overview

The processes module implements the main computational stages of the DFS pipeline:
- **Optimizer**: Generate optimal lineups from projections using CP-SAT or CBC solvers
- **Variants**: Build lineup variants from base optimizations
- **Field Sampler**: Create representative contest fields from variant catalogs
- **GPP Simulator**: Simulate tournament results and calculate EV metrics
- **Orchestrator**: Coordinate multi-stage pipeline runs
- **Metrics**: Generate performance analytics across all stages

## Architecture

```
processes/
├── optimizer/        # Lineup optimization (CP-SAT/CBC)
├── variants/         # Lineup variant generation
├── field_sampler/    # Contest field simulation
├── gpp_sim/          # Tournament simulation & EV calculation
├── orchestrator/     # Multi-stage pipeline coordination
├── metrics/          # Performance analytics
├── api/              # FastAPI endpoints
└── dk_export/        # DraftKings export utilities
```

## Data Flow Pipeline

```
Normalized Projections
        ↓
[1. Optimizer] → Base Lineups
        ↓
[2. Variants] → Variant Catalog
        ↓
[3. Field Sampler] → Contest Field
        ↓
[4. GPP Simulator] → Tournament Results & EV Metrics
```

## Core Components

### 1. Optimizer (`processes/optimizer/`)
**Purpose**: Generate optimal DFS lineups using mathematical optimization

**Algorithms:**
- **Primary**: CP-SAT (OR-Tools) - Constraint Programming Satisfiability
- **Fallback**: CBC (PuLP) - Mixed Integer Linear Programming

**Input**: Normalized projections parquet
**Output**: Optimized lineups with metrics

**CLI Usage:**
```bash
python -m processes.optimizer \
  --slate-id 20251101_NBA \
  --site DK \
  --config configs/optimizer.yaml \
  --engine cbc \
  --seed 42 \
  --out-root data
```

**Key Features:**
- **Constraints**: Salary cap, position requirements, roster construction
- **Advanced Rules**: Player stacking, exposure limits, ownership penalties
- **Deterministic**: Same inputs + seed = same outputs
- **Multi-lineup**: Generate diverse lineup sets

**Configuration Options:**
```yaml
num_lineups: 20
max_salary: 50000
min_salary: 48000
stacking:
  team_stack_sizes: [2, 3]
  max_team_stack: 4
exposure_caps:
  global_max: 0.8
  position_max: 0.6
ownership_penalty: 0.1
randomness: 0.15
```

### 2. Variants (`processes/variants/`)
**Purpose**: Generate lineup variants from optimizer base lineups

**Strategy**: Create diverse lineups by systematic player substitutions

**Input**: Optimizer lineups parquet
**Output**: Variant catalog with expanded lineup pool

**CLI Usage:**
```bash
python -m processes.variants \
  --slate-id 20251101_NBA \
  --config configs/variants.yaml \
  --seed 42 \
  --out-root data \
  --from-run optimizer_run_id
```

**Variant Generation Methods:**
- **Positional Swaps**: Replace players by position
- **Value Optimization**: Salary-based substitutions  
- **Correlation Adjustments**: Account for player correlations
- **Ownership Balancing**: Adjust for projected ownership

### 3. Field Sampler (`processes/field_sampler/`)
**Purpose**: Build representative contest fields from variant catalogs

**Sampling Strategy**: Create realistic tournament field compositions

**Input**: Variant catalog parquet
**Output**: Contest field with entrant lineups

**CLI Usage:**
```bash
python -m processes.field_sampler \
  --slate-id 20251101_NBA \
  --config configs/field.yaml \
  --seed 42 \
  --out-root data \
  --from-run variants_run_id
```

**Field Construction:**
- **Field Size**: Configurable contest size (e.g., 10K entrants)
- **Source Mix**: Blend optimizer + variants + external lineups
- **Ownership Curves**: Model realistic ownership patterns
- **Diversity Controls**: Ensure field diversity metrics

### 4. GPP Simulator (`processes/gpp_sim/`)
**Purpose**: Simulate tournament outcomes and calculate expected value

**Simulation Engine**: Monte Carlo simulation with variance modeling

**Input**: Contest field + contest structure
**Output**: Tournament results with EV metrics

**CLI Usage:**
```bash
python -m processes.gpp_sim \
  --slate-id 20251101_NBA \
  --config configs/sim.yaml \
  --seed 42 \
  --out-root data \
  --from-run field_run_id
```

**Simulation Features:**
- **Score Generation**: Model player performance variance
- **Payout Calculation**: Apply contest prize structures
- **EV Metrics**: Expected value, win probability, ROI
- **Risk Analysis**: Variance, downside protection

### 5. Orchestrator (`processes/orchestrator/`)
**Purpose**: Coordinate multi-stage pipeline execution

**Workflow Management**: Chain optimizer → variants → field → simulation

**CLI Usage:**
```bash
python -m processes.orchestrator \
  --slate-id 20251101_NBA \
  --config configs/full_pipeline.yaml \
  --seed 42 \
  --out-root data
```

### 6. Metrics (`processes/metrics/`)
**Purpose**: Generate performance analytics across pipeline stages

**Analytics Types:**
- Lineup diversity metrics
- Ownership correlation analysis  
- EV performance tracking
- Risk-adjusted returns

## Integration Points

### Input Discovery
Each process automatically discovers inputs using precedence rules:

1. **Explicit Path**: `--input path/to/file.parquet`
2. **Run Reference**: `--from-run previous_run_id`
3. **Registry Lookup**: Latest run of required type for slate

### Output Registration
All processes append to the shared run registry:
```python
{
  "run_id": "20251101_180000_deadbee",
  "run_type": "optimizer",
  "slate_id": "20251101_NBA", 
  "created_ts": "2025-11-01T23:00:00.000Z",
  "primary_outputs": ["lineups.parquet"],
  "config_sha256": "...",
  "seed": 42
}
```

## Dependencies

### External Dependencies
```python
# Optimization engines
"ortools"        # CP-SAT constraint programming (primary)
"pulp"           # CBC linear programming (fallback)

# Data processing  
"pandas"         # DataFrame operations
"numpy"          # Numerical computing
"pyarrow"        # Parquet I/O

# Web framework
"fastapi"        # API endpoints
"pydantic"       # Data validation
```

### Internal Dependencies
- **Pipeline Schemas**: Strict validation against `pipeline/schemas/`
- **Registry System**: Shared run tracking via `pipeline/registry/`
- **Configuration**: YAML configs in `configs/` directory

## API Endpoints (`processes/api/`)

FastAPI server for process orchestration:

**Endpoints:**
- `POST /optimize` - Run optimizer
- `POST /variants` - Generate variants  
- `POST /field` - Sample contest field
- `POST /simulate` - Run GPP simulation
- `GET /runs` - List pipeline runs
- `GET /runs/{run_id}` - Get run details

**Usage:**
```bash
uvicorn processes.api:app --host 0.0.0.0 --port 8000
```

## Configuration System

### Config Files (`configs/`)
- `optimizer.yaml` - Optimization parameters
- `variants.yaml` - Variant generation settings
- `field.yaml` - Field sampling configuration  
- `sim.yaml` - Simulation parameters
- `full_pipeline.yaml` - End-to-end workflow

### Environment Variables
- `DFS_SOLVER_MODE` - Choose solver: `python` (default) or `sampler`
- `OPTIMIZER_IMPL` - Override optimizer implementation
- `FIELD_SAMPLER_IMPL` - Override field sampler implementation

## Output Structure

```
data/runs/
├── optimizer/{run_id}/
│   ├── lineups.parquet          # Optimized lineups
│   ├── metrics.parquet          # Optimization metrics
│   └── manifest.json            # Run metadata
├── variants/{run_id}/
│   ├── variant_catalog.parquet  # Lineup variants
│   ├── metrics.parquet          # Variant metrics  
│   └── manifest.json
├── field/{run_id}/
│   ├── field.parquet           # Contest field
│   ├── metrics.parquet         # Field metrics
│   └── manifest.json
└── sim/{run_id}/
    ├── results.parquet         # Simulation results
    ├── metrics.parquet         # EV metrics
    └── manifest.json
```

## Quality Assurance

### Deterministic Processing
- **Seeded Random**: All stochastic operations use explicit seeds
- **Reproducible**: Same inputs + seed = identical outputs
- **Content Hashing**: Input change detection via SHA-256

### Validation
- **Schema Compliance**: All outputs validate against pipeline schemas
- **Constraint Checking**: Roster rules, salary caps enforced
- **Data Integrity**: Player ID consistency across pipeline stages

### Performance Monitoring  
- **Execution Metrics**: Runtime, memory usage, optimization gaps
- **Quality Metrics**: Lineup diversity, field representativeness  
- **Business Metrics**: EV accuracy, win rate correlation

## Development

### Running Individual Processes
```bash
# Optimizer
python -m processes.optimizer --slate-id 20251101_NBA --config configs/optimizer.yaml

# Full pipeline  
python -m processes.orchestrator --slate-id 20251101_NBA --config configs/full_pipeline.yaml
```

### Testing
```bash
pytest tests/processes/ -v
```

### Code Quality
```bash
ruff check processes/
black processes/  
mypy processes/
```

## Troubleshooting

**Solver Issues:**
- CP-SAT unavailable: Automatically falls back to CBC
- Infeasible problems: Check constraint conflicts in config
- Performance: Adjust `cp_sat_params` timeout settings

**Memory Management:**
- Large fields: Use sampling parameters to control memory usage
- Simulation runs: Configure batch sizes for Monte Carlo runs

**Input Discovery:**
- Missing inputs: Check registry for required run types
- Path resolution: Use absolute paths or verify working directory

## Performance Optimization

### Solver Tuning
```yaml
cp_sat_params:
  max_time_in_seconds: 300
  num_search_workers: 4
  log_search_progress: false
```

### Memory Management
```yaml 
field_sampling:
  batch_size: 1000
  memory_limit_mb: 2048
```

### Parallelization
- **Multi-core**: CP-SAT automatically uses available cores
- **Batch Processing**: Split large problems into smaller chunks
- **Pipeline**: Run stages in parallel where dependencies allow

## Future Enhancements

- **Advanced Stacking**: Multi-team correlation models
- **Dynamic Pricing**: Real-time salary adjustments  
- **Machine Learning**: Projection enhancement with ML models
- **Real-time**: Live contest monitoring and adjustments