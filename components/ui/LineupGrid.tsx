"use client";

import React from "react";
import { ScrollArea } from "./scroll-area";
import { Card } from "./card";
import { useRunStore } from "@/lib/state/run-store";

function composeTitle(s: any): string {
  const name = s?.name ?? "";
  const pos = s?.pos ?? s?.slot ?? "";
  const team = s?.team ?? "";
  const sal = s?.salary ?? "";
  const own = Math.round(100 * (s?.own_proj ?? 0));
  return `${name} (${pos}) - ${team} - $${sal} - own ${own}%`;
}

export default function LineupGrid(): JSX.Element {
  const { status, lineups } = useRunStore();
  return (
    <div className="w-full h-full rounded-md border border-border bg-card/30 p-4" role="region" aria-label="Optimizer Results">
      <div className="text-sm opacity-70">Lineups</div>
      <div className="mt-4 h-[calc(100%-2rem)]">
        {status === "idle" && (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground" aria-live="polite">
            No results yet - click Run to generate lineups.
          </div>
        )}
        {status === "running" && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 pr-1" role="status" aria-live="polite" aria-busy>
            {Array.from({ length: 9 }).map((_, i) => (
              <Card key={i} className="h-24 w-full animate-pulse" />
            ))}
          </div>
        )}
        {status === "done" && (
          <ScrollArea className="h-full">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 pr-4" role="grid" aria-rowcount={lineups.length}>
              {lineups.map((lu) => (
                <Card key={lu.id} className="p-2 text-xs" role="gridcell">
                  <div className="flex items-center justify-between">
                    <div className="font-medium">Score: {lu.score.toFixed(2)}</div>
                    <div className="opacity-70">Salary: {lu.salary}</div>
                  </div>
                  <div className="mt-2 grid grid-cols-4 gap-1">
                    {lu.slots.map((s, idx) => (
                      <div key={idx} className="truncate" title={composeTitle(s)}>
                        <span className="opacity-60">{s.slot}</span> {s.player_id_dk}
                      </div>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          </ScrollArea>
        )}
      </div>
    </div>
  );
}

