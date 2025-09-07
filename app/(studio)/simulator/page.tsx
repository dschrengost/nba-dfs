"use client";

import { useState } from "react";
import PageContainer from "../../../components/ui/PageContainer";
import LineupGridPlaceholder, { type GridMode } from "../../../components/ui/LineupGridPlaceholder";
import { SKELETON_MS } from "../../../lib/ui/constants";
import { prefersReducedMotion } from "../../../lib/ui/a11y";

export default function SimulatorPage() {
  const [mode, setMode] = useState<GridMode>("empty");
  const reduced = prefersReducedMotion();
  function onGridModeChange(m: GridMode) {
    setMode(m);
    if (m === "loading") setTimeout(() => setMode("loaded"), reduced ? 150 : SKELETON_MS);
  }
  return (
    <PageContainer title="Simulator" gridMode={mode} onGridModeChange={onGridModeChange}>
      <LineupGridPlaceholder label="Simulator Grid" mode={mode} />
      <div className="mt-4 text-sm opacity-70">Export to DK Entries button will live here.</div>
    </PageContainer>
  );
}
