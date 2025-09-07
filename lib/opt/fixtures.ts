import type { MergedPlayer } from "@/lib/domain/types";
import { DEFAULT_FIXTURE_DATE } from "@/lib/opt/config";

// Note: static import so it bundles for client with no network fetch
// If you change DEFAULT_FIXTURE_DATE, update this import accordingly.
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore - JSON module import typed below
import mergedPlayers from "../../fixtures/dk/2024-01-15/mergedPlayers.json" assert { type: "json" };

export function loadFixtureMergedPlayers(): { date: string; players: MergedPlayer[] } {
  const arr = (mergedPlayers as any as MergedPlayer[]) ?? [];
  return { date: DEFAULT_FIXTURE_DATE, players: arr };
}

