# Scripts Directory

This directory contains utility scripts, development tools, and automation scripts for the NBA-DFS project.

## Overview

- **Purpose**: Development utilities, data processing scripts, and automation tools
- **Languages**: Python, JavaScript/Node.js, Shell scripts
- **Usage**: Development workflow support and data management

## Directory Structure

```
scripts/
├── pyopt/             # Python optimization scripts
└── README.md          # This file
```

## Script Categories

### Python Optimization (`pyopt/`)
- `optimize_cli.py` - Direct Python optimization interface
- Development and testing utilities for CP-SAT/CBC solvers

### Development Scripts
- Fixture generation and test data preparation
- Database migration and setup utilities
- Build and deployment automation

## Usage Examples

```bash
# Direct Python optimization
python scripts/pyopt/optimize_cli.py --slate-id 20251101_NBA --config configs/optimizer.yaml

# Run with uv environment
uv run python scripts/pyopt/optimize_cli.py [args]
```

## Adding New Scripts

1. Choose appropriate subdirectory or create new category
2. Include shebang line and proper error handling
3. Add usage documentation in script header
4. Update this README with new script descriptions