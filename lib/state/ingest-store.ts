"use client";

import { create } from "zustand";
import type {
  IngestSummary,
  MergedPlayer,
  Player,
  Projection,
} from "@/lib/domain/types";
import {
  PlayerCsvSchema,
  ProjectionCsvSchema,
  PLAYER_ALIASES,
  PROJ_ALIASES,
} from "@/lib/ingest/schemas";
import { parseCsvStream } from "@/lib/ingest/parse";
import { mergePlayers, normalizePlayers, normalizeProjections } from "@/lib/ingest/normalize";

type Status = "idle" | "parsing" | "ready" | "error";

type IngestError = { file: "players" | "projections" | "unknown"; row: number; message: string };

type State = {
  status: Status;
  players: Player[];
  projections: Projection[];
  merged: MergedPlayer[];
  summary: IngestSummary | null;
  errors: IngestError[];
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
  reset: () => set({ status: "idle", players: [], projections: [], merged: [], summary: null, errors: [] }),
  ingestCsv: async (file: File) => {
    set({ status: "parsing" });
    const kind = guessKind(file);

    try {
      if (kind === "players") {
        const rep = await parseCsvStream(file, PlayerCsvSchema, keyToLower(PLAYER_ALIASES));
        const players = normalizePlayers(rep.rows);
        const nextSummary = { ...(get().summary ?? initSummary()) };
        nextSummary.rows_players = rep.rowCount;
        nextSummary.dropped_players = rep.droppedRows;
        nextSummary.unknown_cols_players = rep.unknownColumns;
        const merged = mergePlayers(players, get().projections);
        set({ players, merged, summary: nextSummary, status: "ready" });
      } else if (kind === "projections") {
        const rep = await parseCsvStream(file, ProjectionCsvSchema, keyToLower(PROJ_ALIASES));
        const projections = normalizeProjections(rep.rows);
        const nextSummary = { ...(get().summary ?? initSummary()) };
        nextSummary.rows_projections = rep.rowCount;
        nextSummary.dropped_projections = rep.droppedRows;
        nextSummary.unknown_cols_projections = rep.unknownColumns;
        const merged = mergePlayers(get().players, projections);
        set({ projections, merged, summary: nextSummary, status: "ready" });
      } else {
        // Fallback: try projections first then players
        try {
          const repP = await parseCsvStream(file, ProjectionCsvSchema, keyToLower(PROJ_ALIASES));
          if (repP.rows.length > 0) {
            const projections = normalizeProjections(repP.rows);
            const nextSummary = { ...(get().summary ?? initSummary()) };
            nextSummary.rows_projections = repP.rowCount;
            nextSummary.dropped_projections = repP.droppedRows;
            nextSummary.unknown_cols_projections = repP.unknownColumns;
            const merged = mergePlayers(get().players, projections);
            set({ projections, merged, summary: nextSummary, status: "ready" });
            return;
          }
        } catch {}
        const repPl = await parseCsvStream(file, PlayerCsvSchema, keyToLower(PLAYER_ALIASES));
        const players = normalizePlayers(repPl.rows);
        const nextSummary = { ...(get().summary ?? initSummary()) };
        nextSummary.rows_players = repPl.rowCount;
        nextSummary.dropped_players = repPl.droppedRows;
        nextSummary.unknown_cols_players = repPl.unknownColumns;
        const merged = mergePlayers(players, get().projections);
        set({ players, merged, summary: nextSummary, status: "ready" });
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

