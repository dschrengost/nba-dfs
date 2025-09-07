"use client";

import { useState } from "react";
import PageContainer from "../../../components/ui/PageContainer";
import LineupGridPlaceholder, { type GridMode } from "../../../components/ui/LineupGridPlaceholder";
import { SKELETON_MS } from "../../../lib/ui/constants";
import { prefersReducedMotion } from "../../../lib/ui/a11y";

export default function FieldPage() {
  const [mode, setMode] = useState<GridMode>("empty");
  const reduced = prefersReducedMotion();
  function onGridModeChange(m: GridMode) {
    setMode(m);
    if (m === "loading") setTimeout(() => setMode("loaded"), reduced ? 150 : SKELETON_MS);
  }
  return (
    <PageContainer title="Field" gridMode={mode} onGridModeChange={onGridModeChange}>
      <LineupGridPlaceholder label="Field Grid" mode={mode} />
    </PageContainer>
  );
}
