"use client";

import { create } from "zustand";
import type { Lineup, OptimizationResult, OptimizerConfig } from "@/lib/opt/types";
import { runInWorker } from "@/lib/opt/run";
import { useIngestStore } from "@/lib/state/ingest-store";
import { DEFAULT_MAX_PER_TEAM, DEFAULT_SALARY_CAP, DEFAULT_SEED, DEFAULT_SLOTS, USE_FIXTURE_FALLBACK } from "@/lib/opt/config";
import { loadFixtureMergedPlayers } from "@/lib/opt/fixtures";

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
  salaryCap: DEFAULT_SALARY_CAP,
  slots: DEFAULT_SLOTS,
  maxPerTeam: DEFAULT_MAX_PER_TEAM,
};

export const useRunStore = create<State>((set, get) => ({
  status: "idle",
  lineups: [],
  summary: null,
  tried: 0,
  valid: 0,
  error: null,
  reset: () => set({ status: "idle", lineups: [], summary: null, tried: 0, valid: 0, error: null }),
  run: async ({ seed = DEFAULT_SEED, target = 100, config = {} } = {}) => {
    let players = useIngestStore.getState().merged;
    let usingFixtureDate: string | null = null;
    if (!players || players.length === 0) {
      if (USE_FIXTURE_FALLBACK) {
        const { date, players: arr } = loadFixtureMergedPlayers();
        players = arr;
        usingFixtureDate = date;
      } else {
        set({ status: "error", error: "No players loaded. Upload CSVs or enable fixture fallback." });
        return;
      }
    }
    const cfg: OptimizerConfig = { ...DEFAULT_CONFIG, ...config, slots: (config.slots as any) ?? DEFAULT_CONFIG.slots };
    set({ status: "running", tried: 0, valid: 0, error: null, lineups: [], summary: null });
    try {
      const { promise } = runInWorker(players, cfg, seed, target, (evt) => {
        if (evt.type === "progress") set({ tried: evt.tried, valid: evt.valid });
      });
      const res = await promise;
      if (usingFixtureDate) res.summary.usingFixtureDate = usingFixtureDate;
      set({ status: "done", lineups: res.lineups, summary: res.summary });
    } catch (e: any) {
      set({ status: "error", error: e?.message ?? String(e) });
    }
  },
}));
