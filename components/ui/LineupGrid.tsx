"use client";

import React from "react";
import { ScrollArea, ScrollBar } from "./scroll-area";
import { Card, CardContent, CardHeader } from "./card";
import { Badge } from "./badge";
import { useRunStore } from "@/lib/state/run-store";
import { TrendingUp, DollarSign, Users } from "lucide-react";

function composeTitle(s: any): string {
  const name = s?.name ?? "";
  const pos = s?.pos ?? s?.slot ?? "";
  const team = s?.team ?? "";
  const sal = s?.salary ?? "";
  const own = Math.round(100 * (s?.own_proj ?? 0));
  return `${name} (${pos}) - ${team} - $${sal} - own ${own}%`;
}

function formatSalary(salary: number): string {
  if (salary >= 1000) {
    return `${(salary / 1000).toFixed(0)}K`;
  }
  return salary.toString();
}

export default function LineupGrid() {
  const { status, lineups } = useRunStore();
  
  return (
    <div className="w-full h-full" role="region" aria-label="Optimizer Results">
      {status === "idle" && (
        <div className="h-full flex items-center justify-center text-sm text-muted-foreground" aria-live="polite">
          <div className="text-center">
            <TrendingUp className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>No results yet</p>
            <p className="text-xs mt-1">Click Run to generate lineups</p>
          </div>
        </div>
      )}
      
      {status === "running" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3" role="status" aria-live="polite" aria-busy>
          {Array.from({ length: 12 }).map((_, i) => (
            <Card key={i} className="h-32 animate-pulse bg-muted/20">
              <CardContent className="p-3">
                <div className="h-4 bg-muted rounded mb-2" />
                <div className="space-y-1">
                  {Array.from({ length: 4 }).map((_, j) => (
                    <div key={j} className="h-3 bg-muted/60 rounded w-full" />
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      
      {status === "done" && (
        <div className="h-full w-full overflow-auto custom-scrollbar">
          <div 
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3 p-1" 
            role="grid" 
            aria-rowcount={lineups.length}
          >
            {lineups.map((lu, index) => {
              // Calculate salary used and left
              const salaryUsed = lu.slots.reduce((sum: number, slot: any) => sum + (slot.salary || 0), 0);
              const salaryLeft = 50000 - salaryUsed;
              const ownSum = lu.slots.reduce((sum: number, slot: any) => sum + (slot.own_proj || 0), 0);
              
              return (
                <Card key={lu.id} className="group hover:shadow-md transition-all duration-200 hover:border-primary/20 w-[280px]" role="gridcell">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="text-xs font-mono">
                        #{index + 1}
                      </Badge>
                      <div className="flex items-center gap-1 text-xs">
                        <TrendingUp className="h-3 w-3" />
                        <span className="font-semibold">{lu.score.toFixed(1)}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <DollarSign className="h-3 w-3" />
                        <span>{formatSalary(salaryUsed)}</span>
                        {salaryLeft > 0 && (
                          <span className="text-green-600">+{formatSalary(salaryLeft)}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        <Users className="h-3 w-3" />
                        <span>{(ownSum * 100).toFixed(1)}%</span>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="grid grid-cols-2 gap-1 text-xs">
                      {lu.slots.map((s, idx) => (
                        <div key={idx} className="flex items-center gap-1 truncate group-hover:text-primary transition-colors" title={composeTitle(s)}>
                          <Badge variant="secondary" className="text-[10px] px-1 py-0 h-4 font-mono">
                            {s.slot}
                          </Badge>
                          <span className="truncate">{s.name || s.player_id_dk}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

