"use client";

import { useIngestStore } from "@/lib/state/ingest-store";
import { shallow } from "zustand/shallow";

export default function IngestSummary() {
  const { summary, merged } = useIngestStore((s) => ({ summary: s.summary, merged: s.merged }), shallow);

  if (!summary) return (
    <div className="text-sm text-muted-foreground" aria-live="polite">
      No ingest yet — drop projections.csv and player_ids.csv.
    </div>
  );

  return (
    <div className="text-sm" aria-live="polite">
      <div className="mb-2 font-medium">Ingest Summary</div>
      <ul className="space-y-1">
        <li>Players rows: <span className="font-mono">{summary.rows_players}</span> (dropped {summary.dropped_players})</li>
        <li>Projections rows: <span className="font-mono">{summary.rows_projections}</span> (dropped {summary.dropped_projections})</li>
        <li>Merged players: <span className="font-mono">{merged.length}</span></li>
      </ul>
      {(summary.unknown_cols_players.length > 0 || summary.unknown_cols_projections.length > 0) && (
        <div className="mt-3">
          <div className="font-medium">Unknown columns</div>
          {summary.unknown_cols_players.length > 0 && (
            <div className="mt-1">
              <div className="text-muted-foreground">Players:</div>
              <div className="font-mono text-xs break-words">{summary.unknown_cols_players.join(", ")}</div>
            </div>
          )}
          {summary.unknown_cols_projections.length > 0 && (
            <div className="mt-1">
              <div className="text-muted-foreground">Projections:</div>
              <div className="font-mono text-xs break-words">{summary.unknown_cols_projections.join(", ")}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
