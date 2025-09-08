# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- **Python package management**: Use `uv sync` (includes dev dependencies with `--extra dev`)
- **Development dependencies**: `uv sync --extra dev`
- **Node.js dependencies**: `npm install`

### Code Quality & Testing

**Python**:
- **Format code**: `black .`
- **Lint code**: `ruff check .` (fix with `ruff check . --fix`)
- **Type checking**: `mypy .`
- **Run tests**: `pytest -q` (configured in pyproject.toml)
- **Test coverage**: `pytest --cov`

**Frontend (Next.js)**:
- **Development server**: `npm run dev` (runs on port 3000)
- **Build**: `npm run build`
- **Start production**: `npm run start` (runs on port 3000)
- **Run tests**: `npm run test` (Vitest)

### CI Pipeline (must pass before commit)
```bash
uv sync --extra dev
ruff check .
black --check .
mypy .
pytest -q
```

### Schema Validation
- **Validate YAML schemas**: `yamllint pipeline/schemas/`
- **JSON Schema validation**: Use `jsonschema` package with Draft 2020-12

## Architecture Overview

This is a **monorepo** for NBA Daily Fantasy Sports data pipeline and analysis tools with strict deterministic processing requirements. It combines a Python backend for data processing with a Next.js frontend for visualization and interaction.

### Core Structure
- **`pipeline/`**: Data ingestion, normalization, schemas, and I/O adapters
- **`processes/`**: Core analysis modules (optimizer, variant builder, field sampler, simulator)
- **`app/`**: Unified dashboard (future)
- **`data/`**: Parquet data store (gitignored)
- **`docs/`**: Design documentation and PRPs (Phased Requirement Plans)

### Key Components

**Pipeline Module**:
- `pipeline/ingest/`: CLI for data ingestion with YAML source mappings
- `pipeline/schemas/`: Strict JSON Schema definitions (Draft 2020-12) for all data contracts
- `pipeline/io/`: File operations and validation utilities
- `pipeline/registry/`: Run registry management

**Processes Module**:
- `processes/optimizer/`: DFS lineup optimization using CP-SAT (OR-Tools) or CBC fallback
- `processes/variants/`: Lineup variant generation
- `processes/field_sampler/`: Contest field sampling
- `processes/gpp_sim/`: Tournament simulation
- `processes/api/`: FastAPI endpoints for process orchestration

**Frontend/Integration**:
- `app/`: Next.js dashboard with React components
- `lib/`: Shared TypeScript utilities (domain logic, state management, UI)
- `components/`: Reusable UI components (Shadcn/ui, Aceternity)

## Data Architecture

### Schema System
- **All data uses strict JSON Schema validation** (additionalProperties: false)
- **Versioned schemas** using semantic versioning (major.minor.patch)
- **Primary storage**: Parquet with 1:1 JSON/CSV export capability
- **Schema files**: `pipeline/schemas/*.schema.yaml`

### Core Data Contracts

**Players** (`players.schema.yaml`):
- `player_id_dk`: DraftKings player ID (carries through entire pipeline)
- Position enums: {PG, SG, SF, PF, C, G, F, UTIL}
- Team codes: 3-letter format

**Projections** (`projections_normalized.schema.yaml`):
- Normalized from raw CSV inputs
- Includes salary, projected fantasy points, minutes, ownership
- Must maintain `lineage` object with source tracking

**Run Registry** (`runs_registry.schema.yaml`):
- Every run gets unique ID: `YYYYMMDD_HHMMSS_<shorthash>`
- Immutable run artifacts with metadata and input hashes

### Data Flow
1. **Ingest**: Raw CSV → normalized Parquet (with schema validation)
2. **Optimizer**: Projections → optimal lineups
3. **Variants**: Base lineups → multiple lineup variants  
4. **Field**: Lineups → contest field simulation
5. **Simulator**: Contest field → tournament results

## Development Principles

### Determinism & Reproducibility
- **All stochastic operations require explicit `seed` parameter**
- **Run artifacts include `run_meta.json`** with seed, config, and timestamps
- **Idempotent operations**: Same inputs + seed = same outputs
- **Slate keys**: Format `YY-MM-DD_HHMMSS` (America/New_York timezone)

### Data Integrity
- **Player ID persistence**: `player_id_dk` must flow through entire pipeline
- **Schema validation**: All I/O operations validate against schemas
- **Content hashing**: Input files tracked by SHA256 for change detection
- **Immutable runs**: Run registry is read-only after creation

### Code Quality
- **Python version**: Use current local runtime (avoid 3.13-only features)
- **Typing**: Strict mode enabled for new modules (`mypy --strict`)
- **Import organization**: First-party modules: `["pipeline", "processes", "app"]`
- **Conventional commits**: Use `feat:`, `fix:`, `refactor:`, `docs:` prefixes

## File System Conventions

### Protected Areas (READ-ONLY for agents)
- `data/raw/`: User uploads - never modify
- `runs/`: Run registry - immutable after creation

### Editable Areas
- `pipeline/`, `processes/`, `app/`: Source code
- `tests/`: Test files  
- `configs/`: Configuration files
- `docs/`: Documentation

### Configuration
- **Tracked defaults**: `configs/defaults.yaml`
- **Local overrides**: `configs/local.yaml` (gitignored)
- **Environment**: `.env.example` (tracked), `.env` (gitignored)

## Agent Operating Rules

### Change Management
- **Small changes**: <30 LOC, single module - allowed directly
- **Large changes**: >30 LOC or multi-module - requires PRP documentation
- **Schema changes**: Always require tests and PRP documentation
- **No force-push** to main branch

### Safety Rails
- Never write to `data/raw/` or `runs/` without slate key validation
- Never embed secrets in code or commits
- All new dependencies must update `uv.lock`
- Maintain existing code style and patterns

### Development Workflow
1. Use `uv sync --extra dev` for complete environment setup
2. Run full CI pipeline before committing changes
3. Validate schemas when modifying data contracts
4. Include tests for new modules in `tests/`
5. Follow conventional commit format for all commits

## Testing Strategy

**Python Tests**:
- **Location**: `tests/` directory with fixtures in `tests/fixtures/`
- **Framework**: pytest with coverage support
- **Run specific test**: `pytest tests/test_specific.py -v`
- **Fixtures**: Use `tests/fixtures/` for test data (CSV samples, YAML mappings)

**Frontend Tests**:
- **Framework**: Vitest with React Testing Library patterns
- **Config**: Vitest config in `vitest.config.ts` with path alias `@` for root
- **Component tests**: Located alongside components or in dedicated test directories