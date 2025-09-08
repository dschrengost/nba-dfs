"use client";

import { useRunStore } from "@/lib/state/run-store";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

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

  // Number formatting utilities
  const formatScore = (n: number | undefined) => 
    n !== undefined ? new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) : "—";
  
  const formatOverlap = (n: number | undefined) => 
    n !== undefined ? new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) : "—";
    
  const formatJaccard = (n: number | undefined) => 
    n !== undefined ? new Intl.NumberFormat("en-US", { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(n) : "—";
    
  const formatMs = (n: number | undefined) => 
    n !== undefined ? new Intl.NumberFormat("en-US").format(n) + " ms" : "—";
    
  const formatInteger = (n: number | undefined) => 
    n !== undefined ? new Intl.NumberFormat("en-US").format(n) : "—";

  const ownershipPenaltyOn =
    typeof opts.ownershipPenalty === "boolean"
      ? opts.ownershipPenalty
      : !!d?.ownership_penalty?.enabled;

  return (
    <TooltipProvider>
      <div className="space-y-4" data-testid="run-summary">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="font-medium">Optimizer Run</div>
          <Separator orientation="vertical" className="h-4" />

          {summary.engineUsed && (
            <Tooltip>
              <TooltipTrigger>
                <Badge variant="secondary" className="text-[10px]" data-testid="engine-badge">
                  Engine: {summary.engineUsed === "cp_sat" ? "CP-SAT" : "CBC"}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                <p>Optimization engine used: {summary.engineUsed === "cp_sat" ? "Google CP-SAT" : "COIN-OR CBC"}</p>
              </TooltipContent>
            </Tooltip>
          )}

          {summary.usingFixtureDate && (
            <Tooltip>
              <TooltipTrigger>
                <Badge variant="outline" className="text-[10px]" data-testid="fixture-badge">
                  Fixture: {summary.usingFixtureDate}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                <p>Using fixture data from: {summary.usingFixtureDate}</p>
              </TooltipContent>
            </Tooltip>
          )}

          {typeof lamUsed === "number" && (
            <Tooltip>
              <TooltipTrigger>
                <Badge variant="secondary" className="text-[10px]" data-testid="lambda-badge">
                  λ={lamUsed}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                <p>Ownership penalty lambda: {lamUsed}</p>
              </TooltipContent>
            </Tooltip>
          )}

          {curveLabel && (
            <Tooltip>
              <TooltipTrigger>
                <Badge variant="secondary" className="text-[10px]" data-testid="curve-badge">
                  curve={String(curveLabel)}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                <p>Penalty curve type: {String(curveLabel)}</p>
              </TooltipContent>
            </Tooltip>
          )}

          {typeof dropPct === "number" && (
            <Tooltip>
              <TooltipTrigger>
                <Badge variant="secondary" className="text-[10px]" data-testid="drop-badge">
                  drop={(dropPct * 100).toFixed(0)}%
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                <p>Player pruning drop percentage: {(dropPct * 100).toFixed(1)}%</p>
              </TooltipContent>
            </Tooltip>
          )}

          {typeof uniques === "number" && (
            <Tooltip>
              <TooltipTrigger>
                <Badge variant="secondary" className="text-[10px]" data-testid="uniques-badge">
                  uniques={uniques}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                <p>Minimum unique players per lineup: {uniques}</p>
              </TooltipContent>
            </Tooltip>
          )}
        </div>

        <Card data-testid="inputs-outputs-card">
          <CardHeader className="pb-2">
            <div className="text-xs font-medium">Inputs / Outputs</div>
          </CardHeader>
          <CardContent className="pt-0">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              <div className="flex justify-between">
                <dt className="opacity-70">Lineups</dt>
                <dd className="font-mono tabular-nums">{formatInteger(pool?.lineups)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Unique players</dt>
                <dd className="font-mono tabular-nums">{formatInteger(pool?.unique_player_count)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Avg overlap</dt>
                <dd className="font-mono tabular-nums">{formatOverlap(pool?.avg_overlap_players)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Avg Jaccard</dt>
                <dd className="font-mono tabular-nums">{formatJaccard(pool?.avg_pairwise_jaccard)}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card data-testid="performance-card">
          <CardContent className="pt-4">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              <div className="flex justify-between">
                <dt className="opacity-70">Candidates tried</dt>
                <dd className="font-mono tabular-nums">{formatInteger(summary.tried)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Valid lineups</dt>
                <dd className="font-mono tabular-nums">{formatInteger(summary.valid)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Best score</dt>
                <dd className="font-mono tabular-nums">{formatScore(summary.bestScore)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Elapsed</dt>
                <dd className="font-mono tabular-nums">{formatMs(summary.elapsedMs)}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card data-testid="settings-card">
          <CardHeader className="pb-2">
            <div className="text-xs font-medium">Settings</div>
          </CardHeader>
          <CardContent className="pt-0">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              <div className="flex justify-between">
                <dt className="opacity-70">Seed</dt>
                <dd className="font-mono tabular-nums">{seed ?? "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Candidates</dt>
                <dd className="font-mono tabular-nums">{formatInteger(candidates)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Team cap</dt>
                <dd className="font-mono tabular-nums">{teamCap ?? "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Salary cap</dt>
                <dd className="font-mono tabular-nums">{formatInteger(salaryCap)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Min salary</dt>
                <dd className="font-mono tabular-nums">{formatInteger(minSalary) || "0"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Randomness %</dt>
                <dd className="font-mono tabular-nums">{randomnessPct}%</dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Ownership penalty</dt>
                <dd className="font-mono tabular-nums">{ownershipPenaltyOn ? "on" : "off"}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {summary.invalidReasons && (
          <Card data-testid="invalid-reasons-card">
            <CardHeader className="pb-2">
              <div className="text-xs font-medium">Invalid reasons</div>
            </CardHeader>
            <CardContent className="pt-0">
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                <div className="flex justify-between">
                  <dt className="opacity-70">Salary</dt>
                  <dd className="font-mono tabular-nums">{formatInteger(summary.invalidReasons.salary)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="opacity-70">Slots</dt>
                  <dd className="font-mono tabular-nums">{formatInteger(summary.invalidReasons.slots)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="opacity-70">Team cap</dt>
                  <dd className="font-mono tabular-nums">{formatInteger(summary.invalidReasons.teamcap)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="opacity-70">Duplicate</dt>
                  <dd className="font-mono tabular-nums">{formatInteger(summary.invalidReasons.dup)}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        )}
      </div>
    </TooltipProvider>
  );
}