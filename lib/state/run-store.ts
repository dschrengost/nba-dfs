"use client";

import { create } from "zustand";
import type { Lineup, OptimizationResult, OptimizerConfig } from "@/lib/opt/types";
import { runInWorker } from "@/lib/opt/run";
import { useIngestStore } from "@/lib/state/ingest-store";

type Status = "idle" | "running" | "done" | "error";

type State = {
  status: Status;
  lineups: Lineup[];
  summary: OptimizationResult["summary"] | null;
  tried: number;
  valid: number;
  error?: string | null;
  run: (opts?: { seed?: string | number; target?: number; config?: Partial<OptimizerConfig> }) => Promise<void>;
  reset: () => void;
};

const DEFAULT_CONFIG: OptimizerConfig = {
  salaryCap: 50000,
  slots: ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"],
  maxPerTeam: 3,
};

export const useRunStore = create<State>((set, get) => ({
  status: "idle",
  lineups: [],
  summary: null,
  tried: 0,
  valid: 0,
  error: null,
  reset: () => set({ status: "idle", lineups: [], summary: null, tried: 0, valid: 0, error: null }),
  run: async ({ seed = "opt-seed", target = 100, config = {} } = {}) => {
    const players = useIngestStore.getState().merged;
    if (!players || players.length === 0) {
      // No players loaded; will be wired to fixture fallback in T6
      set({ status: "error", error: "No players loaded. Upload CSVs or enable fixture fallback." });
      return;
    }
    const cfg: OptimizerConfig = { ...DEFAULT_CONFIG, ...config, slots: (config.slots as any) ?? DEFAULT_CONFIG.slots };
    set({ status: "running", tried: 0, valid: 0, error: null, lineups: [], summary: null });
    try {
      const { promise } = runInWorker(players, cfg, seed, target, (evt) => {
        if (evt.type === "progress") set({ tried: evt.tried, valid: evt.valid });
      });
      const res = await promise;
      set({ status: "done", lineups: res.lineups, summary: res.summary });
    } catch (e: any) {
      set({ status: "error", error: e?.message ?? String(e) });
    }
  },
}));

