import type { MergedPlayer } from "@/lib/domain/types";

export type Slot =
  | "PG"
  | "SG"
  | "SF"
  | "PF"
  | "C"
  | "G"
  | "F"
  | "UTIL";

export type OptimizerConfig = {
  salaryCap: number;
  slots: Slot[]; // order matters
  maxPerTeam?: number; // optional cap per NBA team
};

export type OptimizationRequest = {
  players: MergedPlayer[];
  config: OptimizerConfig;
  seed: string | number;
  targetLineups: number; // how many valid lineups to produce
  maxCandidates?: number; // optional limit on candidates sampled
};

export type Lineup = {
  id: string;
  slots: { slot: Slot; player_id_dk: string }[]; // length === config.slots.length
  salary: number;
  score: number; // sum of proj_fp or objective value
};

export type RunSummary = {
  tried: number; // number of candidates evaluated
  valid: number; // number of valid lineups produced
  bestScore: number;
  elapsedMs: number;
  usingFixtureDate?: string | null; // present when fixture fallback was used
};

export type OptimizationResult = {
  lineups: Lineup[];
  summary: RunSummary;
};

export type WorkerMessageIn =
  | { type: "run"; req: OptimizationRequest }
  | { type: "cancel" };

export type WorkerMessageOut =
  | { type: "started"; at: number }
  | { type: "progress"; tried: number; valid: number }
  | { type: "error"; message: string }
  | { type: "done"; res: OptimizationResult };

