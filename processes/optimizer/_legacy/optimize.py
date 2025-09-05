"""
NBA DFS Lineup Optimizer - Streamlit UI
"""
# TODO(PRP-2L): De-UI — Streamlit dependency; UI shell only
import streamlit as st
import pandas as pd
import time
import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
import sys
import os
import numpy as np
from collections import Counter

# Add src to path for imports
# TODO(PRP-2L): De-UI — path hack to import legacy backend modules; replace with proper package imports in adapter
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from backend.nba_optimizer_functional import optimize_with_diagnostics, optimize_dk_strict
from backend.types import Constraints, OptimizerError, GroupRule
from backend.dk_strict_results import lineups_to_grid_df, validate_grid_df, grid_df_to_dk_csv
# TODO(PRP-2L): De-UI — AG Grid UI dependency; not needed for headless adapter
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
from backend.orb_export import write_orb_bundle
from io_facade.run_io import load_pool, load_bases_long, save_pool, save_bases_long, save_variants  # PRP-PIO
from frontend.components.compare_utils import (
    hash_constraints_from_artifact, projection_stats, topN_jaccard,
    exposure_table, stack_freqs, calculate_exposure_delta, calculate_stack_delta,
    read_export_run, try_join_ownership, format_run_label,
    generate_run_id, check_same_run, jaccard_pairwise, jaccard_pool,
    exposure_delta, stack_delta, normalize_grid_columns,
    load_export_ownership, try_join_ownership_with_data
)

# Enhanced AG Grid theme CSS - Reused from csv_ingest_app.py patterns
# TODO(PRP-2L): De-UI — UI CSS; move to UI layer
AGGRID_THEME_CSS = """
<style>
/* Custom AG Grid Theme - Aggressive override for streamlit theme */
div.ag-theme-streamlit,
.stAgGrid div.ag-theme-streamlit,
[data-testid="stAgGrid"] div.ag-theme-streamlit {
    --ag-background-color: #1f2836 !important;
    --ag-header-background-color: #1f2836 !important;
    --ag-odd-row-background-color: #111418 !important;
    --ag-foreground-color: #FFF !important;
    --ag-header-foreground-color: #FFF !important;
    --ag-border-color: transparent !important;
    --ag-row-border-color: transparent !important;
    --ag-font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Oxygen-Sans", Ubuntu, Cantarell, "Helvetica Neue", sans-serif !important;
    --ag-header-font-size: 14px !important;
    --ag-spacing: 5px !important;
    --ag-cell-horizontal-padding: 8px !important;
    --ag-row-hover-color: #2a3441 !important;
    --ag-selected-row-background-color: #3b4c63 !important;
    --ag-header-column-separator-color: transparent !important;
    --ag-checkbox-background-color: #1f2836 !important;
    --ag-checkbox-checked-color: #4F8BF9 !important;
    background-color: #1f2836 !important;
    color: #FFF !important;
}

/* Force all elements */
div.ag-theme-streamlit * {
    border-color: transparent !important;
}

div.ag-theme-streamlit .ag-root-wrapper {
    background-color: #1f2836 !important;
    color: #FFF !important;
}

div.ag-theme-streamlit .ag-header {
    background-color: #1f2836 !important;
    color: #FFF !important;
    border-bottom: 1px solid #3b4c63 !important;
}

div.ag-theme-streamlit .ag-header-cell {
    background-color: #1f2836 !important;
    color: #FFF !important;
    font-weight: 600 !important;
    border-right: none !important;
}

div.ag-theme-streamlit .ag-cell {
    background-color: #1f2836 !important;
    color: #FFF !important;
    border: none !important;
}

/* Numeric column alignment */
div.ag-theme-streamlit .ag-cell.ag-cell-numeric {
    text-align: right !important;
    font-variant-numeric: tabular-nums;
}

div.ag-theme-streamlit .ag-row {
    background-color: #1f2836 !important;
    color: #FFF !important;
    border: none !important;
}

div.ag-theme-streamlit .ag-row.ag-row-odd {
    background-color: #111418 !important;
}

div.ag-theme-streamlit .ag-row:hover {
    background-color: #2a3441 !important;
}

div.ag-theme-streamlit .ag-row.ag-row-selected {
    background-color: #3b4c63 !important;
}

div.ag-theme-streamlit .ag-checkbox-input-wrapper {
    background-color: #1f2836 !important;
    border-color: #4F8BF9 !important;
}

div.ag-theme-streamlit .ag-checkbox-input-wrapper.ag-checked {
    background-color: #4F8BF9 !important;
    border-color: #4F8BF9 !important;
}

/* Additional force for stubborn elements */
div.ag-theme-streamlit .ag-body-viewport,
div.ag-theme-streamlit .ag-body-horizontal-scroll-viewport,
div.ag-theme-streamlit .ag-center-cols-clipper {
    background-color: #1f2836 !important;
}
</style>
"""

def main():  # TODO(PRP-2L): De-UI — UI entrypoint; not part of headless API
    st.set_page_config(page_title="NBA Lineup Optimizer", layout="wide")
    st.markdown(AGGRID_THEME_CSS, unsafe_allow_html=True)
    
    st.title("🏀 NBA Lineup Optimizer")
    st.markdown("Generate optimized NBA DFS lineups with advanced constraints")
    # PRP-PIO: Parquet support preflight
    try:
        import pyarrow  # noqa: F401
    except Exception:
        st.warning("Parquet support (pyarrow) not available. Some features may be disabled.")
    
    # Load normalized projections if available
    normalized_path = Path("data/normalized/projections.parquet")
    if not normalized_path.exists():
        st.error("❌ No projections data found. Please run the CSV ingest tool first.")
        st.markdown("Go to: `streamlit run src/csv_ingest_app.py`")
        return
    
    try:
        projections_df = pd.read_parquet(normalized_path)
        st.success(f"✅ Loaded {len(projections_df)} players from normalized projections")
    except Exception as e:
        st.error(f"❌ Failed to load projections: {str(e)}")
        return
    
    # Layout: Left panel for inputs, right panel for results
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.header("⚙️ Optimization Settings")
        
        # Core inputs
        site = st.selectbox("Site", ["dk", "fd"], help="DraftKings or FanDuel")
        max_unique = 7 if site == "dk" else 8

        engine = st.selectbox(
            "Engine",
            ["cp_sat", "cbc"],
            index=0,
            help="CP-SAT (default) is OR-Tools CP-SAT. CBC is PuLP/CBC (legacy).",
            format_func=lambda x: "CP-SAT (default)" if x == "cp_sat" else "CBC (legacy)"
        )
        
        # CP-SAT Presets (PRP-15)
        cp_sat_params = {}
        if engine == "cp_sat":
            preset = st.selectbox(
                "CP-SAT Preset",
                ["Speed", "Repro", "Custom"],
                index=0,
                help="Speed: Fast solve (0.7s, 0.1% gap). Repro: Full solve (8s, 0% gap, deterministic). Custom: Configure manually."
            )
            
            # Define preset parameter mappings
            if preset == "Speed":
                cp_sat_params = {
                    "max_time_seconds": 0.7,
                    "relative_gap_limit": 0.001,  # 0.1%
                    "num_search_workers": 0,  # All cores
                    "log_search_progress": False
                }
                st.info("🚀 **Speed preset**: 0.7s timeout, 0.1% gap, multi-threaded")
                
            elif preset == "Repro":
                cp_sat_params = {
                    "max_time_seconds": 8.0,
                    "relative_gap_limit": 0.0,  # 0% gap (full optimality)
                    "num_search_workers": 1,  # Single-threaded for determinism
                    "log_search_progress": False
                }
                st.info("🔍 **Repro preset**: 8s timeout, 0% gap, single-threaded for full reproducibility")
                
            elif preset == "Custom":
                st.markdown("🛠️ **Custom CP-SAT Parameters**")
                col_a, col_b = st.columns(2)
                with col_a:
                    max_time = st.number_input("Max Time (seconds)", 0.1, 60.0, 0.7, 0.1,
                                             help="Maximum time per lineup solve")
                    gap_limit = st.number_input("Relative Gap Limit", 0.0, 0.1, 0.001, 0.001,
                                              help="0.001 = 0.1% gap, 0.0 = full optimality")
                with col_b:
                    num_workers = st.number_input("Search Workers", 0, 16, 0,
                                                help="0 = use all cores, 1 = single-threaded")
                    log_progress = st.checkbox("Log Search Progress", value=False,
                                             help="Show detailed solver progress")
                
                cp_sat_params = {
                    "max_time_seconds": max_time,
                    "relative_gap_limit": gap_limit,
                    "num_search_workers": num_workers,
                    "log_search_progress": log_progress
                }
        else:
            # CBC engine - no additional params needed
            preset = None
        
        N_lineups = st.number_input("Number of Lineups", 1, 1000, 20, 
                                   help="How many lineups to generate")
        unique_players = st.number_input("Unique Players", 1, max_unique, 2,
                                       help="Minimum unique players between lineups")
        seed = st.number_input("Seed (for determinism)", 0, 999999, 12345,
                              help="Same seed = same results")
        
        # DK-Strict mode toggle (PRP-07) - default ON per PRP-15
        dk_strict_mode = st.checkbox(
            "🔒 DK-Strict Mode (PRP-07)", 
            value=True,
            help="Enforce hard-fail if any player lacks real DK ID. Uses dk_data/ files only."
        )
        if dk_strict_mode:
            st.info("🔒 **DK-Strict Mode**: Hard-fail if any player lacks real DK ID. No synthetic IDs allowed.")
        
        # Advanced constraints in expander
        with st.expander("Advanced Constraints"):
            randomness_pct = st.slider("Randomness %", 0, 100, 0,
                                     help="Add variance to projections")
            proj_min = st.number_input("Minimum Projection", 0.0, 100.0, 15.0,
                                     help="Filter out low projections")
            
            # Salary constraints
            st.subheader("Salary Limits")
            col_min, col_max = st.columns(2)
            with col_min:
                min_salary = st.number_input("Min Salary", 0, 60000, 
                                           49000 if site == "dk" else 59000)
            with col_max:
                max_salary = st.number_input("Max Salary", 0, 60000,
                                           50000 if site == "dk" else 60000)
            
            # Team constraints
            st.subheader("Team Limits")
            global_team_limit = st.number_input("Global Team Limit", 0, 8, 0,
                                              help="Max players per team (0 = no limit)")
            
            # Player constraints (simplified)
            st.subheader("Player Rules")
            st.markdown("*Advanced player constraints coming soon*")
            
        # PRP-16: Ownership Penalty Controls
        st.subheader("🎯 Ownership Penalty")
        ownership_enabled = st.checkbox("Enable ownership penalty", False, help="Penalize high-owned players to create more contrarian lineups")
        
        ownership_settings = {}
        if ownership_enabled:
            penalty_mode = st.selectbox(
                "Penalty Mode",
                ["by_percent", "by_points"],
                format_func=lambda x: "By % off optimal (recommended)" if x == "by_percent" else "By points (legacy)",
                help="By % off optimal targets a specific % below optimal lineup. By points uses fixed penalty weight."
            )
            
            if penalty_mode == "by_percent":
                col_target, col_tol = st.columns(2)
                with col_target:
                    target_offoptimal_pct = st.slider(
                        "Target off-optimal %", 
                        0.0, 20.0, 8.0, 0.5,
                        help="Target % below optimal (e.g., 8% = lineups ~8% worse than pure optimal)"
                    )
                with col_tol:
                    tol_offoptimal_pct = st.slider(
                        "Tolerance %", 
                        0.1, 1.0, 0.3, 0.1,
                        help="Acceptable tolerance around target (±0.3% default)"
                    )
            else:  # by_points
                weight_lambda = st.slider(
                    "Penalty weight λ", 
                    0.0, 20.0, 1.0, 0.1,
                    help="Higher values = more penalty for owned players"
                )
            
            # Advanced penalty curve settings
            with st.expander("🔧 Advanced Curve Settings"):
                curve_type = st.selectbox(
                    "Curve type",
                    ["sigmoid", "linear", "power", "neglog"],
                    help="Shape of the penalty curve. Sigmoid (default) has smooth transitions."
                )
                
                if curve_type == "power":
                    power_k = st.slider("Power k", 1.2, 1.8, 1.5, 0.1, help="Exponent for power curve")
                else:
                    power_k = 1.5
                    
                if curve_type == "sigmoid":
                    col_pivot, col_alpha = st.columns(2)
                    with col_pivot:
                        pivot_p0 = st.slider("Pivot point %", 5.0, 35.0, 20.0, 1.0, help="Ownership % where penalty increases rapidly") / 100.0
                    with col_alpha:
                        curve_alpha = st.slider("Curve steepness", 1.0, 4.0, 2.0, 0.1, help="Higher = steeper curve")
                else:
                    pivot_p0 = 0.20
                    curve_alpha = 2.0
                
                col_min, col_max = st.columns(2)
                with col_min:
                    clamp_min = st.slider("Min ownership %", 1.0, 10.0, 1.0, 0.5, help="Minimum ownership for calculations") / 100.0
                with col_max:
                    clamp_max = st.slider("Max ownership %", 50.0, 100.0, 80.0, 5.0, help="Maximum ownership for calculations") / 100.0
                
                shrink_gamma = st.slider("Ownership shrink γ", 0.7, 1.0, 1.0, 0.05, help="1.0 = use raw ownership, <1.0 = shrink toward pivot")
            
            # Build ownership settings dict
            ownership_settings = {
                "enabled": True,
                "mode": penalty_mode,
                "target_offoptimal_pct": target_offoptimal_pct / 100.0 if penalty_mode == "by_percent" else 0.08,
                "tol_offoptimal_pct": tol_offoptimal_pct / 100.0 if penalty_mode == "by_percent" else 0.003,
                "weight_lambda": weight_lambda if penalty_mode == "by_points" else 1.0,
                "curve_type": curve_type,
                "power_k": power_k,
                "pivot_p0": pivot_p0,
                "curve_alpha": curve_alpha,
                "clamp_min": clamp_min,
                "clamp_max": clamp_max,
                "shrink_gamma": shrink_gamma,
            }
        else:
            ownership_settings = {"enabled": False}
        
        # Run button
        run_disabled = st.session_state.get("optimizer_running", False)
        if st.button("🔄 Run Optimizer", disabled=run_disabled, type="primary"):
            run_optimizer(projections_df, {
                'N_lineups': N_lineups,
                'unique_players': unique_players,
                'proj_min': proj_min,
                'randomness_pct': randomness_pct,
                'min_salary': min_salary if min_salary > 0 else None,
                'max_salary': max_salary if max_salary > 0 else None,
                'global_team_limit': global_team_limit if global_team_limit > 0 else None,
                'team_limits': {},
                'at_least': [],
                'at_most': [],
                'slate_id': f"{site}_{datetime.now().strftime('%Y_%m_%d')}",
                'dk_strict_mode': dk_strict_mode,
                'cp_sat_params': cp_sat_params,
                'preset': preset,
                'ownership_penalty': ownership_settings  # PRP-16: Pass ownership penalty settings
            }, seed, site, engine)
    
    with col2:
        st.header("📊 Generated Lineups")
        
        # Display results if available
        if "lineups" in st.session_state and st.session_state.lineups:
            # Display solver diagnostics
            if "id_diagnostics" in st.session_state:
                display_solver_diagnostics(st.session_state.id_diagnostics, engine)
                # Display DK ID status panel if available
                display_dk_id_status(st.session_state.id_diagnostics, site)
                # Ownership penalty diagnostics (if provided by optimizer)
                display_ownership_penalty_diagnostics(st.session_state.id_diagnostics)
                # Debug keys expander (optional)
                import os as _os
                if _os.environ.get("DFS_DEBUG"):
                    with st.expander("Debug: Diagnostics Keys", expanded=False):
                        try:
                            st.write(sorted(list(st.session_state.id_diagnostics.keys())))
                        except Exception:
                            st.json(st.session_state.id_diagnostics)
            
            display_results(st.session_state.lineups, st.session_state.get("optimization_runtime", 0), site)
            
            # PRP-18: Display run comparison panel after results
            display_compare_panel()
        else:
            st.info("👈 Configure settings and click 'Run Optimizer' to generate lineups")


def run_optimizer(projections_df: pd.DataFrame, constraints_dict: dict, 
                 seed: int, site: str, engine: str = "cbc"):
    """Run the optimizer and store results in session state

    TODO(PRP-2L): De-UI — Replace session-state usage and spinners with headless wrapper.
    """
    st.session_state.optimizer_running = True
    # PRP-Ownership-Normalization-UI-Cache-Hardening: Clear caches on each solve
    try:
        import streamlit as _st
        _st.cache_data.clear()  # TODO(PRP-2L): De-UI — replace streamlit cache hooks
        _st.cache_resource.clear()  # TODO(PRP-2L): De-UI — replace streamlit cache hooks
    except Exception:
        pass
    
    try:
        with st.spinner("🔄 Generating lineups..."):
            start_time = time.time()
            
            # Create and validate constraints
            dk_strict_mode = constraints_dict.pop('dk_strict_mode', False)
            cp_sat_params = constraints_dict.pop('cp_sat_params', {})
            preset = constraints_dict.pop('preset', None)
            constraints = Constraints.from_dict(constraints_dict)
            constraints.cp_sat_params = cp_sat_params  # Add CP-SAT parameters (PRP-15)
            stddev_available = 'stddev' in projections_df.columns
            constraints = constraints.validate(site, stddev_available)
            # Ownership penalty guardrail: warn if ownership data is missing
            if getattr(constraints, 'ownership_penalty', None) and getattr(constraints.ownership_penalty, 'enabled', False) and 'own_proj' not in projections_df.columns:
                st.warning(
                    "Ownership penalty is enabled, but the projections data has no `own_proj` column. "
                    "The optimizer will proceed without applying the ownership penalty."
                )
            
            # Choose optimizer based on mode
            if dk_strict_mode and site == "dk":
                # DK-Strict mode: use dk_data/ files directly
                projections_path = "dk_data/projections.csv"
                player_ids_path = "dk_data/player_ids.csv"
                
                # Check if dk_data files exist
                if not Path(projections_path).exists():
                    st.error(f"❌ DK-Strict mode requires {projections_path} file")
                    return
                
                # Run DK-strict optimization
                lineups, id_diagnostics = optimize_dk_strict(
                    projections_path=projections_path,
                    constraints=constraints,
                    seed=seed,
                    player_ids_path=player_ids_path if Path(player_ids_path).exists() else None,
                    engine=engine
                )
                
                # PRP-18.2: Show guardrail banner for ownership normalization
                if (constraints.ownership_penalty and constraints.ownership_penalty.enabled and 
                    id_diagnostics.get("normalization", {}).get("ownership")):
                    norm_info = id_diagnostics["normalization"]["ownership"]
                    src_col = norm_info["source_col"]
                    scale = int(norm_info["scaled_by"])
                    if scale > 1:
                        st.info(f"🧭 Detected '{src_col}'; auto-mapped to 'own_proj' (÷{scale}).")
                    else:
                        st.info(f"🧭 Using '{src_col}' as 'own_proj' (no scaling needed).")
                
            else:
                # Standard mode: use loaded projections
                # Check for persisted player IDs
                player_ids_path = Path("dk_data/player_ids.csv")
                player_ids_df = None
                if player_ids_path.exists():
                    try:
                        player_ids_df = pd.read_csv(player_ids_path)
                    except Exception as e:
                        st.warning(f"Could not load player IDs: {e}")

                # Run optimization with diagnostics
                lineups, id_diagnostics = optimize_with_diagnostics(
                    projections_df,
                    constraints,
                    seed,
                    site,
                    player_ids_df,
                    engine=engine,
                )
                # PRP-22: Show ownership normalization banner if present
                try:
                    norm = id_diagnostics.get("normalization", {}).get("ownership")
                    if norm and float(norm.get("scaled_by", 1.0)) > 1.0:
                        src_col = norm.get("source_col", "ownership column")
                        scale = int(norm.get("scaled_by", 100))
                        st.info(f"🧭 Detected '{src_col}'; auto-mapped to 'own_proj' (÷{scale}).")
                except Exception:
                    pass
            
            runtime = time.time() - start_time
            
            # Store results in session state
            st.session_state.lineups = lineups
            st.session_state.id_diagnostics = id_diagnostics
            st.session_state.optimization_runtime = runtime
            st.session_state.optimization_constraints = constraints_dict
            st.session_state.optimization_seed = seed
            st.session_state.optimization_preset = preset  # PRP-15: Store preset for telemetry
            st.session_state.optimization_cp_sat_params = cp_sat_params  # PRP-15: Store params for telemetry
            
            # Performance warning and success message
            if runtime > 10.0:
                st.warning(f"⚠️ Runtime: {runtime:.1f}s exceeded 10s target")
            else:
                mode_label = "DK-Strict" if dk_strict_mode and site == "dk" else "Standard"
                st.success(f"✅ Generated {len(lineups)} lineups in {runtime:.1f}s ({mode_label} mode)")
                if dk_strict_mode and site == "dk":
                    st.info("🔒 **DK-Strict Mode**: All players have validated real DK IDs")
                
    except RuntimeError as e:
        # DK-strict mode failures
        error_message = str(e)
        st.error(f"❌ DK-Strict Mode Failed")
        st.markdown(f"**Error**: {error_message}")
        
        # Show remediation steps
        if "missing/invalid dk_id" in error_message.lower():
            with st.expander("🔧 How to Fix DK ID Issues", expanded=True):
                st.markdown("### Required Steps:")
                st.markdown("1. **Create or update** `dk_data/player_ids.csv` with real DK player data")
                st.markdown("2. **Export player data** from DraftKings contest page (CSV format)")
                st.markdown("3. **Ensure exact name/team matching** between projections and DK data")
                st.markdown("4. **Check team abbreviations**: PHX vs PHO, GSW vs GS, etc.")
                st.markdown("### Expected Format:")
                st.code("ID,Name,TeamAbbrev,Position\n12345,Stephen Curry,GSW,PG\n67890,LeBron James,LAL,SF/PF")
                
    except OptimizerError as e:
        if e.severity == "error":
            st.error(f"❌ {e.user_message}")
        else:
            st.warning(f"⚠️ {e.user_message}")
        
        # Show technical details in expander
        with st.expander("Technical Details"):
            st.json(e.details)
            
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        st.exception(e)
        
    finally:
        st.session_state.optimizer_running = False


def build_optimizer_grid_options(df: pd.DataFrame, view_mode: str = "compact") -> dict:
    """Build AG Grid options with view-specific column configuration

    TODO(PRP-2L): De-UI — AG Grid configuration; move to UI layer.
    """
    gb = GridOptionsBuilder.from_dataframe(df)
    
    # Base numeric formatters - using proper JsCode instead of strings
    numeric_formatter = JsCode("""
    function(params) {
        if (params.value == null || params.value === '') return '';
        return Number(params.value).toFixed(1);
    }
    """)
    
    integer_formatter = JsCode("""
    function(params) {
        if (params.value == null || params.value === '') return '';
        return Number(params.value).toLocaleString();
    }
    """)
    
    precision_formatter = JsCode("""
    function(params) {
        if (params.value == null || params.value === '') return '';
        return Number(params.value).toFixed(4);
    }
    """)
    
    # Common columns (both views)
    # Pin lineup identifier if present
    if "lineup_id" in df.columns:
        gb.configure_column("lineup_id", pinned="left", width=70, headerName="Lineup")
    gb.configure_column("total_proj", 
        type=["numericColumn", "rightAligned"],
        valueFormatter=numeric_formatter,
        width=90, headerName="Proj")
    gb.configure_column("total_salary", 
        type=["numericColumn", "rightAligned"], 
        valueFormatter=integer_formatter,
        width=100, headerName="Salary")
    gb.configure_column("salary_left",
        type=["numericColumn", "rightAligned"],
        valueFormatter=integer_formatter, 
        width=90, headerName="Left")
    
    # View-specific columns
    if view_mode == "compact":
        # Compact: single players column from prepared DF
        players_col = "players_compact" if "players_compact" in df.columns else "players_csv"
        gb.configure_column(players_col, 
            width=600, headerName="Players",
            wrapText=True, autoHeight=True,
            tooltipField=players_col)
        # Hide DK position columns
        dk_positions = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
        for pos in dk_positions:
            if pos in df.columns:
                gb.configure_column(pos, hide=True)
    else:  # DK-style view
        # Hide compact column
        if "players_csv" in df.columns:
            gb.configure_column("players_csv", hide=True)
        # Show position columns
        dk_positions = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
        for pos in dk_positions:
            if pos in df.columns:
                gb.configure_column(pos, width=120, headerName=pos,
                                   wrapText=True, tooltipField=pos)
    
    # Optional metric columns (show only if present and have non-null values)
    optional_columns = {
        "own_sum": ("Own%", 80, numeric_formatter),
        "minutes_sum": ("Min", 70, numeric_formatter), 
        "stddev_sum": ("StdDev", 80, numeric_formatter),
        "own_prod": ("Own Prod", 90, precision_formatter)
    }
    
    for col, (header, width, formatter) in optional_columns.items():
        if col in df.columns and not df[col].isna().all():
            gb.configure_column(col,
                type=["numericColumn", "rightAligned"],
                valueFormatter=formatter,
                width=width, headerName=header)
        elif col in df.columns:
            gb.configure_column(col, hide=True)
    
    # Optional stacks and notes if present
    if "stacks" in df.columns:
        gb.configure_column("stacks", width=120, headerName="Stacks")
    if "notes" in df.columns:
        gb.configure_column("notes", width=150, headerName="Notes", editable=True)
    
    # Hide internal columns
    hidden_columns = ["seed", "player_ids_csv", "players_json"]
    for col in hidden_columns:
        if col in df.columns:
            gb.configure_column(col, hide=True)
    
    # Grid configuration
    gb.configure_pagination(paginationPageSize=50)
    gb.configure_selection("multiple", use_checkbox=True, 
                          header_checkbox=True, header_checkbox_filtered_only=True)
    gb.configure_side_bar()
    gb.configure_grid_options(
        rowHeight=40 if view_mode == "compact" else 32,
        headerHeight=40,
        suppressRowClickSelection=True,
        animateRows=True,
        rowSelection="multiple"
    )
    
    return gb.build()


def display_results(lineups, runtime, site: str = "dk"):
    """Display optimization results with enhanced AG Grid"""
    if not lineups:
        st.warning("No lineups to display")
        return
    
    # View mode toggle
    col_toggle, col_export, col_stats = st.columns([1, 1, 2])
    
    with col_toggle:
        view_mode = st.selectbox(
            "View Mode",
            ["compact", "dk_style"],
            index=1,  # Default to DK Roster Style
            format_func=lambda x: "Compact CSV" if x == "compact" else "DK Roster Style",
            key="lineup_view_mode"
        )
    
    # Transform data using DK-strict approach
    try:
        # Convert lineups to typed DataFrame and include runtime/seed
        full_df = lineups_to_grid_df(
            lineups,
            sport="nba",
            site=site,
            runtime_ms=int(runtime * 1000),
            rand_seed=st.session_state.get("optimization_seed")
        )
        
        # Validate DataFrame and get errors
        valid_df, validation_errors = validate_grid_df(full_df, sport="nba", site=site)
        
        # Store validation state in session
        st.session_state['validation_errors'] = validation_errors
        st.session_state['valid_df'] = valid_df
        st.session_state['export_enabled'] = len(validation_errors) == 0
        
        # PRP-18: Persist run history after successful optimization
        if len(validation_errors) == 0:  # Only add to history if validation passed
            persist_run_to_history(valid_df, site, runtime)
        
        # Use valid lineups for display
        results_df = prepare_display_df(valid_df, view_mode)
        
    except Exception as e:
        st.error(f"Error processing lineups: {str(e)}")
        return
    
    # Display validation errors if any
    if validation_errors:
        with st.expander(f"⚠️ Validation Issues ({len(validation_errors)} lineups excluded)", expanded=False):
            for error in validation_errors[:5]:  # Show first 5 errors
                st.error(f"Lineup {error['lineup_id']}: {', '.join(error['errors'])}")
            if len(validation_errors) > 5:
                st.info(f"... and {len(validation_errors) - 5} more errors")

    # Run Summary badge (Contract + Ownership Normalization)
    try:
        _diag_all = st.session_state.get("id_diagnostics", {})
        _contract = _diag_all.get("solver_contract", {}) if isinstance(_diag_all, dict) else {}
        _norm = _diag_all.get("normalization", {}).get("ownership", {}) if isinstance(_diag_all, dict) else {}
        run_id = _contract.get("run_id") or _norm.get("run_id") or "—"
        chash = (_contract.get("contract_hash") or "")[:12]
        scaled_by_100 = bool(_norm.get("scaled_by_100", False))
        max_pre = _norm.get("own_proj_max_pre_solve", _norm.get("max_after", 0.0))
        clipped = _norm.get("num_clipped", 0)
        st.caption(f"Run {run_id} • contract {chash} • scaled_by_100={scaled_by_100} • own_max_pre={max_pre:.3f} • clipped={clipped}")
        # If available, surface a quick path to the exact solver inputs for this run
        _solver_inputs_path = _contract.get("solver_inputs_path")
        if _solver_inputs_path:
            st.caption(f"Open inputs: `{_solver_inputs_path}`")
    except Exception:
        pass

    # Build grid options
    grid_options = build_optimizer_grid_options(results_df, view_mode)
    
    # Display grid with enhanced theme
    # Cache-busted, per-run grid key
    _grid_key = None
    try:
        _diag_all = st.session_state.get('id_diagnostics', {})
        _rid = None
        if isinstance(_diag_all, dict):
            _rid = _diag_all.get('solver_contract', {}).get('run_id') or _diag_all.get('normalization', {}).get('ownership', {}).get('run_id')
        _grid_key = f"grid_{_rid or uuid.uuid4().hex}"
    except Exception:
        _grid_key = f"grid_{uuid.uuid4().hex}"

    grid_response = AgGrid(
        results_df,
        gridOptions=grid_options,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=False,
        theme="streamlit",
        height=600,
        width="100%",
        reload_data=False,
        allow_unsafe_jscode=True,  # Required for JsCode formatters
        enable_enterprise_modules=False,
        key=_grid_key,
    )
    
    # Export functionality (enhanced for PRP-15)
    with col_export:
        export_enabled = st.session_state.get('export_enabled', False)
        
        # Main telemetry export button (PRP-15)
        telemetry_export_button = st.button("📦 Export with Telemetry", disabled=not export_enabled, type="primary",
                                           help="Export to structured directory with CSV files and telemetry JSON (PRP-15)")

        # ORB export controls (PRP-ORB)
        run_name = st.text_input("Run Name", value="baseline", help="Used to slug folder name in runs/ directory")
        orb_export_button = st.button(
            "📁 Export ORB Bundle",
            disabled=not export_enabled,
            help="Create runs/<timestamp>__<slug> with player_pool.parquet, bases_long.parquet, run_meta.json",
        )
        
        # Legacy download buttons
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            export_button = st.button("📥 DK CSV", disabled=not export_enabled, 
                                    help="Download DK-compatible CSV")
        with btn_col2:
            export_human_button = st.button("📥 Human CSV", disabled=not export_enabled,
                                           help="Download human-readable CSV")

        # Handle export actions
        if telemetry_export_button and export_enabled:
            # Need projections for hash generation
            normalized_path = Path("data/normalized/projections.parquet")
            try:
                projections_df = pd.read_parquet(normalized_path)
                export_with_telemetry(st.session_state.get('valid_df'), projections_df)
            except Exception as e:
                st.error(f"Could not load projections for telemetry export: {e}")
                
        if export_button and export_enabled:
            export_dk_csv(st.session_state.get('valid_df'))
        if export_human_button and export_enabled:
            export_human_csv(st.session_state.get('valid_df'))

        # Handle ORB export
        if orb_export_button and export_enabled:
            try:
                # Try to load projections for player_pool; fall back gracefully
                projections_df = None
                try:
                    normalized_path = Path("data/normalized/projections.parquet")
                    if normalized_path.exists():
                        projections_df = pd.read_parquet(normalized_path)
                except Exception:
                    projections_df = None

                out_dir = write_orb_bundle(
                    run_name=run_name or "run",
                    lineups=lineups,
                    projections_df=projections_df,
                    diagnostics=st.session_state.get("id_diagnostics", {}),
                    constraints=Constraints.from_dict(st.session_state.get("optimization_constraints", {})) if st.session_state.get("optimization_constraints") else None,
                )
                st.success("✅ ORB bundle created")
                st.info(f"📁 {out_dir}")
                st.session_state["last_run_dir"] = str(out_dir)
                # Preflight: surface potential bad exports early
                try:
                    pool_df = load_pool(out_dir)
                    zero_proj_frac = float((pool_df['proj'] == 0).mean()) if 'proj' in pool_df.columns else 1.0
                    own_100_frac = float((pool_df.get('own', 0).fillna(0) >= 100.0).mean()) if 'own' in pool_df.columns else 0.0
                    if zero_proj_frac > 0.20:
                        st.warning(f"⚠️ {zero_proj_frac*100:.1f}% of player proj are zero; check column mapping.")
                    if own_100_frac > 0.10:
                        st.warning(f"⚠️ {own_100_frac*100:.1f}% of ownership are 100%; verify ownership normalization.")
                    # Show top-10 players by proj for a quick eyeball
                    if 'proj' in pool_df.columns:
                        preview_cols = [c for c in ['player_id','name','team','pos','salary','proj','own'] if c in pool_df.columns]
                        st.dataframe(pool_df.sort_values('proj', ascending=False).head(10)[preview_cols], use_container_width=True, height=280)
                except Exception:
                    pass
            except Exception as e:
                st.error(f"❌ ORB export failed: {e}")
    
    with col_stats:
        st.markdown(f"*Runtime: {runtime:.1f}s | Generated: {len(lineups)} lineups*")
    
    # Save lineup set option
    if st.button("💾 Save Lineup Set"):
        save_lineup_set(lineups, runtime)

    # PRP-SVD-IO: Run management and explicit CSV export buttons for latest run
    last_run_dir = st.session_state.get("last_run_dir")
    if last_run_dir and Path(last_run_dir).exists():
        st.markdown("---")
        st.subheader("Run Management")
        st.caption("Parquet is authoritative. Use buttons below to export CSVs on demand.")
        # Legacy upgrade helper
        pp_parq = Path(last_run_dir) / "player_pool.parquet"
        pp_csv = Path(last_run_dir) / "player_pool.csv"
        bl_parq = Path(last_run_dir) / "bases_long.parquet"
        bl_csv = Path(last_run_dir) / "bases_long.csv"
        if (not pp_parq.exists() and pp_csv.exists()) or (not bl_parq.exists() and bl_csv.exists()):
            if st.button("Upgrade legacy CSV run → Parquet"):
                try:
                    if pp_csv.exists() and not pp_parq.exists():
                        df = pd.read_csv(pp_csv)
                        save_pool(last_run_dir, df, export_csv=False)
                    if bl_csv.exists() and not bl_parq.exists():
                        df = pd.read_csv(bl_csv)
                        save_bases_long(last_run_dir, df, export_csv=False)
                    st.success("Run upgraded to Parquet.")
                except Exception as e:
                    st.error(f"Upgrade failed: {e}")
        exp_col1, exp_col2, exp_col3 = st.columns(3)
        with exp_col1:
            if st.button("Export player_pool.csv"):
                try:
                    df = load_pool(last_run_dir)
                    save_pool(last_run_dir, df, export_csv=True)
                    st.success("Exported player_pool.csv")
                except Exception as e:
                    st.error(f"Export failed: {e}")
        with exp_col2:
            if st.button("Export bases_long.csv"):
                try:
                    df = load_bases_long(last_run_dir)
                    save_bases_long(last_run_dir, df, export_csv=True)
                    st.success("Exported bases_long.csv")
                except Exception as e:
                    st.error(f"Export failed: {e}")
        with exp_col3:
            if st.button("Export variant_catalog.csv"):
                try:
                    # Only exports if variants exist
                    df = None
                    try:
                        from io_facade.run_io import load_variants
                        df = load_variants(last_run_dir)
                    except Exception:
                        df = None
                    if df is None:
                        st.warning("No variant_catalog found to export.")
                    else:
                        save_variants(last_run_dir, df, export_csv=True)
                        st.success("Exported variant_catalog.csv")
                except Exception as e:
                    st.error(f"Export failed: {e}")

        # Retention/Archiving
        st.markdown("")
        st.subheader("Run Retention")
        col_keep, col_btn = st.columns([1, 1])
        with col_keep:
            keep_n = st.number_input("Keep last N runs", min_value=1, max_value=100, value=5)
        with col_btn:
            if st.button("Archive Old Runs"):
                try:
                    from tools.cleanup_runs import cleanup_runs as _cleanup_runs
                    zip_path = _cleanup_runs("src/runs", keep=int(keep_n), archive=True)
                    if zip_path:
                        st.success(f"Archived to {zip_path}")
                    else:
                        st.info("No runs archived.")
                except Exception as e:
                    st.error(f"Retention failed: {e}")


def export_optimizer_results(grid_response, view_mode: str, runtime: float, site: str):
    """Export exactly what's visible in grid

    TODO(PRP-2L): De-UI — Streamlit download button and CSV export belong in UI layer.
    """
    try:
        # Get filtered and sorted data from grid
        export_df = grid_response["data"]
        
        if export_df is None or len(export_df) == 0:
            st.error("No data to export")
            return
        
        # Remove internal/hidden columns for export but keep user-editable ones
        hidden_columns = ["seed", "player_ids_csv", "players_json"]
        
        # Also remove position columns if in compact view, or players_csv if in DK view
        if view_mode == "compact":
            dk_positions = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
            hidden_columns.extend([pos for pos in dk_positions if pos in export_df.columns])
        else:
            if "players_csv" in export_df.columns:
                hidden_columns.append("players_csv")
        
        # Create clean export DataFrame
        visible_df = export_df.drop(columns=[col for col in hidden_columns if col in export_df.columns])
        
        # Remove empty optional metric columns
        for col in ["own_sum", "minutes_sum", "stddev_sum", "own_prod"]:
            if col in visible_df.columns and visible_df[col].isna().all():
                visible_df = visible_df.drop(columns=[col])
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        view_suffix = "compact" if view_mode == "compact" else "dk"
        filename = f"lineups_{view_suffix}_{site}_{timestamp}.csv"
        
        # Convert to CSV
        csv_data = visible_df.to_csv(index=False)
        
        # Download button
        st.download_button(
            label=f"Download {filename}",
            data=csv_data,
            file_name=filename,
            mime="text/csv"
        )
        
        st.success(f"✅ Exported {len(visible_df)} lineups to {filename}")
        
    except Exception as e:
        st.error(f"❌ Export failed: {str(e)}")


def transform_lineups_for_grid(lineups, site: str = "dk", view_mode: str = "compact") -> pd.DataFrame:
    """Convert lineup objects to comprehensive grid format"""
    rows = []
    salary_cap = 50000 if site == "dk" else 60000
    
    for lineup in lineups:
        # Basic metrics
        base_data = {
            "id": lineup.lineup_id,
            "total_proj": round(lineup.total_proj, 2),
            "total_salary": lineup.total_salary,
            "salary_left": salary_cap - lineup.total_salary,
        }
        
        # Extract optional player metrics safely
        own_values = [p.own_proj for p in lineup.players if hasattr(p, 'own_proj') and p.own_proj is not None]
        minutes_values = [p.minutes for p in lineup.players if hasattr(p, 'minutes') and p.minutes is not None]
        stddev_values = [p.stddev for p in lineup.players if hasattr(p, 'stddev') and p.stddev is not None]
        
        # Computed metrics (only if data available)
        optional_data = {}
        if own_values and len(own_values) > 0:
            optional_data.update({
                "own_sum": round(sum(own_values), 1),
                "own_prod": round(np.prod(own_values), 4) if len(own_values) == len(lineup.players) else None
            })
        if minutes_values and len(minutes_values) > 0:
            optional_data["minutes_sum"] = round(sum(minutes_values), 0)
        if stddev_values and len(stddev_values) > 0:
            optional_data["stddev_sum"] = round(sum(stddev_values), 2)
            
        # View-specific player formatting
        if view_mode == "compact":
            base_data["players_csv"] = ", ".join(f"{p.name} ({p.pos} {p.team})" for p in lineup.players)
        else:  # DK-style view
            # Map players to roster positions with player IDs
            dk_positions = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
            position_map = {pos: "" for pos in dk_positions}
            
            # Sort players by DK position order to ensure consistent display
            sorted_players = sorted(lineup.players, key=lambda p: dk_positions.index(p.pos))
            
            for player in sorted_players:
                if player.pos in position_map:
                    # Extract clean ID for display (use last part of synthetic ID or first 8 chars)
                    clean_id = player.player_id.split('_')[-1] if '_' in player.player_id else player.player_id[:8]
                    # Handle cases where clean_id might be empty or cause truncation
                    if not clean_id or len(clean_id) == 0:
                        position_map[player.pos] = f"{player.name} ({player.team})"
                    else:
                        position_map[player.pos] = f"{player.name} ({clean_id} {player.team})"
            
            base_data.update(position_map)
        
        # Team stacking analysis
        team_counts = Counter(p.team for p in lineup.players)
        stacks = [f"{team}x{count}" for team, count in team_counts.items() if count >= 2]
        base_data["stacks"] = ", ".join(sorted(stacks)) if stacks else ""
        
        # Metadata and notes
        base_data.update({
            "notes": "",
            **optional_data
        })
        
        # Hidden fields for export/tracking
        base_data.update({
            "seed": st.session_state.get("optimization_seed", 0),
            "player_ids_csv": ",".join(p.player_id for p in lineup.players),
            "players_json": json.dumps([p.to_dict() for p in lineup.players])
        })
        
        rows.append(base_data)
    
    return pd.DataFrame(rows)


def save_lineup_set(lineups, runtime):
    """Save lineup set to disk with metadata"""
    try:
        # Create output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        seed = st.session_state.get("optimization_seed", 0)
        out_dir = Path(f"data/lineup_sets/{timestamp}_{seed}")
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Create lineup set metadata
        lineup_set = {
            "id": str(uuid.uuid4()),
            "created_at": datetime.utcnow().isoformat(),
            "seed": seed,
            "slate_id": st.session_state.get("optimization_constraints", {}).get("slate_id"),
            "constraints": st.session_state.get("optimization_constraints", {}),
            "engine": "nba_optimizer_functional.py",
            "version": "v1.0",
            "runtime_sec": runtime,
            "lineups": [lineup.to_dict() for lineup in lineups]
        }
        
        # Save JSON
        json_path = out_dir / "lineup_set.json"
        with open(json_path, 'w') as f:
            json.dump(lineup_set, f, indent=2)
        
        # Save CSV for DK upload
        csv_data = []
        for lineup in lineups:
            # Sort players by DK position order
            dk_order = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
            sorted_players = sorted(lineup.players, key=lambda p: dk_order.index(p.pos))
            
            csv_data.append([
                f"{p.name} ({p.player_id})" for p in sorted_players
            ] + [lineup.total_salary, round(lineup.total_proj, 2)])
        
        csv_path = out_dir / "lineups.csv"
        with open(csv_path, 'w', newline='') as f:
            import csv
            writer = csv.writer(f)
            writer.writerow(["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL", "Salary", "Fpts Proj"])
            writer.writerows(csv_data)
        
        st.success(f"✅ Lineup set saved to: {out_dir}")
        
    except Exception as e:
        st.error(f"❌ Failed to save lineup set: {str(e)}")


def prepare_display_df(valid_df: pd.DataFrame, view_mode: str) -> pd.DataFrame:
    """Prepare DataFrame for display in AG Grid based on view mode"""
    if valid_df.empty:
        return pd.DataFrame()
    
    if view_mode == "compact":
        # Show compact view with key + metrics columns
        display_cols = ["lineup_id", "total_proj", "total_salary"]
        if "salary_left" in valid_df.columns:
            display_cols.append("salary_left")
        for opt in ["own_sum", "minutes_sum", "stddev_sum", "own_prod"]:
            if opt in valid_df.columns:
                display_cols.append(opt)
        display_cols.append("players_compact")
        if "stacks" in valid_df.columns:
            display_cols.append("stacks")
        if "runtime_ms" in valid_df.columns:
            display_cols.append("runtime_ms")
        return valid_df[[c for c in display_cols if c in valid_df.columns]].copy()
    
    else:  # dk_style
        # Show DK-style with slot columns - derive from site config
        try:
            from backend.dk_strict_results import load_site_config
            site_config = load_site_config("nba", "dk", 1)
            slots = site_config.get("slots", ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"])
        except Exception:
            # Fallback if config loading fails
            slots = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
        display_cols = ["lineup_id", "total_proj", "total_salary"]
        if "salary_left" in valid_df.columns:
            display_cols.append("salary_left")
        
        # Add slot display columns (name with ID and team)
        for slot in slots:
            # Create display values directly without lambda function issues
            display_values = []
            for idx, row in valid_df.iterrows():
                name = str(row.get(f'{slot}_name', 'Unknown')).strip()
                dk_id = str(row.get(f'{slot}_dk_id', '')).strip()
                team = str(row.get(f'{slot}_team', '')).strip()
                
                # Handle missing or invalid data
                if not name or name.lower() in ['', 'nan', 'none', 'unknown']:
                    name = f'Missing_Player_{slot}'
                
                # Clean up DK ID - treat 'nan', 'none', empty string as missing
                if not dk_id or dk_id.lower() in ['', 'nan', 'none']:
                    # No DK ID available - just show name and team
                    display_values.append(f"{name} ({team})")
                else:
                    # DK ID available - show full format
                    display_values.append(f"{name} ({dk_id} {team})")
            
            valid_df[slot] = display_values
            display_cols.append(slot)
        
        # Append optional metrics at the end
        for opt in ["own_sum", "minutes_sum", "stddev_sum", "own_prod"]:
            if opt in valid_df.columns:
                display_cols.append(opt)
        if "stacks" in valid_df.columns:
            display_cols.append("stacks")
        return valid_df[[c for c in display_cols if c in valid_df.columns]].copy()


def export_dk_csv(valid_df: pd.DataFrame):
    """Export valid lineups as DK-compatible CSV"""
    if valid_df is None or valid_df.empty:
        st.error("No valid lineups to export")
        return
        
    try:
        # Generate DK CSV content
        csv_content = grid_df_to_dk_csv(valid_df, sport="nba", site="dk")
        
        # Create download
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dk_lineups_{timestamp}.csv"
        
        st.download_button(
            label="📥 Download DK CSV",
            data=csv_content,
            file_name=filename,
            mime="text/csv",
            help="Download DK-compatible lineup CSV"
        )
        
        st.success(f"✅ Generated {len(valid_df)} valid lineups for DK import")
        
    except Exception as e:
        st.error(f"❌ Export failed: {str(e)}")


def export_human_csv(valid_df: pd.DataFrame):
    """Export valid lineups as human-readable DK-style CSV with Name (ID TEAM)."""
    if valid_df is None or valid_df.empty:
        st.error("No valid lineups to export")
        return

    try:
        slots = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
        header = slots + ["Salary", "Fpts Proj"]
        rows = [",".join(header)]

        for _, row in valid_df.iterrows():
            slot_vals = [f"{row[f'{s}_name']} ({row[f'{s}_dk_id']} {row[f'{s}_team']})" for s in slots]
            slot_vals += [str(int(row["total_salary"])), f"{float(row['total_proj']):.2f}"]
            rows.append(",".join(slot_vals))

        csv_content = "\n".join(rows)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dk_lineups_human_{timestamp}.csv"
        st.download_button(
            label="📥 Download Human CSV",
            data=csv_content,
            file_name=filename,
            mime="text/csv",
            help="Download lineup CSV with Name (ID TEAM) per slot"
        )

        st.success(f"✅ Generated {len(valid_df)} human-readable lineups")
    except Exception as e:
        st.error(f"❌ Export failed: {str(e)}")


def display_dk_id_status(diagnostics: dict, site: str):
    """Display DK ID matching status with actionable guidance"""
    if site != "dk":
        return  # Only relevant for DraftKings
    
    success_rate = diagnostics.get("success_rate", 0.0)
    matched = diagnostics.get("matched_players", 0)
    total = diagnostics.get("total_players", 0)
    data_source = diagnostics.get("data_source")
    
    # Create status panel
    if success_rate >= 95.0:
        # Great success
        st.success(f"🎯 **DK ID Status: Excellent** ({success_rate:.1f}% - {matched}/{total} players)")
        with st.expander("📋 DK Compatibility Details", expanded=False):
            st.write(f"✅ **Match Rate**: {success_rate:.1f}% ({matched} of {total} players)")
            st.write(f"🗂️ **Data Source**: {data_source or 'No IDs available'}")
            if diagnostics.get("warnings"):
                for warning in diagnostics["warnings"]:
                    st.info(f"ℹ️ {warning}")
            st.write("**Export Status**: ✅ Ready for DraftKings import")
            
    elif success_rate >= 75.0:
        # Moderate success - warning
        st.warning(f"⚠️ **DK ID Status: Needs Attention** ({success_rate:.1f}% - {matched}/{total} players)")
        with st.expander("🔧 How to Improve DK Compatibility", expanded=True):
            st.write(f"📊 **Current Match Rate**: {success_rate:.1f}% ({matched} of {total} players)")
            st.write(f"🗂️ **Data Source**: {data_source or 'No IDs available'}")
            
            # Show specific issues
            failed_name = diagnostics.get("failed_name_matching", 0)
            failed_pos = diagnostics.get("failed_position_validation", 0)
            
            if failed_name > 0:
                st.write(f"❌ **Name/Team Mismatches**: {failed_name} players")
            if failed_pos > 0:
                st.write(f"❌ **Position Validation Issues**: {failed_pos} players")
            
            st.markdown("### 🛠️ **Action Steps**:")
            st.markdown("1. **Update player_ids.csv** - ensure names and teams match exactly")
            st.markdown("2. **Check team abbreviations** - DEN vs DEN, PHX vs PHO, etc.")
            st.markdown("3. **Export fresh IDs** from current DraftKings contest")
            
            if diagnostics.get("warnings"):
                st.markdown("### ⚠️ **Specific Issues**:")
                for warning in diagnostics["warnings"]:
                    st.info(f"• {warning}")
                    
            st.warning("**Export Status**: ⚠️ Some lineups may not import correctly to DraftKings")
            
    else:
        # Poor success - critical
        st.error(f"🚨 **DK ID Status: Critical Issues** ({success_rate:.1f}% - {matched}/{total} players)")
        with st.expander("⚠️ Critical DK Compatibility Problems", expanded=True):
            st.write(f"📊 **Current Match Rate**: {success_rate:.1f}% ({matched} of {total} players)")
            st.write(f"🗂️ **Data Source**: {data_source or 'No IDs available'}")
            
            # Show errors
            if diagnostics.get("errors"):
                st.markdown("### ❌ **Errors**:")
                for error in diagnostics["errors"]:
                    st.error(f"• {error}")
            
            # Show specific issues  
            failed_name = diagnostics.get("failed_name_matching", 0)
            failed_pos = diagnostics.get("failed_position_validation", 0)
            
            if failed_name > 0:
                st.write(f"❌ **Name/Team Mismatches**: {failed_name} players")
            if failed_pos > 0:
                st.write(f"❌ **Position Validation Issues**: {failed_pos} players")
            
            st.markdown("### 🆘 **Required Actions**:")
            st.markdown("1. **Create dk_data/player_ids.csv** with format: ID, Name, TeamAbbrev, Position")
            st.markdown("2. **Export player data** from DraftKings contest page")
            st.markdown("3. **Ensure exact name matching** between projections and DK data") 
            st.markdown("4. **Enable fail-fast mode** (require_dk_ids=True) to prevent invalid lineups")
            
            st.markdown("### 🔧 **Quick Fix Tools**:")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📄 Generate Template", key="dk_template_btn"):
                    st.code('''python -c "from src.utils.dk_id_generator import generate_template_from_projections; generate_template_from_projections('dk_data/projections.csv')"''')
                    st.info("Run this command to generate a template from your projections")
            
            with col2:
                if st.button("🔍 Validation Help", key="dk_help_btn"):
                    st.code('''python -c "from src.utils.dk_id_generator import print_dk_id_help; print_dk_id_help()"''')
                    st.info("Run this command for comprehensive setup guidance")
                    
            st.error("**Export Status**: ❌ Lineups will NOT import correctly to DraftKings")


# Ownership penalty diagnostics panel
def display_ownership_penalty_diagnostics(diagnostics: dict):
    """Render ownership penalty diagnostics if present in optimizer diagnostics."""
    pen = diagnostics.get("ownership_penalty") if isinstance(diagnostics, dict) else None
    # If penalty was enabled but diagnostics missing, show gating banner
    snapshot = diagnostics.get("constraints_snapshot", {}) if isinstance(diagnostics, dict) else {}
    if not pen and snapshot.get("ownership_enabled"):
        with st.expander("🎯 Ownership Penalty Diagnostics", expanded=True):
            st.error("Ownership penalty was enabled, but diagnostics were not emitted. Check ownership data and wiring.")
        return
    if not pen:
        return
    with st.expander("🎯 Ownership Penalty Diagnostics", expanded=True):
        if pen.get("error") == "missing_ownership":
            st.error("Ownership data is missing (`own_proj` not found). Penalty could not be applied.")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            mode = pen.get("mode", "—")
            st.metric("Mode", str(mode).replace("_", " ").title())
            lam = pen.get("lambda_used")
            if lam is not None:
                st.metric("λ Used", f"{lam:.3f}")
        with c2:
            tgt = pen.get("target_offoptimal_pct")
            ach = pen.get("achieved_offoptimal_pct")
            if tgt is not None:
                st.metric("Target % Off", f"{100*float(tgt):.2f}%")
            if ach is not None:
                st.metric("Achieved % Off", f"{100*float(ach):.2f}%")
        with c3:
            chalk = pen.get("avg_chalk_index")
            if chalk is not None:
                st.metric("Avg Chalk Index", f"{float(chalk):.2f}")
        with c4:
            ppts = pen.get("avg_penalty_points")
            if ppts is not None:
                st.metric("Avg Penalty Points", f"{float(ppts):.2f}")
        if pen.get("capped"):
            st.warning("Hit λ cap during search; used closest achievable value.")
        # Optional debug expander if backend provided and DFS_DEBUG
        import os as _os
        if _os.environ.get("DFS_DEBUG") and pen.get("debug"):
            with st.expander("Debug: Ownership Penalty Details", expanded=False):
                st.json(pen["debug"]) 


# PRP-15 T4: Hash helpers for reproducibility
def hash_projections(projections_df: pd.DataFrame) -> str:
    """Generate reproducible hash of projections data"""
    try:
        # Create sorted DataFrame for consistent hashing
        # Accept both 'pos' and 'position' columns; create a unified 'position'
        df = projections_df.copy()
        if 'position' not in df.columns and 'pos' in df.columns:
            df = df.rename(columns={'pos': 'position'})
        sorted_df = df.sort_values(['name', 'team', 'position']).reset_index(drop=True)
        
        # Include key columns that affect optimization
        hash_columns = ['name', 'team', 'position', 'salary', 'proj', 'own_proj', 'stddev', 'minutes']
        available_columns = [col for col in hash_columns if col in sorted_df.columns]
        
        # Convert to JSON string with sorted keys
        hash_data = sorted_df[available_columns].to_dict('records')
        json_str = json.dumps(hash_data, sort_keys=True, default=str)
        
        # Generate SHA-256 hash
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]  # First 16 chars for brevity
    except Exception as e:
        return f"hash_error_{str(e)[:8]}"


def hash_constraints(constraints_dict: dict) -> str:
    """Generate reproducible hash of constraints"""
    try:
        # Create clean constraints dict without session-specific data
        clean_constraints = constraints_dict.copy()
        
        # Remove items that don't affect optimization reproducibility
        exclusions = ['slate_id', 'dk_strict_mode', 'preset']
        for key in exclusions:
            clean_constraints.pop(key, None)
        
        # Sort keys for consistent hashing
        json_str = json.dumps(clean_constraints, sort_keys=True, default=str)
        
        # Generate SHA-256 hash
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]  # First 16 chars for brevity
    except Exception as e:
        return f"hash_error_{str(e)[:8]}"


def _try_build_projections_used(projections_df):
    """
    Try to build projections_used.csv data from various sources (PRP-18.3)
    
    Args:
        projections_df: Projections DataFrame from ingest pipeline (may be None)
        
    Returns:
        DataFrame with columns [dk_id, name, team, position, salary, proj, own_proj] if successful, else None
    """
    # Prefer provided projections_df (ingest path)
    if projections_df is not None:
        df = projections_df.copy()
    else:
        df = None
    
    # Fallback to DK-strict source if needed
    if (df is None) or ("own_proj" not in df.columns):
        dk_p = Path("dk_data/projections.csv")
        if dk_p.exists():
            df = pd.read_csv(dk_p)
            # Normalize ownership column variants to own_proj if needed
            if "own_proj" not in df.columns:
                # Accept headers (case-insensitive): Own%, Ownership, Ownership%, Projected Ownership, Own pct, own_pct
                ownership_candidates = ["Own%", "Ownership", "Ownership%", "Projected Ownership", "Own pct", "own_pct"]
                for candidate in ownership_candidates:
                    if candidate in df.columns:
                        ser = pd.to_numeric(df[candidate], errors="coerce").astype(float)
                        # If max value > 1.5, divide by 100; clip to [0,1]
                        if ser.max(skipna=True) and ser.max(skipna=True) > 1.5:
                            ser = ser / 100.0
                        df["own_proj"] = ser.clip(0.0, 1.0)
                        break
    
    if df is None or "own_proj" not in df.columns:
        return None
    
    # Helpful renames for compatibility: ID→dk_id, TeamAbbrev→team, Name→name, FPTS→proj
    rename_map = {"ID": "dk_id", "TeamAbbrev": "team", "Team": "team", "Name": "name", "FPTS": "proj", "Position": "position", "Salary": "salary"}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
    # Select only the columns we want to persist
    cols = [c for c in ["dk_id", "name", "team", "position", "salary", "proj", "own_proj"] if c in df.columns]
    return df[cols] if cols else None


# PRP-15 T3: Telemetry save functionality
def export_with_telemetry(valid_df: pd.DataFrame, projections_df: pd.DataFrame):
    """Export lineups with telemetry to structured directory (PRP-15 T3)"""
    if valid_df is None or valid_df.empty:
        st.error("No valid lineups to export")
        return
    
    try:
        # Create export directory structure
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = Path(f"exports/run_{timestamp}")
        export_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate DK CSV for import
        dk_csv_content = grid_df_to_dk_csv(valid_df, sport="nba", site="dk")
        dk_csv_path = export_dir / "dk_import.csv"
        with open(dk_csv_path, 'w') as f:
            f.write(dk_csv_content)
        
        # Generate human-readable grid CSV
        slots = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
        header = ["lineup_id"] + slots + ["Salary", "Fpts Proj"]
        grid_rows = [",".join(header)]
        
        for _, row in valid_df.iterrows():
            lineup_id = str(row["lineup_id"])
            slot_vals = [f"{row[f'{s}_name']} ({row[f'{s}_dk_id']} {row[f'{s}_team']})" for s in slots]
            slot_vals += [str(int(row["total_salary"])), f"{float(row['total_proj']):.2f}"]
            grid_rows.append(",".join([lineup_id] + slot_vals))
        
        grid_csv_path = export_dir / "lineups_grid.csv"
        with open(grid_csv_path, 'w') as f:
            f.write("\n".join(grid_rows))
        
        # PRP-18.3 + PRP Ownership Hardening: Prefer exact solver input for projections_used.csv
        projections_used_path = export_dir / "projections_used.csv"
        copied = False
        try:
            diag = st.session_state.get("id_diagnostics", {})
            # 1) Prefer in-memory contract CSV from diagnostics (single-location flow)
            csv_data = None
            manifest_obj = None
            if isinstance(diag, dict):
                csv_data = diag.get("solver_contract", {}).get("csv")
                manifest_obj = diag.get("solver_contract", {}).get("manifest")
            if csv_data:
                with open(projections_used_path, 'w') as f:
                    f.write(csv_data)
                copied = True
                if manifest_obj:
                    import json as _json
                    with open(export_dir / 'contract_manifest.json', 'w') as mf:
                        _json.dump(manifest_obj, mf, indent=2)
            else:
                # 2) Fallback to any saved path (if DFS_WRITE_CONTRACT_ARTIFACTS was enabled)
                path = None
                solver_dir = None
                if isinstance(diag, dict):
                    solver_path = diag.get("solver_contract", {}).get("solver_inputs_path")
                    if solver_path:
                        try:
                            from pathlib import Path as _P
                            p = _P(solver_path)
                            solver_dir = p.parent
                        except Exception:
                            solver_dir = None
                    path = solver_path or diag.get("normalization", {}).get("ownership", {}).get("projections_used_path")
                if path and Path(path).exists():
                    with open(path, 'r') as src, open(projections_used_path, 'w') as dst:
                        dst.write(src.read())
                    copied = True
                    try:
                        if solver_dir and (solver_dir / 'manifest.json').exists():
                            with open(solver_dir / 'manifest.json', 'r') as srcm, open(export_dir / 'contract_manifest.json', 'w') as dstm:
                                dstm.write(srcm.read())
                    except Exception:
                        pass
        except Exception:
            copied = False
        
        if not copied:
            # Fallback: try to build from available sources
            proj_used = _try_build_projections_used(projections_df)
            if proj_used is not None:
                with open(projections_used_path, 'w') as f:
                    f.write(proj_used.to_csv(index=False))
        
        # Generate telemetry JSON
        diagnostics = st.session_state.get("id_diagnostics", {})
        constraints_dict = st.session_state.get("optimization_constraints", {})
        preset = st.session_state.get("optimization_preset")
        cp_sat_params = st.session_state.get("optimization_cp_sat_params", {})
        
        telemetry = {
            "export_info": {
                "timestamp": timestamp,
                "export_time": datetime.now().isoformat(),
                "version": "PRP-15",
                "lineups_exported": len(valid_df)
            },
            "optimization": {
                "engine": diagnostics.get("engine", "unknown"),
                "seed": st.session_state.get("optimization_seed", 0),
                "preset": preset,
                "runtime_sec": st.session_state.get("optimization_runtime", 0.0)
            },
            "solver_metrics": {
                "status": diagnostics.get("status"),
                "best_objective": diagnostics.get("best_objective"),
                "best_bound": diagnostics.get("best_bound"),
                "achieved_gap": diagnostics.get("achieved_gap"),
                "wall_time_sec": diagnostics.get("wall_time_sec")
            },
            "parameters": cp_sat_params,
            "constraints": constraints_dict,
            "data_hashes": {
                "projections_hash": hash_projections(projections_df),
                "constraints_hash": hash_constraints(constraints_dict)
            },
            # Include ownership normalization and penalty diagnostics if present
            "normalization": diagnostics.get("normalization", {}),
            "ownership_penalty": diagnostics.get("ownership_penalty", {}),
            "pruning": diagnostics.get("pruning", {}),
            "dk_id_diagnostics": {
                "success_rate": diagnostics.get("success_rate", 0.0),
                "matched_players": diagnostics.get("matched_players", 0),
                "total_players": diagnostics.get("total_players", 0),
                "data_source": diagnostics.get("data_source")
            },
            # Persist contract + wiring info if available so compare panel can use it
            "solver_contract": diagnostics.get("solver_contract", {}),
            "wiring_check": diagnostics.get("wiring_check", {}),
        }
        
        telemetry_path = export_dir / "telemetry.json"
        with open(telemetry_path, 'w') as f:
            json.dump(telemetry, f, indent=2, default=str)
        
        st.success(f"✅ **Complete Export Created**")
        st.info(f"📁 Export directory: `{export_dir}`")
        
        # Show export summary
        with st.expander("📋 Export Summary", expanded=False):
            st.write(f"**Directory**: {export_dir}")
            st.write(f"**Files created**:")
            st.write(f"• `dk_import.csv` - DK-compatible import file ({len(valid_df)} lineups)")
            st.write(f"• `lineups_grid.csv` - Human-readable lineup grid")
            try:
                chash = diagnostics.get('solver_contract', {}).get('contract_hash')
                if chash:
                    st.write(f"• `projections_used.csv` - Exact solver inputs (contract {chash[:12]})")
                    if (export_dir / 'contract_manifest.json').exists():
                        st.write(f"• `contract_manifest.json` - Copy of solver manifest")
                else:
                    st.write(f"• `projections_used.csv` - Built from available sources")
            except Exception:
                pass
            st.write(f"• `telemetry.json` - Complete optimization telemetry")
            st.write(f"**Data fingerprints**:")
            st.write(f"• Projections: `{telemetry['data_hashes']['projections_hash']}`")
            st.write(f"• Constraints: `{telemetry['data_hashes']['constraints_hash']}`")
        
    except Exception as e:
        st.error(f"❌ Export failed: {str(e)}")


def display_solver_diagnostics(diagnostics: dict, selected_engine: str):
    """Enhanced solver diagnostics display (PRP-15 T2)"""
    # Check if we have solver-specific diagnostics
    if "engine" in diagnostics:
        actual_engine = diagnostics["engine"]
        
        # Create solver status panel - expanded by default for PRP-15
        with st.expander(f"🔧 Solver Diagnostics & Performance", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Engine", selected_engine.upper())
                if actual_engine == selected_engine:
                    st.success("✅ Match confirmed")
                else:
                    st.error(f"❌ Expected {selected_engine}, got {actual_engine}")
            
            with col2:
                if actual_engine == "cp_sat":
                    status = diagnostics.get("status", "N/A")
                    st.metric("Status", status)
                    
                    # Enhanced gap display (PRP-15 T2)
                    gap = diagnostics.get("achieved_gap")
                    if gap is not None:
                        gap_pct = gap * 100
                        st.metric("Gap", f"{gap_pct:.3f}%")
                else:
                    st.metric("Status", "CBC (PuLP)")
                    
            with col3:
                n_lineups = diagnostics.get("N", 0)
                st.metric("Lineups", f"{n_lineups}")
                
                # Enhanced wall time metrics (PRP-15 T2)
                if actual_engine == "cp_sat":
                    wall_time = diagnostics.get("wall_time_sec")
                    if wall_time and n_lineups > 0:
                        avg_time = wall_time / n_lineups
                        st.metric("Avg/Lineup", f"{avg_time:.3f}s")
                        
            with col4:
                # Best objective and bound (PRP-15 T2)
                if actual_engine == "cp_sat":
                    best_obj = diagnostics.get("best_objective")
                    best_bound = diagnostics.get("best_bound")
                    if best_obj is not None:
                        st.metric("Best Obj", f"{best_obj:.1f}")
                    if best_bound is not None:
                        st.metric("Best Bound", f"{best_bound:.1f}")
            
            # Show preset information (PRP-15)
            preset = st.session_state.get("optimization_preset")
            if preset and actual_engine == "cp_sat":
                st.markdown(f"**🎯 Preset Used**: {preset}")
                
                # Show preset description
                if preset == "Speed":
                    st.info("🚀 Speed preset: Optimized for fast results (0.7s, 0.1% gap)")
                elif preset == "Repro":
                    st.info("🔍 Repro preset: Full optimization for reproducibility (8s, 0% gap)")
                elif preset == "Custom":
                    st.info("🛠️ Custom preset: User-defined parameters")
                        
            # Enhanced parameter summary (PRP-15 T2)
            if actual_engine == "cp_sat" and "params" in diagnostics:
                params = diagnostics["params"]
                st.markdown("**⚙️ Solver Parameters:**")
                param_cols = st.columns(4)
                
                with param_cols[0]:
                    time_limit = params.get('max_time_in_seconds', 'N/A')
                    st.write(f"**Time**: {time_limit}s")
                    
                with param_cols[1]:
                    gap_limit = params.get('relative_gap_limit', 'N/A')
                    if isinstance(gap_limit, (int, float)) and gap_limit > 0:
                        st.write(f"**Gap**: {gap_limit*100:.1f}%")
                    else:
                        st.write(f"**Gap**: 0% (optimal)")
                    
                with param_cols[2]:
                    workers = params.get('num_search_workers', 'N/A')
                    worker_text = "All cores" if workers == 0 else f"{workers} worker{'s' if workers != 1 else ''}"
                    st.write(f"**Workers**: {worker_text}")
                    
                with param_cols[3]:
                    seed = params.get('random_seed', 'N/A')
                    st.write(f"**Seed**: {seed}")
                    
            # Show PRP-13 Pruning diagnostics (CP-SAT only)
            if actual_engine == "cp_sat" and "pruning" in diagnostics:
                pruning = diagnostics["pruning"]
                if pruning.get("enabled"):
                    st.markdown("**🚀 PRP-13 Safe Position-Aware Pruning:**")
                    prune_cols = st.columns(3)
                    
                    with prune_cols[0]:
                        st.metric("Original Players", pruning.get("original_players", "N/A"))
                    with prune_cols[1]:
                        st.metric("Players Kept", pruning.get("kept_players", "N/A"))
                    with prune_cols[2]:
                        reduction = pruning.get("reduction_pct", 0)
                        st.metric("Reduction", f"{reduction}%")
                    
                    # Show top pruned players if any
                    if pruning.get("top_pruned"):
                        st.write(f"🔍 **Top pruned players**: {', '.join(pruning['top_pruned'])}")
                    
                    # Show locks kept if any
                    locks_kept = pruning.get("locks_kept", 0)
                    if locks_kept > 0:
                        st.write(f"🔒 **Locks kept**: {locks_kept}")


def display_compare_panel():
    """
    Display run comparison panel — simplified to manual export selection only
    for testing stability. We can re-enable history later.
    """
    with st.expander("🆚 Compare Runs", expanded=True):
        display_export_folder_comparison()


def display_export_folder_comparison():
    """Display UI for comparing runs from export folders"""
    col1, col2 = st.columns(2)
    
    with col1:
        export_path_a = st.text_input(
            "Export Folder A",
            placeholder="exports/run_20240101_120000",
            key="export_path_a"
        )
        
    with col2:
        export_path_b = st.text_input(
            "Export Folder B", 
            placeholder="exports/run_20240101_130000",
            key="export_path_b"
        )
    
    # Top-N selector
    top_n = st.number_input("Top-N for Jaccard", 10, 500, 50, key="export_jaccard_n")
    
    if export_path_a and export_path_b:
        # Try to read export runs
        run_a = read_export_run(export_path_a)
        run_b = read_export_run(export_path_b)
        
        if run_a and run_b:
            st.success("✅ Successfully loaded both export runs")
            display_run_comparison(run_a, run_b, top_n)
        else:
            if not run_a:
                st.error(f"❌ Could not load run from: {export_path_a}")
            if not run_b:
                st.error(f"❌ Could not load run from: {export_path_b}")


def display_run_comparison(run_a: dict, run_b: dict, top_n: int):
    """Display detailed comparison between two runs"""
    
    # Run metadata comparison
    st.markdown("### 📋 Run Metadata")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Run A**")
        st.write(f"🏷️ **Label**: {format_run_label(run_a)}")
        st.write(f"⚙️ **Engine**: {run_a.get('engine', 'Unknown')}")
        st.write(f"🎲 **Seed**: {run_a.get('seed', 'N/A')}")
        st.write(f"🔧 **Preset**: {run_a.get('preset', 'N/A')}")
        st.write(f"⏱️ **Runtime**: {run_a.get('runtime_sec', 0):.2f}s")
        ch_a = run_a.get('contract_hash')
        if ch_a:
            st.write(f"📄 **Contract**: {str(ch_a)[:12]}")
        
    with col2:
        st.markdown("**Run B**")
        st.write(f"🏷️ **Label**: {format_run_label(run_b)}")
        st.write(f"⚙️ **Engine**: {run_b.get('engine', 'Unknown')}")
        st.write(f"🎲 **Seed**: {run_b.get('seed', 'N/A')}")
        st.write(f"🔧 **Preset**: {run_b.get('preset', 'N/A')}")
        st.write(f"⏱️ **Runtime**: {run_b.get('runtime_sec', 0):.2f}s")
        ch_b = run_b.get('contract_hash')
        if ch_b:
            st.write(f"📄 **Contract**: {str(ch_b)[:12]}")
    
    # Check for slate compatibility
    hash_a = run_a.get('constraints_hash', 'unknown')
    hash_b = run_b.get('constraints_hash', 'unknown')
    if hash_a != hash_b and hash_a != 'unknown' and hash_b != 'unknown':
        st.warning("⚠️ **Different slates detected** - constraints hashes don't match")
    # Contract hash mismatch warning helps avoid comparing against wrong inputs
    ch_a = run_a.get('contract_hash')
    ch_b = run_b.get('contract_hash')
    if ch_a and ch_b and ch_a != ch_b:
        st.warning("⚠️ **Different contract inputs** - contract hashes don't match")
    
    # Get DataFrames
    df_a = run_a.get('valid_df')
    df_b = run_b.get('valid_df')
    
    if df_a is None or df_b is None:
        st.error("❌ Missing lineup data for comparison")
        return
    
    # PRP-18.1a: Normalize columns immediately after loading
    df_a = normalize_grid_columns(df_a)
    df_b = normalize_grid_columns(df_b)
    
    # Projection summary
    st.markdown("### 📊 Projection Summary")
    
    stats_a = projection_stats(df_a)
    stats_b = projection_stats(df_b)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Mean A", f"{stats_a['mean']:.1f}")
        st.metric("Mean B", f"{stats_b['mean']:.1f}")
        delta_mean = stats_b['mean'] - stats_a['mean']
        st.metric("Δ Mean", f"{delta_mean:+.2f}")
        
    with col2:
        st.metric("Median A", f"{stats_a['median']:.1f}")
        st.metric("Median B", f"{stats_b['median']:.1f}")
        delta_median = stats_b['median'] - stats_a['median'] 
        st.metric("Δ Median", f"{delta_median:+.2f}")
        
    with col3:
        st.metric("P95 A", f"{stats_a['p95']:.1f}")
        st.metric("P95 B", f"{stats_b['p95']:.1f}")
        delta_p95 = stats_b['p95'] - stats_a['p95']
        st.metric("Δ P95", f"{delta_p95:+.2f}")
        
    with col4:
        st.metric("Top A", f"{stats_a['top']:.1f}")
        st.metric("Top B", f"{stats_b['top']:.1f}")
        delta_top = stats_b['top'] - stats_a['top']
        st.metric("Δ Top", f"{delta_top:+.2f}")
    
    # PRP-18.1: Lineup overlap (both Jaccard metrics)
    st.markdown("### 🎯 Lineup Overlap")
    
    col_j1, col_j2 = st.columns(2)
    
    with col_j1:
        try:
            # Pairwise Top-N Jaccard
            jaccard_pw = jaccard_pairwise(df_a, df_b, top_n)
            if jaccard_pw is not None:
                st.metric(f"Pairwise Top-{top_n} Jaccard", f"{jaccard_pw:.3f}")
                
                if jaccard_pw > 0.8:
                    st.success("🟢 High pairwise overlap")
                elif jaccard_pw > 0.5:
                    st.info("🟡 Moderate pairwise overlap")
                else:
                    st.warning("🔴 Low pairwise overlap")
            else:
                st.metric(f"Pairwise Top-{top_n} Jaccard", "N/A")
                st.info("ℹ️ Projection column not found; normalize failed or export schema changed.")
                
        except Exception as e:
            st.error(f"❌ Failed to calculate pairwise Jaccard: {str(e)}")
    
    with col_j2:
        try:
            # Aggregate Pool Jaccard  
            jaccard_pool_val = jaccard_pool(df_a, df_b, top_n)
            if jaccard_pool_val is not None:
                st.metric(f"Aggregate Pool Top-{top_n} Jaccard", f"{jaccard_pool_val:.3f}")
                
                if jaccard_pool_val > 0.8:
                    st.success("🟢 High pool overlap")
                elif jaccard_pool_val > 0.5:
                    st.info("🟡 Moderate pool overlap")
                else:
                    st.warning("🔴 Low pool overlap")
            else:
                st.metric(f"Aggregate Pool Top-{top_n} Jaccard", "N/A")
                st.info("ℹ️ Projection column not found; normalize failed or export schema changed.")
                
        except Exception as e:
            st.error(f"❌ Failed to calculate pool Jaccard: {str(e)}")
    
    # PRP-18.1: Player exposures comparison with robust delta computation
    st.markdown("### 👥 Player Exposure Deltas")
    
    try:
        # Use new robust exposure delta function
        exposure_deltas_robust = exposure_delta(df_a, df_b)
        
        if not exposure_deltas_robust.empty:
            # Limit to top 100 by absolute delta for performance
            display_deltas = exposure_deltas_robust.head(100).copy()
            
            # Format for display
            display_deltas['A_pct'] = display_deltas['A'].apply(lambda x: f"{x:.1%}")
            display_deltas['B_pct'] = display_deltas['B'].apply(lambda x: f"{x:.1%}")
            display_deltas['delta_pct'] = display_deltas['delta'].apply(lambda x: f"{x:+.1%}")
            
            # Show formatted table
            st.dataframe(
                display_deltas[['A_pct', 'B_pct', 'delta_pct']].rename(columns={
                    'A_pct': 'Exposure A',
                    'B_pct': 'Exposure B',
                    'delta_pct': 'Δ Exposure'
                }),
                use_container_width=True,
                height=300
            )
            
            # CSV download with raw values
            if st.button("📥 Download Exposure Deltas CSV", key="download_exposures"):
                csv_content = exposure_deltas_robust.to_csv(index=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="💾 exposures_delta.csv",
                    data=csv_content,
                    file_name=f"exposures_delta_{timestamp}.csv",
                    mime="text/csv"
                )
        else:
            st.info("ℹ️ No player IDs parsed; cannot compute exposures.")
            
    except Exception as e:
        st.error(f"❌ Failed to calculate exposure deltas: {str(e)}")
        # Fallback to legacy approach
        try:
            exposures_a = exposure_table(df_a)
            exposures_b = exposure_table(df_b)
            if not exposures_a.empty and not exposures_b.empty:
                st.info("ℹ️ Using fallback exposure calculation")
                legacy_deltas = calculate_exposure_delta(exposures_a, exposures_b)
                if not legacy_deltas.empty:
                    st.dataframe(legacy_deltas.head(20), use_container_width=True)
        except Exception as fallback_e:
            st.error(f"❌ Fallback also failed: {str(fallback_e)}")
    
    # PRP-18.1: Stack frequency comparison with robust delta computation
    st.markdown("### 🏗️ Stack Frequency Deltas")
    
    try:
        # Use new robust stack delta function
        stack_deltas_robust = stack_delta(df_a, df_b)
        
        if not stack_deltas_robust.empty:
            # Show aligned table with A, B, delta columns
            st.dataframe(
                stack_deltas_robust.rename(columns={
                    'A': 'Freq A',
                    'B': 'Freq B',
                    'delta': 'Δ Freq'
                }),
                use_container_width=True,
                height=200
            )
            
            # CSV download with raw values
            if st.button("📥 Download Stack Deltas CSV", key="download_stacks"):
                csv_content = stack_deltas_robust.to_csv(index=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="💾 stacks_delta.csv",
                    data=csv_content,
                    file_name=f"stacks_delta_{timestamp}.csv",
                    mime="text/csv"
                )
        else:
            st.info("ℹ️ No stack data available for comparison")
            
    except Exception as e:
        st.error(f"❌ Failed to calculate stack deltas: {str(e)}")
        # Fallback to legacy approach
        try:
            stacks_a = stack_freqs(df_a)
            stacks_b = stack_freqs(df_b)
            if not stacks_a.empty and not stacks_b.empty:
                st.info("ℹ️ Using fallback stack calculation")
                legacy_stacks = calculate_stack_delta(stacks_a, stacks_b)
                if not legacy_stacks.empty:
                    st.dataframe(legacy_stacks.head(20), use_container_width=True)
        except Exception as fallback_e:
            st.error(f"❌ Fallback also failed: {str(fallback_e)}")
    
    # Ownership penalty diagnostics comparison
    display_ownership_penalty_comparison(run_a, run_b)
    
    # Ownership trends (if available)
    display_ownership_trends_comparison(df_a, df_b, run_a, run_b)


def display_ownership_penalty_comparison(run_a: dict, run_b: dict):
    """Display ownership penalty diagnostics comparison"""
    diag_a = run_a.get('diagnostics', {}).get('ownership_penalty')
    diag_b = run_b.get('diagnostics', {}).get('ownership_penalty')
    
    if diag_a or diag_b:
        st.markdown("### 🎯 Ownership Penalty Comparison")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Run A**")
            if diag_a:
                display_ownership_penalty_box(diag_a)
            else:
                st.info("No ownership penalty used")
                
        with col2:
            st.markdown("**Run B**")
            if diag_b:
                display_ownership_penalty_box(diag_b)
            else:
                st.info("No ownership penalty used")


def display_ownership_penalty_box(penalty_diag: dict):
    """Display ownership penalty diagnostics in compact format"""
    mode = penalty_diag.get("mode", "—")
    lambda_used = penalty_diag.get("lambda_used")
    target_pct = penalty_diag.get("target_offoptimal_pct")
    achieved_pct = penalty_diag.get("achieved_offoptimal_pct")
    chalk_index = penalty_diag.get("avg_chalk_index")
    penalty_points = penalty_diag.get("avg_penalty_points")
    capped = penalty_diag.get("capped", False)
    
    st.write(f"**Mode**: {mode.replace('_', ' ').title()}")
    if lambda_used is not None:
        st.write(f"**λ**: {lambda_used:.3f}")
    if target_pct is not None:
        st.write(f"**Target % Off**: {target_pct*100:.1f}%")
    if achieved_pct is not None:
        st.write(f"**Achieved % Off**: {achieved_pct*100:.1f}%") 
    if chalk_index is not None:
        st.write(f"**Avg Chalk Index**: {chalk_index:.2f}")
    if penalty_points is not None:
        st.write(f"**Avg Penalty Pts**: {penalty_points:.2f}")
    if capped:
        st.warning("⚠️ Hit λ cap during search")


def display_ownership_trends_comparison(df_a: pd.DataFrame, df_b: pd.DataFrame, run_a: dict, run_b: dict):
    """Ownership trends that are robust to DK-strict vs ingest flows (PRP-18.3).
    Prefers each export's own `projections_used.csv`, then falls back to
    normalized parquet, then dk_data/projections.csv.
    """
    from pathlib import Path

    st.markdown("### 📈 Ownership Trends")

    # Export paths (may be missing for in-session runs)
    export_path_a = run_a.get("export_path")
    export_path_b = run_b.get("export_path")

    # Load ownership for each side using PRP-18.3 order
    own_a = load_export_ownership(Path(export_path_a)) if export_path_a else load_export_ownership(Path("."))
    own_b = load_export_ownership(Path(export_path_b)) if export_path_b else load_export_ownership(Path("."))

    # Join ownership onto lineup grids (computes own_sum / own_prod when possible)
    df_a_own = try_join_ownership_with_data(df_a, own_a) if own_a is not None else None
    df_b_own = try_join_ownership_with_data(df_b, own_b) if own_b is not None else None

    if df_a_own is None and df_b_own is None:
        st.info("Ownership data not available — no usable `own_proj` found in export, normalized parquet, or dk_data.")
        return

    # Top-N from UI (fallback to 50)
    top_n = st.session_state.get("jaccard_n") or st.session_state.get("export_jaccard_n") or 50
    c1, c2 = st.columns(2)

    def _render_side(df_own: pd.DataFrame, label: str, col):
        if df_own is None or df_own.empty:
            with col:
                st.metric(f"Avg Own Sum {label} (Top-{top_n})", "N/A")
                st.metric(f"Avg Own Prod {label} (Top-{top_n})", "N/A")
            return
        ranked = df_own.sort_values("total_proj", ascending=False).head(int(top_n))
        avg_sum_pct = float(ranked["own_sum"].mean() * 100.0) if "own_sum" in ranked.columns else None
        avg_prod = float(ranked["own_prod"].mean()) if "own_prod" in ranked.columns and not ranked["own_prod"].isna().all() else None
        with col:
            st.metric(f"Avg Own Sum {label} (Top-{top_n})", f"{avg_sum_pct:.1f}%" if avg_sum_pct is not None else "N/A")
            st.metric(f"Avg Own Prod {label} (Top-{top_n})", f"{avg_prod:.4f}" if avg_prod is not None else "N/A")

    _render_side(df_a_own, "A", c1)
    _render_side(df_b_own, "B", c2)

    # Source caption (helps debug which source fed ownership)
    def _source_caption(run: dict, own_df: pd.DataFrame | None) -> str:
        # Prefer attrs from loader if present
        if own_df is not None and hasattr(own_df, 'attrs'):
            src = own_df.attrs.get('source')
            scaled = own_df.attrs.get('scaled_by')
            if src:
                if scaled and float(scaled) > 1.0:
                    return f"{src} (÷{int(scaled)})"
                return f"{src}"
        # Fallback inference by paths
        p = run.get("export_path")
        if p and (Path(p) / "projections_used.csv").exists():
            return "export’s `projections_used.csv`"
        if Path("data/normalized/projections.parquet").exists():
            return "normalized parquet"
        if Path("dk_data/projections.csv").exists():
            return "dk_data/projections.csv"
        return "unknown"

    st.caption(f"Ownership sources — A: {_source_caption(run_a, own_a)} · B: {_source_caption(run_b, own_b)}")


def persist_run_to_history(valid_df: pd.DataFrame, site: str, runtime: float):
    """
    Persist run artifact to session history for comparison (PRP-18.1)
    
    Args:
        valid_df: Validated lineup DataFrame  
        site: Site identifier (e.g., 'dk')
        runtime: Optimization runtime in seconds
    """
    try:
        # Get session state data
        constraints_dict = st.session_state.get("optimization_constraints", {})
        seed = st.session_state.get("optimization_seed", 0)
        preset = st.session_state.get("optimization_preset")
        id_diagnostics = st.session_state.get("id_diagnostics", {})
        engine = id_diagnostics.get("engine", "unknown")
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%H%M%S")
        
        # PRP-18.1: Create run artifact with run_id and deep copy
        artifact = {
            "run_id": generate_run_id(),  # PRP-18.1: Unique run ID (UUID)
            "label": f"{site.upper()} • {engine.upper()} • seed={seed} • {preset or '—'} • {timestamp}",
            "timestamp": timestamp,
            "engine": engine,
            "site": site,
            "seed": seed,
            "preset": preset,
            "constraints_hash": hash_constraints(constraints_dict),
            "valid_df": valid_df.copy(deep=True),  # PRP-18.1: Deep copy to avoid aliasing
            "diagnostics": id_diagnostics,
            "runtime_sec": runtime
        }
        
        # Initialize or update run history
        if "run_history" not in st.session_state:
            st.session_state["run_history"] = []
            
        st.session_state["run_history"].append(artifact)
        
        # Cap history length to 5 (keep most recent)
        st.session_state["run_history"] = st.session_state["run_history"][-5:]
        
    except Exception as e:
        # Don't fail the main flow, just log the error
        print(f"Failed to persist run to history: {e}")


if __name__ == "__main__":
    main()
