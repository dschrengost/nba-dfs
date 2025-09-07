"use client";

import { useRunStore } from "@/lib/state/run-store";

export default function RunSummary() {
  const { summary, tried, valid } = useRunStore();
  if (!summary) return null;
  return (
    <div className="text-sm">
      <div className="flex items-center gap-2">
        <div className="font-medium">Optimizer Run</div>
        {summary.usingFixtureDate ? (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
            Fixture: {summary.usingFixtureDate}
          </span>
        ) : null}
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div className="flex justify-between"><dt className="opacity-70">Candidates tried</dt><dd>{tried}</dd></div>
        <div className="flex justify-between"><dt className="opacity-70">Valid lineups</dt><dd>{valid}</dd></div>
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
