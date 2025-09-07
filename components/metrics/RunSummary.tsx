"use client";

import { useRunStore } from "@/lib/state/run-store";

export default function RunSummary() {
  const { summary } = useRunStore();
  if (!summary) return null;
  const d: any = (summary as any).diagnostics || {};
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
    (d?.constraints?.pruning?.drop_pct ?? d?.constraints_raw?.pruning?.drop_pct);
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
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div className="flex justify-between"><dt className="opacity-70">Candidates tried</dt><dd>{summary.tried}</dd></div>
        <div className="flex justify-between"><dt className="opacity-70">Valid lineups</dt><dd>{summary.valid}</dd></div>
        <div className="flex justify-between"><dt className="opacity-70">Best score</dt><dd>{summary.bestScore.toFixed(2)}</dd></div>
        <div className="flex justify-between"><dt className="opacity-70">Elapsed</dt><dd>{summary.elapsedMs} ms</dd></div>
      </dl>
      {summary.optionsUsed ? (
        <div className="mt-3">
          <div className="text-xs font-medium opacity-80">Settings</div>
          <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div className="flex justify-between"><dt className="opacity-70">Seed</dt><dd>{String(summary.optionsUsed.seed)}</dd></div>
            <div className="flex justify-between"><dt className="opacity-70">Candidates</dt><dd>{summary.optionsUsed.candidates}</dd></div>
            <div className="flex justify-between"><dt className="opacity-70">Team cap</dt><dd>{summary.optionsUsed.teamCap}</dd></div>
            <div className="flex justify-between"><dt className="opacity-70">Salary cap</dt><dd>{summary.optionsUsed.salaryCap}</dd></div>
            <div className="flex justify-between"><dt className="opacity-70">Min salary</dt><dd>{summary.optionsUsed.minSalary ?? 0}</dd></div>
            <div className="flex justify-between"><dt className="opacity-70">Randomness %</dt><dd>{summary.optionsUsed.randomnessPct ?? 0}</dd></div>
            <div className="flex justify-between"><dt className="opacity-70">Ownership penalty</dt><dd>{summary.optionsUsed.ownershipPenalty ? "on" : "off"}</dd></div>
          </dl>
        </div>
      ) : null}
      {summary.invalidReasons ? (
        <div className="mt-3">
          <div className="text-xs font-medium opacity-80">Invalid reasons</div>
          <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div className="flex justify-between"><dt className="opacity-70">Salary</dt><dd>{summary.invalidReasons.salary}</dd></div>
            <div className="flex justify-between"><dt className="opacity-70">Slots</dt><dd>{summary.invalidReasons.slots}</dd></div>
            <div className="flex justify-between"><dt className="opacity-70">Team cap</dt><dd>{summary.invalidReasons.teamcap}</dd></div>
            <div className="flex justify-between"><dt className="opacity-70">Duplicate</dt><dd>{summary.invalidReasons.dup}</dd></div>
          </dl>
        </div>
      ) : null}
    </div>
  );
}
