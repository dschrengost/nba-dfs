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
import { ChevronDown, Settings2, Zap, Target, FolderOpen } from "lucide-react";
import LoadRunModal from "@/components/runs/LoadRunModal";

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

  // Input state for validation on blur
  const [nLineupsInput, setNLineupsInput] = useState<string>(String(nLineups));
  const [seedInput, setSeedInput] = useState<string>(String(seed));
  const [minUniquesInput, setMinUniquesInput] = useState<string>(String(minUniques));
  const [lambdaInput, setLambdaInput] = useState<string>(String(lambdaVal));
  const [candidatesInput, setCandidatesInput] = useState<string>(String(options.candidates ?? 0));
  const [teamCapInput, setTeamCapInput] = useState<string>(String(options.teamCap ?? 0));
  const [salaryCapInput, setSalaryCapInput] = useState<string>(String(options.salaryCap ?? 0));
  const [minSalaryInput, setMinSalaryInput] = useState<string>(String(options.minSalary ?? 0));
  const [showLoad, setShowLoad] = useState<boolean>(false);

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

  // Sync input states when main values change
  useEffect(() => setNLineupsInput(String(nLineups)), [nLineups]);
  useEffect(() => setSeedInput(String(seed)), [seed]);
  useEffect(() => setMinUniquesInput(String(minUniques)), [minUniques]);
  useEffect(() => setLambdaInput(String(lambdaVal)), [lambdaVal]);
  useEffect(() => setCandidatesInput(String(options.candidates ?? 0)), [options.candidates]);
  useEffect(() => setTeamCapInput(String(options.teamCap ?? 0)), [options.teamCap]);
  useEffect(() => setSalaryCapInput(String(options.salaryCap ?? 0)), [options.salaryCap]);
  useEffect(() => setMinSalaryInput(String(options.minSalary ?? 0)), [options.minSalary]);

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
                className="w-20 h-7 text-xs"
                type="text"
                value={nLineupsInput}
                onChange={(e) => setNLineupsInput(e.target.value)}
                onBlur={() => {
                  const val = Math.max(1, Number(nLineupsInput || 1));
                  setNLineups(val);
                  setNLineupsInput(String(val));
                }}
              />
            </div>
            <div className="flex items-center gap-1">
              <label className="text-xs text-muted-foreground">Seed:</label>
              <Input
                className="w-16 h-7 text-xs"
                type="text"
                value={seedInput}
                onChange={(e) => setSeedInput(e.target.value)}
                onBlur={() => {
                  const val = Number(seedInput || 0);
                  setSeed(val);
                  setSeedInput(String(val));
                }}
              />
            </div>
            <div className="flex items-center gap-1">
              <label className="text-xs text-muted-foreground">Uniques:</label>
              <Input
                className="w-16 h-7 text-xs"
                type="text"
                value={minUniquesInput}
                onChange={(e) => setMinUniquesInput(e.target.value)}
                onBlur={() => {
                  const val = Math.max(0, Number(minUniquesInput || 0));
                  setMinUniques(val);
                  setMinUniquesInput(String(val));
                }}
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
                      className="w-16 h-6 text-xs"
                      type="text"
                      value={lambdaInput}
                      onChange={(e) => setLambdaInput(e.target.value)}
                      onBlur={() => {
                        const val = Math.max(0, Number(lambdaInput || 0));
                        setLambdaVal(val);
                        setLambdaInput(String(val));
                      }}
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
                        type="text"
                        value={candidatesInput}
                        onChange={(e) => setCandidatesInput(e.target.value)}
                        onBlur={() => {
                          const val = Math.max(0, Number(candidatesInput || 0));
                          setOptions({ candidates: val });
                          setCandidatesInput(String(val));
                        }}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Team Cap</label>
                      <Input
                        className="h-6 text-xs"
                        type="text"
                        value={teamCapInput}
                        onChange={(e) => setTeamCapInput(e.target.value)}
                        onBlur={() => {
                          const val = Math.max(0, Number(teamCapInput || 0));
                          setOptions({ teamCap: val });
                          setTeamCapInput(String(val));
                        }}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Salary Cap</label>
                      <Input
                        className="h-6 text-xs"
                        type="text"
                        value={salaryCapInput}
                        onChange={(e) => setSalaryCapInput(e.target.value)}
                        onBlur={() => {
                          const val = Math.max(0, Number(salaryCapInput || 0));
                          setOptions({ salaryCap: val });
                          setSalaryCapInput(String(val));
                        }}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Min Salary</label>
                      <Input
                        className="h-6 text-xs"
                        type="text"
                        value={minSalaryInput}
                        onChange={(e) => setMinSalaryInput(e.target.value)}
                        onBlur={() => {
                          const val = Math.max(0, Number(minSalaryInput || 0));
                          setOptions({ minSalary: val });
                          setMinSalaryInput(String(val));
                        }}
                      />
                    </div>
                  </div>
                </div>
              </DropdownMenuContent>
            </DropdownMenu>
            
            <div className="flex gap-1">
              <Button variant="outline" onClick={() => setShowLoad(true)} disabled={status === "running"} size="sm" className="h-6 px-2 text-xs">
                <FolderOpen className="h-3 w-3 mr-1" /> Load
              </Button>
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
        <LoadRunModal open={showLoad} onClose={() => setShowLoad(false)} />
      </Card>
    </TooltipProvider>
  );
}
