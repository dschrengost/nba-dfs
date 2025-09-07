import { describe, it, expect } from "vitest";
import { PlayerCsvSchema, ProjectionCsvSchema, PLAYER_ALIASES, PROJ_ALIASES } from "@/lib/ingest/schemas";
import { parseCsvStream } from "@/lib/ingest/parse";
import { mergePlayers, normalizePlayers, normalizeProjections } from "@/lib/ingest/normalize";

const playersCsv = `player_id_dk,player_name,team,pos_primary,pos_secondary\n1001,LeBron James,LAL,SF,PF\n1002,Stephen Curry,GSW,PG,`;
const projectionsCsv = `player_id_dk,salary,proj_fp,mins,ownership,ceiling,floor,source,version_ts\n1001,10500,55.5,36,18.2,70,40,Rotogrinders,2025-09-04T17:15:00Z\n1002,9800,50.1,34,,65,35,Rotogrinders,2025-09-04T17:15:00Z`;

describe("ingest pipeline", () => {
  it("parses and validates players", async () => {
    const rep = await parseCsvStream(playersCsv, PlayerCsvSchema, lower(PLAYER_ALIASES));
    expect(rep.rowCount).toBe(2);
    expect(rep.droppedRows).toBe(0);
    const players = normalizePlayers(rep.rows);
    expect(players[0].team).toBe("LAL");
  });

  it("parses and validates projections", async () => {
    const rep = await parseCsvStream(projectionsCsv, ProjectionCsvSchema, lower(PROJ_ALIASES));
    expect(rep.rowCount).toBe(2);
    const projections = normalizeProjections(rep.rows);
    expect(projections[0].salary).toBe(10500);
    expect(projections[1].ownership).toBe(null);
  });

  it("merges on player_id_dk", async () => {
    const repPl = await parseCsvStream(playersCsv, PlayerCsvSchema, lower(PLAYER_ALIASES));
    const repPr = await parseCsvStream(projectionsCsv, ProjectionCsvSchema, lower(PROJ_ALIASES));
    const merged = mergePlayers(normalizePlayers(repPl.rows), normalizeProjections(repPr.rows));
    expect(merged.length).toBe(2);
    expect(merged[0]).toHaveProperty("salary");
    expect(merged[0]).toHaveProperty("player_name");
  });
});

function lower<T extends Record<string, any>>(obj: T): T {
  const out: any = {};
  for (const [k, v] of Object.entries(obj)) out[k.toLowerCase()] = v;
  return out as T;
}

