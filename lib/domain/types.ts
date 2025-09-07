// Domain models for canonical ingest types

export type Player = {
  player_id_dk: string;
  player_name: string;
  team: string; // 3-letter
  pos_primary: string;
  pos_secondary?: string | null;
};

export type Projection = {
  player_id_dk: string; // FK -> players
  salary: number;
  proj_fp: number;
  mins?: number | null;
  ownership?: number | null;
  ceiling?: number | null;
  floor?: number | null;
  source: string;
  version_ts?: string | null; // ISO string if known
};

export type MergedPlayer = Player & Projection;

export type IngestSummary = {
  rows_players: number;
  rows_projections: number;
  dropped_players: number;
  dropped_projections: number;
  unknown_cols_players: string[];
  unknown_cols_projections: string[];
};

