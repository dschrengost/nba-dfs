import { z } from "zod";
import type { ParseReport } from "./parse";
import { parseCsvStream } from "./parse";
import {
  PlayerCsvSchema,
  ProjectionCsvSchema,
  type PlayerCsv,
  type ProjectionCsv,
} from "./schemas";
import { normalizeNameKey, normalizeTeam, splitPositions } from "./aliases";

// ================= DK RAW SCHEMAS + ALIASES =================

const toStr = z
  .string()
  .transform((s) => s.trim())
  .pipe(z.string().min(1));

const toNum = z
  .union([z.number(), z.string()])
  .transform((v) => (typeof v === "number" ? v : Number(String(v).trim())))
  .pipe(z.number().finite());

const toOptNum = z
  .union([z.number(), z.string(), z.null(), z.undefined()])
  .transform((v) => {
    if (v === null || v === undefined) return null;
    const s = String(v).trim().replace(/%$/, "");
    if (s === "" || s.toLowerCase() === "na") return null;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  })
  .nullable();

export const DkPlayerSchema = z.object({
  id: toStr,
  name: toStr,
  position: toStr,
  teamabbrev: toStr,
});

export type DkPlayer = z.infer<typeof DkPlayerSchema>;

export const DK_PLAYER_ALIASES: Record<string, keyof DkPlayer> = {
  id: "id",
  "player id": "id",
  name: "name",
  position: "position",
  teamabbrev: "teamabbrev",
  "team abbrev": "teamabbrev",
};

export const DkProjectionSchema = z.object({
  name: toStr,
  position: toStr,
  team: toStr,
  salary: toNum,
  fpts: toNum,
  stddev: toOptNum.optional(),
  ceiling: toOptNum.optional(),
  own_pct: toOptNum.optional(),
  minutes: toOptNum.optional(),
  fieldfpts: toOptNum.optional(),
});

export type DkProjection = z.infer<typeof DkProjectionSchema>;

export const DK_PROJ_ALIASES: Record<string, keyof DkProjection> = {
  // core
  name: "name",
  position: "position",
  team: "team",
  salary: "salary",
  fpts: "fpts",
  // alternates
  stddev: "stddev",
  ceiling: "ceiling",
  "own%": "own_pct",
  own: "own_pct",
  minutes: "minutes",
  mins: "minutes",
  fieldfpts: "fieldfpts",
};

// ================= ADAPTERS (DK → canonical) =================

export async function parseDkPlayers(
  file: File | Blob | string
): Promise<ParseReport<PlayerCsv>> {
  const rep = await parseCsvStream(file, DkPlayerSchema, lower(DK_PLAYER_ALIASES));
  const rows: PlayerCsv[] = rep.rows.map((r) => {
    const [pos_primary, pos_secondary] = splitPositions(r.position);
    return {
      player_id_dk: String(r.id),
      player_name: r.name,
      team: normalizeTeam(r.teamabbrev),
      pos_primary,
      pos_secondary,
    } satisfies PlayerCsv;
  });

  // Validate against canonical schema to honor canonical Zod
  const validated = rows.map((row, idx) => {
    const parsed = PlayerCsvSchema.safeParse(row);
    if (!parsed.success) {
      throw new Error(
        `DK players row ${idx + 1} failed canonical validation: ` +
          parsed.error.issues.map((i) => `${i.path.join(".")}:${i.message}`).join("; ")
      );
    }
    return parsed.data;
  });

  return {
    rows: validated,
    errors: rep.errors,
    rowCount: rep.rowCount,
    droppedRows: rep.droppedRows,
    unknownColumns: rep.unknownColumns,
  };
}

export async function parseDkProjections(
  file: File | Blob | string
): Promise<ParseReport<DkProjection>> {
  return parseCsvStream(file, DkProjectionSchema, lower(DK_PROJ_ALIASES));
}

export function buildCanonicalProjectionsFromDk(
  dkRows: DkProjection[],
  players: PlayerCsv[] | { player_id_dk: string; player_name: string; team: string; pos_primary: string; pos_secondary?: string | null }[]
): { rows: ProjectionCsv[]; unmatched: DkProjection[] } {
  // Build lookup maps
  const byNameTeamPos = new Map<string, string>(); // composite -> player_id_dk
  const makeKey = (name: string, team: string, pos: string) =>
    `${normalizeNameKey(name)}|${normalizeTeam(team)}|${pos.toUpperCase()}`;

  for (const p of players) {
    const k = makeKey(p.player_name, p.team, p.pos_primary);
    if (!byNameTeamPos.has(k)) byNameTeamPos.set(k, p.player_id_dk);
  }

  const rows: ProjectionCsv[] = [];
  const unmatched: DkProjection[] = [];

  for (const r of dkRows) {
    const [pos_primary] = splitPositions(r.position);
    const pid = byNameTeamPos.get(makeKey(r.name, r.team, pos_primary));
    if (!pid) {
      unmatched.push(r);
      continue;
    }
    rows.push({
      player_id_dk: pid,
      salary: Number(r.salary),
      proj_fp: Number(r.fpts),
      mins: r.minutes ?? null,
      ownership: r.own_pct ?? null,
      ceiling: r.ceiling ?? null,
      floor: r.fieldfpts ?? null, // DK sheet has FieldFpts; keep as floor? if absent, null
      source: "DK",
      version_ts: null,
    } satisfies ProjectionCsv);
  }

  // Validate all rows via canonical Zod
  const validated: ProjectionCsv[] = rows.map((row, idx) => {
    const parsed = ProjectionCsvSchema.safeParse(row);
    if (!parsed.success) {
      throw new Error(
        `DK projections row ${idx + 1} failed canonical validation: ` +
          parsed.error.issues.map((i) => `${i.path.join(".")}:${i.message}`).join("; ")
      );
    }
    return parsed.data;
  });

  return { rows: validated, unmatched };
}

function lower<T extends Record<string, any>>(obj: T): T {
  const out: any = {};
  for (const [k, v] of Object.entries(obj)) out[k.toLowerCase()] = v;
  return out as T;
}
