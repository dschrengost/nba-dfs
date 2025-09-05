
# PRP-2L: Document Legacy Optimizer & Plan De-UI Extraction

## Status
**Planned** — immediate follow-up to PRP‑1b. Focused on documentation and a clean plan to reuse legacy logic without UI cruft.

---

## Objective
1) **Inventory & document** legacy optimizer modules (`optimize.py`, `nba_optimizer_functional.py`, `cpsat_solver.py`, `pruning.py`, plus any helpers) and their relationships.  
2) **Separate concerns**: identify Streamlit/UI/AG Grid code vs. pure compute logic.  
3) Produce a **De‑UI extraction plan** so PRP‑2 (adapter) can call the logic headlessly.

No functional rewrites in this PRP; only docs and *surgical* annotations (e.g., TODO tags) are allowed.

---

## Start Bookend — Branch
```
PRP Start → branch=feature/legacy-docs-deui-plan
```

---

## Scope & Deliverables

### A. Written docs (checked into repo)
- `processes/optimizer/_legacy/README.md`
  - Purpose of each legacy file
  - Public functions/classes intended for reuse
  - Known UI dependencies and side effects (imports, global state, streamlit calls)
  - Data contracts expected/returned by each public entrypoint
  - Ownership penalty & other knobs — where they are parsed and applied

- `docs/legacy/LEGACY-OPTIMIZER.md`
  - High-level overview of legacy optimizer architecture
  - **Mermaid diagrams**:
    - Module dependency graph
    - Call sequence for a typical optimize run
  - I/O shapes (tables) for the primary entrypoint (inputs, outputs)
  - Known tech debt: Streamlit/AG Grid coupling, path hacks (`sys.path.append`), UI exports
  - **De‑UI extraction plan** (see Section C)

- `docs/legacy/SYMBOLS-TO-KEEP.md`
  - Whitelist of symbols to preserve as the stable programmatic API
  - For each symbol: signature, description, input/output schema mapping

### B. Code annotations (non-breaking)
- Add `# TODO(PRP-2L):` comments where UI code intrudes into logic. Examples to tag:
  - `import streamlit as st`, `st_aggrid`, AG Grid CSS, `st.sidebar`, etc.
  - `sys.path.append` hacks to import `backend.*`
  - File I/O intended for UI (e.g., writing CSV previews directly)
  - Global state / mutable module-level config
- Do **not** change behavior — comments only.

### C. De‑UI Extraction Plan
- Define new **headless API surface** to be consumed by the adapter in PRP‑2:
  - `run_optimizer(projections_df, constraints: dict, seed: int, site: str, engine: str) -> (lineups_df, metrics_dict)`
  - Optional `telemetry` object for solver diagnostics
- Map legacy functions to this surface (which function provides which part).
- Identify minimal set of refactors needed in PRP‑2 (e.g., move export helpers to a non‑UI module).
- Identify any **hard dependencies** on UI packages and how to remove/replace them (e.g., replace `st.cache_data` with local memoization).

---

## Out of Scope
- No refactors beyond comments.
- No adapter implementation (that’s PRP‑2).
- No UI deletion — only documentation of what to remove later.

---

## Method (how the agent should do this)
1) **Static scan** the following legacy files and any modules they import from the same folder:
   - `processes/optimizer/_legacy/optimize.py`
   - `processes/optimizer/_legacy/nba_optimizer_functional.py`
   - `processes/optimizer/_legacy/cpsat_solver.py`
   - `processes/optimizer/_legacy/pruning.py`

2) Build a **module dependency map** (imports between these files; ignore stdlib/3p).

3) Identify all **public entrypoints** (functions/classes used externally in the old app).

4) For each entrypoint, document:
   - **Inputs** (dataframes/objects & required columns/fields)
   - **Outputs** (dataframes/objects & required columns/fields)
   - **Side effects** (file writes, logging, global state, UI calls)

5) Tag UI‑coupled lines with `# TODO(PRP-2L): De‑UI` comments (no behavior change).

6) Draft the **De‑UI plan** (Section C) with a small table mapping legacy functions → headless API.

7) Write the docs (A) and commit.

---

## Acceptance Criteria
- `processes/optimizer/_legacy/README.md` explains each legacy file and lists stable symbols to reuse.
- `docs/legacy/LEGACY-OPTIMIZER.md` contains:
  - A clear narrative of how the legacy optimizer works
  - Mermaid diagrams for modules and call flow
  - An explicit De‑UI extraction plan and list of UI-only code to remove
- `docs/legacy/SYMBOLS-TO-KEEP.md` lists function signatures + brief purpose + I/O shapes.
- Source code contains `# TODO(PRP-2L): De‑UI` comments at all UI touchpoints.
- **No test or runtime behavior changes**; CI still green.

---

## Directory Changes
```
processes/optimizer/_legacy/
  README.md            # updated/created by this PRP
docs/legacy/
  LEGACY-OPTIMIZER.md
  SYMBOLS-TO-KEEP.md
```

---

## Risks & Mitigations
- **Hidden dependencies** → The dependency map should flag any imports that live outside `_legacy`. Note gaps explicitly.
- **Over‑documenting internals** → Focus docs on API surfaces and relationships; don’t narrate every helper.

---

## Start/End Bookends — Actions

**Start**  
```
PRP Start → branch=feature/legacy-docs-deui-plan
```

**End**  
```
PRP End → branch=feature/legacy-docs-deui-plan
```

(Manual alternative)
```bash
git checkout -b feature/legacy-docs-deui-plan
# … make the changes per Scope …
git commit -m "Docs: legacy optimizer inventory + De‑UI extraction plan (PRP‑2L)"
git push -u origin feature/legacy-docs-deui-plan

# Merge after review
git checkout main
git merge --no-ff feature/legacy-docs-deui-plan -m "Merge PRP‑2L: legacy docs + De‑UI plan"
git push origin main
```
