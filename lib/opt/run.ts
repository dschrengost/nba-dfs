"use client";

import type { MergedPlayer } from "@/lib/domain/types";
import type { OptimizationRequest, OptimizationResult, OptimizerConfig, RunOptions, WorkerMessageOut } from "@/lib/opt/types";

export type RunHandle = { cancel: () => void };

async function runViaPython(
  players: any[],
  config: OptimizerConfig,
  seed: string | number,
  targetLineups: number,
  onEvent?: (msg: WorkerMessageOut) => void,
  options?: RunOptions
): Promise<OptimizationResult> {
  const body = {
    site: "dk",
    enginePreferred: "cp_sat",
    constraints: {
      N_lineups: targetLineups,
      max_salary: options?.salaryCap ?? config.salaryCap,
      min_salary: options?.minSalary ?? undefined,
      global_team_limit: options?.teamCap ?? config.maxPerTeam,
      randomness_pct: options?.randomnessPct ?? 0,
      ownership_penalty: options?.ownershipPenalty ? { enabled: true } : { enabled: false },
      cp_sat_params: { random_seed: Number(seed) || 0 },
    },
    players: players.map((p) => ({
      name: p.player_name,
      team: p.team,
      position: [p.pos_primary, p.pos_secondary].filter(Boolean).join("/"),
      salary: p.salary,
      proj_fp: p.proj_fp,
      own_proj: p.ownership ?? null,
      dk_id: p.player_id_dk,
    })),
    seed: Number(seed) || 0,
  };
  onEvent?.({ type: "started", at: Date.now() });
  const t0 = performance.now();
  const resp = await fetch("/api/optimize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`Optimizer service error: ${resp.status} ${txt}`);
  }
  const data = await resp.json();
  if (!data.ok) {
    throw new Error(data.error || "Optimization failed");
  }
  const lineups = (data.lineups as any[]).map((lu) => ({
    id: String(lu.lineup_id),
    slots: (lu.players as any[]).map((pl) => ({
      slot: pl.pos,
      player_id_dk: pl.dk_id ?? pl.player_id,
      name: pl.name,
      team: pl.team,
      salary: pl.salary,
      own_proj: pl.own_proj,
      pos: pl.pos,
    })),
    salary: lu.total_salary,
    score: lu.total_proj,
  }));
  const elapsedMs = Math.round(performance.now() - t0);
  onEvent?.({ type: "done", res: { lineups, summary: {
    tried: data.summary?.tried ?? lineups.length,
    valid: data.summary?.valid ?? lineups.length,
    bestScore: lineups.reduce((m, l) => Math.max(m, l.score), 0),
    elapsedMs,
    engineUsed: data.engineUsed,
    diagnostics: data.diagnostics,
    optionsUsed: options,
    invalidReasons: data.summary?.invalidReasons ?? { salary: 0, slots: 0, teamcap: 0, dup: 0 },
  }}});
  return { lineups, summary: {
    tried: data.summary?.tried ?? lineups.length,
    valid: data.summary?.valid ?? lineups.length,
    bestScore: lineups.reduce((m, l) => Math.max(m, l.score), 0),
    elapsedMs,
    engineUsed: data.engineUsed,
    diagnostics: data.diagnostics,
    optionsUsed: options,
    invalidReasons: data.summary?.invalidReasons ?? { salary: 0, slots: 0, teamcap: 0, dup: 0 },
  }};
}

export function runInWorker(
  players: MergedPlayer[],
  config: OptimizerConfig,
  seed: string | number,
  targetLineups: number,
  onEvent?: (msg: WorkerMessageOut) => void,
  options?: RunOptions
): { handle: RunHandle; promise: Promise<OptimizationResult> } {
  const mode = (process.env.NEXT_PUBLIC_DFS_SOLVER_MODE || process.env.DFS_SOLVER_MODE || "python").toLowerCase();
  if (mode === "python") {
    // Orchestrate via server API → Python CLI
    const promise = runViaPython(players as any[], config, seed, targetLineups, onEvent, options);
    return {
      handle: { cancel() { /* noop (not yet supported) */ } },
      promise,
    };
  } else {
    const worker = new Worker(new URL("../../workers/optimizer.worker.ts", import.meta.url));
    let done = false;
    const promise = new Promise<OptimizationResult>((resolve, reject) => {
      worker.onmessage = (ev: MessageEvent<WorkerMessageOut>) => {
        const msg = ev.data;
        onEvent?.(msg);
        if (msg.type === "error") {
          if (!done) {
            done = true;
            worker.terminate();
            reject(new Error(msg.message));
          }
        } else if (msg.type === "done") {
          if (!done) {
            done = true;
            worker.terminate();
            resolve(msg.res);
          }
        }
      };
      const req: OptimizationRequest = {
        players,
        config,
        seed: options?.seed ?? seed,
        targetLineups,
        maxCandidates: options?.candidates,
        options,
      };
      worker.postMessage({ type: "run", req });
    });
    return {
      handle: {
        cancel() {
          if (!done) worker.postMessage({ type: "cancel" });
        },
      },
      promise,
    };
  }
}
