"use client";

import { Button } from "./button";
import { useRunStore } from "@/lib/state/run-store";
import type { GridMode } from "./LineupGridPlaceholder";

export default function ControlsBar({
  gridMode,
  onGridModeChange,
}: {
  gridMode?: GridMode;
  onGridModeChange?: (m: GridMode) => void;
}) {
  const { status, run, reset } = useRunStore();
  const showDev = process.env.NODE_ENV !== "production" && onGridModeChange;
  return (
    <div className="h-[96px] w-full border-t border-border px-4 flex items-center justify-between bg-background">
      <div className="text-sm font-medium opacity-80">Controls / Knobs</div>
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
      <div className="flex gap-2">
        <Button onClick={() => run()} disabled={status === "running"}>Run</Button>
        <Button variant="outline" onClick={() => reset()} disabled={status === "running"}>
          Reset
        </Button>
      </div>
    </div>
  );
}
