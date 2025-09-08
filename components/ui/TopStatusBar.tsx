"use client";

import { ThemeToggle } from "../theme/ThemeToggle";

export default function TopStatusBar() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="h-[40px] w-full border-b border-border px-4 flex items-center justify-between bg-muted/20"
    >
      <span className="text-sm font-medium">Live Game Status</span>
      <ThemeToggle />
    </div>
  );
}

