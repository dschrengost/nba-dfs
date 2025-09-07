"use client";

import * as React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { useRunStore } from "@/lib/state/run-store";
import LineupGrid from "@/components/ui/LineupGrid";
import { LineupTable } from "./LineupTable";
import { LineupTableData } from "@/lib/table/columns";
import { useRosterMap } from "@/hooks/useRosterMap";
import RunSummary from "@/components/metrics/RunSummary";

interface LineupViewsProps {
  className?: string;
}

export function LineupViews({ className }: LineupViewsProps) {
  const { status, lineups, summary } = useRunStore();
  const [activeView, setActiveView] = React.useState<string>("cards");

  // Transform lineups data for table view
  const tableData: LineupTableData[] = React.useMemo(() => {
    if (!lineups?.length) return [];
    
    return lineups.map((lineup: any) => {
      const slots = lineup.slots || [];
      
      // Calculate derived metrics from available data
      const salaryUsed = slots.reduce((sum: number, slot: any) => sum + (slot.salary || 0), 0);
      const salaryLeft = 50000 - salaryUsed; // DK salary cap is 50,000
      const ownSum = slots.reduce((sum: number, slot: any) => sum + (slot.own_proj || 0), 0);
      const ownAvg = slots.length > 0 ? ownSum / slots.length : 0;
      const projSum = slots.reduce((sum: number, slot: any) => sum + (slot.proj || slot.proj_fp || 0), 0);
      const teams = new Set(slots.map((slot: any) => slot.team).filter(Boolean));
      
      const tableLineup: LineupTableData = {
        lineup_id: lineup.id,
        score: lineup.score,
        salary_used: salaryUsed,
        salary_left: salaryLeft,
        dup_risk: lineup.dup_risk, // Not available from backend
        own_sum: ownSum,
        own_avg: ownAvg,
        lev_sum: lineup.lev_sum, // Not available from backend 
        lev_avg: lineup.lev_avg, // Not available from backend
        num_uniques_in_pool: lineup.num_uniques_in_pool, // Not available from backend
        teams_used: Array.from(teams),
        proj_pts_sum: projSum,
        stack_flags: lineup.stack_flags, // Not available from backend
      };

      // Map player slots to table columns
      slots.forEach((slot: any) => {
        const position = slot.slot;
        if (position) {
          (tableLineup as any)[position] = slot.player_id_dk;
        }
      });

      return tableLineup;
    });
  }, [lineups]);

  // Get roster map from summary or derive from lineup slots
  const { getRosterMap } = useRosterMap({
    playerMap: (summary as any)?.playerMap,
    lineups,
    runId: (summary as any)?.runId,
  });
  
  const rosterMap = getRosterMap();

  if (status === "idle") {
    return (
      <div className={`w-full h-full rounded-md border border-border bg-card/30 p-4 ${className}`} role="region" aria-label="Lineup Results">
        <div className="h-full flex items-center justify-center text-sm text-muted-foreground" aria-live="polite">
          No results yet - click Run to generate lineups.
        </div>
      </div>
    );
  }

  if (status === "running") {
    return (
      <div className={`w-full h-full rounded-md border border-border bg-card/30 p-4 ${className}`} role="region" aria-label="Lineup Results">
        <div className="text-sm opacity-70 mb-4">Lineups</div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 pr-1" role="status" aria-live="polite" aria-busy>
          {Array.from({ length: 9 }).map((_, i) => (
            <Card key={i} className="h-24 w-full animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={`w-full h-full ${className}`} role="region" aria-label="Lineup Results">
      {/* Compact RunSummary above results for quick context */}
      <div className="mb-3">
        <RunSummary />
      </div>
      <Tabs value={activeView} onValueChange={setActiveView} className="w-full h-full">
        <div className="flex items-center justify-between mb-4">
          <div className="text-sm opacity-70">Lineups</div>
          <TabsList className="grid w-fit grid-cols-2" data-testid="lineup-view-tabs">
            <TabsTrigger value="cards" data-testid="cards-tab">Cards</TabsTrigger>
            <TabsTrigger value="table" data-testid="table-tab">Table</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="cards" className="mt-0 h-[calc(100%-3rem)]" data-testid="cards-view">
          <div className="w-full h-full rounded-md border border-border bg-card/30 p-4">
            <LineupGrid />
          </div>
        </TabsContent>

        <TabsContent value="table" className="mt-0 h-[calc(100%-3rem)]" data-testid="table-view">
          <LineupTable 
            data={tableData}
            playerMap={(summary as any)?.playerMap}
            lineups={lineups}
            runId={(summary as any)?.runId}
            className="h-full"
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
