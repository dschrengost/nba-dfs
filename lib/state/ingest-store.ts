"use client";

import { create } from "zustand";
import type {
  IngestSummary,
  MergedPlayer,
  Player,
  Projection,
} from "@/lib/domain/types";
import { PlayerCsvSchema } from "@/lib/ingest/schemas";
import { parseCsvStream } from "@/lib/ingest/parse";
import { mergePlayersStrict, normalizePlayers, normalizeProjections } from "@/lib/ingest/normalize";
import {
  parseDkPlayers,
  parseDkProjections,
  buildCanonicalProjectionsFromDk,
  type DkProjection,
} from "@/lib/ingest/adapter";

type Status = "idle" | "parsing" | "ready" | "error";

type IngestError = { file: "players" | "projections" | "unknown"; row: number; message: string };

type State = {
  status: Status;
  players: Player[];
  projections: Projection[];
  merged: MergedPlayer[];
  summary: IngestSummary | null;
  errors: IngestError[];
  _pendingDkProjections: DkProjection[] | null;
  ingestCsv: (file: File) => Promise<void>;
  reset: () => void;
};

function initSummary(): IngestSummary {
  return {
    rows_players: 0,
    rows_projections: 0,
    dropped_players: 0,
    dropped_projections: 0,
    unknown_cols_players: [],
    unknown_cols_projections: [],
  };
}

function guessKind(file: File): "players" | "projections" | null {
  const n = file.name.toLowerCase();
  if (n.includes("player")) return "players";
  if (n.includes("proj")) return "projections";
  return null;
}

export const useIngestStore = create<State>((set, get) => ({
  status: "idle",
  players: [],
  projections: [],
  merged: [],
  summary: null,
  errors: [],
  _pendingDkProjections: null,
  reset: () =>
    set({
      status: "idle",
      players: [],
      projections: [],
      merged: [],
      summary: null,
      errors: [],
      _pendingDkProjections: null,
    }),
  ingestCsv: async (file: File) => {
    set({ status: "parsing" });
    const kind = guessKind(file);

    try {
      if (kind === "players") {
        // Prefer DK adapter for real DK files; fall back to canonical if needed
        let players: Player[] = [];
        let unknownCols: string[] = [];
        let rowCount = 0;
        let droppedRows = 0;
        try {
          const repDk = await parseDkPlayers(file);
          players = normalizePlayers(repDk.rows);
          rowCount = repDk.rowCount;
          droppedRows = repDk.droppedRows;
          unknownCols = repDk.unknownColumns;
        } catch {
          const rep = await parseCsvStream(file, PlayerCsvSchema, {} as any);
          players = normalizePlayers(rep.rows);
          rowCount = rep.rowCount;
          droppedRows = rep.droppedRows;
          unknownCols = rep.unknownColumns;
        }
        const nextSummary = { ...(get().summary ?? initSummary()) };
        nextSummary.rows_players = rowCount;
        nextSummary.dropped_players = droppedRows;
        nextSummary.unknown_cols_players = unknownCols;

        // If projections already parsed DK-raw, adapt now
        let projections = get().projections;
        const pending = get()._pendingDkProjections;
        if (pending && pending.length > 0) {
          const res = buildCanonicalProjectionsFromDk(pending, players);
          // If any unmatched remain, mark error
          if (res.unmatched.length > 0) {
            set({
              status: "error",
              errors: res.unmatched.map((r) => ({
                file: "projections",
                row: -1,
                message: `Unmatched DK projection: ${r.name} ${r.team} ${r.position}`,
              })),
            });
          }
          projections = normalizeProjections(res.rows);
        }

        const strict = mergePlayersStrict(players, projections);
        const status: Status = strict.ok ? "ready" : "error";
        set({ players, projections, merged: strict.merged, summary: nextSummary, status, _pendingDkProjections: null });
      } else if (kind === "projections") {
        // Parse DK raw projections first; then adapt once players are available
        const repDk = await parseDkProjections(file);
        const nextSummary = { ...(get().summary ?? initSummary()) };
        nextSummary.rows_projections = repDk.rowCount;
        nextSummary.dropped_projections = repDk.droppedRows;
        nextSummary.unknown_cols_projections = repDk.unknownColumns;

        const players = get().players;
        if (players.length > 0) {
          const res = buildCanonicalProjectionsFromDk(repDk.rows, players);
          if (res.unmatched.length > 0) {
            set({
              status: "error",
              errors: res.unmatched.map((r) => ({
                file: "projections",
                row: -1,
                message: `Unmatched DK projection: ${r.name} ${r.team} ${r.position}`,
              })),
            });
          }
          const projections = normalizeProjections(res.rows);
          const strict = mergePlayersStrict(players, projections);
          const status: Status = strict.ok ? "ready" : "error";
          set({ projections, merged: strict.merged, summary: nextSummary, status, _pendingDkProjections: null });
        } else {
          // wait for players to be ingested
          set({ _pendingDkProjections: repDk.rows, summary: nextSummary, status: "ready" });
        }
      } else {
        // Fallback: try projections first then players
        // try DK projections first
        try {
          const repP = await parseDkProjections(file);
          const nextSummary = { ...(get().summary ?? initSummary()) };
          nextSummary.rows_projections = repP.rowCount;
          nextSummary.dropped_projections = repP.droppedRows;
          nextSummary.unknown_cols_projections = repP.unknownColumns;
          const players = get().players;
          if (players.length > 0) {
            const res = buildCanonicalProjectionsFromDk(repP.rows, players);
            const projections = normalizeProjections(res.rows);
            const strict = mergePlayersStrict(players, projections);
            const status: Status = strict.ok ? "ready" : "error";
            set({ projections, merged: strict.merged, summary: nextSummary, status });
            return;
          }
          set({ _pendingDkProjections: repP.rows, summary: nextSummary, status: "ready" });
          return;
        } catch {}
        // finally, try players
        const repPl = await parseDkPlayers(file);
        const players = normalizePlayers(repPl.rows);
        const nextSummary = { ...(get().summary ?? initSummary()) };
        nextSummary.rows_players = repPl.rowCount;
        nextSummary.dropped_players = repPl.droppedRows;
        nextSummary.unknown_cols_players = repPl.unknownColumns;
        const strict = mergePlayersStrict(players, get().projections);
        const status: Status = strict.ok ? "ready" : "error";
        set({ players, merged: strict.merged, summary: nextSummary, status });
      }
    } catch (e: any) {
      set((s) => ({
        status: "error",
        errors: s.errors.concat({ file: "unknown", row: -1, message: e?.message ?? String(e) }),
      }));
    }
  },
}));

function keyToLower<T extends Record<string, any>>(obj: T): T {
  const out: any = {};
  for (const [k, v] of Object.entries(obj)) out[k.toLowerCase()] = v;
  return out as T;
}
