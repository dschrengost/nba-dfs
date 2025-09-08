"use client";

import { useState } from "react";
import PageContainer from "../../../components/ui/PageContainer";
import LineupGridPlaceholder, { type GridMode } from "../../../components/ui/LineupGridPlaceholder";
import { LineupViews } from "@/components/lineups/LineupViews";
import { SKELETON_MS } from "../../../lib/ui/constants";
import { prefersReducedMotion } from "../../../lib/ui/a11y";

export default function OptimizerPage() {
  const [mode, setMode] = useState<GridMode>("empty");
  const reduced = prefersReducedMotion();
  function onGridModeChange(m: GridMode) {
    setMode(m);
    if (m === "loading") {
      setTimeout(() => setMode("loaded"), reduced ? 150 : SKELETON_MS);
    }
  }
  return (
    <PageContainer title="Optimizer" gridMode={mode} onGridModeChange={onGridModeChange}>
      {mode === "loaded" ? (
        <LineupViews />
      ) : (
        <LineupGridPlaceholder label="Optimizer Grid" mode={mode} />
      )}
    </PageContainer>
  );
}
