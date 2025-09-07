"use client";

import { useRef, useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetHeader,
  SheetTitle,
} from "./sheet";
import { Button } from "./button";
import { Skeleton } from "./skeleton";
import { DRAWER_SKELETON_MS } from "@/lib/ui/constants";
import { prefersReducedMotion } from "@/lib/ui/a11y";
import IngestSummary from "../metrics/IngestSummary";

export default function MetricsDrawer() {
  const [loading, setLoading] = useState(false);
  const titleRef = useRef<HTMLHeadingElement>(null);

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button
          variant="outline"
          className="fixed right-2 bottom-[110px] z-40"
          aria-label="Open metrics drawer"
          aria-controls="metrics-panel"
        >
          Metrics
        </Button>
      </SheetTrigger>
      <SheetContent
        side="right"
        className="w-[450px] sm:max-w-[450px]"
        id="metrics-panel"
        onOpenAutoFocus={(e) => {
          // prevent default auto-focus and move focus to title instead
          e.preventDefault();
          setTimeout(() => titleRef.current?.focus(), 0);
          const reduced = prefersReducedMotion();
          setLoading(true);
          const ms = reduced ? 150 : DRAWER_SKELETON_MS;
          const t = setTimeout(() => setLoading(false), ms);
          // store timer id on element dataset for cleanup
          (e.currentTarget as any)._timerId = t;
        }}
        onCloseAutoFocus={(e) => {
          // cleanup timer and reset loading state
          const anyTarget = e.currentTarget as any;
          if (anyTarget._timerId) clearTimeout(anyTarget._timerId);
          setLoading(false);
        }}
      >
        <SheetHeader>
          <SheetTitle ref={titleRef as any} tabIndex={-1}>Metrics</SheetTitle>
        </SheetHeader>
        <div className="mt-4 h-[calc(100%-3rem)] rounded-md border border-border bg-card/40 p-4">
          {loading ? (
            <div className="space-y-3" role="status" aria-busy>
              <Skeleton className="h-4 w-2/3 motion-reduce:animate-none" />
              <Skeleton className="h-4 w-1/2 motion-reduce:animate-none" />
              <Skeleton className="h-4 w-5/6 motion-reduce:animate-none" />
            </div>
          ) : (
            <div className="space-y-4">
              <IngestSummary />
              <div className="text-xs text-muted-foreground">Optimizer/Simulator metrics TBD.</div>
            </div>
          )}
        </div>
      </SheetContent>
      {/* Spacer for bottom controls */}
      <div className="h-[96px]" />
    </Sheet>
  );
}
