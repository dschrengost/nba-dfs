#!/usr/bin/env node
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import Papa from "papaparse";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const date = process.argv[2] || "2024-01-15";
const outDir = path.resolve(__dirname, `../fixtures/dk/${date}`);
const candidates = [
  path.resolve(__dirname, `../fixtures/dk/${date}`),
  path.resolve(__dirname, `../tests/fixtures/dk/${date}`),
];

function findInputDir() {
  for (const p of candidates) {
    if (fs.existsSync(path.join(p, "projections.csv")) && fs.existsSync(path.join(p, "player_ids.csv"))) return p;
  }
  return null;
}

function readCsv(file) {
  const text = fs.readFileSync(file, "utf8");
  const res = Papa.parse(text, { header: true, skipEmptyLines: true });
  const rows = res.data;
  // normalize keys to lower-case for easier matching
  return rows.map((r) => {
    const out = {};
    for (const k of Object.keys(r)) out[k.toLowerCase()] = r[k];
    return out;
  });
}

function coerceNumber(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function normalizePlayers(rows) {
  return rows.map((r) => {
    const pid = r.player_id_dk ?? r.player_id ?? r.dk_id ?? r.id ?? null;
    const pos = r.pos ?? r.pos_primary ?? r.position ?? "";
    const posSplit = String(pos).split("/");
    return {
      player_id_dk: pid === null ? null : String(pid).trim(),
      player_name: String(r.player_name ?? r.name ?? "").trim(),
      team: normalizeTeam(String(r.team ?? r.team_abbrev ?? r.teamabbrev ?? "")),
      pos_primary: String(posSplit[0] ?? "").trim(),
      pos_secondary: posSplit.length > 1 ? String(posSplit[1]).trim() : null,
    };
  });
}

function normalizeProjections(rows) {
  return rows.map((r) => {
    const pid = r.player_id_dk ?? r.player_id ?? r.dk_id ?? r.id ?? null;
    return {
      player_id_dk: pid === null ? null : String(pid).trim(),
      name: String(r.name ?? r.player_name ?? "").trim(),
      team: normalizeTeam(String(r.team ?? r.team_abbrev ?? "")),
      position: String(r.position ?? r.pos ?? "").trim(),
      salary: Number(r.salary ?? r.sal ?? 0),
      proj_fp: Number(r.proj_fp ?? r.proj ?? r.projection ?? r.fp ?? r.fpts ?? 0),
      mins: coerceNumber(r.mins ?? r.minutes),
      ownership: coerceNumber(r.ownership ?? r.own),
      ceiling: coerceNumber(r.ceiling ?? r.ceil),
      floor: coerceNumber(r.floor),
      source: String(r.source ?? "fixture").trim(),
      version_ts: (r.version_ts ?? r.timestamp ?? r.version) ? String(r.version_ts ?? r.timestamp ?? r.version).trim() : null,
    };
  });
}

function merge(players, projections) {
  const byId = new Map(projections.filter((p) => p.player_id_dk).map((p) => [p.player_id_dk, p]));
  const byComposite = new Map(
    projections.map((p) => [makeKey(p.name, p.team, (p.position ?? p.pos ?? "").split("/")[0] ?? ""), p])
  );
  const out = [];
  for (const pl of players) {
    let pj = pl.player_id_dk ? byId.get(pl.player_id_dk) : undefined;
    if (!pj)
      pj = byComposite.get(makeKey(pl.player_name, pl.team, pl.pos_primary));
    if (!pj) continue;
    // Keep the player_id_dk from players as the source of truth
    out.push({ ...pj, ...pl, player_id_dk: pl.player_id_dk });
  }
  return out;
}

function normalizeTeam(t) {
  const u = String(t).trim().toUpperCase();
  const m = { NO: "NOP", NOP: "NOP", PHO: "PHX", PHX: "PHX", SA: "SAS", SAS: "SAS" };
  return m[u] ?? u;
}

function normalizeNameKey(name) {
  return String(name)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toUpperCase()
    .replace(/\./g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function makeKey(name, team, pos) {
  return `${normalizeNameKey(name)}|${normalizeTeam(team)}|${String(pos).toUpperCase()}`;
}

function main() {
  const dir = findInputDir();
  if (!dir) {
    console.error("Could not find projections.csv and player_ids.csv under fixtures or tests for date", date);
    process.exit(1);
  }
  const playersCsv = path.join(dir, "player_ids.csv");
  const projCsv = path.join(dir, "projections.csv");
  const players = normalizePlayers(readCsv(playersCsv));
  const projections = normalizeProjections(readCsv(projCsv));
  const merged = merge(players, projections);
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, "mergedPlayers.json");
  fs.writeFileSync(outFile, JSON.stringify(merged, null, 2));
  console.log(`Wrote ${merged.length} merged players to ${outFile}`);
}

main();
