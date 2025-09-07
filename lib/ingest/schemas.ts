import { z } from "zod";

// Common alias maps for CSV headers
export const PLAYER_ALIASES: Record<string, keyof z.infer<typeof PlayerCsvSchema>> = {
  player_id_dk: "player_id_dk",
  player_id: "player_id_dk",
  dk_id: "player_id_dk",
  id: "player_id_dk",
  name: "player_name",
  player_name: "player_name",
  team: "team",
  team_abbr: "team",
  pos: "pos_primary",
  pos_primary: "pos_primary",
  pos_secondary: "pos_secondary",
};

export const PROJ_ALIASES: Record<string, keyof z.infer<typeof ProjectionCsvSchema>> = {
  player_id_dk: "player_id_dk",
  player_id: "player_id_dk",
  dk_id: "player_id_dk",
  id: "player_id_dk",
  salary: "salary",
  sal: "salary",
  proj_fp: "proj_fp",
  proj: "proj_fp",
  projection: "proj_fp",
  fp: "proj_fp",
  mins: "mins",
  minutes: "mins",
  own: "ownership",
  ownership: "ownership",
  ceil: "ceiling",
  ceiling: "ceiling",
  floor: "floor",
  source: "source",
  version_ts: "version_ts",
  timestamp: "version_ts",
  version: "version_ts",
};

// Helpers
const toStr = z
  .string()
  .transform((s) => s.trim())
  .pipe(z.string().min(1));

const toNum = z
  .union([z.number(), z.string()])
  .transform((v) => (typeof v === "number" ? v : Number(String(v).trim())))
  .pipe(z.number().finite());

const toOptNum = z
  .union([z.number(), z.string()])
  .transform((v) => {
    if (v === null || v === undefined) return null;
    const s = String(v).trim();
    if (s === "" || s.toLowerCase() === "na") return null;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  })
  .nullable()
  .optional();

const toOptStr = z
  .union([z.string(), z.null(), z.undefined()])
  .transform((v) => {
    if (v === null || v === undefined) return null;
    const s = String(v).trim();
    return s === "" ? null : s;
  })
  .nullable()
  .optional();

// Row schemas for CSV after aliasing
export const PlayerCsvSchema = z.object({
  player_id_dk: toStr,
  player_name: toStr,
  team: toStr.transform((s) => s.toUpperCase()),
  pos_primary: toStr,
  pos_secondary: toOptStr,
});

export type PlayerCsv = z.infer<typeof PlayerCsvSchema>;

export const ProjectionCsvSchema = z.object({
  player_id_dk: toStr,
  salary: toNum,
  proj_fp: toNum,
  mins: toOptNum,
  ownership: toOptNum,
  ceiling: toOptNum,
  floor: toOptNum,
  source: toStr,
  version_ts: toOptStr, // ISO or null
});

export type ProjectionCsv = z.infer<typeof ProjectionCsvSchema>;

export type AliasMap<T extends z.ZodRawShape> = Record<string, keyof z.infer<z.ZodObject<T>>>;
