from __future__ import annotations

from typing import Any

import pandas as pd

from processes.field_sampler.engine import SamplerEngine


def run_sampler(
    catalog_df: pd.DataFrame, config: dict[str, Any], seed: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Bridge function to integrate SamplerEngine with field_sampler adapter.

    This function adapts the new SamplerEngine to work with the existing
    field_sampler adapter interface.

    Args:
        catalog_df: Variant catalog DataFrame
        config: Configuration dictionary with sampling parameters
        seed: Random seed for reproducibility

    Returns:
        Tuple of (entrants_list, telemetry_dict)
    """
    # Extract config parameters with defaults
    field_size = config.get("field_size", 100)

    # For now, create a minimal projections DataFrame from catalog if needed
    # In practice, projections should come from a separate source
    if "salary" not in catalog_df.columns:
        # Mock up minimal projections structure for engine
        unique_players = set()
        for _, row in catalog_df.iterrows():
            if "players" in row:
                unique_players.update(row["players"])

        # Create mock projections
        projections_rows = []
        for i, player_id in enumerate(sorted(unique_players)):
            projections_rows.append(
                {
                    "player_id": player_id,
                    "team": f"T{i % 8}",  # Mock team assignments
                    "positions": (
                        "PG/SG" if i % 5 == 0 else ["PG", "SG", "SF", "PF", "C"][i % 5]
                    ),
                    "salary": 5000 + (i % 6000),  # Mock salaries
                    "ownership": 0.1 + (i % 10) * 0.05,  # Mock ownership
                }
            )
        projections = pd.DataFrame(projections_rows)
    else:
        # Use catalog as projections if it has the right structure
        projections = catalog_df

    # Initialize engine
    engine = SamplerEngine(
        projections=projections,
        seed=seed,
        salary_cap=config.get("salary_cap", 50000),
        max_per_team=config.get("max_per_team", 4),
    )

    # Convert catalog to variant format for sampling
    variants: list[dict[str, Any]] = []
    for _, row in catalog_df.iterrows():
        if (
            "players" in row
            and isinstance(row["players"], list)
            and len(row["players"]) == 8
        ):
            variant = {
                "players": row["players"],
                "variant_id": row.get("variant_id", f"v_{len(variants)}"),
                "export_csv_row": ",".join(row["players"]),
            }
            variants.append(variant)

    # Sample from variants
    if variants:
        entrants = engine.sample(variants, field_size)
    else:
        # Fallback: generate from scratch using projections
        engine.generate(field_size)
        # Convert generated lineups to entrant format
        entrants = []
        # This is a simplified conversion - in practice we'd read from the
        # generated files
        # For now, return empty list as fallback
        entrants = []

    # Build telemetry
    telemetry = {
        "field_size_requested": field_size,
        "field_size_generated": len(entrants),
        "variants_available": len(variants),
        "config_used": config,
        "seed": seed,
    }

    return entrants, telemetry
