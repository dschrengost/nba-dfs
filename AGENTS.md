# Purpose & Scope
This document outlines the guidelines and best practices for agents working within the NBA DFS project. It aims to ensure consistency, clarity, and efficiency across all contributions.

# Core Principles
- Maintain high code quality and readability.
- Ensure reproducibility and determinism in data pipelines.
- Prioritize automation and testing.
- Foster clear communication and documentation.

# Repo Layout
- `src/`: Source code and modules.
- `data/`: Raw and processed datasets.
- `tests/`: Unit and integration tests.
- `configs/`: Configuration files and secrets.
- `docs/`: Documentation and process guidelines.

# Tech Stack & Versions
- Python 3.9+
- PostgreSQL 13
- Docker 20.x
- GitHub Actions for CI/CD

# Data Pipeline Contracts
- All data transformations must adhere to defined schemas.
- Version data contracts explicitly in the codebase.
- Migrations require clear documentation and backward compatibility.

# Slate & Keys
- Slates represent game groupings; keys uniquely identify players and games.
- Ensure keys are stable and consistent across datasets.

# Run Registry & Artifacts
- Maintain a registry of all pipeline runs with metadata.
- Store artifacts in versioned directories for auditability.

# Config & Secrets
- Use environment variables for secrets.
- Store configs in `configs/` with example templates.
- Avoid committing secrets to the repository.

# Testing & CI
- Write tests for all new features and bug fixes.
- Use GitHub Actions for automated linting, testing, and deployment.
- Ensure tests pass before merging PRs.

## 10) Branching & PR Rules
- Branches: `main` (protected), `dev` (integration), feature `feat/<slug>`.
- PRs only; no direct commits to `main`.
- PR Discipline: One Task = One PR

**Problem:**  
Agents sometimes open a new PR after review feedback instead of updating the original.  
This fragments history and adds chaos.

**Policy:**  
1. **One task = one branch = one PR** until merged.  
2. If changes are requested, the agent **must push commits to the same branch/PR**.  
3. If scope truly changes → close current PR and open a **new PR with a new PRP ID**, explicitly noting it **supersedes** the old one.  
4. PR titles must include the PRP ID:  
   ```
   <PRP-ID>: <short description>
   ```
   Branch naming:  
   ```
   agent/<agent-name>/<PRP-ID>
   ```

**Agent Instructions (paste as PR comment):**
> You are required to update **this PR only**.  
> Do **not** open a new PR for follow-ups.  
> - Push commits to the **same branch**  
> - Mark resolved threads  
> - Keep total diff under 400 lines  
> - If scope must change, comment first and wait for approval

**Maintainer Checklist:**  
- If requesting changes, add label `needs-changes` and remind agent: *“Update this PR, don’t open another.”*  
- If a duplicate PR appears → comment *“duplicate; continue in #<original>”* and close it.  
- Convert to **Draft** if scope is unclear.  

**Automation:**  
A GitHub Action (`Agent PR Guardian`) can auto-flag duplicate PRs for the same PRP ID and label them `duplicate`.

# Agent Operating Rules
- Agents must follow the branching and PR rules strictly.
- Use descriptive commit messages.
- Communicate blockers promptly.

# Performance & Determinism
- Ensure pipelines run within expected timeframes.
- Validate outputs for determinism with each run.

# Observability & Metrics
- Instrument code with logging and metrics.
- Monitor pipeline health and alert on anomalies.

# Safety Rails
- Implement rollback plans for failed deployments.
- Use feature flags for experimental changes.

# House Processes
- Regularly review and update documentation.
- Conduct periodic code audits and knowledge sharing sessions.

# Open TBDs
- Define standards for new data sources.
- Explore automation for data quality checks.
