"use client";

import { useState } from "react";

export default function MetricsDrawer() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        aria-label={open ? "Close metrics drawer" : "Open metrics drawer"}
        onClick={() => setOpen((v) => !v)}
        className="fixed right-2 bottom-[110px] z-40 px-3 py-1.5 rounded-md border border-border text-sm bg-background hover:bg-muted/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {open ? "Close Metrics" : "Metrics"}
      </button>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Metrics Drawer"
        className={`fixed top-0 right-0 h-full w-[450px] bg-background border-l border-border shadow-xl z-30 transform transition-transform duration-200 ease-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="p-4 h-full">
          <div className="h-full rounded-md border border-border bg-card/40 p-4">Metrics</div>
        </div>
      </div>
      {/* Spacer for bottom controls */}
      <div className="h-[96px]" />
    </>
  );
}

