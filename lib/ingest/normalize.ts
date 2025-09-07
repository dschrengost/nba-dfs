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

export function mergePlayersStrict(
  players: Player[],
  projections: Projection[]
): { merged: MergedPlayer[]; ok: boolean; expected: number; missing_player_ids: string[]; missing_projection_ids: string[] } {
  const projById = new Map(projections.map((p) => [p.player_id_dk, p] as const));
  const plById = new Map(players.map((p) => [p.player_id_dk, p] as const));
  const merged: MergedPlayer[] = [];

  const missingFromProjections: string[] = [];
  for (const pl of players) {
    const pj = projById.get(pl.player_id_dk);
    if (!pj) {
      missingFromProjections.push(pl.player_id_dk);
      continue;
    }
    merged.push({ ...pl, ...pj });
  }

  const missingFromPlayers: string[] = [];
  for (const pj of projections) {
    if (!plById.has(pj.player_id_dk)) missingFromPlayers.push(pj.player_id_dk);
  }

  const expected = Math.max(players.length, projections.length);
  const ok = merged.length === players.length && merged.length === projections.length;
  return {
    merged,
    ok,
    expected,
    missing_player_ids: missingFromPlayers,
    missing_projection_ids: missingFromProjections,
  };
}
