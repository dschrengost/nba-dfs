"use client";

import { useState } from "react";
import { ScrollArea } from "./scroll-area";
import { Button } from "./button";
import { Skeleton } from "./skeleton";
import { SKELETON_MS } from "@/lib/ui/constants";
import { prefersReducedMotion } from "@/lib/ui/a11y";

type Mode = "empty" | "loading" | "loaded";

export default function LineupGridPlaceholder({ label = "Grid" }: { label?: string }) {
  const [mode, setMode] = useState<Mode>("empty");

  function triggerLoad() {
    setMode("loading");
    const reduced = prefersReducedMotion();
    setTimeout(() => setMode("loaded"), reduced ? 150 : SKELETON_MS);
  }

  return (
    <div className="w-full h-full rounded-md border border-border bg-card/30 p-4" role="region" aria-label={`${label} area`}>
      <div className="flex items-center justify-between">
        <div className="text-sm opacity-70">{label}</div>
        <div className="flex gap-2" aria-label="Grid state controls">
          <Button variant={mode === "empty" ? "default" : "outline"} onClick={() => setMode("empty")}>Empty</Button>
          <Button variant={mode === "loading" ? "default" : "outline"} onClick={triggerLoad}>Loading</Button>
          <Button variant={mode === "loaded" ? "default" : "outline"} onClick={() => setMode("loaded")}>Loaded</Button>
        </div>
      </div>

      <div className="mt-4 h-[calc(100%-2rem)]">
        {mode === "empty" && (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground" aria-live="polite">
            No results yet — run an action to populate the grid.
          </div>
        )}
        {mode === "loading" && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 pr-1" role="status" aria-live="polite" aria-busy>
            {Array.from({ length: 9 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full motion-reduce:animate-none" />
            ))}
          </div>
        )}
        {mode === "loaded" && (
          <ScrollArea className="h-full">
            <div className="grid grid-cols-3 gap-3 pr-4" role="grid" aria-rowcount={6} aria-colcount={3}>
              {Array.from({ length: 18 }).map((_, i) => (
                <div key={i} className="h-24 rounded-md bg-muted/40 border border-muted-foreground/10" role="gridcell" />
              ))}
            </div>
          </ScrollArea>
        )}
      </div>
    </div>
  );
}
