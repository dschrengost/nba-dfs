import type { Player, Projection, MergedPlayer } from "@/lib/domain/types";
import type { PlayerCsv, ProjectionCsv } from "./schemas";

export function normalizePlayers(rows: PlayerCsv[]): Player[] {
  return rows.map((r) => ({
    player_id_dk: String(r.player_id_dk),
    player_name: r.player_name,
    team: r.team.toUpperCase(),
    pos_primary: r.pos_primary,
    pos_secondary: r.pos_secondary ?? null,
  }));
}

export function normalizeProjections(rows: ProjectionCsv[]): Projection[] {
  return rows.map((r) => ({
    player_id_dk: String(r.player_id_dk),
    salary: Number(r.salary),
    proj_fp: Number(r.proj_fp),
    mins: r.mins ?? null,
    ownership: r.ownership ?? null,
    ceiling: r.ceiling ?? null,
    floor: r.floor ?? null,
    source: r.source,
    version_ts: r.version_ts ?? null,
  }));
}

export function mergePlayers(
  players: Player[],
  projections: Projection[]
): MergedPlayer[] {
  const projById = new Map(projections.map((p) => [p.player_id_dk, p] as const));
  const merged: MergedPlayer[] = [];
  for (const pl of players) {
    const pj = projById.get(pl.player_id_dk);
    if (!pj) continue; // inner join
    merged.push({ ...pl, ...pj });
  }
  return merged;
}

