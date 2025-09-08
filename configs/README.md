# Configuration Directory

This directory contains YAML configuration files for all NBA-DFS pipeline processes. Configurations define parameters, constraints, and settings for optimization, variant generation, field sampling, and simulation.

## Overview

- **Purpose**: Centralized configuration management for all pipeline stages
- **Format**: YAML files with strict validation against JSON schemas
- **Environment**: `defaults.yaml` (tracked) + `local.yaml` (gitignored overrides)
- **Usage**: Referenced by CLI tools via `--config` parameter

## Configuration Files

### Core Process Configs
- `optimizer.yaml` - Lineup optimization parameters
- `variants.yaml` - Variant generation settings  
- `field.yaml` - Contest field sampling configuration
- `sim.yaml` - GPP simulation parameters
- `full_pipeline.yaml` - End-to-end workflow configuration

### Environment Configs
- `defaults.yaml` - Default settings (version controlled)
- `local.yaml` - Local overrides (gitignored)

## Usage Examples

```bash
# Use specific config file
python -m processes.optimizer --config configs/optimizer.yaml

# Override with local settings
python -m processes.optimizer --config configs/local.yaml
```