import type { MergedPlayer } from "@/lib/domain/types";
import { eligibleForSlot, withinTeamCap } from "@/lib/opt/constraints";
import type { Lineup, OptimizationRequest, OptimizationResult, Slot } from "@/lib/opt/types";

type ProgressCb = (tried: number, valid: number) => void;

// Simple LCG for deterministic RNG without deps
function makeRng(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    // Constants from Numerical Recipes
    s = (1664525 * s + 1013904223) >>> 0;
    return (s & 0xffffffff) / 0x100000000;
  };
}

function seedToInt(seed: string | number): number {
  if (typeof seed === "number") return seed;
  let h = 2166136261 >>> 0; // FNV-1a basis
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function scoreLineup(line: Lineup, byId: Map<string, MergedPlayer>): number {
  let s = 0;
  for (const { player_id_dk } of line.slots) s += byId.get(player_id_dk)?.proj_fp ?? 0;
  return s;
}

function computeSalary(line: Lineup, byId: Map<string, MergedPlayer>): number {
  let s = 0;
  for (const { player_id_dk } of line.slots) s += byId.get(player_id_dk)?.salary ?? 0;
  return s;
}

function pick<T>(arr: T[], rng: () => number): T | undefined {
  if (arr.length === 0) return undefined;
  const i = Math.floor(rng() * arr.length);
  return arr[i];
}

function lineupKey(playerIds: string[]): string {
  return playerIds.slice().sort().join("|");
}

export function greedyRandom(
  req: OptimizationRequest,
  onProgress?: ProgressCb
): OptimizationResult {
  const rng = makeRng(seedToInt(req.seed));
  const { salaryCap, slots, maxPerTeam } = req.config;
  const byId = new Map(req.players.map((p) => [p.player_id_dk, p] as const));
  const eligibleBySlot: Record<Slot, MergedPlayer[]> = Object.fromEntries(
    slots.map((s) => [s, req.players.filter((p) => eligibleForSlot(p, s))])
  ) as any;

  const target = Math.max(1, req.targetLineups);
  const maxCand = Math.max(target * 2, req.maxCandidates ?? target * 200);
  let tried = 0;
  let valid = 0;
  const out: Lineup[] = [];
  const seen = new Set<string>();

  while (tried < maxCand && out.length < target) {
    tried++;
    const used = new Set<string>();
    const teamCounts: Record<string, number> = {};
    const picked: { slot: Slot; player_id_dk: string }[] = [];
    let ok = true;
    let runningSalary = 0;

    for (const sl of slots) {
      const pool = eligibleBySlot[sl].filter((p) => !used.has(p.player_id_dk) && withinTeamCap(teamCounts, p.team, maxPerTeam));
      // prune by salary: keep only those that fit now
      const affordable = pool.filter((p) => runningSalary + p.salary <= salaryCap);
      const choice = pick(affordable.length > 0 ? affordable : pool, rng);
      if (!choice) {
        ok = false;
        break;
      }
      used.add(choice.player_id_dk);
      teamCounts[choice.team] = (teamCounts[choice.team] ?? 0) + 1;
      runningSalary += choice.salary;
      picked.push({ slot: sl, player_id_dk: choice.player_id_dk });
      if (runningSalary > salaryCap) {
        ok = false;
        break;
      }
    }

    if (!ok) {
      if (onProgress && tried % 250 === 0) onProgress(tried, valid);
      continue;
    }

    const line: Lineup = {
      id: lineupKey(picked.map((x) => x.player_id_dk)),
      slots: picked,
      salary: runningSalary,
      score: 0,
    };
    if (line.salary > salaryCap) {
      if (onProgress && tried % 250 === 0) onProgress(tried, valid);
      continue;
    }
    const key = line.id;
    if (seen.has(key)) {
      if (onProgress && tried % 250 === 0) onProgress(tried, valid);
      continue;
    }
    seen.add(key);
    line.score = scoreLineup(line, byId);
    line.salary = computeSalary(line, byId);
    out.push(line);
    valid++;
    if (onProgress && valid % 25 === 0) onProgress(tried, valid);
  }

  // sort by score desc
  out.sort((a, b) => b.score - a.score);
  const bestScore = out[0]?.score ?? 0;
  return {
    lineups: out,
    summary: { tried, valid, bestScore, elapsedMs: 0 },
  };
}

