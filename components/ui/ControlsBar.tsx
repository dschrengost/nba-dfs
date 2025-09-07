"use client";

import { useEffect, useState } from "react";
import { Button } from "./button";
import { useRunStore } from "@/lib/state/run-store";
import type { GridMode } from "./LineupGridPlaceholder";
import { Input } from "./input";

export default function ControlsBar({
  gridMode,
  onGridModeChange,
}: {
  gridMode?: GridMode;
  onGridModeChange?: (m: GridMode) => void;
}) {
  const { status, run, reset, options, setOptions, runSolve } = useRunStore();
  const showDev = process.env.NODE_ENV !== "production" && onGridModeChange;

  // New UX controls state
  const [nLineups, setNLineups] = useState<number>(5);
  const [penaltyEnabled, setPenaltyEnabled] = useState<boolean>(false);
  const [lambdaVal, setLambdaVal] = useState<number>(8);
  const [penaltyCurve, setPenaltyCurve] = useState<"linear" | "g_curve">("linear");
  const [dropIntensity, setDropIntensity] = useState<number>(0.2);
  const [seed, setSeed] = useState<number>(Number(options.seed) || 42);
  const [sigma, setSigma] = useState<number>(0.07);
  const [minUniques, setMinUniques] = useState<number>(1);
  const [projectionsPath, setProjectionsPath] = useState<string>("");
  const [playerIdsPath, setPlayerIdsPath] = useState<string>("");

  // Persist file paths
  useEffect(() => {
    try {
      const last = JSON.parse(localStorage.getItem("dfs_paths") ?? "{}");
      setProjectionsPath(last.projectionsPath ?? "");
      setPlayerIdsPath(last.playerIdsPath ?? "");
    } catch {}
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem("dfs_paths", JSON.stringify({ projectionsPath, playerIdsPath }));
    } catch {}
  }, [projectionsPath, playerIdsPath]);

  const onRunClick = () =>
    runSolve({
      site: "dk",
      projectionsPath,
      playerIdsPath,
      nLineups,
      minUniques,
      penaltyEnabled,
      lambdaVal,
      penaltyCurve,
      dropIntensity,
      seed,
      sigma,
    });

  return (
    <div className="h-auto w-full border-t border-border px-4 py-3 flex flex-col gap-3 bg-background">
      <div className="text-sm font-medium opacity-80">Controls / Knobs</div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 items-end">
        <div>
          <label className="block text-[11px] opacity-70 mb-1">Seed</label>
          <Input
            value={String(seed)}
            onChange={(e) => setSeed(Number(e.target.value || 0))}
            placeholder="seed"
          />
        </div>
        <div>
          <label className="block text-[11px] opacity-70 mb-1">Min uniques (0-5)</label>
          <Input
            type="number"
            value={Number(minUniques)}
            onChange={(e) => setMinUniques(Math.max(0, Math.min(5, Number(e.target.value || 0))))}
            min={0}
            max={5}
          />
        </div>
        <div>
          <label className="block text-[11px] opacity-70 mb-1">N lineups</label>
          <Input
            type="number"
            value={Number(nLineups)}
            onChange={(e) => setNLineups(Math.max(1, Math.min(150, Number(e.target.value || 1))))}
            min={1}
            max={150}
          />
        </div>
        <div>
          <label className="block text-[11px] opacity-70 mb-1">Sigma (0-0.25)</label>
          <Input
            type="number"
            step="0.01"
            value={Number(sigma)}
            onChange={(e) => setSigma(Math.max(0, Math.min(0.25, Number(e.target.value || 0))))}
            min={0}
            max={0.25}
          />
        </div>
        <div>
          <label className="block text-[11px] opacity-70 mb-1">Drop intensity (0-0.5)</label>
          <Input
            type="number"
            step="0.01"
            value={Number(dropIntensity)}
            onChange={(e) => setDropIntensity(Math.max(0, Math.min(0.5, Number(e.target.value || 0))))}
            min={0}
            max={0.5}
          />
        </div>
        <div className="flex items-center gap-2 mt-1">
          <input
            id="ownershipPenalty"
            type="checkbox"
            className="h-4 w-4"
            checked={Boolean(penaltyEnabled)}
            onChange={(e) => setPenaltyEnabled(e.target.checked)}
          />
          <label htmlFor="ownershipPenalty" className="text-xs opacity-80 select-none">
            Ownership penalty
          </label>
        </div>
        {penaltyEnabled && (
          <>
            <div>
              <label className="block text-[11px] opacity-70 mb-1">Lambda (0-50)</label>
              <Input
                type="number"
                value={Number(lambdaVal)}
                onChange={(e) => setLambdaVal(Math.max(0, Math.min(50, Number(e.target.value || 0))))}
                min={0}
                max={50}
              />
            </div>
            <div>
              <label className="block text-[11px] opacity-70 mb-1">Penalty curve</label>
              <select
                className="h-9 w-full bg-background border border-input rounded px-2 text-sm"
                value={penaltyCurve}
                onChange={(e) => setPenaltyCurve((e.target.value as any) === "g_curve" ? "g_curve" : "linear")}
              >
                <option value="linear">Linear</option>
                <option value="g_curve">G-curve</option>
              </select>
            </div>
          </>
        )}
        <div className="col-span-2">
          <label className="block text-[11px] opacity-70 mb-1">Projections path</label>
          <Input
            value={projectionsPath}
            onChange={(e) => setProjectionsPath(e.target.value)}
            placeholder="tests/fixtures/dk/2024-01-15/projections.csv"
          />
        </div>
        <div className="col-span-2">
          <label className="block text-[11px] opacity-70 mb-1">Player IDs path</label>
          <Input
            value={playerIdsPath}
            onChange={(e) => setPlayerIdsPath(e.target.value)}
            placeholder="tests/fixtures/dk/2024-01-15/player_ids.csv"
          />
        </div>

        {/* Legacy options (kept for dev) */}
        <div>
          <label className="block text-[11px] opacity-70 mb-1">Candidates</label>
          <Input
            type="number"
            value={Number(options.candidates ?? 0)}
            onChange={(e) => setOptions({ candidates: Math.max(0, Number(e.target.value || 0)) })}
            min={0}
          />
        </div>
        <div>
          <label className="block text-[11px] opacity-70 mb-1">Team cap</label>
          <Input
            type="number"
            value={Number(options.teamCap ?? 0)}
            onChange={(e) => setOptions({ teamCap: Math.max(0, Number(e.target.value || 0)) })}
            min={0}
          />
        </div>
        <div>
          <label className="block text-[11px] opacity-70 mb-1">Salary cap</label>
          <Input
            type="number"
            value={Number(options.salaryCap ?? 0)}
            onChange={(e) => setOptions({ salaryCap: Math.max(0, Number(e.target.value || 0)) })}
            min={0}
          />
        </div>
        <div>
          <label className="block text-[11px] opacity-70 mb-1">Min salary</label>
          <Input
            type="number"
            value={Number(options.minSalary ?? 0)}
            onChange={(e) => setOptions({ minSalary: Math.max(0, Number(e.target.value || 0)) })}
            min={0}
          />
        </div>
      </div>
      {showDev ? (
        <div className="flex items-center gap-2" aria-label="Dev grid state toggles">
          <Button
            variant={gridMode === "empty" ? "default" : "outline"}
            onClick={() => onGridModeChange?.("empty")}
          >
            Empty
          </Button>
          <Button
            variant={gridMode === "loading" ? "default" : "outline"}
            onClick={() => onGridModeChange?.("loading")}
          >
            Loading
          </Button>
          <Button
            variant={gridMode === "loaded" ? "default" : "outline"}
            onClick={() => onGridModeChange?.("loaded")}
          >
            Loaded
          </Button>
        </div>
      ) : (
        <div />
      )}
      <div className="flex gap-2 justify-end">
        <Button onClick={onRunClick} disabled={status === "running"}>Run</Button>
        <Button variant="outline" onClick={() => reset()} disabled={status === "running"}>
          Reset
        </Button>
      </div>
    </div>
  );
}
