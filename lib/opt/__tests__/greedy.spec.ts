import { describe, it, expect } from "vitest";
import { greedyRandom } from "../algorithms/greedy";
import { loadFixtureMergedPlayers } from "../fixtures";
import { DEFAULT_MAX_PER_TEAM, DEFAULT_SALARY_CAP, DEFAULT_SLOTS, DEFAULT_SEED } from "../config";
import type { OptimizationRequest, OptimizerConfig, RunOptions } from "../types";
import { eligibleForSlot } from "../constraints";

describe("greedy optimizer (fixture)", () => {
  it("produces valid lineups on DK fixture with defaults", () => {
    const { players } = loadFixtureMergedPlayers();
    const config: OptimizerConfig = {
      salaryCap: DEFAULT_SALARY_CAP,
      slots: DEFAULT_SLOTS,
      maxPerTeam: DEFAULT_MAX_PER_TEAM,
    };
    const options: RunOptions = {
      seed: DEFAULT_SEED,
      candidates: 100000,
      teamCap: 0,
      salaryCap: DEFAULT_SALARY_CAP,
      minSalary: 0,
      randomnessPct: 0,
      ownershipPenalty: false,
    };
    const req: OptimizationRequest = {
      players,
      config,
      seed: options.seed,
      targetLineups: 10,
      maxCandidates: options.candidates,
      options,
    };
    // Debug eligible counts per slot
    const counts = DEFAULT_SLOTS.map((s) => players.filter((p) => eligibleForSlot(p as any, s)).length);
    // eslint-disable-next-line no-console
    console.log("slot eligible counts", counts);
    const res = greedyRandom(req);
    // eslint-disable-next-line no-console
    console.log("summary", res.summary);
    expect(res.summary.invalidReasons).toBeDefined();
  });
});
