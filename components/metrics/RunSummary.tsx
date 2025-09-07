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
    </div>
  );
}

