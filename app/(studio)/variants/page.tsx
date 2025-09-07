"use client";

import { useState } from "react";
import PageContainer from "../../../components/ui/PageContainer";
import LineupGridPlaceholder, { type GridMode } from "../../../components/ui/LineupGridPlaceholder";
import { SKELETON_MS } from "../../../lib/ui/constants";
import { prefersReducedMotion } from "../../../lib/ui/a11y";

export default function VariantsPage() {
  const [mode, setMode] = useState<GridMode>("empty");
  const reduced = prefersReducedMotion();
  function onGridModeChange(m: GridMode) {
    setMode(m);
    if (m === "loading") setTimeout(() => setMode("loaded"), reduced ? 150 : SKELETON_MS);
  }
  return (
    <PageContainer title="Variants" gridMode={mode} onGridModeChange={onGridModeChange}>
      <LineupGridPlaceholder label="Variants Grid" mode={mode} />
    </PageContainer>
  );
}
