"use client";

import { useEffect, useState } from "react";
import { Button } from "./button";
import { useRunStore } from "@/lib/state/run-store";
import type { GridMode } from "./LineupGridPlaceholder";
import { Input } from "./input";
import { Slider } from "./slider";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./tooltip";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./collapsible";
import { Card } from "./card";
import { Badge } from "./badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "./dropdown-menu";
import { ChevronDown, Settings2, Zap, Target } from "lucide-react";

export default function ControlsBar({
  gridMode,
  onGridModeChange,
}: {
  gridMode?: GridMode;
  onGridModeChange?: (m: GridMode) => void;
}) {
  const { status, reset, options, setOptions, runSolve } = useRunStore();
  const showDev = process.env.NEXT_PUBLIC_DEV_UI === "true" && onGridModeChange;

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
      setProjectionsPath(last.projectionsPath ?? "tests/fixtures/dk/2024-01-15/projections.csv");
      setPlayerIdsPath(last.playerIdsPath ?? "tests/fixtures/dk/2024-01-15/player_ids.csv");
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

  // Sync grid placeholder mode with run status so results view appears
  useEffect(() => {
    if (!onGridModeChange) return;
    if (status === "running") onGridModeChange("loading");
    else if (status === "done" || status === "error") onGridModeChange("loaded");
    else if (status === "idle") onGridModeChange("empty");
  }, [status, onGridModeChange]);

  return (
    <TooltipProvider>
      <Card className="w-96 bg-card/50 backdrop-blur-sm">
        <div className="p-3">
          {/* Compact Header with Run Button */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Settings2 className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Settings</span>
            </div>
            <Button onClick={onRunClick} disabled={status === "running"} size="sm" className="h-8">
              {status === "running" ? (
                <span className="inline-flex items-center gap-1">
                  <svg
                    className="animate-spin h-3 w-3"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    aria-hidden
                  >
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                  </svg>
                  Running…
                </span>
              ) : (
                <span className="inline-flex items-center gap-1">
                  <Zap className="h-3 w-3" />
                  Run
                </span>
              )}
            </Button>
          </div>

          {/* Compact Core Settings Row */}
          <div className="flex items-center gap-3 mb-3">
            <div className="flex items-center gap-1">
              <label className="text-xs text-muted-foreground">Lineups:</label>
              <Input
                className="w-14 h-7 text-xs"
                type="number"
                value={nLineups}
                onChange={(e) => setNLineups(Math.max(1, Math.min(150, Number(e.target.value || 1))))}
                min={1}
                max={150}
              />
            </div>
            <div className="flex items-center gap-1">
              <label className="text-xs text-muted-foreground">Seed:</label>
              <Input
                className="w-12 h-7 text-xs"
                value={String(seed)}
                onChange={(e) => setSeed(Number(e.target.value || 0))}
              />
            </div>
            <div className="flex items-center gap-1">
              <label className="text-xs text-muted-foreground">Uniques:</label>
              <Input
                className="w-12 h-7 text-xs"
                type="number"
                value={minUniques}
                onChange={(e) => setMinUniques(Math.max(0, Math.min(5, Number(e.target.value || 0))))}
                min={0}
                max={5}
              />
            </div>
          </div>

          {/* Ownership Penalty - Always Visible Compact Row */}
          <div className="rounded border bg-muted/30 p-2 mb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <input
                  id="ownershipPenalty"
                  type="checkbox"
                  className="h-3 w-3 rounded"
                  checked={Boolean(penaltyEnabled)}
                  onChange={(e) => setPenaltyEnabled(e.target.checked)}
                />
                <label htmlFor="ownershipPenalty" className="text-xs font-medium select-none flex items-center gap-1">
                  <Target className="h-3 w-3" />
                  Ownership Penalty
                </label>
                {penaltyEnabled && (
                  <Badge variant="secondary" className="text-xs px-1 py-0 h-4">
                    Active
                  </Badge>
                )}
              </div>
              
              {penaltyEnabled && (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1">
                    <label className="text-xs text-muted-foreground">λ:</label>
                    <Input
                      className="w-12 h-6 text-xs"
                      type="number"
                      value={lambdaVal}
                      onChange={(e) => setLambdaVal(Math.max(0, Math.min(50, Number(e.target.value || 0))))}
                      min={0}
                      max={50}
                    />
                  </div>
                  <select
                    className="h-6 bg-background border border-input rounded px-1 text-xs"
                    value={penaltyCurve}
                    onChange={(e) => setPenaltyCurve((e.target.value as any) === "g_curve" ? "g_curve" : "linear")}
                  >
                    <option value="linear">Linear</option>
                    <option value="g_curve">G-curve</option>
                  </select>
                </div>
              )}
            </div>
          </div>

          {/* Advanced Settings & Actions Row */}
          <div className="flex items-center justify-between relative">
            {/* Advanced Dropdown Menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="h-6 px-2 text-xs">
                  <ChevronDown className="h-3 w-3 mr-1" />
                  Advanced
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" side="right" className="w-80 p-3">
                <div className="space-y-3">
                  {/* Variance Controls */}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <label className="text-xs font-medium text-muted-foreground cursor-help">Sigma</label>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>Randomness applied to projections. 0 = deterministic; 0.25 = high variance.</p>
                          </TooltipContent>
                        </Tooltip>
                        <span className="text-xs text-muted-foreground">{sigma.toFixed(3)}</span>
                      </div>
                      <Slider
                        value={[Math.max(0, Math.min(0.25, sigma))]}
                        min={0}
                        max={0.25}
                        step={0.005}
                        onValueChange={(v) => setSigma(v?.[0] ?? 0)}
                        className="mt-1"
                        data-testid="sigma-slider"
                        aria-label="Sigma"
                      />
                    </div>
                    
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <label className="text-xs font-medium text-muted-foreground cursor-help">Drop</label>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>Prunes low-projection players to speed up search. 0 = keep all; 0.5 = aggressive pruning.</p>
                          </TooltipContent>
                        </Tooltip>
                        <span className="text-xs text-muted-foreground">{dropIntensity.toFixed(3)}</span>
                      </div>
                      <Slider
                        value={[Math.max(0, Math.min(0.5, dropIntensity))]}
                        min={0}
                        max={0.5}
                        step={0.01}
                        onValueChange={(v) => setDropIntensity(v?.[0] ?? 0)}
                        className="mt-1"
                        data-testid="drop-slider"
                        aria-label="Drop intensity"
                      />
                    </div>
                  </div>

                  {/* Additional Settings */}
                  <div className="grid grid-cols-4 gap-2">
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Candidates</label>
                      <Input
                        className="h-6 text-xs"
                        type="number"
                        value={Number(options.candidates ?? 0)}
                        onChange={(e) => setOptions({ candidates: Math.max(0, Number(e.target.value || 0)) })}
                        min={0}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Team Cap</label>
                      <Input
                        className="h-6 text-xs"
                        type="number"
                        value={Number(options.teamCap ?? 0)}
                        onChange={(e) => setOptions({ teamCap: Math.max(0, Number(e.target.value || 0)) })}
                        min={0}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Salary Cap</label>
                      <Input
                        className="h-6 text-xs"
                        type="number"
                        value={Number(options.salaryCap ?? 0)}
                        onChange={(e) => setOptions({ salaryCap: Math.max(0, Number(e.target.value || 0)) })}
                        min={0}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Min Salary</label>
                      <Input
                        className="h-6 text-xs"
                        type="number"
                        value={Number(options.minSalary ?? 0)}
                        onChange={(e) => setOptions({ minSalary: Math.max(0, Number(e.target.value || 0)) })}
                        min={0}
                      />
                    </div>
                  </div>
                </div>
              </DropdownMenuContent>
            </DropdownMenu>
            
            <div className="flex gap-1">
              <Button variant="outline" onClick={() => reset()} disabled={status === "running"} size="sm" className="h-6 px-2 text-xs">
                Reset
              </Button>
              {showDev && (
                <div className="flex gap-1" aria-label="Dev grid state toggles">
                  <Button
                    variant={gridMode === "empty" ? "default" : "outline"}
                    size="sm"
                    onClick={() => onGridModeChange?.("empty")}
                    className="text-xs px-1 h-6 w-6"
                  >
                    E
                  </Button>
                  <Button
                    variant={gridMode === "loading" ? "default" : "outline"}
                    size="sm"
                    onClick={() => onGridModeChange?.("loading")}
                    className="text-xs px-1 h-6 w-6"
                  >
                    L
                  </Button>
                  <Button
                    variant={gridMode === "loaded" ? "default" : "outline"}
                    size="sm"
                    onClick={() => onGridModeChange?.("loaded")}
                    className="text-xs px-1 h-6 w-6"
                  >
                    D
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </Card>
    </TooltipProvider>
  );
}
