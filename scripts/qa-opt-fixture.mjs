#!/usr/bin/env node
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const date = process.argv[2] || "2024-01-15";
const seedStr = process.argv[3] || `dk-fixture-${date}`;
const target = Number(process.argv[4] || 100);

const slots = ["PG", "SG", "SF", "PF", "C"];
const salaryCap = 50000;
const maxPerTeam = 8;

const fixtureFile = path.resolve(__dirname, `../fixtures/dk/${date}/mergedPlayers.json`);
if (!fs.existsSync(fixtureFile)) {
  console.error("Snapshot not found:", fixtureFile);
  console.error("Run: node scripts/make-fixture-snapshot.mjs", date);
  process.exit(1);
}
const players = JSON.parse(fs.readFileSync(fixtureFile, "utf8"));

function eligibleForSlot(p, slot) {
  const pos = [p.pos_primary, p.pos_secondary].filter(Boolean);
  if (slot === "PG") return pos.includes("PG");
  if (slot === "SG") return pos.includes("SG");
  if (slot === "SF") return pos.includes("SF");
  if (slot === "PF") return pos.includes("PF");
  if (slot === "C") return pos.includes("C");
  if (slot === "G") return pos.includes("PG") || pos.includes("SG");
  if (slot === "F") return pos.includes("SF") || pos.includes("PF");
  if (slot === "UTIL") return true;
  return false;
}

function makeRng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (1664525 * s + 1013904223) >>> 0;
    return (s & 0xffffffff) / 0x100000000;
  };
}
function seedToInt(seed) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
function pick(arr, rng) {
  if (arr.length === 0) return undefined;
  const i = Math.floor(rng() * arr.length);
  return arr[i];
}
function lineupKey(ids) {
  return ids.slice().sort().join("|");
}

const rng = makeRng(seedToInt(seedStr));
const getId = (p) => (p.player_id_dk && String(p.player_id_dk).trim() !== "" ? String(p.player_id_dk) : String(p.player_name || p.name || ""));
const byId = new Map(players.map((p) => [getId(p), p]));
const eligibleBySlot = Object.fromEntries(slots.map((s) => [s, players.filter((p) => eligibleForSlot(p, s))]));

const triedMax = Math.max(target * 2, target * 200);
let tried = 0;
let valid = 0;
const out = [];
const seen = new Set();
const t0 = Date.now();

while (tried < triedMax && out.length < target) {
  tried++;
  const used = new Set();
  const teamCounts = {};
  const picked = [];
  let ok = true;
  let salary = 0;
  for (const sl of slots) {
    const pool = eligibleBySlot[sl].filter((p) => !used.has(getId(p)) && ((teamCounts[p.team] ?? 0) + 1) <= maxPerTeam);
    const affordable = pool.filter((p) => salary + p.salary <= salaryCap);
    const choice = pick(affordable.length > 0 ? affordable : pool, rng);
    if (!choice) {
      ok = false; break;
    }
    used.add(getId(choice));
    teamCounts[choice.team] = (teamCounts[choice.team] ?? 0) + 1;
    salary += choice.salary;
    picked.push({ slot: sl, player_id_dk: getId(choice) });
    if (salary > salaryCap) { ok = false; break; }
  }
  if (!ok) continue;
  const key = lineupKey(picked.map((x) => x.player_id_dk));
  if (seen.has(key)) continue;
  seen.add(key);
  const score = picked.reduce((s, x) => s + (byId.get(x.player_id_dk)?.proj_fp ?? 0), 0);
  out.push({ id: key, slots: picked, salary, score });
  valid++;
}

out.sort((a, b) => b.score - a.score);
const elapsed = Date.now() - t0;
console.log(JSON.stringify({ date, seed: seedStr, players: players.length, tried, valid, bestScore: out[0]?.score || 0, elapsedMs: elapsed }, null, 2));
