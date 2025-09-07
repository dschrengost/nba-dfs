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
  runSolve: (inputs: {
    site: "dk" | "fd";
    projectionsPath: string;
    playerIdsPath?: string;
    nLineups: number;
    minUniques?: number;
    penaltyEnabled: boolean;
    lambdaVal?: number;
    penaltyCurve?: "linear" | "g_curve";
    dropIntensity?: number; // 0.0 - 0.5
    seed?: number;
    sigma?: number; // 0.0 - 0.25
  }) => Promise<void>;
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
  setOptions: (patch) => set((s) => ({ options: { ...s.options, ...patch } })),
  reset: () => set({ status: "idle", lineups: [], summary: null, tried: 0, valid: 0, error: null }),

  // Legacy/worker-based run (kept for dev)
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
    const cfg: OptimizerConfig = {
      ...DEFAULT_CONFIG,
      ...config,
      salaryCap: opts.salaryCap ?? DEFAULT_CONFIG.salaryCap,
      maxPerTeam: opts.teamCap ?? DEFAULT_CONFIG.maxPerTeam,
      slots: (config.slots as any) ?? DEFAULT_CONFIG.slots,
    };
    set({ status: "running", tried: 0, valid: 0, error: null, lineups: [], summary: null });
    try {
      const { promise } = runInWorker(
        players,
        cfg,
        String(opts.seed),
        target,
        (evt) => {
          if (evt.type === "progress") set({ tried: evt.tried, valid: evt.valid });
        },
        opts
      );
      const res = await promise;
      if (usingFixtureDate) res.summary.usingFixtureDate = usingFixtureDate;
      set({ status: "done", lineups: res.lineups, summary: res.summary });
    } catch (e: any) {
      set({ status: "error", error: e?.message ?? String(e) });
    }
  },

  // New path-first runner that posts to /api/optimize (Python wrapper)
  runSolve: async (inputs) => {
    const {
      site,
      projectionsPath,
      playerIdsPath,
      nLineups,
      minUniques = 1,
      penaltyEnabled,
      lambdaVal = 0,
      penaltyCurve = "linear",
      dropIntensity = 0,
      seed = 42,
      sigma = 0,
    } = inputs || ({} as any);

    set({ status: "running", tried: 0, valid: 0, error: null, lineups: [], summary: null });

    const ownership_penalty = penaltyEnabled
      ? {
          enabled: true,
          // Always use by_points for backend; express curve via curve_type
          mode: "by_points",
          weight_lambda: Number(lambdaVal) || 0,
          curve_type: penaltyCurve === "g_curve" ? "sigmoid" : "linear",
        }
      : { enabled: false } as const;

    // Inline players fallback from ingest store when paths are not provided
    const merged = useIngestStore.getState().merged || [];
    const useInlinePlayers = (!projectionsPath || String(projectionsPath).trim() === "") && merged.length > 0;

    const body: any = {
      site,
      enginePreferred: "cp_sat",
      constraints: {
        N_lineups: Math.max(1, Number(nLineups) || 5),
        unique_players: Math.max(0, Math.min(5, Number(minUniques) || 0)),
        ownership_penalty,
        pruning: { drop_pct: Math.max(0, Math.min(0.5, Number(dropIntensity) || 0)) },
        randomness_pct: Math.round((Number(sigma) || 0) * 100),
      },
      seed: Number(seed) || 42,
      projectionsPath,
      playerIdsPath,
    };
    if (useInlinePlayers) {
      body.players = merged.map((p: any) => ({
        name: p.player_name,
        team: p.team,
        position: [p.pos_primary, p.pos_secondary].filter(Boolean).join("/"),
        salary: p.salary,
        proj_fp: p.proj_fp,
        own_proj: p.ownership ?? null,
        dk_id: p.player_id_dk,
      }));
    }

    try {
      const res = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok || !data?.ok) {
        throw new Error(data?.error || `Request failed (${res.status})`);
      }

      // Map backend lineups -> UI shape
      const lineups = (Array.isArray(data.lineups) ? data.lineups : []).map((lu: any) => ({
        id: String(lu.lineup_id ?? lu.id ?? Math.random().toString(36).slice(2)),
        slots: (Array.isArray(lu.players) ? lu.players : []).map((pl: any) => ({
          slot: pl.pos ?? pl.position ?? "UTIL",
          player_id_dk: pl.dk_id ?? pl.player_id,
          name: pl.name,
          team: pl.team,
          salary: pl.salary,
          own_proj: pl.own_proj,
          pos: pl.pos ?? pl.position,
        })),
        salary: Number(lu.total_salary ?? 0),
        score: Number(lu.total_proj ?? 0),
      }));
      set({
        status: "done",
        lineups,
        summary: {
          ...data.summary,
          valid: lineups.length,
          tried: data.diagnostics?.N ?? data.summary?.tried ?? lineups.length,
          elapsedMs:
            data.summary?.elapsedMs ?? (data.diagnostics?.wall_time_sec ? Math.round(1000 * data.diagnostics.wall_time_sec) : 0),
          bestScore: data.summary?.bestScore ?? (lineups.reduce((m: number, l: any) => Math.max(m, Number(l.score || 0)), 0)),
          engineUsed: data.engineUsed ?? data.diagnostics?.engine,
          diagnostics: data.diagnostics,
        },
      });

      // Toast warnings
      try {
        const { toast } = await import("@/components/ui/sonner");
        const matched = data.diagnostics?.matched_players;
        if (typeof matched === "number" && matched < 90) {
          (toast as any).warning?.("Low DK ID match rate; check playerIdsPath") ||
            (toast as any).warn?.("Low DK ID match rate; check playerIdsPath") ||
            toast("Low DK ID match rate; check playerIdsPath");
        }
        const ownMax =
          data.diagnostics?.normalization?.ownership?.max_after ??
          data.diagnostics?.normalization?.ownership?.own_max_after ?? 0;
        if (ownership_penalty.enabled && (ownMax ?? 0) === 0) {
          (toast as any).info?.("Ownerships are all 0; penalty has no effect") ||
            toast("Ownerships are all 0; penalty has no effect");
        }
      } catch {
        // no-op if toast not available
      }
    } catch (e: any) {
      set({ status: "error", error: e?.message ?? String(e) });
      try {
        const { toast } = await import("@/components/ui/sonner");
        (toast as any).error?.(String(e?.message ?? e)) || toast(String(e?.message ?? e));
      } catch {}
    }
  },
}));
