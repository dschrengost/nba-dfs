import type { MergedPlayer } from "@/lib/domain/types";
import type { Slot } from "./types";

export const DK_SLOTS: Slot[] = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"];

export function eligibleForSlot(p: MergedPlayer, slot: Slot): boolean {
  // Prefer canonical ingest array; fall back to legacy fields.
  const raw =
    Array.isArray((p as any).pos) && (p as any).pos.length
      ? ((p as any).pos as string[])
      : [ (p as any).pos_primary, (p as any).pos_secondary, (p as any).pos_tertiary ]
          .filter(Boolean) as string[];

  const pos = raw
    .flatMap(s => String(s).split(/[\/ ,]/)) // handle "PG/SG" or comma/space separated
    .map(s => s.trim().toUpperCase())
    .filter(Boolean);

  // If we can't determine a position, only UTIL is permissive.
  if (pos.length === 0) return slot === "UTIL";

  switch (slot) {
    case "PG":
      return pos.includes("PG");
    case "SG":
      return pos.includes("SG");
    case "SF":
      return pos.includes("SF");
    case "PF":
      return pos.includes("PF");
    case "C":
      return pos.includes("C");
    case "G":
      return pos.includes("PG") || pos.includes("SG");
    case "F":
      return pos.includes("SF") || pos.includes("PF");
    case "UTIL":
      return true;
    default:
      return false;
  }
}

export function withinTeamCap(teamCounts: Record<string, number>, team: string, maxPerTeam?: number): boolean {
  if (!maxPerTeam || maxPerTeam <= 0) return true;
  const n = teamCounts[team] ?? 0;
  return n + 1 <= maxPerTeam;
}

