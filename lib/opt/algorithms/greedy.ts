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

function scoreLineup(
  line: Lineup,
  byId: Map<string, MergedPlayer>,
  randomnessPct = 0,
  ownershipPenalty = false
): number {
  let s = 0;
  const noise = Math.max(0, Math.min(100, randomnessPct)) / 100;
  for (const { player_id_dk } of line.slots) {
    const p = byId.get(player_id_dk);
    if (!p) continue;
    let proj = p.proj_fp ?? 0;
    if (noise > 0) {
      // Uniform jitter in ±noise range (deterministic via id hash)
      const h = seedToInt(player_id_dk) % 1000;
      const u = (h / 1000) * 2 - 1; // [-1, 1)
      proj = proj * (1 + u * noise);
    }
    if (ownershipPenalty && p.ownership && p.ownership > 0) {
      // Minimal no-op-ish penalty: subtract a tiny fraction to keep behavior stable
      proj = proj - 0.0 * p.ownership; // intentionally 0 for now (plumb only)
    }
    s += proj;
  }
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

function getId(p: MergedPlayer): string {
  const id = (p as any).player_id_dk ?? null;
  if (id && String(id).trim() !== "") return String(id);
  // Fallback to name for fixtures without DK ID
  return String((p as any).player_name ?? (p as any).name ?? "");
}

export function greedyRandom(
  req: OptimizationRequest,
  onProgress?: ProgressCb
): OptimizationResult {
  const opts = req.options ?? ({} as any);
  const seed = (opts.seed ?? req.seed) as string | number;
  const rng = makeRng(seedToInt(seed));
  const salaryCap = (opts.salaryCap ?? req.config.salaryCap) as number;
  const slots = req.config.slots;
  const maxPerTeam = (opts.teamCap ?? req.config.maxPerTeam) as number | undefined;
  const minSalary = (opts.minSalary ?? 0) as number;
  const randomnessPct = (opts.randomnessPct ?? 0) as number;
  const ownershipPenalty = Boolean(opts.ownershipPenalty);
  const byId = new Map(req.players.map((p) => [getId(p), p] as const));
  const eligibleBySlot: Record<Slot, MergedPlayer[]> = Object.fromEntries(
    slots.map((s) => [s, req.players.filter((p) => eligibleForSlot(p, s))])
  ) as any;

  const target = Math.max(1, req.targetLineups);
  const maxCand = Math.max(
    target * 2,
    (req.maxCandidates ?? opts.candidates ?? target * 200) as number
  );
  let tried = 0;
  let valid = 0;
  const out: Lineup[] = [];
  const seen = new Set<string>();
  const reasons = { salary: 0, slots: 0, teamcap: 0, dup: 0 };

  while (tried < maxCand && out.length < target) {
    tried++;
    const used = new Set<string>();
    const teamCounts: Record<string, number> = {};
    const picked: { slot: Slot; player_id_dk: string }[] = [];
    let ok = true;
    let runningSalary = 0;

    for (const sl of slots) {
      const elig = eligibleBySlot[sl];
      const pool = elig.filter((p) => !used.has(getId(p)) && withinTeamCap(teamCounts, p.team, maxPerTeam));
      // prune by salary: keep only those that fit now
      const affordable = pool.filter((p) => runningSalary + p.salary <= salaryCap);
      const choice = pick(affordable.length > 0 ? affordable : pool, rng);
      if (!choice) {
        ok = false;
        // Diagnose reason if we can
        if (elig.length === 0) reasons.slots++;
        else if (pool.length === 0) reasons.teamcap++;
        else reasons.salary++;
        break;
      }
      used.add(getId(choice));
      teamCounts[choice.team] = (teamCounts[choice.team] ?? 0) + 1;
      runningSalary += choice.salary;
      picked.push({ slot: sl, player_id_dk: getId(choice) });
      if (runningSalary > salaryCap) {
        ok = false;
        reasons.salary++;
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
      reasons.salary++;
      if (onProgress && tried % 250 === 0) onProgress(tried, valid);
      continue;
    }
    if (minSalary && line.salary < minSalary) {
      reasons.salary++;
      if (onProgress && tried % 250 === 0) onProgress(tried, valid);
      continue;
    }
    const key = line.id;
    if (seen.has(key)) {
      reasons.dup++;
      if (onProgress && tried % 250 === 0) onProgress(tried, valid);
      continue;
    }
    seen.add(key);
    line.score = scoreLineup(line, byId, randomnessPct, ownershipPenalty);
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
    summary: {
      tried,
      valid,
      bestScore,
      elapsedMs: 0,
      optionsUsed: {
        seed,
        candidates: maxCand,
        teamCap: maxPerTeam ?? 0,
        salaryCap,
        minSalary: minSalary || 0,
        randomnessPct,
        ownershipPenalty,
      },
      invalidReasons: reasons,
    },
  };
}
