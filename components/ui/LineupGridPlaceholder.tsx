"use client";

import { ScrollArea } from "./scroll-area";

export default function LineupGridPlaceholder({ label = "Grid" }: { label?: string }) {
  return (
    <div className="w-full h-full rounded-md border border-border bg-card/30 p-4">
      <div className="text-sm opacity-70">{label}</div>
      <ScrollArea className="mt-4 h-[calc(100%-2rem)]">
        <div className="grid grid-cols-3 gap-3 pr-4">
          {Array.from({ length: 18 }).map((_, i) => (
            <div
              key={i}
              className="h-24 rounded-md bg-muted/40 border border-muted-foreground/10"
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
