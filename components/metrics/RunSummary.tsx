"use client";

import { useRunStore } from "@/lib/state/run-store";

export default function RunSummary() {
  const { summary } = useRunStore();
  if (!summary) return null;

  // Diagnostics payload (backend sidecar)
  const d: any = (summary as any).diagnostics || {};

  // Helper: coerce numeric-like values to numbers (or undefined)
  const toNum = (v: unknown): number | undefined => {
    const n = typeof v === "string" ? Number(v) : (v as number);
    return Number.isFinite(n as number) ? (n as number) : undefined;
  };

  // Pool metrics (emitted by CLI)
  const rawPool = d?.pool as
    | {
        lineups?: number | string;
        avg_overlap_players?: number | string;
        avg_pairwise_jaccard?: number | string;
        unique_player_count?: number | string;
      }
    | undefined;

  const pool = rawPool
    ? {
        lineups: toNum(rawPool.lineups),
        avg_overlap_players: toNum(rawPool.avg_overlap_players),
        avg_pairwise_jaccard: toNum(rawPool.avg_pairwise_jaccard),
        unique_player_count: toNum(rawPool.unique_player_count),
      }
    : undefined;

  // Badges (λ / curve / drop / uniques)
  const lamUsed =
    d?.ownership_penalty?.lambda_used ??
    d?.wiring_check?.objective?.lambda_ui ??
    d?.ownership_penalty?.weight_lambda;

  const curveLabel =
    d?.ownership_penalty?.curve_type ||
    d?.ownership_penalty?.curve ||
    d?.ownership_penalty?.mode ||
    undefined;

  const dropPct =
    d?.constraints?.pruning?.drop_pct ??
    d?.constraints_raw?.pruning?.drop_pct;

  const uniques =
    d?.constraints?.unique_players ??
    d?.constraints_raw?.unique_players ??
    (summary as any)?.optionsUsed?.unique_players;

  // Settings block — normalize / provide fallbacks
  const opts: any = (summary as any).optionsUsed || {};

  const seed =
    opts.seed ?? d?.seed ?? (summary as any).seed ?? undefined;

  const candidates =
    opts.candidates ??
    (typeof summary.tried === "number" ? summary.tried : undefined);

  const teamCap =
    opts.teamCap ??
    d?.constraints?.global_team_limit ??
    d?.constraints_raw?.global_team_limit ??
    d?.constraints_raw?.team_cap ??
    undefined;

  const salaryCap =
    opts.salaryCap ??
    d?.constraints?.max_salary ??
    d?.constraints_raw?.max_salary ??
    undefined;

  const minSalary =
    opts.minSalary ??
    d?.constraints?.min_salary ??
    d?.constraints_raw?.min_salary ??
    undefined;

  const randomnessPctRaw =
    opts.randomnessPct ??
    d?.constraints?.randomness_pct ??
    d?.constraints_raw?.randomness_pct ??
    0;

  // Accept 0–1 or 0–100, render as 0–100
  const randomnessPct =
    typeof randomnessPctRaw === "number"
      ? randomnessPctRaw <= 1
        ? Math.round(randomnessPctRaw * 100)
        : Math.round(randomnessPctRaw)
      : 0;

  const ownershipPenaltyOn =
    typeof opts.ownershipPenalty === "boolean"
      ? opts.ownershipPenalty
      : !!d?.ownership_penalty?.enabled;

  return (
    <div className="text-sm">
      <div className="flex items-center gap-2">
        <div className="font-medium">Optimizer Run</div>

        {summary.engineUsed ? (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            Engine: {summary.engineUsed === "cp_sat" ? "CP-SAT" : "CBC"}
          </span>
        ) : null}

        {summary.usingFixtureDate ? (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
            Fixture: {summary.usingFixtureDate}
          </span>
        ) : null}

        {typeof lamUsed === "number" ? (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-400 border border-sky-500/30">
            λ={lamUsed}
          </span>
        ) : null}

        {curveLabel ? (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
            curve={String(curveLabel)}
          </span>
        ) : null}

        {typeof dropPct === "number" ? (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-fuchsia-500/15 text-fuchsia-400 border border-fuchsia-500/30">
            drop={(dropPct * 100).toFixed(0)}%
          </span>
        ) : null}

        {typeof uniques === "number" ? (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-500/15 text-teal-400 border border-teal-500/30">
            uniques={uniques}
          </span>
        ) : null}
      </div>

      {pool && (
        <div className="mt-2" data-testid="pool-metrics">
          <div className="text-xs font-medium opacity-80">Inputs / Outputs</div>
          <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div className="flex justify-between">
              <dt className="opacity-70">Lineups</dt>
              <dd>{typeof pool.lineups === "number" ? pool.lineups : "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="opacity-70">Unique players</dt>
              <dd>
                {typeof pool.unique_player_count === "number"
                  ? pool.unique_player_count
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="opacity-70">Avg overlap (players)</dt>
              <dd>
                {typeof pool.avg_overlap_players === "number"
                  ? pool.avg_overlap_players.toFixed(2)
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="opacity-70">Avg Jaccard</dt>
              <dd>
                {typeof pool.avg_pairwise_jaccard === "number"
                  ? pool.avg_pairwise_jaccard.toFixed(3)
                  : "—"}
              </dd>
            </div>
          </dl>
        </div>
      )}

      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div className="flex justify-between">
          <dt className="opacity-70">Candidates tried</dt>
          <dd>{summary.tried}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="opacity-70">Valid lineups</dt>
          <dd>{summary.valid}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="opacity-70">Best score</dt>
          <dd>{summary.bestScore.toFixed(2)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="opacity-70">Elapsed</dt>
          <dd>{summary.elapsedMs} ms</dd>
        </div>
      </dl>

      <div className="mt-3">
        <div className="text-xs font-medium opacity-80">Settings</div>
        <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <div className="flex justify-between">
            <dt className="opacity-70">Seed</dt>
            <dd>{seed ?? "—"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="opacity-70">Candidates</dt>
            <dd>{candidates ?? "—"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="opacity-70">Team cap</dt>
            <dd>{teamCap ?? "—"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="opacity-70">Salary cap</dt>
            <dd>{salaryCap ?? "—"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="opacity-70">Min salary</dt>
            <dd>{minSalary ?? 0}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="opacity-70">Randomness %</dt>
            <dd>{randomnessPct}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="opacity-70">Ownership penalty</dt>
            <dd>{ownershipPenaltyOn ? "on" : "off"}</dd>
          </div>
        </dl>
      </div>

      {summary.invalidReasons ? (
        <div className="mt-3">
          <div className="text-xs font-medium opacity-80">Invalid reasons</div>
          <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div className="flex justify-between">
              <dt className="opacity-70">Salary</dt>
              <dd>{summary.invalidReasons.salary}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="opacity-70">Slots</dt>
              <dd>{summary.invalidReasons.slots}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="opacity-70">Team cap</dt>
              <dd>{summary.invalidReasons.teamcap}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="opacity-70">Duplicate</dt>
              <dd>{summary.invalidReasons.dup}</dd>
            </div>
          </dl>
        </div>
      ) : null}
    </div>
  );
}