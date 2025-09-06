"use client";

export default function LineupGridPlaceholder({ label = "Grid" }: { label?: string }) {
  return (
    <div className="w-full h-full rounded-md border border-border bg-card/30 p-4">
      <div className="text-sm opacity-70">{label}</div>
      <div className="mt-4 grid grid-cols-3 gap-3">
        {Array.from({ length: 9 }).map((_, i) => (
          <div
            key={i}
            className="h-24 rounded-md bg-muted/40 border border-muted-foreground/10"
          />
        ))}
      </div>
    </div>
  );
}

