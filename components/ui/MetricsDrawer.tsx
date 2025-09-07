"use client";

import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetHeader,
  SheetTitle,
} from "./sheet";
import { Button } from "./button";

export default function MetricsDrawer() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button
          variant="outline"
          className="fixed right-2 bottom-[110px] z-40"
          aria-label="Open metrics drawer"
        >
          Metrics
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[450px] sm:max-w-[450px]">
        <SheetHeader>
          <SheetTitle>Metrics</SheetTitle>
        </SheetHeader>
        <div className="mt-4 h-[calc(100%-3rem)] rounded-md border border-border bg-card/40 p-4" />
      </SheetContent>
      {/* Spacer for bottom controls */}
      <div className="h-[96px]" />
    </Sheet>
  );
}
