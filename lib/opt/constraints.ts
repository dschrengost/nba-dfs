import type { MergedPlayer } from "@/lib/domain/types";
import type { Slot } from "./types";

export const DK_SLOTS: Slot[] = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"];

export function eligibleForSlot(p: MergedPlayer, slot: Slot): boolean {
  const pos = [p.pos_primary, p.pos_secondary ?? undefined].filter(Boolean) as string[];
  if (pos.length === 0) return false;
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

