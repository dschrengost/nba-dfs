"use client";

import { Button } from "./button";

export default function ControlsBar() {
  return (
    <div className="h-[96px] w-full border-t border-border px-4 flex items-center justify-between bg-background">
      <div className="text-sm font-medium opacity-80">Controls / Knobs</div>
      <div className="flex gap-2">
        <Button disabled>Run</Button>
        <Button variant="outline" disabled>
          Reset
        </Button>
      </div>
    </div>
  );
}
