"use client";

export default function ControlsBar() {
  return (
    <div className="h-[96px] w-full border-t border-border px-4 flex items-center justify-between bg-background">
      <div className="text-sm font-medium opacity-80">Controls / Knobs</div>
      <div className="flex gap-2">
        <button className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted/50" disabled>
          Run
        </button>
        <button className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted/50" disabled>
          Reset
        </button>
      </div>
    </div>
  );
}

