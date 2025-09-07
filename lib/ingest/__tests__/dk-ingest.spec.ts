import { describe, it, expect } from "vitest";
import { parseDkPlayers, parseDkProjections, buildCanonicalProjectionsFromDk } from "../../ingest/adapter";
import { normalizePlayers, normalizeProjections, mergePlayersStrict } from "../../ingest/normalize";

const dkPlayersCsv = `Name,ID,Position,TeamAbbrev,Game Info\nStephen Curry,36385604,PG,GSW,GSW@POR 10/23/2024 10:00PM ET\nKevin Durant,36385598,PF,PHX,PHX@LAC 10/23/2024 10:00PM ET`;

const dkProjectionsCsv = `Name,Position,Team,Salary,FPTS,StdDev,Ceiling,Own%,Minutes,FieldFpts\nStephen Curry,PG,GSW,8500,42.9,11.2,54.1,13.4,32,42.9\nKevin Durant,PF,PHX,8600,46.8,10.4,57.2,14.2,32,46.8`;

describe("DK adapter + strict join", () => {
  it("adapts DK rows and merges strictly with zero drop", async () => {
    const repPl = await parseDkPlayers(dkPlayersCsv);
    const players = normalizePlayers(repPl.rows);
    const repPr = await parseDkProjections(dkProjectionsCsv);
    const canPr = buildCanonicalProjectionsFromDk(repPr.rows, players);
    expect(canPr.unmatched.length).toBe(0);
    const projections = normalizeProjections(canPr.rows);
    const strict = mergePlayersStrict(players, projections);
    expect(strict.ok).toBe(true);
    expect(strict.merged.length).toBe(2);
  });
});
