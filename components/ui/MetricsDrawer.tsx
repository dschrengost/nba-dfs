"use client";

import { useEffect, useRef, useState } from "react";
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

export default function MetricsDrawer() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (open) {
      // Focus title for accessibility
      setTimeout(() => titleRef.current?.focus(), 0);
      // Show loading skeleton briefly on open
      const reduced = prefersReducedMotion();
      setLoading(true);
      const ms = reduced ? 150 : DRAWER_SKELETON_MS;
      const t = setTimeout(() => setLoading(false), ms);
      return () => clearTimeout(t);
    }
  }, [open]);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="outline"
          className="fixed right-2 bottom-[110px] z-40"
          aria-label="Open metrics drawer"
          aria-expanded={open}
          aria-controls="metrics-panel"
        >
          Metrics
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[450px] sm:max-w-[450px]" id="metrics-panel">
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
            <div className="text-sm text-muted-foreground" aria-live="polite">
              No metrics yet — run Optimizer or Simulator.
            </div>
          )}
        </div>
      </SheetContent>
      {/* Spacer for bottom controls */}
      <div className="h-[96px]" />
    </Sheet>
  );
}
