"use client";

import { create } from "zustand";
import type { Lineup, OptimizationResult, OptimizerConfig, RunOptions } from "@/lib/opt/types";
import { runInWorker } from "@/lib/opt/run";
import { useIngestStore } from "@/lib/state/ingest-store";
import {
  DEFAULT_CANDIDATES,
  DEFAULT_MAX_PER_TEAM,
  DEFAULT_MIN_SALARY,
  DEFAULT_OWNERSHIP_PENALTY,
  DEFAULT_RANDOMNESS_PCT,
  DEFAULT_SALARY_CAP,
  DEFAULT_SEED,
  DEFAULT_SLOTS,
  USE_FIXTURE_FALLBACK,
} from "@/lib/opt/config";
import { loadFixtureMergedPlayers } from "@/lib/opt/fixtures";

type Status = "idle" | "running" | "done" | "error";

type State = {
  status: Status;
  lineups: Lineup[];
  summary: OptimizationResult["summary"] | null;
  tried: number;
  valid: number;
  error?: string | null;
  options: RunOptions;
  setOptions: (patch: Partial<RunOptions>) => void;
  run: (opts?: { target?: number; config?: Partial<OptimizerConfig> }) => Promise<void>;
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
  options: {
    seed: DEFAULT_SEED,
    candidates: DEFAULT_CANDIDATES,
    teamCap: DEFAULT_MAX_PER_TEAM,
    salaryCap: DEFAULT_SALARY_CAP,
    minSalary: DEFAULT_MIN_SALARY,
    randomnessPct: DEFAULT_RANDOMNESS_PCT,
    ownershipPenalty: DEFAULT_OWNERSHIP_PENALTY,
  },
  setOptions: (patch) =>
    set((s) => ({ options: { ...s.options, ...patch } })),
  reset: () => set({ status: "idle", lineups: [], summary: null, tried: 0, valid: 0, error: null }),
  run: async ({ target = 100, config = {} } = {}) => {
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
    const opts = get().options;
    // Merge display config with options for this run
    const cfg: OptimizerConfig = {
      ...DEFAULT_CONFIG,
      ...config,
      salaryCap: opts.salaryCap ?? DEFAULT_CONFIG.salaryCap,
      maxPerTeam: opts.teamCap ?? DEFAULT_CONFIG.maxPerTeam,
      slots: (config.slots as any) ?? DEFAULT_CONFIG.slots,
    };
    set({ status: "running", tried: 0, valid: 0, error: null, lineups: [], summary: null });
    try {
      const { promise } = runInWorker(players, cfg, String(opts.seed), target, (evt) => {
        if (evt.type === "progress") set({ tried: evt.tried, valid: evt.valid });
      }, opts);
      const res = await promise;
      if (usingFixtureDate) res.summary.usingFixtureDate = usingFixtureDate;
      set({ status: "done", lineups: res.lineups, summary: res.summary });
    } catch (e: any) {
      set({ status: "error", error: e?.message ?? String(e) });
    }
  },
}));
