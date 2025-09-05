Mapping catalog for projection sources → canonical fields.

Structure (YAML):

name: example_source
map:
  # source_header: canonical_field
  DK_ID: dk_player_id
  Name: name
  Team: team
  Pos: pos
  Salary: salary
  Minutes: minutes
  FP: proj_fp
  Ceil: ceil_fp
  Floor: floor_fp
  Own: own_proj

Notes:
- Coercions: salary cast to int (stripping $, ,), others to float when applicable.
- Unknown columns are ignored but preserved as lineage.source_fields.

