"use client";

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
  const { status, run, reset, options, setOptions } = useRunStore();
  const showDev = process.env.NODE_ENV !== "production" && onGridModeChange;
  return (
    <div className="h-auto w-full border-t border-border px-4 py-3 flex flex-col gap-3 bg-background">
      <div className="text-sm font-medium opacity-80">Controls / Knobs</div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 items-end">
        <div>
          <label className="block text-[11px] opacity-70 mb-1">Seed</label>
          <Input
            value={String(options.seed ?? "")}
            onChange={(e) => setOptions({ seed: e.target.value })}
            placeholder="seed"
          />
        </div>
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
        <div>
          <label className="block text-[11px] opacity-70 mb-1">Randomness %</label>
          <Input
            type="number"
            value={Number(options.randomnessPct ?? 0)}
            onChange={(e) => {
              const v = Math.max(0, Math.min(100, Number(e.target.value || 0)));
              setOptions({ randomnessPct: v });
            }}
            min={0}
            max={100}
          />
        </div>
        <div className="flex items-center gap-2 mt-1">
          <input
            id="ownershipPenalty"
            type="checkbox"
            className="h-4 w-4"
            checked={Boolean(options.ownershipPenalty)}
            onChange={(e) => setOptions({ ownershipPenalty: e.target.checked })}
          />
          <label htmlFor="ownershipPenalty" className="text-xs opacity-80 select-none">
            Ownership penalty
          </label>
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
        <Button onClick={() => run()} disabled={status === "running"}>Run</Button>
        <Button variant="outline" onClick={() => reset()} disabled={status === "running"}>
          Reset
        </Button>
      </div>
    </div>
  );
}
